"""Registro único de modelos y sus proveedores."""

from .base import PlainQueryProvider, PromptedQueryProvider


EMBEDDING_MODELS = {
    "alia": "SINAI/ALIA-MrBERT-es-biomedical-embeddings",
    "qwen3": "Qwen/Qwen3-Embedding-0.6B",
    "bge-m3": "BAAI/bge-m3",
}


class AliaProvider(PromptedQueryProvider):
    """ALIA usa el prompt `query` almacenado en su configuración."""


class QwenProvider(PromptedQueryProvider):
    """Qwen3 usa una instrucción para consultas y documentos sin instrucción."""


class BgeProvider(PlainQueryProvider):
    """BGE-M3 no requiere instrucciones para consultas."""


PROVIDER_CLASSES = {
    "alia": AliaProvider,
    "qwen3": QwenProvider,
    "bge-m3": BgeProvider,
}


def available_models() -> tuple[str, ...]:
    return tuple(EMBEDDING_MODELS)
