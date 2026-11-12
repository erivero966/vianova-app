"""Consulta RAG, recomendaciones, lectura de documentos y administración del corpus."""
import re
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..logs import log_event, audit
from ..models import User, Document, Chunk, Feedback
from ..rag import engine_client, grounded
from ..rag.assistant import ask
from ..rag.safety import is_urgent, URGENT_MESSAGE
from ..rag.corpus import upsert_document, bump_version, current_version, pdf_to_text, rebuild_chunks
from ..rag.index import INDEX
from ..recommender import recommend
from ..security import require, current_user
from ..timeutil import iso, now

router = APIRouter(prefix="/api", tags=["conocimiento"])
cuidador = require("cuidador")
curador = require("curador")


class AskIn(BaseModel):
    query: str = Field(min_length=2, max_length=600)
    channel: str = Field(default="texto", pattern="^(texto|voz)$")


@router.post("/assistant/ask")
def assistant(data: AskIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    res = ask(db, data.query)
    resultado = {"respondida": "exito", "abstencion": "abstencion", "fuera_de_alcance": "abstencion"}[res["status"]]
    log_event(db, user, "consulta_rag", "asistente", canal=data.channel, resultado=resultado,
              fuente_id=";".join(s["doc_id"] for s in res["sources"]), version_corpus=res["corpus_version"],
              duracion_ms=res["duration_ms"])
    return res


class RagSearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=600)
    channel: str = Field(default="texto", pattern="^(texto|voz)$")


RAG_UNAVAILABLE = "No se pudo consultar la base de conocimiento en este momento. Inténtalo nuevamente."


