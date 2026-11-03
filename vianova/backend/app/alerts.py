"""Motor de avisos basado en reglas documentadas (RF-11). No realiza triaje ni clasificación clínica."""
import json
from functools import lru_cache
from sqlalchemy.orm import Session

from .config import RULES_FILE
from .models import CareEvent, Alert, Document


@lru_cache
def load_rules() -> dict:
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def matching_rules(ev: CareEvent) -> list[dict]:
    out = []
    for r in load_rules()["rules"]:
        if r["symptom"] != ev.symptom:
            continue
        if "min_value" in r and (ev.value is None or ev.value < r["min_value"]):
            continue
        if r.get("requires_no_value") and ev.value is not None:
            continue
        if "min_intensity" in r and (ev.intensity is None or ev.intensity < r["min_intensity"]):
            continue
        if "min_frequency" in r and (ev.frequency is None or ev.frequency < r["min_frequency"]):
            continue
        out.append(r)
    return out


def evaluate(db: Session, ev: CareEvent) -> list[Alert]:
    contact = load_rules()["contact_text"]
    alerts = []
    for r in matching_rules(ev):
        doc = db.get(Document, r["doc_id"])
        if doc is None or doc.status != "incluido":
            continue          # una regla sin fuente vigente no genera aviso
        a = Alert(user_id=ev.user_id, event_id=ev.id, rule_id=r["id"], message=f"{r['message']} {contact}",
                  doc_id=r["doc_id"])
        db.add(a)
        alerts.append(a)
    db.flush()
    return alerts


def alert_dict(db: Session, a: Alert) -> dict:
    d = db.get(Document, a.doc_id)
    return {"id": a.id, "rule_id": a.rule_id, "message": a.message, "created_at": a.created_at.isoformat(),
            "acknowledged": a.acknowledged,
            "source": {"doc_id": d.id, "title": d.title, "institution": d.institution, "version": d.version,
                       "is_demo": d.is_demo} if d else None}
