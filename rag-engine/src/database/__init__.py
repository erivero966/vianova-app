"""Capa de persistencia: PostgreSQL + pgvector. El resto del RAG no escribe SQL."""

from .connection import (
    DatabaseUnavailableError,
    SchemaDriftError,
    VectorExtensionMissingError,
    apply_schema,
    connect,
)
from .indexing import FragmentInput, IndexReport, index_document
from .repositories import (
    ConfiguracionModelo,
    DocumentRepository,
    Documento,
    FragmentRepository,
    Fragmento,
    Ingesta,
    IngestionRepository,
    ModelConfigRepository,
    VersionDocumento,
    VersionRepository,
)
from .vector_repository import SearchResult, VectorRepository

__all__ = [
    "ConfiguracionModelo",
    "DatabaseUnavailableError",
    "DocumentRepository",
    "Documento",
    "FragmentInput",
    "FragmentRepository",
    "Fragmento",
    "IndexReport",
    "Ingesta",
    "IngestionRepository",
    "ModelConfigRepository",
    "SchemaDriftError",
    "SearchResult",
    "VectorExtensionMissingError",
    "VectorRepository",
    "VersionDocumento",
    "VersionRepository",
    "apply_schema",
    "connect",
    "index_document",
]
