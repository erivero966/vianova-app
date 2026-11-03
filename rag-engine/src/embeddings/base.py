"""Contrato y adaptadores de modelos de embeddings."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np


ModelLoader = Callable[..., Any]


class BaseEmbeddingProvider(ABC):
    """Contrato común para codificar consultas y documentos."""

    def __init__(
        self,
        model_id: str,
        device: str,
        batch_size: int,
        model_loader: ModelLoader | None = None,
    ) -> None:
        if model_loader is None:
            from sentence_transformers import SentenceTransformer

            model_loader = SentenceTransformer
        self.model_id = model_id
        self.device = device
        self.batch_size = batch_size
        self._model = model_loader(model_id, device=device)
        get_dimension = getattr(self._model, "get_embedding_dimension", None)
        if get_dimension is None:  # Compatibilidad con sentence-transformers < 6.
            get_dimension = self._model.get_sentence_embedding_dimension
        dimension = get_dimension()
        if dimension is None:
            raise RuntimeError(f"El modelo {model_id} no informó su dimensión de salida.")
        self.dimension = int(dimension)
        # Opcionales: los backends simulados de las pruebas no los tienen.
        self.tokenizer = getattr(self._model, "tokenizer", None)
        self.max_seq_length = getattr(self._model, "max_seq_length", None)

    def encode_document(self, text: str) -> np.ndarray:
        return self.encode_documents([text])[0]

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        clean_texts = self._validate_texts(texts)
        return self._encode(clean_texts)

    @abstractmethod
    def encode_query(self, query: str) -> np.ndarray:
        """Codifica una consulta con el formato recomendado por el modelo."""

    def _encode(self, texts: list[str], **kwargs: Any) -> np.ndarray:
        vectors = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            **kwargs,
        )
        result = np.asarray(vectors, dtype=np.float32)
        if result.ndim != 2 or result.shape[1] != self.dimension:
            raise RuntimeError(
                f"Forma de embeddings inesperada: {result.shape}; "
                f"se esperaba (*, {self.dimension})."
            )
        return result

    @staticmethod
    def _validate_text(text: str, field: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{field} debe ser texto no vacío.")
        return text

    @classmethod
    def _validate_texts(cls, texts: Sequence[str]) -> list[str]:
        if isinstance(texts, (str, bytes)):
            raise TypeError("texts debe ser una secuencia de textos, no un único string.")
        values = list(texts)
        if not values:
            raise ValueError("texts no puede estar vacío.")
        return [cls._validate_text(text, "Cada documento") for text in values]


class PromptedQueryProvider(BaseEmbeddingProvider):
    """Proveedor para modelos cuyo model card exige el prompt `query`."""

    def encode_query(self, query: str) -> np.ndarray:
        clean_query = self._validate_text(query, "query")
        return self._encode([clean_query], prompt_name="query")[0]


class PlainQueryProvider(BaseEmbeddingProvider):
    """Proveedor para modelos que codifican consultas sin instrucciones."""

    def encode_query(self, query: str) -> np.ndarray:
        clean_query = self._validate_text(query, "query")
        return self._encode([clean_query])[0]
