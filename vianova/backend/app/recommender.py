"""Motor de recomendaciones basado en conocimiento y contexto (RF-04, RF-06, RF-07).

Puntaje(d) = w1·S_sem(d,q) + w2·S_ctx(d,c) + w3·S_reg(d) + w4·S_pref(d,u)

Antes de puntuar se aplican las reglas de seguridad: solo se recomiendan documentos incluidos en el corpus
verificado, y los documentos fuente de un aviso activo se ubican primero, con independencia de su puntaje.
"""
import math
from datetime import timedelta
from sqlalchemy.orm import Session

from . import config
from .models import Document, CareEvent, Feedback, Alert, User, Chunk
from .rag.index import INDEX
from .timeutil import now

SYMPTOM_TOPIC = {  # síntoma registrado → tema del corpus
    "fiebre": "fiebre", "dolor": "dolor", "nauseas": "nauseas", "vomito": "vomito", "fatiga": "fatiga",
    "diarrea": "diarrea", "estrenimiento": "estrenimiento", "disnea": "disnea", "sangrado": "sangrado",
    "mucositis": "mucositis", "mareo": "mareo", "insomnio": "insomnio", "ansiedad": "ansiedad", "tos": "tos",
    "confusion": "confusion", "hinchazon": "signos_alarma", "apetito": "apetito", "piel": "piel",
}
SYMPTOM_LABEL = {
    "fiebre": "fiebre", "dolor": "dolor", "nauseas": "náuseas", "vomito": "vómitos", "fatiga": "fatiga",
    "diarrea": "diarrea", "estrenimiento": "estreñimiento", "disnea": "falta de aire", "sangrado": "sangrado",
    "mucositis": "llagas en la boca", "mareo": "mareo", "insomnio": "problemas de sueño", "ansiedad": "ansiedad",
    "tos": "tos", "confusion": "confusión", "hinchazon": "hinchazón", "apetito": "falta de apetito", "piel": "piel",
}
TREAT_LABEL = {"quimioterapia": "quimioterapia", "radioterapia": "radioterapia", "cirugia": "cirugía",
               "inmunoterapia": "inmunoterapia", "paliativo": "cuidados paliativos"}


def context_of(db: Session, user: User) -> dict:
    p = user.profile
    since = now() - timedelta(days=7)
    events = (db.query(CareEvent).filter(CareEvent.user_id == user.id, CareEvent.occurred_at >= since)
              .order_by(CareEvent.occurred_at.desc()).all())
    recent = {}
    for e in events:
        if e.symptom and e.symptom not in recent:
            recent[e.symptom] = e.occurred_at
    tags = set()
    treatments = (p.treatments if p else []) or []
    tags.update(treatments)
    for s in recent:
        if s in SYMPTOM_TOPIC:
            tags.add(SYMPTOM_TOPIC[s])
    if p and p.mobility in ("ayuda_parcial", "encamado"):
        tags.add("movilidad")
    alerts = (db.query(Alert).filter(Alert.user_id == user.id, Alert.acknowledged.is_(False),
                                     Alert.created_at >= now() - timedelta(hours=72)).all())
    return {"tags": tags, "recent": recent, "treatments": treatments, "alert_docs": {a.doc_id for a in alerts}}


def _ago(dt) -> str:
    h = (now() - dt).total_seconds() / 3600
    if h < 1:
        return "hace menos de una hora"
    if h < 24:
        return f"hace {int(h)} h"
    d = int(h // 24)
    return "hace 1 día" if d == 1 else f"hace {d} días"


def recommend(db: Session, user: User, query: str | None = None, limit: int = 5) -> list[dict]:
    ctx = context_of(db, user)
    docs = db.query(Document).filter(Document.status == "incluido").all()
    if not docs:
        return []
    sem_text = query or " ".join([SYMPTOM_LABEL.get(s, s) for s in ctx["recent"]] + list(ctx["treatments"]))
    sem_raw = INDEX.doc_scores(sem_text) if sem_text.strip() else {}
    mx = max(sem_raw.values()) if sem_raw else 0
    fb = {}
    for f in db.query(Feedback).filter(Feedback.user_id == user.id).all():
        fb[f.doc_id] = fb.get(f.doc_id, 0) + (1 if f.useful else -1)
    recent_72 = {s for s, t in ctx["recent"].items() if t >= now() - timedelta(hours=72)}
    out = []
    for d in docs:
        topics = set(d.topics or [])
        reasons = []
        s_sem = (sem_raw.get(d.id, 0) / mx) if mx > 0 else 0.0
        if query and s_sem >= 0.5:
            reasons.append("Coincide con tu consulta")
        overlap = topics & ctx["tags"]
        s_ctx = min(1.0, len(overlap) / max(1, min(3, len(ctx["tags"])))) if ctx["tags"] else 0.0
        for t in sorted(overlap & set(ctx["treatments"])):
            reasons.append(f"Relacionado con el tratamiento: {TREAT_LABEL.get(t, t)}")
        if "movilidad" in overlap:
            reasons.append("Relacionado con la movilidad del paciente")
        s_reg = 0.0
        if d.id in ctx["alert_docs"]:
            s_reg = 1.0
            reasons.insert(0, "Fuente del aviso mostrado por un registro reciente")
        else:
            matched = [s for s in recent_72 if SYMPTOM_TOPIC.get(s) in topics]
            if matched:
                s_reg = 0.7
                for s in matched:
                    reasons.append(f"Registraste {SYMPTOM_LABEL.get(s, s)} ({_ago(ctx['recent'][s])})")
            elif "signos_alarma" in topics and recent_72:
                s_reg = 0.3
                reasons.append("Ayuda a reconocer cuándo buscar atención")
        net = fb.get(d.id, 0)
        s_pref = 0.5 + 0.5 * math.tanh(net / 2)
        if net > 0:
            reasons.append("Lo marcaste como útil")
        score = config.W_SEM * s_sem + config.W_CTX * s_ctx + config.W_REG * s_reg + config.W_PREF * s_pref
        if not reasons:
            reasons.append("Recomendación general para cuidadores")
        out.append({"doc_id": d.id, "title": d.title, "institution": d.institution, "version": d.version,
                    "year": d.year, "url": d.url, "is_demo": d.is_demo, "score": round(score, 4),
                    "components": {"sem": round(s_sem, 3), "ctx": round(s_ctx, 3), "reg": round(s_reg, 3),
                                   "pref": round(s_pref, 3)},
                    "reasons": reasons, "priority": d.id in ctx["alert_docs"]})
    out.sort(key=lambda r: (not r["priority"], -r["score"]))
    top = out[:limit]
    for r in top:
        ch = db.query(Chunk).filter(Chunk.doc_id == r["doc_id"]).order_by(Chunk.ordinal).first()
        r["snippet"] = (ch.text[:220] + "…") if ch and len(ch.text) > 220 else (ch.text if ch else "")
        r["section"] = ch.section if ch else ""
    return top
