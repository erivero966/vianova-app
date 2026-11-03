"""Autenticación (JWT), autorización por roles, hash de contraseñas y cifrado de campos sensibles (RNF-S01)."""
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import JWT_SECRET, JWT_HOURS, ENCRYPTION_KEY_FILE, DATA_DIR
from .db import get_db
from .models import User
from .timeutil import now
import os


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()          # hash con sal (bcrypt)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_HOURS)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp},
                      JWT_SECRET, algorithm="HS256")


bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no válido")
    # Devuelve la conexión al pool mientras la petición espera un hilo libre para el endpoint
    # (sin esto, con alta concurrencia el pool se agota: hallazgo OBS-08 de la prueba de estrés)
    db.commit()
    return user


def require(*roles: str):
    """Autorización por rol. El administrador gestiona cuentas, pero no accede a datos de cuidado ni al corpus."""
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permisos para esta acción")
        return user
    return dep


# --------------------------------------------------------------- cifrado en reposo de texto libre
def _load_key() -> bytes:
    env = os.getenv("VIANOVA_FERNET_KEY")
    if env:
        return env.encode()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ENCRYPTION_KEY_FILE.exists():
        ENCRYPTION_KEY_FILE.write_bytes(Fernet.generate_key())
        try:
            os.chmod(ENCRYPTION_KEY_FILE, 0o600)
        except OSError:
            pass
    return ENCRYPTION_KEY_FILE.read_bytes().strip()


_fernet = Fernet(_load_key())


def encrypt(text: str) -> str:
    return _fernet.encrypt(text.encode()).decode() if text else ""


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return ""