@router.post("/rag/search")
def rag_search(data: RagSearchIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    """RAG completo: retrieval en rag-engine (BGE-M3 + pgvector) -> reglas de seguridad -> qwen2.5:7b (Ollama local).

    La respuesta incluye los Top-K originales (`sources`) para la evidencia. Si Ollama falla, las fuentes se
    devuelven igual con un aviso (`answer_status = sin_generacion`).
    """
    query = data.query.strip()
    if not query:
        raise HTTPException(422, "Escribe una consulta antes de continuar.")
    start = time.perf_counter()
    try:
        res = engine_client.search(query)
    except engine_client.RagEngineError:
        log_event(db, user, "consulta_rag", "fuentes_verificadas", canal=data.channel, resultado="error",
                  duracion_ms=int((time.perf_counter() - start) * 1000))
        raise HTTPException(503, RAG_UNAVAILABLE)
    retrieval_ms = int((time.perf_counter() - start) * 1000)
    sources = res["results"]
    gen = grounded.answer(query, sources)
    total_ms = int((time.perf_counter() - start) * 1000)
    # Fuentes utilizadas: las citadas por el modelo ([n] = posición en el contexto); si no cita, todas las entregadas.
    used = [sources[i - 1]["rank"] for i in gen["cited"]] or (
        [s["rank"] for s in sources] if gen["status"] == "respondida" else [])
    log_event(db, user, "consulta_rag", "fuentes_verificadas", canal=data.channel,
              resultado={"respondida": "exito", "sin_generacion": "error"}.get(gen["status"], "abstencion"),
              fuente_id=";".join(f"{s['document'][:30]} p.{s['page_start']}" for s in sources if s["rank"] in used),
              duracion_ms=total_ms)
    return {
        "query": query,
        "answer": gen["answer"],
        "answer_status": gen["status"],
        "sources": [dict(s, used=s["rank"] in used) for s in sources],
        "urgent": is_urgent(query),               # regla determinista: no depende del LLM
        "urgent_message": URGENT_MESSAGE,
        "timing_ms": {"retrieval": retrieval_ms, "total": total_ms},
    }


@router.get("/recommendations")
def recommendations(q: str | None = None, limit: int = 5, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    recs = recommend(db, user, q, max(1, min(limit, 10)))
    ver = current_version(db)
    for r in recs:
        log_event(db, user, "recomendacion_mostrada", "recomendaciones", id_recurso=r["doc_id"], fuente_id=r["doc_id"],
                  version_corpus=ver, commit=False)
    db.commit()
    return {"corpus_version": ver, "items": recs}


class FeedbackIn(BaseModel):
    doc_id: str
    useful: bool


@router.post("/recommendations/feedback")
def feedback(data: FeedbackIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    if not db.get(Document, data.doc_id):
        raise HTTPException(404, "Documento no encontrado")
    db.add(Feedback(user_id=user.id, doc_id=data.doc_id, useful=data.useful))
    db.commit()
    log_event(db, user, "recomendacion_valorada", "recomendaciones", id_recurso=data.doc_id,
              resultado="exito", fuente_id=data.doc_id)
    return {"ok": True}


def doc_out(d: Document, full: bool = False) -> dict:
    out = {"id": d.id, "institution": d.institution, "title": d.title, "year": d.year, "version": d.version,
           "url": d.url, "doc_type": d.doc_type, "topics": d.topics, "audience": d.audience, "criteria": d.criteria,
           "status": d.status, "status_reason": d.status_reason, "is_demo": d.is_demo, "curator": d.curator,
           "reviewed_at": iso(d.reviewed_at)}
    if full:
        out["content"] = d.content
    return out


@router.get("/documents/{doc_id}")
def read_document(doc_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d or (d.status != "incluido" and user.role == "cuidador"):
        raise HTTPException(404, "Documento no disponible")
    out = doc_out(d, full=True)
    out["sections"] = [{"section": c.section, "text": c.text} for c in
                       db.query(Chunk).filter(Chunk.doc_id == d.id).order_by(Chunk.ordinal)]
    return out


# ------------------------------------------------------------------ administración del corpus (curador)
@router.get("/corpus")
def corpus_list(user: User = Depends(curador), db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.id).all()
    return {"version": current_version(db), "indexed_chunks": len(INDEX.chunks),
            "documents": [dict(doc_out(d), chunks=db.query(Chunk).filter(Chunk.doc_id == d.id).count()) for d in docs]}


@router.post("/corpus")
async def corpus_upload(file: UploadFile = File(...), doc_id: str = Form(...), institution: str = Form(...),
                        title: str = Form(...), year: int | None = Form(None), version: str = Form("1.0"),
                        url: str = Form(""), doc_type: str = Form("guía"), topics: str = Form(""),
                        audience: str = Form("cuidadores"), crit_oficial: bool = Form(False),
                        crit_vigente: bool = Form(False), crit_idioma: bool = Form(False),
                        crit_pertinente: bool = Form(False),
                        user: User = Depends(curador), db: Session = Depends(get_db)):
    if not re.fullmatch(r"[A-Za-z0-9_\-]{2,40}", doc_id):
        raise HTTPException(400, "El identificador solo admite letras, números, guiones (2-40 caracteres)")
    raw = await file.read()
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        body = pdf_to_text(raw)
    elif name.endswith((".md", ".txt")):
        body = raw.decode("utf-8", errors="replace")
    else:
        raise HTTPException(400, "Formatos admitidos: PDF, TXT o MD")
    if len(body.strip()) < 100:
        raise HTTPException(400, "No se pudo extraer texto suficiente del archivo")
    if "##" not in body:   # PDF o texto plano: segmentar por párrafos dobles
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        body = "\n\n".join(f"## Parte {i + 1}\n{p}" for i, p in enumerate(paras))
    meta = {"id": doc_id, "institution": institution, "title": title, "year": str(year or ""), "version": version,
            "url": url, "doc_type": doc_type, "topics": [t.strip() for t in topics.split(",") if t.strip()],
            "audience": audience}
    crit = {"fuente_oficial_o_revisada": crit_oficial, "vigente": crit_vigente, "idioma_es_en": crit_idioma,
            "pertinente_cuidado_domiciliario": crit_pertinente}
    all_ok = all(crit.values())
    new_ver = bump_version(db)
    d = upsert_document(db, meta, body, curator=user.full_name, is_demo=False)
    d.criteria = crit
    d.status = "incluido" if all_ok else "excluido"
    d.status_reason = "" if all_ok else "No cumple todos los criterios de inclusión de la ficha de curaduría"
    rebuild_chunks(db, d)
    db.commit()
    INDEX.build(db)
    audit(db, user, "corpus_incorporar", f"{doc_id} v{version} -> {d.status} (corpus {new_ver})")
    return doc_out(d)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(incluido|excluido|retirado)$")
    reason: str = ""


@router.put("/corpus/{doc_id}/status")
def corpus_status(doc_id: str, data: StatusIn, user: User = Depends(curador), db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Documento no encontrado")
    if data.status != "incluido" and not data.reason.strip():
        raise HTTPException(400, "Indique el motivo de la exclusión o retiro")
    d.status, d.status_reason, d.reviewed_at, d.curator = data.status, data.reason.strip(), now(), user.full_name
    new_ver = bump_version(db)
    db.commit()
    INDEX.build(db)
    audit(db, user, "corpus_estado", f"{doc_id} -> {data.status} ({data.reason}) corpus {new_ver}")
    return doc_out(d)


@router.post("/corpus/reindex")
def corpus_reindex(user: User = Depends(curador), db: Session = Depends(get_db)):
    INDEX.build(db)
    audit(db, user, "corpus_reindexar", f"{len(INDEX.chunks)} fragmentos")
    return {"indexed_chunks": len(INDEX.chunks), "version": current_version(db)}
