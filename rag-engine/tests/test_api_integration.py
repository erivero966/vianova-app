"""Integración real de la API: BGE-M3 (caché local de HF) + PostgreSQL `vianova_rag`.

Solo lectura: no genera embeddings de documentos ni modifica la base.
    pytest -q -m integration tests/test_api_integration.py
"""

from fastapi.testclient import TestClient
import pytest

from src.api.app import create_app
from src.api.dependencies import load_engine
from src.database import DatabaseUnavailableError, ModelConfigRepository, VectorRepository, connect


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    try:
        connect().close()
    except (DatabaseUnavailableError, ValueError) as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    with TestClient(create_app(load_engine)) as test_client:
        if test_client.app.state.engine is None:
            pytest.skip("BGE-M3 no pudo cargarse.")
        yield test_client


def test_health_connects_to_real_database(client) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["model"] == "BAAI/bge-m3"
    assert body["dimension"] == 1024
    assert body["embeddings"] > 0


def test_api_matches_direct_repository_search(client) -> None:
    query = "náuseas después de la quimioterapia"
    body = client.post("/api/rag/search", json={"query": query, "top_k": 5}).json()

    engine = client.app.state.engine
    with connect() as conn:
        repository = VectorRepository(conn, ModelConfigRepository(conn).get_active("bge-m3"))
        expected = repository.search_similar(engine.service.encode_query(query), top_k=5)

    assert [r["fragment_id"] for r in body["results"]] == [str(r.fragmento_id) for r in expected]
    assert [r["distance"] for r in body["results"]] == pytest.approx([r.distancia for r in expected], abs=1e-5)
    # Solo corpus normal: nada retirado (documento sintético) ni índices.
    assert all(r["entity"] == "National Cancer Institute (NCI)" for r in body["results"])
