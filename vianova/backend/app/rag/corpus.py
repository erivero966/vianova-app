"""Ingesta, segmentación y versionado del corpus documental (RF-09)."""
import re
from pathlib import Path
from sqlalchemy.orm import Session

from ..models import Document, Chunk, CorpusState
from ..timeutil import now


def parse_markdown(raw: str) -> tuple[dict, str]:
    """Lee el encabezado YAML simple (clave: valor) y devuelve (metadatos, cuerpo)."""
    meta, body = {}, raw
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if m:
        body = m.group(2)
        for line in m.group(1).splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip() for x in v[1:-1].split(",") if x.strip()]
            meta[k.strip()] = v
    return meta, body.strip()


def split_sections(body: str) -> list[tuple[str, str]]:
    """Segmenta por encabezados '## '. Las secciones largas se dividen en fragmentos de ~900 caracteres."""
    sections, title, buf = [], "", []
    for line in body.splitlines():
        if line.startswith("#"):
            if buf:
                sections.append((title, " ".join(buf).strip()))
            title, buf = line.lstrip("#").strip(), []
        elif line.strip():
            buf.append(line.strip())
    if buf:
        sections.append((title, " ".join(buf).strip()))
    out = []
    for title, text in sections:
        if len(text) <= 1100:
            out.append((title, text))
            continue
        cur = ""
        for sent in re.split(r"(?<=[\.\!\?])\s+", text):
            if len(cur) + len(sent) > 900 and cur:
                out.append((title, cur.strip()))
                cur = ""
            cur += " " + sent
        if cur.strip():
            out.append((title, cur.strip()))
    return out


def current_version(db: Session) -> str:
    st = db.query(CorpusState).order_by(CorpusState.id.desc()).first()
    return st.version if st else "v1.0"


def bump_version(db: Session) -> str:
    cur = current_version(db)
    major, minor = cur.lstrip("v").split(".")
    new = f"v{major}.{int(minor) + 1}"
    db.add(CorpusState(version=new, indexed_at=now()))
    db.commit()
    return new


def upsert_document(db: Session, meta: dict, body: str, curator: str = "", is_demo: bool | None = None) -> Document:
    doc_id = str(meta.get("id") or "").strip()
    if not doc_id:
        raise ValueError("El documento debe tener un campo 'id'")
    doc = db.get(Document, doc_id) or Document(id=doc_id)
    doc.institution = meta.get("institution", doc.institution or "")
    doc.title = meta.get("title", doc.title or doc_id)
    yr = str(meta.get("year", "") or "")
    doc.year = int(yr) if yr.isdigit() else doc.year
    doc.version = str(meta.get("version", doc.version or "1.0"))
    doc.url = meta.get("url", doc.url or "")
    doc.doc_type = meta.get("doc_type", doc.doc_type or "guía")
    topics = meta.get("topics", doc.topics or [])
    doc.topics = topics if isinstance(topics, list) else [t.strip() for t in str(topics).split(",") if t.strip()]
    doc.audience = meta.get("audience", doc.audience or "cuidadores")
    doc.is_demo = doc_id.startswith("DEMO") if is_demo is None else is_demo
    if doc.status is None:
        doc.status = "incluido"
    doc.curator = curator or doc.curator or "sistema"
    doc.reviewed_at = now()
    doc.content = body
    db.add(doc)
    db.flush()
    rebuild_chunks(db, doc)
    return doc


def rebuild_chunks(db: Session, doc: Document) -> None:
    db.query(Chunk).filter(Chunk.doc_id == doc.id).delete()
    ver = current_version(db)
    for i, (sec, text) in enumerate(split_sections(doc.content)):
        db.add(Chunk(doc_id=doc.id, ordinal=i, section=sec, text=text, corpus_version=ver))


def load_directory(db: Session, folder: Path) -> int:
    n = 0
    for f in sorted(folder.glob("*.md")):
        meta, body = parse_markdown(f.read_text(encoding="utf-8"))
        upsert_document(db, meta, body)
        n += 1
    db.commit()
    return n


def pdf_to_text(data: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data))
    return "\n\n".join((p.extract_text() or "") for p in reader.pages)
