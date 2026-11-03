"""Modelo de datos del sistema Vianova."""
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .timeutil import now


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)      # código seudonimizado (CUI-001)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="cuidador")          # cuidador | curador | investigador
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    profile: Mapped["PatientProfile"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))        # estudio | dispositivos
    version: Mapped[str] = mapped_column(String(30))
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PatientProfile(Base):
    """Contexto básico del paciente configurado por el cuidador (RF-01)."""
    __tablename__ = "patient_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    patient_alias: Mapped[str] = mapped_column(String(100), default="")
    relationship_to_patient: Mapped[str] = mapped_column(String(60), default="")
    patient_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancer_type: Mapped[str] = mapped_column(String(100), default="")
    treatments: Mapped[list] = mapped_column(JSON, default=list)        # quimioterapia, radioterapia, cirugia, inmunoterapia, paliativo
    mobility: Mapped[str] = mapped_column(String(40), default="")       # independiente | ayuda_parcial | encamado
    interaction_pref: Mapped[str] = mapped_column(String(20), default="texto")   # texto | voz
    devices_authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)

    user: Mapped[User] = relationship(back_populates="profile")


class Task(Base):
    """Medicamento, cita o actividad con recordatorio (RF-02)."""
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))            # medicamento | cita | actividad
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text, default="")   # indicación tal como la dio el equipo de salud
    start_at: Mapped[datetime] = mapped_column(DateTime)
    recurrence: Mapped[str] = mapped_column(String(20), default="unica")   # unica | diaria | cada_n_horas
    every_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    occurrence_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(20), default="hecha")   # hecha | omitida


class CareEvent(Base):
    """Registro confirmado de síntoma u observación (RF-03). El texto libre se guarda cifrado."""
    __tablename__ = "care_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="sintoma")    # sintoma | observacion | actividad
    symptom: Mapped[str] = mapped_column(String(60), default="")
    intensity: Mapped[int | None] = mapped_column(Integer, nullable=True)     # 0-10
    value: Mapped[float | None] = mapped_column(Float, nullable=True)         # p. ej., temperatura
    unit: Mapped[str] = mapped_column(String(20), default="")
    moment: Mapped[str] = mapped_column(String(60), default="")
    frequency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_enc: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(String(20), default="texto")       # texto | seleccion | voz
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Alert(Base):
    """Aviso mostrado por coincidir un registro con una regla documentada (RF-11)."""
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("care_events.id"), nullable=True)
    rule_id: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    doc_id: Mapped[str] = mapped_column(String(40), default="")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Document(Base):
    """Documento del corpus con los campos de la ficha de curaduría (Instrumento 7)."""
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    institution: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    url: Mapped[str] = mapped_column(String(500), default="")
    doc_type: Mapped[str] = mapped_column(String(60), default="guía")
    topics: Mapped[list] = mapped_column(JSON, default=list)
    audience: Mapped[str] = mapped_column(String(60), default="cuidadores")
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)         # criterios de inclusión cumplidos
    status: Mapped[str] = mapped_column(String(20), default="incluido")    # incluido | excluido | retirado
    status_reason: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    curator: Mapped[str] = mapped_column(String(120), default="")
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    content: Mapped[str] = mapped_column(Text, default="")


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text)
    corpus_version: Mapped[str] = mapped_column(String(20), default="")
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)     # vector denso (almacenamiento vectorial)


class CorpusState(Base):
    __tablename__ = "corpus_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(20), default="v1.0")
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Feedback(Base):
    """Valoración útil/no útil de una recomendación (RF-07). No altera reglas de seguridad."""
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    doc_id: Mapped[str] = mapped_column(String(40), index=True)
    useful: Mapped[bool] = mapped_column(Boolean)
    at: Mapped[datetime] = mapped_column(DateTime, default=now)


class DeviceReading(Base):
    """Dato importado de wearable/IoT autorizado (RF-08). No equivale a una medición clínica."""
    __tablename__ = "device_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    metric: Mapped[str] = mapped_column(String(40))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default="")
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    device: Mapped[str] = mapped_column(String(120), default="")
    source_file: Mapped[str] = mapped_column(String(200), default="")
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class EventLog(Base):
    """Registro del sistema con la estructura de la Tabla 8 (Instrumento 4)."""
    __tablename__ = "event_logs"
    id_evento: Mapped[str] = mapped_column(String(36), primary_key=True)
    id_participante: Mapped[str] = mapped_column(String(20), index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    tipo_evento: Mapped[str] = mapped_column(String(40), index=True)
    modulo: Mapped[str] = mapped_column(String(40))
    id_recurso: Mapped[str] = mapped_column(String(60), default="")
    hora_programada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    canal: Mapped[str] = mapped_column(String(20), default="")
    resultado: Mapped[str] = mapped_column(String(20), default="exito")
    fuente_id: Mapped[str] = mapped_column(String(200), default="")
    version_corpus: Mapped[str] = mapped_column(String(20), default="")
    duracion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AuditLog(Base):
    """Auditoría de acciones sensibles (RF-10)."""
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_code: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=now)
