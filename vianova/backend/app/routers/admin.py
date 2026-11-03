"""Administración (RF-13): usuarios, roles, estado de cuentas, auditoría y configuración vigente (RF-12)."""
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..logs import audit
from ..models import User, AuditLog, Document
from ..rag.corpus import current_version
from ..rag.index import INDEX
from ..security import require, hash_password
from ..timeutil import iso

router = APIRouter(prefix="/api/admin", tags=["administración"])
admin = require("admin")
ROLES = ("cuidador", "curador", "investigador", "admin")
PREFIX = {"curador": "CUR", "investigador": "INV", "admin": "ADM", "cuidador": "CUI"}


def u_out(u: User) -> dict:
    return {"id": u.id, "code": u.code, "email": u.email, "full_name": u.full_name, "role": u.role,
            "active": u.active, "created_at": iso(u.created_at)}


@router.get("/users")
def users(user: User = Depends(admin), db: Session = Depends(get_db)):
    return [u_out(u) for u in db.query(User).order_by(User.role, User.code)]


class NewUser(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=10, max_length=100)
    role: str = Field(pattern="^(curador|investigador|admin)$")


@router.post("/users")
def create_user(data: NewUser, user: User = Depends(admin), db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Correo no válido")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "Ya existe una cuenta con ese correo")
    p = PREFIX[data.role]
    n = db.query(User).filter(User.code.like(f"{p}-%")).count() + 1
    while db.query(User).filter(User.code == f"{p}-{n:03d}").first():
        n += 1
    u = User(code=f"{p}-{n:03d}", email=email, full_name=data.full_name.strip(),
             password_hash=hash_password(data.password), role=data.role)
    db.add(u)
    db.commit()
    audit(db, user, "crear_usuario", f"{u.code} rol={u.role}")
    return u_out(u)


class UpdUser(BaseModel):
    role: str | None = Field(default=None, pattern="^(cuidador|curador|investigador|admin)$")
    active: bool | None = None


@router.put("/users/{uid}")
def update_user(uid: int, data: UpdUser, user: User = Depends(admin), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id == user.id and (data.active is False or (data.role and data.role != "admin")):
        raise HTTPException(400, "No puede desactivar ni quitarse el rol de administrador a sí mismo")
    if data.role and (u.role == "cuidador") != (data.role == "cuidador"):
        raise HTTPException(400, "Las cuentas de cuidador no pueden convertirse en cuentas internas (ni al revés)")
    changes = []
    if data.role and data.role != u.role:
        changes.append(f"rol {u.role}->{data.role}")
        u.role = data.role
    if data.active is not None and data.active != u.active:
        changes.append("activada" if data.active else "desactivada")
        u.active = data.active
    db.commit()
    if changes:
        audit(db, user, "modificar_usuario", f"{u.code}: " + ", ".join(changes))
    return u_out(u)


@router.get("/audit")
def audit_log(user: User = Depends(admin), db: Session = Depends(get_db)):
    return [{"at": iso(a.at), "user": a.user_code, "action": a.action, "detail": a.detail}
            for a in db.query(AuditLog).order_by(AuditLog.at.desc()).limit(300)]


def _sha(path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


@router.get("/config")
def current_config(user: User = Depends(require("admin", "curador", "investigador")), db: Session = Depends(get_db)):
    """Configuración vigente del modelo (lectura). Los cambios se hacen por variables de entorno y quedan versionados."""
    docs = db.query(Document).all()
    return {
        "ambiente": config.APP_ENV,
        "version_corpus": current_version(db),
        "documentos": {"incluidos": sum(d.status == "incluido" for d in docs), "total": len(docs),
                       "demo": sum(bool(d.is_demo) for d in docs)},
        "indice": {"fragmentos": len(INDEX.chunks), "dimension_embeddings": INDEX.dim,
                   "peso_denso": config.RAG_DENSE_WEIGHT, "top_k": config.RAG_TOP_K},
        "rag": {"tau": config.RAG_TAU, "cobertura_minima": config.RAG_MIN_COVERAGE,
                "proveedor": config.LLM_PROVIDER,
                "modelo": {"anthropic": config.ANTHROPIC_MODEL, "openai": config.OPENAI_MODEL}.get(config.LLM_PROVIDER,
                                                                                                     "extractivo local")},
        "recomendador": {"w_sem": config.W_SEM, "w_ctx": config.W_CTX, "w_reg": config.W_REG, "w_pref": config.W_PREF},
        "reglas": {"archivo": config.RULES_FILE.name, "sha256": _sha(config.RULES_FILE),
                   "n": len(json.loads(config.RULES_FILE.read_text(encoding="utf-8")).get("rules", []))
                   if config.RULES_FILE.exists() else 0},
        "consentimiento_vigente": config.CONSENT_VERSION,
        "tolerancia_a_tiempo_min": config.ON_TIME_TOLERANCE_MIN,
    }
