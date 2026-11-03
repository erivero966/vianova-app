"""Flujo RAG completo (RF-05, RF-06): alcance → recuperación → abstención τ → generación → fuentes."""
import time
from sqlalchemy.orm import Session

from .. import config
from ..models import Document
from .index import INDEX
from .safety import check_scope, is_urgent, SCOPE_MESSAGE, URGENT_MESSAGE
from .generator import generate
from .corpus import current_version
from .text import coverage
from ..models import Document as _Doc

ABSTAIN_MESSAGE = ("No encontré información suficiente en las fuentes verificadas del sistema para responder esta "
                   "consulta. Para no darle información no respaldada, prefiero no responder: consulte esta duda con el "
                   "equipo de salud.")


def ask(db: Session, query: str, tau: float | None = None, k: int | None = None) -> dict:
    t0 = time.time()
    tau = config.RAG_TAU if tau is None else tau
    k = k or config.RAG_TOP_K
    version = current_version(db)
    res = {"query": query, "status": "", "answer": "", "sources": [], "urgent": is_urgent(query),
           "urgent_message": URGENT_MESSAGE, "corpus_version": version, "mode": "", "top_score": 0.0}
    # Traza del flujo RAG (evidencia de que la respuesta se genera a partir de lo recuperado)
    trace = {"pasos": [], "candidatos": [], "tau": tau, "cobertura_minima": config.RAG_MIN_COVERAGE,
             "peso_denso": config.RAG_DENSE_WEIGHT, "dimension_embeddings": INDEX.dim, "k": k}
    res["trace"] = trace
    reason = check_scope(query)
    trace["pasos"].append({"paso": "1. Filtro de alcance y seguridad", "resultado": f"rechazada ({reason})" if reason else "dentro del alcance"})
    if reason:
        res.update(status="fuera_de_alcance", answer=SCOPE_MESSAGE, scope_reason=reason)
    else:
        original = query
        query, changes = INDEX.correct(query)
        if changes:
            trace["pasos"].append({"paso": "1b. Corrección ortográfica",
                                   "resultado": ", ".join(f"«{a}» → «{b}»" for a, b in changes)})
            res["corrected_query"] = query
        hits = INDEX.search(query, k)
        trace["pasos"].append({"paso": "2. Recuperación híbrida (TF-IDF + embeddings densos)",
                               "resultado": f"{len(hits)} fragmentos candidatos de {len(INDEX.chunks)} indexados"})
        res["top_score"] = round(hits[0].score, 4) if hits else 0.0
        relevant = []
        for h in hits:
            d = db.get(_Doc, h.doc_id)
            # Segunda verificación: la consulta debe compartir contenido con el fragmento (evita falsas coincidencias)
            cov = coverage(query, f"{d.title} {h.section} {h.text} {' '.join(d.topics or [])}")
            ok = h.score >= tau and cov >= config.RAG_MIN_COVERAGE
            trace["candidatos"].append({"doc_id": h.doc_id, "seccion": h.section, "puntaje": round(h.score, 4),
                                        "disperso": round(h.sparse, 4), "denso": round(h.dense, 4),
                                        "cobertura": round(cov, 2), "supera_tau": h.score >= tau, "usado": False,
                                        "seleccionado": ok, "fragmento": h.text[:220]})
            if ok:
                relevant.append(h)
        trace["pasos"].append({"paso": "3. Umbral de abstención τ y cobertura",
                               "resultado": f"{len(relevant)} fragmentos superan τ={tau} y cobertura ≥ {config.RAG_MIN_COVERAGE}"})
        if not relevant:
            trace["pasos"].append({"paso": "4. Decisión", "resultado": "abstención: no hay evidencia suficiente"})
            res.update(status="abstencion", answer=ABSTAIN_MESSAGE)
        else:
            relevant = relevant[:3]
            text, used, mode = generate(original, relevant)
            trace["pasos"].append({"paso": "4. Generación aumentada con el contexto recuperado",
                                   "resultado": f"modo {mode}; {len(relevant)} fragmentos en el contexto; "
                                                f"{'respuesta generada' if text else 'el generador indicó NO_EVIDENCIA'}"})
            sel = [c for c in trace["candidatos"] if c["seleccionado"]][:3]
            for i in (used or []):
                if i < len(sel):
                    sel[i]["usado"] = True
            if text is None:
                res.update(status="abstencion", answer=ABSTAIN_MESSAGE, mode=mode)
            else:
                srcs, seen = [], {}
                for i in used:
                    h = relevant[i]
                    if h.doc_id in seen:
                        if h.section and h.section not in seen[h.doc_id]["section"]:
                            seen[h.doc_id]["section"] += "; " + h.section
                        continue
                    d = db.get(Document, h.doc_id)
                    src = {"doc_id": d.id, "title": d.title, "institution": d.institution, "year": d.year,
                           "version": d.version, "url": d.url, "section": h.section, "score": round(h.score, 4),
                           "is_demo": d.is_demo}
                    seen[h.doc_id] = src
                    srcs.append(src)
                # Regla de negocio: toda respuesta muestra al menos una fuente válida o se abstiene
                if not srcs:
                    res.update(status="abstencion", answer=ABSTAIN_MESSAGE)
                else:
                    res.update(status="respondida", answer=text, sources=srcs, mode=mode)
                    trace["pasos"].append({"paso": "5. Verificación de fuentes", "resultado": f"{len(srcs)} fuente(s) citadas con versión"})
    res["duration_ms"] = int((time.time() - t0) * 1000)
    return res
