"""Pruebas rápidas de la API: sin pesos de Hugging Face ni PostgreSQL real."""

from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient
import numpy as np
import pytest

from src.api import dependencies
from src.api.app import create_app
from src.api.dependencies import ModelUnavailableError, RetrievalEngine
from src.database import DatabaseUnavailableError, SearchResult
from src.embeddings import EmbeddingService


def make_result(distance: float = 0.3, **overrides) -> SearchResult:
    values = dict(
        fragmento_id=uuid4(), orden=0, texto="Náuseas y vómitos", ubicacion="Náuseas y vómitos",
        documento_id=uuid4(), titulo="La quimioterapia y usted", entidad="National Cancer Institute (NCI)",
        version_id=uuid4(), version="2019", distancia=distance, pagina_inicio=65, pagina_fin=65,
    )
    values.update(overrides)
    return SearchResult(**values)


class FakeService:
    model_name = "BAAI/bge-m3"
    device = "cpu"
    dimension = 1024


class FakeEngine:
    def __init__(self, results=None, search_error=None, db_error=None) -> None:
        self.service = FakeService()
        self.model_name = FakeService.model_name
        self.results = results if results is not None else [make_result(0.30), make_result(0.35)]
        self.search_error = search_error
        self.db_error = db_error
        self.calls: list[tuple[str, int]] = []

    def check_database(self) -> int:
        if self.db_error:
            raise self.db_error
        return 419

    def search(self, query: str, top_k: int):
        self.calls.append((query, top_k))
        if self.search_error:
            raise self.search_error
        return self.results[:top_k]


@contextmanager
def client_for(engine_or_error):
    def factory():
        if isinstance(engine_or_error, Exception):
            raise engine_or_error
        return engine_or_error

    with TestClient(create_app(factory), raise_server_exceptions=False) as client:
        yield client


# --- /health -----------------------------------------------------------------

def test_health_ok_reports_model_and_database() -> None:
    with client_for(FakeEngine()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "database": "connected", "model": "BAAI/bge-m3",
        "retrieval": "pgvector_exact", "device": "cpu", "dimension": 1024, "embeddings": 419,
    }


def test_health_503_when_database_unavailable() -> None:
    engine = FakeEngine(db_error=DatabaseUnavailableError("sin conexión"))
    with client_for(engine) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
    assert response.json()["status"] == "error"


def test_health_503_when_model_did_not_load() -> None:
    with client_for(ModelUnavailableError("sin pesos")) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "error"


# --- /api/rag/search: request válido y formato ---------------------------------

def test_valid_search_returns_documented_format() -> None:
    engine = FakeEngine()
    with client_for(engine) as client:
        response = client.post("/api/rag/search",
                               json={"query": "  náuseas después de la quimioterapia ", "top_k": 2})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"query", "model", "top_k", "results"}
    assert body["query"] == "náuseas después de la quimioterapia"  # se recortan espacios
    assert body["model"] == "BAAI/bge-m3"
    assert body["top_k"] == 2
    assert engine.calls == [("náuseas después de la quimioterapia", 2)]
    first = body["results"][0]
    assert set(first) == {"rank", "fragment_id", "score", "distance", "text", "document", "entity",
                          "version", "section", "page_start", "page_end"}
    assert [r["rank"] for r in body["results"]] == [1, 2]
    assert first["distance"] == pytest.approx(0.30)
    assert first["score"] == pytest.approx(1 - first["distance"])
    assert first["document"] == "La quimioterapia y usted"
    assert first["section"] == "Náuseas y vómitos"
    assert (first["page_start"], first["page_end"]) == (65, 65)


def test_top_k_defaults_to_three() -> None:
    engine = FakeEngine()
    with client_for(engine) as client:
        assert client.post("/api/rag/search", json={"query": "fatiga"}).json()["top_k"] == 3
    assert engine.calls == [("fatiga", 3)]


