"""API HTTP del motor RAG (solo retrieval dense, sin LLM ni reranking).

Arranque:
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000
Swagger: http://localhost:8000/docs
"""

from collections.abc import Callable
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg

from ..config import DatabaseSettings
from ..database import DatabaseUnavailableError, VectorExtensionMissingError
from .dependencies import API_MODEL_ALIAS, RETRIEVAL_MODE, ModelUnavailableError, RetrievalEngine, load_engine
from .schemas import ErrorResponse, HealthResponse, SearchRequest, SearchResponse, SearchResultItem


logger = logging.getLogger("rag_api")

EXPECTED_MODEL_ID = "BAAI/bge-m3"
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

# Errores de base que se traducen a 503 sin exponer detalles internos.
DATABASE_ERRORS = (DatabaseUnavailableError, VectorExtensionMissingError, psycopg.Error, LookupError)


class ServiceUnavailable(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


def cors_origins() -> list[str]:
    raw = os.getenv("API_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _database_label() -> str:
    try:
        s = DatabaseSettings.from_env()
    except ValueError as exc:
        return f"(configuración inválida: {exc})"
    return f"{s.host}:{s.port}/{s.dbname}"


def create_app(engine_factory: Callable[[], RetrievalEngine] = load_engine) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = None
        try:
            app.state.engine = engine_factory()
        except ModelUnavailableError:
            logger.exception("El modelo no cargó; /api/rag/search responderá 503.")
        else:
            logger.info("Modelo: %s", app.state.engine.model_name)
            logger.info("Device: %s", app.state.engine.service.device)
            logger.info("Dimensión: %d", app.state.engine.service.dimension)
        logger.info("Database: %s", _database_label())
        if app.state.engine is not None:
            try:
                count = app.state.engine.check_database()
                logger.info("Database: conectada | embeddings BGE-M3: %d", count)
            except Exception as exc:  # el servidor arranca igual; /health lo reporta
                logger.warning("Database: no disponible al iniciar (%s)", exc)
        yield
        app.state.engine = None

    app = FastAPI(
        title="Vianova RAG Engine",
        description="Recuperación semántica dense (BGE-M3 + pgvector, búsqueda exacta) "
                    "sobre el corpus NCI. No genera respuestas: devuelve fragmentos con su fuente.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(ServiceUnavailable)
    async def _unavailable(_: Request, exc: ServiceUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no controlado en la API")
        return JSONResponse(status_code=500, content={"detail": "Error interno del motor de recuperación."})

    def _engine(request: Request) -> RetrievalEngine:
        engine = request.app.state.engine
        if engine is None:
            raise ServiceUnavailable(f"El modelo {EXPECTED_MODEL_ID} no está cargado.")
        return engine

    @app.get("/health", response_model=HealthResponse,
             responses={503: {"model": HealthResponse}})
    def health(request: Request):
        engine = request.app.state.engine
        body = {"status": "ok", "database": "connected", "model": EXPECTED_MODEL_ID,
                "retrieval": RETRIEVAL_MODE}
        if engine is None:
            body.update(status="error", database="unknown", model=f"{EXPECTED_MODEL_ID} (no cargado)")
            return JSONResponse(status_code=503, content=body)
        body.update(model=engine.model_name, device=engine.service.device,
                    dimension=engine.service.dimension)
        try:
            body["embeddings"] = engine.check_database()
        except DATABASE_ERRORS as exc:
            logger.warning("Health: base no disponible (%s)", exc)
            body.update(status="error", database="unavailable")
            return JSONResponse(status_code=503, content=body)
        return body

    @app.post("/api/rag/search", response_model=SearchResponse,
              responses={422: {"description": "query vacía o top_k fuera de 1-10"},
                         503: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
    def search(payload: SearchRequest, request: Request) -> SearchResponse:
        engine = _engine(request)
        try:
            results = engine.search(payload.query, payload.top_k)
        except DATABASE_ERRORS as exc:
            logger.warning("Search: base no disponible (%s)", exc)
            raise ServiceUnavailable("La base de datos vectorial no está disponible.") from exc
        except ValueError as exc:  # p. ej. encoder/configuración incompatibles
            logger.error("Search: retrieval inválido (%s)", exc)
            raise ServiceUnavailable("El motor de recuperación no está disponible.") from exc
        return SearchResponse(
            query=payload.query,
            model=engine.model_name,
            top_k=payload.top_k,
            results=[
                SearchResultItem(
                    rank=rank,
                    fragment_id=str(r.fragmento_id),
                    score=round(r.similitud, 6),
                    distance=round(r.distancia, 6),
                    text=r.texto,
                    document=r.titulo,
                    entity=r.entidad,
                    version=r.version,
                    section=r.ubicacion,
                    page_start=r.pagina_inicio,
                    page_end=r.pagina_fin,
                )
                for rank, r in enumerate(results, start=1)
            ],
        )

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for _noisy in ("httpx", "httpx2", "huggingface_hub"):  # cada petición HEAD al Hub no aporta
    logging.getLogger(_noisy).setLevel(logging.WARNING)
app = create_app()
