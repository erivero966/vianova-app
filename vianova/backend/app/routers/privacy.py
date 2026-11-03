"""Privacidad y derechos ARCO (RF-15, Ley 29733 y DS 016-2024-JUS): consentimientos, acceso, revocación y cancelación."""
import secrets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import CONSENT_VERSION
from ..db import get_db
from ..logs import audit
from ..models import (User, Consent, Task, TaskCompletion, CareEvent, Alert, DeviceReading, Feedback)
from ..security import require, verify_password, hash_password, decrypt
from ..timeutil import iso

router = APIRouter(prefix="/api/privacy", tags=["privacidad"])
cuidador = require("cuidador")


def consent_state(db: Session, user: User) -> dict:
    out = {}
    for c in db.query(Consent).filter(Consent.user_id == user.id).order_by(Consent.at):
        out[c.kind] = {"granted": c.granted, "version": c.version, "at": iso(c.at)}
    return out


@router.get("/consents")
def consents(user: User = Depends(cuidador), db: Session = Depends(get_db)):
    hist = [{"kind": c.kind, "granted": c.granted, "version": c.version, "at": iso(c.at)}
            for c in db.query(Consent).filter(Consent.user_id == user.id).order_by(Consent.at.desc())]
    return {"vigente": consent_state(db, user), "historial": hist, "version_actual": CONSENT_VERSION}


class RevokeIn(BaseModel):
    kind: str = Field(pattern="^(dispositivos)$")


@router.post("/consents/revoke")
def revoke(data: RevokeIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    """Revocar la autorización de dispositivos elimina además los datos importados."""
    n = db.query(DeviceReading).filter(DeviceReading.user_id == user.id).delete()
    user.profile.devices_authorized = False
    db.add(Consent(user_id=user.id, kind="dispositivos", version=CONSENT_VERSION, granted=False))
    db.commit()
    audit(db, user, "revocar_consentimiento", f"dispositivos; {n} lecturas eliminadas")
    return {"ok": True, "lecturas_eliminadas": n}


@router.get("/export")
def export_my_data(user: User = Depends(cuidador), db: Session = Depends(get_db)):
    """Derecho de acceso: todos los datos personales del titular en formato JSON."""
    p = user.profile
    data = {
        "cuenta": {"codigo": user.code, "correo": user.email, "nombre": user.full_name, "creada": iso(user.created_at)},
        "perfil": {"alias_paciente": p.patient_alias, "parentesco": p.relationship_to_patient, "edad": p.patient_age,
                   "tipo_cancer": p.cancer_type, "tratamientos": p.treatments, "movilidad": p.mobility,
                   "preferencia": p.interaction_pref} if p else {},
        "consentimientos": [{"tipo": c.kind, "otorgado": c.granted, "version": c.version, "fecha": iso(c.at)}
                            for c in db.query(Consent).filter(Consent.user_id == user.id)],
        "tareas": [{"tipo": t.kind, "titulo": t.title, "indicaciones": t.instructions, "inicio": iso(t.start_at),
                    "recurrencia": t.recurrence} for t in db.query(Task).filter(Task.user_id == user.id)],
        "registros": [{"tipo": e.kind, "sintoma": e.symptom, "intensidad": e.intensity, "valor": e.value,
                       "unidad": e.unit, "texto": decrypt(e.text_enc), "fecha": iso(e.occurred_at)}
                      for e in db.query(CareEvent).filter(CareEvent.user_id == user.id)],
        "avisos": [{"regla": a.rule_id, "mensaje": a.message, "fecha": iso(a.created_at)}
                   for a in db.query(Alert).filter(Alert.user_id == user.id)],
        "dispositivos": [{"metrica": r.metric, "valor": r.value, "unidad": r.unit, "fecha": iso(r.measured_at)}
                         for r in db.query(DeviceReading).filter(DeviceReading.user_id == user.id)],
        "valoraciones": [{"documento": f.doc_id, "util": f.useful, "fecha": iso(f.at)}
                         for f in db.query(Feedback).filter(Feedback.user_id == user.id)],
    }
    audit(db, user, "acceso_datos_personales", "exportación ARCO")
    return JSONResponse(data, headers={"Content-Disposition": f"attachment; filename=mis_datos_{user.code}.json"})


class DeleteIn(BaseModel):
    password: str
    confirm: str = Field(pattern="^ELIMINAR$")


@router.post("/delete-account")
def delete_account(data: DeleteIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    """Derecho de cancelación: borra los datos personales y anonimiza la cuenta.
    Los registros de uso (Tabla 8) se conservan solo con el código seudonimizado, sin datos identificatorios."""
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(403, "Contraseña incorrecta")
    uid = user.id
    task_ids = [t.id for t in db.query(Task).filter(Task.user_id == uid)]
    db.query(TaskCompletion).filter(TaskCompletion.user_id == uid).delete()
    db.query(Alert).filter(Alert.user_id == uid).delete()
    db.query(CareEvent).filter(CareEvent.user_id == uid).delete()
    db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
    db.query(DeviceReading).filter(DeviceReading.user_id == uid).delete()
    db.query(Feedback).filter(Feedback.user_id == uid).delete()
    if user.profile:
        db.delete(user.profile)
    db.add(Consent(user_id=uid, kind="estudio", version=CONSENT_VERSION, granted=False))
    user.email = f"eliminado-{user.code.lower()}@anon.invalid"
    user.full_name = "Cuenta eliminada"
    user.password_hash = hash_password(secrets.token_urlsafe(24))
    user.active = False
    db.commit()
    audit(db, user, "cancelacion_cuenta", "datos personales eliminados; cuenta anonimizada")
    return {"ok": True}
