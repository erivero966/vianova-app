"""Perfil, tareas y recordatorios, registro de eventos, avisos, dispositivos y resumen exportable."""
import csv
import io
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import alerts as alert_engine
from ..config import CONSENT_VERSION
from ..db import get_db
from ..logs import log_event
from ..models import (User, PatientProfile, Consent, Task, TaskCompletion, CareEvent, Alert, DeviceReading)
from ..nlp import extract
from ..recommender import SYMPTOM_LABEL
from ..schedule import occurrences
from ..security import require, encrypt, decrypt
from ..timeutil import now, parse, iso

router = APIRouter(prefix="/api", tags=["cuidado"])
cuidador = require("cuidador")

TREATMENTS = {"quimioterapia", "radioterapia", "cirugia", "inmunoterapia", "paliativo"}


# ------------------------------------------------------------------ perfil (RF-01)
class ProfileIn(BaseModel):
    patient_alias: str = ""
    relationship_to_patient: str = ""
    patient_age: int | None = Field(default=None, ge=18, le=120)
    cancer_type: str = ""
    treatments: list[str] = []
    mobility: str = ""
    interaction_pref: str = "texto"


def profile_out(p: PatientProfile) -> dict:
    return {"patient_alias": p.patient_alias, "relationship_to_patient": p.relationship_to_patient,
            "patient_age": p.patient_age, "cancer_type": p.cancer_type, "treatments": p.treatments or [],
            "mobility": p.mobility, "interaction_pref": p.interaction_pref, "devices_authorized": p.devices_authorized}


@router.get("/profile")
def get_profile(user: User = Depends(cuidador)):
    return profile_out(user.profile)


