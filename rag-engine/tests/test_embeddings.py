"""Pruebas rápidas del contrato sin descargar pesos desde Hugging Face."""

import numpy as np
import pytest

from src.embeddings import EmbeddingService
from src.embeddings.registry import EMBEDDING_MODELS


class FakeSentenceTransformer:
    dimension = 4

    def __init__(self, model_id: str, device: str) -> None:
        self.model_id = model_id
        self.device = device
        self.calls: list[dict] = []

    def get_sentence_embedding_dimension(self) -> int:
        return self.dimension

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, texts: list[str], **kwargs) -> np.ndarray:
        self.calls.append(kwargs)
        rows = []
        for index, text in enumerate(texts):
            vector = np.array([len(text), index + 1, 2.0, 3.0], dtype=np.float32)
            vector /= np.linalg.norm(vector)
            rows.append(vector)
        return np.stack(rows)


def make_service(model: str = "alia", device: str = "cpu") -> EmbeddingService:
    return EmbeddingService(model, device=device, model_loader=FakeSentenceTransformer)


def test_alia_loads_and_reports_real_dimension() -> None:
    service = make_service()
    vector = service.encode_document("Documento biomédico")
    assert service.model_name == EMBEDDING_MODELS["alia"]
    assert service.dimension == vector.shape[0] == FakeSentenceTransformer.dimension


def test_result_is_nonempty_numpy_array_and_normalized() -> None:
    vector = make_service().encode_query("Consulta clínica")
    assert isinstance(vector, np.ndarray)
    assert vector.size > 0
    assert np.linalg.norm(vector) == pytest.approx(1.0, abs=1e-6)


def test_documents_are_encoded_in_batch() -> None:
    vectors = make_service().encode_documents(["Documento uno", "Documento dos"])
    assert vectors.shape == (2, FakeSentenceTransformer.dimension)
    assert np.linalg.norm(vectors, axis=1) == pytest.approx([1.0, 1.0], abs=1e-6)


@pytest.mark.parametrize("alias", ["alia", "qwen3"])
def test_prompted_models_distinguish_query_from_documents(alias: str) -> None:
    service = make_service(alias)
    service.encode_query("Una consulta")
    assert service._provider._model.calls[-1]["prompt_name"] == "query"
    service.encode_documents(["Un documento"])
    assert "prompt_name" not in service._provider._model.calls[-1]


def test_bge_uses_no_query_instruction() -> None:
    service = make_service("bge-m3")
    service.encode_query("Una consulta")
    assert "prompt_name" not in service._provider._model.calls[-1]


def test_invalid_model_has_clear_error() -> None:
    with pytest.raises(ValueError, match="Modelo 'inexistente' no válido"):
        make_service("inexistente")


def test_auto_uses_cpu_when_cuda_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr("src.embeddings.service.torch.cuda.is_available", lambda: False)
    assert make_service(device="auto").device == "cpu"


def test_auto_uses_cuda_when_available(monkeypatch) -> None:
    monkeypatch.setattr("src.embeddings.service.torch.cuda.is_available", lambda: True)
    assert make_service(device="auto").device == "cuda"


def test_explicit_cuda_falls_back_to_cpu(monkeypatch) -> None:
    monkeypatch.setattr("src.embeddings.service.torch.cuda.is_available", lambda: False)
    assert make_service(device="cuda").device == "cpu"


def test_empty_input_is_rejected() -> None:
    service = make_service()
    with pytest.raises(ValueError, match="no puede estar vacío"):
        service.encode_documents([])
