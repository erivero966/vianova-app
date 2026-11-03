"""Prueba opt-in que descarga y ejecuta el modelo ALIA real."""

import os

import numpy as np
import pytest

from src.embeddings import EmbeddingService


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_MODEL_TESTS") != "1",
    reason="Defina RUN_MODEL_TESTS=1 para descargar y probar el modelo real.",
)
def test_real_alia_model() -> None:
    service = EmbeddingService("alia")
    documents = service.encode_documents(["Náuseas por quimioterapia", "Higiene de manos"])
    query = service.encode_query("Tengo náuseas después de la quimioterapia")
    assert service.dimension == 768
    assert documents.shape == (2, service.dimension)
    assert query.shape == (service.dimension,)
    assert np.linalg.norm(query) == pytest.approx(1.0, abs=1e-5)