@router.put("/profile")
def put_profile(data: ProfileIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    p = user.profile
    for k, v in data.model_dump().items():
        if k == "treatments":
            v = [t for t in v if t in TREATMENTS]
        setattr(p, k, v)
    db.commit()
    return profile_out(p)


class DeviceConsentIn(BaseModel):
    granted: bool


@router.post("/profile/devices-consent")
def devices_consent(data: DeviceConsentIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    user.profile.devices_authorized = data.granted
    db.add(Consent(user_id=user.id, kind="dispositivos", version=CONSENT_VERSION, granted=data.granted))
    db.commit()
    return profile_out(user.profile)


# ------------------------------------------------------------------ tareas (RF-02)
class TaskIn(BaseModel):
    kind: str = Field(pattern="^(medicamento|cita|actividad)$")
    title: str = Field(min_length=1, max_length=200)
    instructions: str = ""
    start_at: str
    recurrence: str = Field(default="unica", pattern="^(unica|diaria|cada_n_horas)$")
    every_hours: int | None = Field(default=None, ge=1, le=48)
    end_date: str | None = None


def task_out(t: Task) -> dict:
    return {"id": t.id, "kind": t.kind, "title": t.title, "instructions": t.instructions, "start_at": iso(t.start_at),
            "recurrence": t.recurrence, "every_hours": t.every_hours, "end_date": iso(t.end_date), "active": t.active}


@router.get("/tasks")
def list_tasks(user: User = Depends(cuidador), db: Session = Depends(get_db)):
    return [task_out(t) for t in db.query(Task).filter(Task.user_id == user.id, Task.active.is_(True))
            .order_by(Task.start_at).all()]


@router.post("/tasks")
def create_task(data: TaskIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    if data.recurrence == "cada_n_horas" and not data.every_hours:
        raise HTTPException(400, "Indique cada cuántas horas se repite")
    t = Task(user_id=user.id, kind=data.kind, title=data.title.strip(), instructions=data.instructions.strip(),
             start_at=parse(data.start_at), recurrence=data.recurrence, every_hours=data.every_hours,
             end_date=parse(data.end_date) if data.end_date else None)
    db.add(t)
    db.commit()
    log_event(db, user, "tarea_creada", "actividades", id_recurso=f"TAR-{t.id:04d}", hora_programada=t.start_at)
    return task_out(t)


@router.put("/tasks/{task_id}")
def update_task(task_id: int, data: TaskIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Tarea no encontrada")
    t.kind, t.title, t.instructions = data.kind, data.title.strip(), data.instructions.strip()
    t.start_at, t.recurrence, t.every_hours = parse(data.start_at), data.recurrence, data.every_hours
    t.end_date = parse(data.end_date) if data.end_date else None
    db.commit()
    return task_out(t)


@router.delete("/tasks/{task_id}")
def deactivate_task(task_id: int, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Tarea no encontrada")
    t.active = False
    t.end_date = now()
    db.commit()
    return {"ok": True}


@router.get("/tasks/agenda")
def agenda(date: str | None = None, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    day = parse(date).date() if date else now().date()
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1) - timedelta(seconds=1)
    items = []
    for t in db.query(Task).filter(Task.user_id == user.id).all():
        if not t.active and (t.end_date is None or t.end_date < start):
            continue
        done = {c.occurrence_at: c for c in db.query(TaskCompletion).filter(
            TaskCompletion.task_id == t.id, TaskCompletion.occurrence_at >= start, TaskCompletion.occurrence_at <= end)}
        for occ in occurrences(t, start, end):
            c = done.get(occ)
            items.append({"task": task_out(t), "occurrence_at": iso(occ),
                          "status": c.status if c else ("vencida" if occ < now() else "pendiente"),
                          "completed_at": iso(c.completed_at) if c else None})
    items.sort(key=lambda x: x["occurrence_at"])
    return {"date": day.isoformat(), "items": items}


class CompleteIn(BaseModel):
    occurrence_at: str
    status: str = Field(default="hecha", pattern="^(hecha|omitida)$")
    from_reminder: bool = False


@router.post("/tasks/{task_id}/complete")
def complete(task_id: int, data: CompleteIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Tarea no encontrada")
    occ = parse(data.occurrence_at)
    if occ not in occurrences(t, occ - timedelta(seconds=1), occ + timedelta(seconds=1)):
        raise HTTPException(400, "La tarea no tiene una ocurrencia en esa hora")
    if db.query(TaskCompletion).filter(TaskCompletion.task_id == t.id, TaskCompletion.occurrence_at == occ).first():
        raise HTTPException(400, "Esta ocurrencia ya fue registrada")
    c = TaskCompletion(task_id=t.id, user_id=user.id, occurrence_at=occ, status=data.status)
    db.add(c)
    db.commit()
    rid = f"TAR-{t.id:04d}"
    if data.status == "hecha":
        log_event(db, user, "tarea_completada", "actividades", id_recurso=rid, hora_programada=occ)
        if data.from_reminder:
            log_event(db, user, "recordatorio_confirmado", "recordatorios", id_recurso=rid, hora_programada=occ)
    return {"ok": True, "completed_at": iso(c.completed_at)}


# ------------------------------------------------------------------ eventos (RF-03) y avisos (RF-11)
class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("/events/parse")
def parse_event(data: ParseIn, user: User = Depends(cuidador)):
    """Propone una estructura a partir del texto (o la transcripción de voz). NO guarda nada."""
    return extract(data.text)


class EventIn(BaseModel):
    kind: str = Field(default="sintoma", pattern="^(sintoma|observacion|actividad)$")
    symptom: str = ""
    intensity: int | None = Field(default=None, ge=0, le=10)
    value: float | None = None
    unit: str = ""
    moment: str = ""
    frequency: int | None = Field(default=None, ge=0, le=50)
    text: str = ""
    channel: str = Field(default="texto", pattern="^(texto|seleccion|voz)$")
    confirmed: bool = False
    occurred_at: str | None = None


def event_out(e: CareEvent) -> dict:
    return {"id": e.id, "kind": e.kind, "symptom": e.symptom, "symptom_label": SYMPTOM_LABEL.get(e.symptom, e.symptom),
            "intensity": e.intensity, "value": e.value, "unit": e.unit, "moment": e.moment, "frequency": e.frequency,
            "text": decrypt(e.text_enc), "channel": e.channel, "occurred_at": iso(e.occurred_at)}


@router.post("/events")
def save_event(data: EventIn, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    if not data.confirmed:
        raise HTTPException(400, "El registro debe ser confirmado por el cuidador antes de guardarse")
    if not data.symptom and not data.text.strip():
        raise HTTPException(400, "Indique un síntoma o una descripción")
    e = CareEvent(user_id=user.id, kind=data.kind, symptom=data.symptom, intensity=data.intensity, value=data.value,
                  unit=data.unit, moment=data.moment, frequency=data.frequency, text_enc=encrypt(data.text.strip()),
                  channel=data.channel, occurred_at=parse(data.occurred_at) if data.occurred_at else now())
    db.add(e)
    db.flush()
    new_alerts = alert_engine.evaluate(db, e)
    db.commit()
    log_event(db, user, "registro_evento", "registro", id_recurso=f"EVT-{e.id:05d}", canal=data.channel)
    for a in new_alerts:
        log_event(db, user, "aviso_mostrado", "avisos", id_recurso=a.rule_id, fuente_id=a.doc_id)
    return {"event": event_out(e), "alerts": [alert_engine.alert_dict(db, a) for a in new_alerts]}


@router.get("/events")
def list_events(days: int = 14, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    since = now() - timedelta(days=days)
    return [event_out(e) for e in db.query(CareEvent).filter(CareEvent.user_id == user.id, CareEvent.occurred_at >= since)
            .order_by(CareEvent.occurred_at.desc()).all()]


@router.get("/alerts")
def list_alerts(history: bool = False, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    """Avisos recientes (inicio) o historial completo (pantalla Historial de avisos, RF-09)."""
    q = db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at.desc()).limit(200 if history else 20)
    return [alert_engine.alert_dict(db, a) for a in q]


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    a = db.get(Alert, alert_id)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Aviso no encontrado")
    a.acknowledged = True
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ wearables / IoT (RF-08)
METRICS = {"frecuencia_cardiaca": "lpm", "pasos": "pasos", "temperatura": "°C", "spo2": "%", "sueno_horas": "h"}


@router.post("/devices/import")
async def import_device(file: UploadFile = File(...), user: User = Depends(cuidador), db: Session = Depends(get_db)):
    if not user.profile.devices_authorized:
        raise HTTPException(403, "Primero autorice la importación de datos de dispositivos en su perfil")
    raw = (await file.read()).decode("utf-8", errors="replace")
    rows, device_default = [], ""
    try:
        if file.filename.lower().endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(raw)))
        else:
            data = json.loads(raw)
            rows = data.get("lecturas", data) if isinstance(data, dict) else data
            device_default = data.get("dispositivo", "") if isinstance(data, dict) else ""
    except (json.JSONDecodeError, csv.Error):
        raise HTTPException(400, "Archivo no válido: use JSON o CSV con columnas metrica, valor, fecha, dispositivo")
    imported, rejected = 0, 0
    for r in rows:
        try:
            metric = str(r.get("metrica", "")).strip()
            if metric not in METRICS:
                raise ValueError
            db.add(DeviceReading(user_id=user.id, metric=metric, value=float(r["valor"]), unit=METRICS[metric],
                                 measured_at=parse(str(r["fecha"])),
                                 device=str(r.get("dispositivo") or device_default or "desconocido"),
                                 source_file=file.filename[:200]))
            imported += 1
        except (KeyError, ValueError, TypeError):
            rejected += 1
    db.commit()
    log_event(db, user, "importacion_dispositivo", "dispositivos", id_recurso=file.filename[:60],
              resultado="exito" if imported else "error")
    return {"importadas": imported, "rechazadas": rejected}


@router.get("/devices/readings")
def readings(days: int = 7, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    since = now() - timedelta(days=days)
    q = db.query(DeviceReading).filter(DeviceReading.user_id == user.id, DeviceReading.measured_at >= since) \
        .order_by(DeviceReading.measured_at.desc()).limit(500)
    return [{"metric": r.metric, "value": r.value, "unit": r.unit, "measured_at": iso(r.measured_at), "device": r.device,
             "source_file": r.source_file, "imported_at": iso(r.imported_at)} for r in q]


# ------------------------------------------------------------------ resumen exportable (RF-12)
def build_summary(db: Session, user: User, days: int) -> dict:
    since = now() - timedelta(days=days)
    p = user.profile
    events = [event_out(e) for e in db.query(CareEvent).filter(CareEvent.user_id == user.id, CareEvent.occurred_at >= since)
              .order_by(CareEvent.occurred_at).all()]
    by_symptom = {}
    for e in events:
        if not e["symptom"]:
            continue
        s = by_symptom.setdefault(e["symptom_label"], {"registros": 0, "intensidad_max": None, "valor_max": None})
        s["registros"] += 1
        if e["intensity"] is not None:
            s["intensidad_max"] = max(s["intensidad_max"] or 0, e["intensity"])
        if e["value"] is not None:
            s["valor_max"] = max(s["valor_max"] or 0, e["value"])
    tasks = db.query(Task).filter(Task.user_id == user.id).all()
    adherence = []
    for t in tasks:
        if t.kind != "medicamento":
            continue
        occ = occurrences(t, since, now())
        done = db.query(TaskCompletion).filter(TaskCompletion.task_id == t.id, TaskCompletion.status == "hecha",
                                               TaskCompletion.occurrence_at >= since).count()
        adherence.append({"medicamento": t.title, "indicacion": t.instructions, "programadas": len(occ), "realizadas": done})
    alerts = [alert_engine.alert_dict(db, a) for a in db.query(Alert).filter(Alert.user_id == user.id,
                                                                             Alert.created_at >= since)]
    dev = db.query(DeviceReading).filter(DeviceReading.user_id == user.id, DeviceReading.measured_at >= since).all()
    dev_sum = {}
    for r in dev:
        d = dev_sum.setdefault(r.metric, {"n": 0, "min": r.value, "max": r.value, "unidad": r.unit})
        d["n"] += 1
        d["min"], d["max"] = min(d["min"], r.value), max(d["max"], r.value)
    return {"generado": iso(now()), "periodo_dias": days, "cuidador": user.full_name,
            "paciente": profile_out(p), "sintomas": by_symptom, "eventos": events, "medicamentos": adherence,
            "avisos": alerts, "dispositivos": dev_sum,
            "nota": "Resumen generado por el cuidador para compartir con el equipo de salud. Los datos de dispositivos "
                    "no equivalen a mediciones clínicas certificadas."}


@router.get("/summary")
def summary(days: int = 14, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    return build_summary(db, user, max(1, min(days, 90)))


@router.get("/summary.csv")
def summary_csv(days: int = 14, user: User = Depends(cuidador), db: Session = Depends(get_db)):
    s = build_summary(db, user, max(1, min(days, 90)))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fecha_hora", "tipo", "sintoma", "intensidad_0_10", "valor", "unidad", "momento", "veces", "nota", "canal"])
    for e in s["eventos"]:
        w.writerow([e["occurred_at"], e["kind"], e["symptom_label"], e["intensity"], e["value"], e["unit"], e["moment"],
                    e["frequency"], e["text"], e["channel"]])
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=resumen_registros.csv"})
