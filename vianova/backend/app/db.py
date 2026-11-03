import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import DATABASE_URL, DATA_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)
_sqlite = DATABASE_URL.startswith("sqlite")
_args = {"check_same_thread": False, "timeout": 15} if _sqlite else {}
# El pool debe ser mayor que el número de hilos del servidor (40 por defecto en FastAPI/Starlette); con un pool
# pequeño, bajo alta concurrencia los hilos quedan esperando conexiones (hallazgo de la prueba de estrés, OBS-08).
engine = create_engine(DATABASE_URL, connect_args=_args, future=True,
                       pool_size=int(os.getenv("DB_POOL_SIZE", "50")), max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "50")),
                       pool_timeout=30, pool_pre_ping=not _sqlite)

if _sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")       # lecturas concurrentes mientras se escribe
        cur.execute("PRAGMA busy_timeout=15000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
