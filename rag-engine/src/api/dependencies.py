"""Motor de recuperación compartido por la API.

No reimplementa nada: el embedding de la consulta lo calcula `EmbeddingService`
y la búsqueda exacta (con los filtros normales del corpus: versión activa y
`tipo_contenido = 'contenido'`) la hace `search_selected` -> `VectorRepository`.
El modelo se carga una sola vez por proceso y se reutiliza en cada request.
"""

from collections.abc import Callable
import logging
import threading

import psycopg

from ..database import ModelConfigRepository, SearchResult, VectorRepository, connect
from ..database.indexing import ensure_encoder_matches
from ..embeddings import EmbeddingService
from ..experiments import search_selected


logger = logging.getLogger(__name__)

API_MODEL_ALIAS = "bge-m3"
RETRIEVAL_MODE = "pgvector_exact"


class ModelUnavailableError(RuntimeError):
    """El modelo de embeddings no se pudo cargar al iniciar el servidor."""


class RetrievalEngine:
    """Modelo cargado + acceso a PostgreSQL con una conexión corta por request."""

    def __init__(
        self,
        service: EmbeddingService,
        connect_fn: Callable[[], psycopg.Connection] = connect,
    ) -> None:
        self.service = service
        self._connect = connect_fn
        # SentenceTransformer no garantiza encode concurrente seguro en GPU; el
        # retrieval exacto tarda milisegundos, serializar es suficiente aquí.
        self._lock = threading.Lock()

    @classmethod
    def load(cls) -> "RetrievalEngine":
        service = EmbeddingService(API_MODEL_ALIAS)  # device auto: CUDA si está disponible
        return cls(service)

    @property
    def model_name(self) -> str:
        return self.service.model_name

    def _repository(self, conn: psycopg.Connection) -> VectorRepository:
        config = ModelConfigRepository(conn).get_active(API_MODEL_ALIAS)
        return VectorRepository(conn, config)

    def check_database(self) -> int:
        """Comprueba la conexión real y devuelve cuántos embeddings BGE-M3 hay almacenados."""
        with self._connect() as conn:
            repository = self._repository(conn)
            ensure_encoder_matches(self.service, repository.config)
            return repository.count_embeddings()

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        with self._lock, self._connect() as conn:
            return search_selected(self.service, self._repository(conn), query, top_k=top_k)


def load_engine() -> RetrievalEngine:
    try:
        engine = RetrievalEngine.load()
    except Exception as exc:  # pesos ausentes, CUDA sin memoria, etc.
        raise ModelUnavailableError(f"No se pudo cargar {API_MODEL_ALIAS}: {exc}") from exc
    return engine
