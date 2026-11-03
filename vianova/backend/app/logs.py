"""Registro de eventos del sistema según la Tabla 8 del informe (Instrumento 4) y auditoría.

Los registros NO guardan el contenido de consultas ni transcripciones: solo metadatos.
"""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from .models import EventLog, AuditLog, User

TIPOS_EVENTO = {
    "inicio_sesion", "fin_sesion", "tarea_creada", "tarea_completada", "recordatorio_emitido",
    "recordatorio_confirmado", "registro_evento", "consulta_rag", "recomendacion_mostrada",
    "recomendacion_valorada", "aviso_mostrado", "importacion_dispositivo",
}
# Eventos que el cliente puede reportar directamente (el resto lo registra el servidor)
TIPOS_CLIENTE = {"fin_sesion", "recordatorio_emitido", "recomendacion_mostrada"}


def log_event(db: Session, user: User, tipo: str, modulo: str, *, id_recurso: str = "",
              hora_programada: datetime | None = None, canal: str = "", resultado: str = "exito",
              fuente_id: str = "", version_corpus: str = "", duracion_ms: int | None = None,
              commit: bool = True) -> EventLog:
    assert tipo in TIPOS_EVENTO, tipo
    ev = EventLog(id_evento=str(uuid.uuid4()), id_participante=user.code, tipo_evento=tipo, modulo=modulo,
                  id_recurso=str(id_recurso), hora_programada=hora_programada, canal=canal, resultado=resultado,
                  fuente_id=fuente_id[:200], version_corpus=version_corpus, duracion_ms=duracion_ms)
    db.add(ev)
    if commit:
        db.commit()
    return ev


def audit(db: Session, user: User, action: str, detail: str = "") -> None:
    db.add(AuditLog(user_code=user.code, action=action, detail=detail[:2000]))
    db.commit()
