"""Configuración del motor (embeddings y base de datos) mediante variables de entorno."""

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class EmbeddingSettings:
    model: str = "alia"
    device: str = "auto"
    batch_size: int = 16

    @classmethod
    def from_env(cls) -> "EmbeddingSettings":
        model = os.getenv("EMBEDDING_MODEL", "alia").strip().lower()
        device = os.getenv("EMBEDDING_DEVICE", "auto").strip().lower()
        raw_batch_size = os.getenv("EMBEDDING_BATCH_SIZE", "16")
        try:
            batch_size = int(raw_batch_size)
        except ValueError as exc:
            raise ValueError("EMBEDDING_BATCH_SIZE debe ser un número entero.") from exc
        if device not in {"auto", "cpu", "cuda"}:
            raise ValueError("EMBEDDING_DEVICE debe ser 'auto', 'cpu' o 'cuda'.")
        if batch_size < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE debe ser mayor que cero.")
        return cls(model=model, device=device, batch_size=batch_size)


@dataclass(frozen=True)
class DatabaseSettings:
    host: str = "localhost"
    port: int = 5432
    dbname: str = "vianova_rag"
    user: str = "vianova"
    password: str = field(default="", repr=False)

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        password = os.getenv("POSTGRES_PASSWORD", "")
        if not password:
            raise ValueError("POSTGRES_PASSWORD no está definida. Copie .env.example a .env.")
        raw_port = os.getenv("POSTGRES_PORT", "5432")
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("POSTGRES_PORT debe ser un número entero.") from exc
        return cls(
            host=os.getenv("POSTGRES_HOST", "localhost").strip(),
            port=port,
            dbname=os.getenv("POSTGRES_DB", "vianova_rag").strip(),
            user=os.getenv("POSTGRES_USER", "vianova").strip(),
            password=password,
        )

    def connection_kwargs(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
        }
