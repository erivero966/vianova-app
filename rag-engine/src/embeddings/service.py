"""Fachada pública: ningún consumidor necesita conocer SentenceTransformer."""

import logging
from typing import Any

import numpy as np
import torch

from ..config import EmbeddingSettings
from .base import ModelLoader
from .registry import EMBEDDING_MODELS, PROVIDER_CLASSES, available_models


logger = logging.getLogger(__name__)


def select_device(requested: str = "auto") -> str:
    requested = requested.strip().lower()
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError("device debe ser 'auto', 'cpu' o 'cuda'.")
    if requested == "cpu":
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if requested == "cuda":
        logger.warning("CUDA fue solicitado pero no está disponible; se usará CPU.")
    return "cpu"


class EmbeddingService:
    """Interfaz estable para los modelos de embeddings soportados."""

    def __init__(
        self,
        model: str | None = None,
        device: str | None = None,
        batch_size: int | None = None,
        *,
        model_loader: ModelLoader | None = None,
    ) -> None:
        settings = EmbeddingSettings.from_env()
        alias = (model or settings.model).strip().lower()
        if alias not in EMBEDDING_MODELS:
            valid = ", ".join(available_models())
            raise ValueError(f"Modelo '{alias}' no válido. Opciones disponibles: {valid}.")

        selected_batch_size = settings.batch_size if batch_size is None else batch_size
        if selected_batch_size < 1:
            raise ValueError("batch_size debe ser mayor que cero.")
        selected_device = select_device(device or settings.device)
        provider_type = PROVIDER_CLASSES[alias]
        self._alias = alias
        self._provider = provider_type(
            model_id=EMBEDDING_MODELS[alias],
            device=selected_device,
            batch_size=selected_batch_size,
            model_loader=model_loader,
        )
        logger.info(
            "Modelo seleccionado: %s\nModel ID: %s\nDispositivo: %s\nDimensión: %d",
            alias,
            self.model_name,
            self.device,
            self.dimension,
        )

    @property
    def dimension(self) -> int:
        return self._provider.dimension

    @property
    def model_name(self) -> str:
        return self._provider.model_id

    @property
    def device(self) -> str:
        return self._provider.device

    @property
    def tokenizer(self) -> Any | None:
        """Tokenizer del modelo cargado (para contar tokens al segmentar)."""
        return self._provider.tokenizer

    @property
    def max_seq_length(self) -> int | None:
        return self._provider.max_seq_length

    def encode_document(self, text: str) -> np.ndarray:
        return self._provider.encode_document(text)

    def encode_documents(self, texts: list[str] | tuple[str, ...]) -> np.ndarray:
        return self._provider.encode_documents(texts)

    def encode_query(self, query: str) -> np.ndarray:
        return self._provider.encode_query(query)
