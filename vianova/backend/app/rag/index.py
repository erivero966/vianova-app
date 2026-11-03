"""Índice de recuperación semántica híbrida.

- Representación dispersa: TF-IDF de palabras (1-2 gramas) y de n-gramas de caracteres.
- Representación densa (embeddings): proyección semántica latente (LSA, TruncatedSVD) del TF-IDF, de
  dimensión configurable; los vectores se guardan en la tabla de fragmentos (almacenamiento vectorial).
- Puntaje híbrido = (1 − α)·coseno disperso + α·coseno denso, con α = RAG_DENSE_WEIGHT.
Funciona sin servicios externos; en PostgreSQL los vectores pueden migrarse a pgvector sin cambiar la interfaz.
"""
from dataclasses import dataclass, field
import threading
import numpy as np
from scipy.sparse import hstack
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy.orm import Session

from .. import config
from ..models import Chunk, Document
from .text import normalize, expand_query, STOPWORDS
import re


def phonetic_key(w: str) -> str:
    """Clave fonética simple del español (ll/y, c/k/qu/z/s, b/v, h muda, g/j) para tolerar errores ortográficos."""
    w = w.replace("ll", "y").replace("qu", "k").replace("h", "")
    w = re.sub(r"c(?=[ei])", "s", w).replace("c", "k").replace("z", "s").replace("v", "b").replace("x", "ks")
    w = re.sub(r"g(?=[ei])", "j", w)
    return re.sub(r"(.)\1+", r"\1", w)


@dataclass
class Hit:
    chunk_id: int
    doc_id: str
    section: str
    text: str
    score: float
    sparse: float = 0.0
    dense: float = 0.0


class Index:
    def __init__(self):
        self.lock = threading.Lock()
        self.ready = False
        self.chunks: list[dict] = []
        self.dim = 0

    def build(self, db: Session) -> None:
        rows = (db.query(Chunk, Document).join(Document, Chunk.doc_id == Document.id)
                .filter(Document.status == "incluido").order_by(Chunk.doc_id, Chunk.ordinal).all())
        chunks = [{"id": c.id, "doc_id": d.id, "section": c.section, "text": c.text,
                   "full": f"{d.title}. {c.section}. {c.text} {' '.join(d.topics or [])}"} for c, d in rows]
        with self.lock:
            self.chunks = chunks
            if not chunks:
                self.ready = False
                return
            corpus = [normalize(c["full"]) for c in chunks]
            self.wv = TfidfVectorizer(ngram_range=(1, 2), stop_words=list(STOPWORDS), sublinear_tf=True, min_df=1)
            self.cv = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
            W = self.wv.fit_transform(corpus)
            Cm = self.cv.fit_transform(corpus)
            self.M = hstack([W * 0.6, Cm * 0.4]).tocsr()
            norms = np.sqrt(self.M.multiply(self.M).sum(axis=1)).A1
            norms[norms == 0] = 1
            self.norms = norms
            # embeddings densos (LSA)
            k = max(2, min(config.RAG_EMBED_DIM, W.shape[0] - 1, W.shape[1] - 1))
            self.svd = TruncatedSVD(n_components=k, random_state=42)
            E = self.svd.fit_transform(W)
            E /= np.linalg.norm(E, axis=1, keepdims=True).clip(min=1e-9)
            self.E = E
            self.dim = k
            # vocabulario y claves fonéticas para la corrección ortográfica de consultas
            vocab: dict[str, int] = {}
            for text in corpus:
                for w in re.findall(r"[a-zñ]{4,}", text):
                    vocab[w] = vocab.get(w, 0) + 1
            self.vocab = vocab
            self.phon: dict[str, str] = {}
            for w, n in sorted(vocab.items(), key=lambda x: -x[1]):
                self.phon.setdefault(phonetic_key(w), w)
            self.ready = True
        # persistir los vectores en la tabla de fragmentos
        by_id = {c["id"]: i for i, c in enumerate(chunks)}
        for ch in db.query(Chunk).filter(Chunk.id.in_(list(by_id))).all():
            ch.embedding = [round(float(x), 5) for x in self.E[by_id[ch.id]]]
        db.commit()

    def correct(self, query: str) -> tuple[str, list[tuple[str, str]]]:
        """Corrige palabras que no existen en el corpus pero comparten clave fonética con una que sí existe."""
        if not self.ready:
            return query, []
        out, changes = [], []
        for tok in normalize(query).split():
            if len(tok) >= 4 and tok not in self.vocab and tok not in STOPWORDS:
                cand = self.phon.get(phonetic_key(tok))
                if cand and cand != tok:
                    changes.append((tok, cand))
                    tok = cand
            out.append(tok)
        return (" ".join(out) if changes else query), changes

    def _sparse(self, q: str) -> np.ndarray:
        v = hstack([self.wv.transform([q]) * 0.6, self.cv.transform([q]) * 0.4]).tocsr()
        qn = np.sqrt(v.multiply(v).sum()) or 1.0
        return (self.M @ v.T).toarray().ravel() / (self.norms * qn)

    def _dense(self, q: str) -> np.ndarray:
        e = self.svd.transform(self.wv.transform([q]))[0]
        n = np.linalg.norm(e)
        if n == 0:
            return np.zeros(len(self.chunks))
        return self.E @ (e / n)

    def scores(self, text: str):
        q = normalize(expand_query(text) or text)
        sp = self._sparse(q)
        de = np.clip(self._dense(q), 0, None)
        a = config.RAG_DENSE_WEIGHT
        return (1 - a) * sp + a * de, sp, de

    def search(self, query: str, k: int = 5) -> list[Hit]:
        with self.lock:
            if not self.ready:
                return []
            sims, sp, de = self.scores(query)
            order = np.argsort(-sims)[:k]
            return [Hit(self.chunks[i]["id"], self.chunks[i]["doc_id"], self.chunks[i]["section"],
                        self.chunks[i]["text"], float(sims[i]), float(sp[i]), float(de[i])) for i in order]

    def doc_scores(self, text: str) -> dict[str, float]:
        """Mejor similitud por documento (para el recomendador)."""
        with self.lock:
            if not self.ready or not text.strip():
                return {}
            sims, _, _ = self.scores(text)
            out: dict[str, float] = {}
            for c, s in zip(self.chunks, sims):
                out[c["doc_id"]] = max(out.get(c["doc_id"], 0.0), float(s))
            return out


INDEX = Index()
