"""Autenticación, registro con consentimiento y eventos de sesión."""
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import CONSENT_VERSION
from ..db import get_db
from ..logs import log_event, TIPOS_CLIENTE
from ..models import User, Consent, PatientProfile
from ..security import hash_password, verify_password, create_token, current_user
from ..timeutil import parse

router = APIRouter(prefix="/api", tags=["auth"])


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=100)
    consent_study: bool


class LoginIn(BaseModel):
    email: str
    password: str


def next_code(db: Session) -> str:
    n = db.query(User).filter(User.role == "cuidador").count() + 1
    while db.query(User).filter(User.code == f"CUI-{n:03d}").first():
        n += 1
    return f"CUI-{n:03d}"


def user_out(u: User) -> dict:
    return {"id": u.id, "code": u.code, "email": u.email, "full_name": u.full_name, "role": u.role,
            "has_profile": bool(u.profile and u.profile.cancer_type)}


@router.post("/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if not data.consent_study:
        raise HTTPException(400, "Para usar el sistema debe aceptar el consentimiento informado")
    email = data.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Correo no válido")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Ya existe una cuenta con ese correo")
    u = User(code=next_code(db), email=email, full_name=data.full_name.strip(),
             password_hash=hash_password(data.password), role="cuidador")
    db.add(u)
    db.flush()
    db.add(Consent(user_id=u.id, kind="estudio", version=CONSENT_VERSION, granted=True))
    db.add(PatientProfile(user_id=u.id, treatments=[]))
    db.commit()
    log_event(db, u, "inicio_sesion", "autenticacion")
    return {"token": create_token(u), "user": user_out(u)}


# Bloqueo temporal ante intentos fallidos repetidos (protección contra fuerza bruta)
MAX_FAILS, LOCK_MIN = 5, 15
_fails: dict[str, list[float]] = {}


def _recent_fails(email: str) -> list[float]:
    t = time.time()
    lst = [x for x in _fails.get(email, []) if t - x < LOCK_MIN * 60]
    _fails[email] = lst
    return lst


@router.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if len(_recent_fails(email)) >= MAX_FAILS:
        raise HTTPException(429, f"Demasiados intentos fallidos. Intente de nuevo en {LOCK_MIN} minutos")
    u = db.query(User).filter(User.email == email).first()
    if not u or not verify_password(data.password, u.password_hash) or not u.active:
        _fails.setdefault(email, []).append(time.time())
        raise HTTPException(401, "Correo o contraseña incorrectos")
    _fails.pop(email, None)
    log_event(db, u, "inicio_sesion", "autenticacion")
    return {"token": create_token(u), "user": user_out(u)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


class ClientLogIn(BaseModel):
    tipo_evento: str
    modulo: str = "app"
    id_recurso: str = ""
    hora_programada: str | None = None
    duracion_ms: int | None = None


@router.post("/logs/client")
def client_log(data: ClientLogIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.tipo_evento not in TIPOS_CLIENTE:
        raise HTTPException(400, "Tipo de evento no permitido desde el cliente")
    log_event(db, user, data.tipo_evento, data.modulo[:40], id_recurso=data.id_recurso,
              hora_programada=parse(data.hora_programada) if data.hora_programada else None,
              duracion_ms=data.duracion_ms)
    return {"ok": True}
