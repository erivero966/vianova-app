"""Conexiones a PostgreSQL y aplicación idempotente del esquema."""

import hashlib
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from ..config import PROJECT_ROOT, DatabaseSettings


SQL_DIR = PROJECT_ROOT / "sql"


class DatabaseUnavailableError(RuntimeError):
    """PostgreSQL no responde con la configuración actual."""


class VectorExtensionMissingError(RuntimeError):
    """La base existe pero la extensión pgvector no está instalada."""


def connect(
    settings: DatabaseSettings | None = None,
    *,
    register: bool = True,
    autocommit: bool = False,
) -> psycopg.Connection:
    """Abre una conexión; con `register` adapta `vector` <-> numpy.ndarray.

    Las transacciones las controla el llamador: `with connect() as conn:`
    confirma al salir sin errores y revierte si se produce una excepción.
    """
    settings = settings or DatabaseSettings.from_env()
    try:
        conn = psycopg.connect(
            **settings.connection_kwargs(),
            autocommit=autocommit,
            connect_timeout=5,
        )
    except psycopg.OperationalError as exc:
        raise DatabaseUnavailableError(
            f"No se pudo conectar a PostgreSQL en {settings.host}:{settings.port}/"
            f"{settings.dbname}. ¿Se ejecutó `docker compose up -d`?"
        ) from exc
    if register:
        try:
            register_vector(conn)
        except psycopg.ProgrammingError as exc:
            conn.close()
            raise VectorExtensionMissingError(
                "La extensión pgvector no está instalada en la base. "
                "Aplique el esquema con apply_schema() o recree el volumen."
            ) from exc
    return conn


class SchemaDriftError(RuntimeError):
    """Una migración ya aplicada fue modificada después de aplicarse."""


def schema_files() -> list[Path]:
    return sorted(SQL_DIR.glob("*.sql"))


def apply_schema(conn: psycopg.Connection) -> list[str]:
    """Aplica en orden las migraciones de sql/ aún no registradas.

    Cada migración se registra con su SHA-256 en `schema_migracion`. Si un
    archivo ya aplicado cambia, se aborta: los cambios de esquema van en una
    migración nueva. Docker ejecuta los mismos archivos al crear el volumen;
    como son idempotentes, registrarlos después es seguro.
    """
    applied = []
    with conn.transaction():
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migracion (
                archivo     TEXT PRIMARY KEY,
                sha256      TEXT NOT NULL,
                aplicado_en TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        for path in schema_files():
            content = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
            row = conn.execute(
                "SELECT sha256 FROM schema_migracion WHERE archivo = %s", (path.name,)
            ).fetchone()
            if row is not None:
                if row[0] != checksum:
                    raise SchemaDriftError(
                        f"La migración {path.name} cambió después de aplicarse. "
                        "Cree una migración nueva en lugar de editarla."
                    )
                continue
            conn.execute(content)
            conn.execute(
                "INSERT INTO schema_migracion (archivo, sha256) VALUES (%s, %s)", (path.name, checksum)
            )
            applied.append(path.name)
    register_vector(conn)
    return applied