# --- validaciones ----------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"query": "", "top_k": 3},
    {"query": "   \n\t", "top_k": 3},
    {"top_k": 3},
    {"query": None},
    {"query": "fatiga", "top_k": 0},
    {"query": "fatiga", "top_k": 11},
    {"query": "fatiga", "top_k": -1},
    {"query": "fatiga", "top_k": "muchos"},
    {"query": "x" * 2001},
    {"query": "fatiga", "modo": "hybrid"},  # campos desconocidos se rechazan
])
def test_invalid_requests_return_422_without_calling_retrieval(payload) -> None:
    engine = FakeEngine()
    with client_for(engine) as client:
        response = client.post("/api/rag/search", json=payload)
    assert response.status_code == 422
    assert engine.calls == []


@pytest.mark.parametrize("top_k", [1, 10])
def test_top_k_limits_are_inclusive(top_k: int) -> None:
    with client_for(FakeEngine(results=[make_result()] * 10)) as client:
        response = client.post("/api/rag/search", json={"query": "fatiga", "top_k": top_k})
    assert response.status_code == 200
    assert len(response.json()["results"]) == top_k


# --- errores -----------------------------------------------------------------

def test_search_503_when_database_unavailable() -> None:
    engine = FakeEngine(search_error=DatabaseUnavailableError("host=localhost password=secreto"))
    with client_for(engine) as client:
        response = client.post("/api/rag/search", json={"query": "fatiga"})
    assert response.status_code == 503
    assert response.json() == {"detail": "La base de datos vectorial no está disponible."}


def test_search_503_when_model_did_not_load() -> None:
    with client_for(ModelUnavailableError("sin pesos")) as client:
        response = client.post("/api/rag/search", json={"query": "fatiga"})
    assert response.status_code == 503
    assert "no está cargado" in response.json()["detail"]


def test_unexpected_retrieval_error_returns_500_without_stack_trace() -> None:
    engine = FakeEngine(search_error=RuntimeError("CUDA out of memory en /ruta/interna.py"))
    with client_for(engine) as client:
        response = client.post("/api/rag/search", json={"query": "fatiga"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Error interno del motor de recuperación."}
    assert "Traceback" not in response.text and "interna.py" not in response.text


# --- reutilización del retrieval existente ------------------------------------

class FakeSentenceTransformer:
    dimension = 4

    def __init__(self, model_id: str, device: str) -> None:
        self.encoded: list[list[str]] = []

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, texts, **kwargs):
        self.encoded.append(list(texts))
        return np.tile(np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32), (len(texts), 1))


class FakeConfig:
    model_id = "BAAI/bge-m3"
    dimension = 4


class FakeRepository:
    config = FakeConfig()

    def __init__(self) -> None:
        self.calls = []

    def search_similar(self, vector, top_k: int):
        self.calls.append((vector, top_k))
        return [make_result()]


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_engine_delegates_to_existing_search_selected(monkeypatch) -> None:
    calls = []

    def spy(service, repository, text, top_k=10):
        calls.append((service, repository, text, top_k))
        return ["resultado"]

    monkeypatch.setattr(dependencies, "search_selected", spy)
    service = EmbeddingService("bge-m3", device="cpu", model_loader=FakeSentenceTransformer)
    engine = RetrievalEngine(service, connect_fn=FakeConnection)
    repository = FakeRepository()
    monkeypatch.setattr(engine, "_repository", lambda conn: repository)

    assert engine.search("fatiga", 5) == ["resultado"]
    assert calls == [(service, repository, "fatiga", 5)]


def test_engine_encodes_query_once_with_loaded_model_and_queries_pgvector(monkeypatch) -> None:
    loads = []

    class CountingLoader(FakeSentenceTransformer):
        def __init__(self, *args, **kwargs) -> None:
            loads.append(1)
            super().__init__(*args, **kwargs)

    service = EmbeddingService("bge-m3", device="cpu", model_loader=CountingLoader)
    engine = RetrievalEngine(service, connect_fn=FakeConnection)
    repository = FakeRepository()
    monkeypatch.setattr(engine, "_repository", lambda conn: repository)

    engine.search("náuseas", 3)
    engine.search("diarrea", 2)

    assert loads == [1]  # el modelo se carga una sola vez y se reutiliza
    assert service._provider._model.encoded == [["náuseas"], ["diarrea"]]
    assert [top_k for _, top_k in repository.calls] == [3, 2]
    assert repository.calls[0][0].shape == (4,)


def test_engine_model_alias_is_bge_m3() -> None:
    assert dependencies.API_MODEL_ALIAS == "bge-m3"
