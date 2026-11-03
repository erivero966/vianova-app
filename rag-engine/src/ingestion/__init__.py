"""Ingestión documental: PDF -> páginas -> limpieza -> chunks -> embeddings -> pgvector."""

from .chunker import Chunk, ChunkingConfig, chunk_paragraphs
from .cleaner import CleaningReport, Paragraph, clean_document
from .metadata import DocumentMetadata, MetadataError, default_metadata_path
from .pdf_extractor import (
    ExtractionProvenance,
    ExtractionResult,
    InvalidPdfError,
    detect_extraction_provenance,
    extract_pdf,
    sha256_file,
)
from .pipeline import (
    APPROVED_DIR,
    DuplicateDocumentError,
    ExtractionRejectedError,
    IngestionError,
    IngestionReport,
    NotApprovedError,
    VersionConflictError,
    ingest_document,
)
from .tokenizer import HFTokenCounter, TokenCounter, WhitespaceTokenCounter

__all__ = [
    "APPROVED_DIR",
    "Chunk",
    "ChunkingConfig",
    "CleaningReport",
    "DocumentMetadata",
    "DuplicateDocumentError",
    "ExtractionRejectedError",
    "ExtractionResult",
    "ExtractionProvenance",
    "HFTokenCounter",
    "IngestionError",
    "IngestionReport",
    "InvalidPdfError",
    "MetadataError",
    "NotApprovedError",
    "Paragraph",
    "TokenCounter",
    "VersionConflictError",
    "WhitespaceTokenCounter",
    "chunk_paragraphs",
    "clean_document",
    "default_metadata_path",
    "extract_pdf",
    "detect_extraction_provenance",
    "ingest_document",
    "sha256_file",
]
