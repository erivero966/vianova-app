"""Cálculo de indicadores a partir de los registros del sistema (Técnica 2, Instrumento 4, Tabla 8).

- Actividades por día = (tareas completadas + eventos registrados) / días con uso
- % tareas a tiempo = tareas completadas hasta ON_TIME_TOLERANCE_MIN después de la hora programada
                      / tareas programadas en el periodo × 100
"""
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .config import ON_TIME_TOLERANCE_MIN
from .models import EventLog, Task, User
from .schedule import occurrences
from .timeutil import now


def participant_indicators(db: Session, user: User, start: datetime, end: datetime) -> dict:
    end = min(end, now())
    logs = (db.query(EventLog).filter(EventLog.id_participante == user.code, EventLog.fecha_hora >= start,
                                      EventLog.fecha_hora <= end).all())
    days = {l.fecha_hora.date() for l in logs}
    completed = [l for l in logs if l.tipo_evento == "tarea_completada"]
    registered = [l for l in logs if l.tipo_evento == "registro_evento"]
    tol = timedelta(minutes=ON_TIME_TOLERANCE_MIN)
    on_time = sum(1 for l in completed if l.hora_programada and l.fecha_hora <= l.hora_programada + tol)
    scheduled = 0
    for t in db.query(Task).filter(Task.user_id == user.id).all():
        # solo cuentan las ocurrencias posteriores a la creación de la tarea
        scheduled += len(occurrences(t, max(start, t.created_at), end))
    sessions = [l for l in logs if l.tipo_evento == "fin_sesion" and l.duracion_ms]
    return {
        "participante": user.code,
        "dias_con_uso": len(days),
        "actividades_registradas": len(completed) + len(registered),
        "actividades_por_dia": round((len(completed) + len(registered)) / len(days), 2) if days else 0.0,
        "tareas_programadas": scheduled,
        "tareas_completadas_a_tiempo": on_time,
        "pct_tareas_a_tiempo": round(100 * on_time / scheduled, 1) if scheduled else None,
        "ingresos": sum(1 for l in logs if l.tipo_evento == "inicio_sesion"),
        "consultas_rag": sum(1 for l in logs if l.tipo_evento == "consulta_rag"),
        "recordatorios_confirmados": sum(1 for l in logs if l.tipo_evento == "recordatorio_confirmado"),
        "avisos_mostrados": sum(1 for l in logs if l.tipo_evento == "aviso_mostrado"),
        "modulos_utilizados": sorted({l.modulo for l in logs}),
        "duracion_media_sesion_min": round(sum(l.duracion_ms for l in sessions) / len(sessions) / 60000, 1) if sessions else None,
    }


def weekly(db: Session, user: User, start: datetime, weeks: int = 8) -> list[dict]:
    out = []
    for w in range(weeks):
        s = start + timedelta(weeks=w)
        e = s + timedelta(weeks=1) - timedelta(seconds=1)
        if s > now():
            break
        ind = participant_indicators(db, user, s, e)
        ind["semana"] = w + 1
        out.append(ind)
    return out
