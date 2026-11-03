"""Pipeline de ingestión: PDF aprobado -> fragmentos con página -> ALIA -> pgvector.

    validar archivo -> SHA-256 -> ¿duplicado? -> extraer páginas -> validar
    extracción -> limpiar -> segmentar -> generar embeddings
    -> [transacción: documento, versión, fragmentos, embeddings, ingesta,
        activar versión]

Los embeddings se generan antes de abrir la transacción de escritura: si el
modelo falla no se escribe nada, y si falla la escritura del fragmento 17 de
30 la transacción completa se revierte. Nunca queda una versión activa
incompleta.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
import statistics
import time
from typing import Any, Literal
from uuid import UUID

import numpy as np
import psycopg

from ..config import PROJECT_ROOT
from ..database import (
    DocumentRepository,
    FragmentRepository,
    IngestionRepository,
    ModelConfigRepository,
    VectorRepository,
    VersionRepository,
    connect,
)
from ..database.indexing import DocumentEncoder, ensure_encoder_matches
from .chunker import Chunk, ChunkingConfig, chunk_paragraphs
from .cleaner import CLEANER_VERSION, CleaningReport, clean_document
from .metadata import DocumentMetadata
from .pdf_extractor import (
    EXTRACTOR_VERSION,
    ExtractionProvenance,
    ExtractionResult,
    detect_extraction_provenance,
    extract_pdf,
    sha256_file,
    validate_pdf_file,
)
from .tokenizer import HFTokenCounter, TokenCounter


PIPELINE_VERSION = "2"
APPROVED_DIR = PROJECT_ROOT / "corpus" / "aprobados"
EMBEDDING_PROGRESS_BATCH = 32

Progress = Callable[[str], None]
IngestionStatus = Literal["indexado", "reindexado", "ya_indexado"]


class IngestionError(RuntimeError):
    """Base de los errores de ingestión que deben mostrarse al usuario."""


class NotApprovedError(IngestionError):
    """El PDF no está en corpus/aprobados/."""


class ExtractionRejectedError(IngestionError):
    """La extracción es inválida o el PDF requiere OCR/revisión."""


class DuplicateDocumentError(IngestionError):
    """El mismo archivo ya está registrado y no se pidió reindexar."""


class VersionConflictError(IngestionError):
    """La etiqueta de versión ya existe para el documento con otro archivo."""


@dataclass
class IngestionReport:
    status: IngestionStatus
    metadata: DocumentMetadata
    archivo: str
    sha256: str
    documento_id: UUID
    version_id: UUID
    estado: str
    model_id: str
    dimension: int
    device: str | None
    parametros: dict[str, Any]
    metricas: dict[str, Any]
    chunks: list[Chunk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def ensure_approved(pdf_path: Path, approved_dir: Path = APPROVED_DIR) -> None:
    resolved, approved = pdf_path.resolve(), approved_dir.resolve()
    if not resolved.is_relative_to(approved):
        raise NotApprovedError(
            f"{pdf_path} no está en {approved_dir}. Solo se indexan documentos aprobados; "
            "candidatos/ y rechazados/ nunca se indexan."
        )


def build_token_counter(encoder: DocumentEncoder) -> TokenCounter:
    """Tokenizer del modelo ya cargado; si no lo expone, se carga desde la caché."""
    tokenizer = getattr(encoder, "tokenizer", None)
    if tokenizer is not None and getattr(tokenizer, "is_fast", False):
        return HFTokenCounter(tokenizer, encoder.model_name)
    return HFTokenCounter.from_pretrained(encoder.model_name)


def ingestion_parameters(
    extraction_version: str,
    chunking: ChunkingConfig,
    counter: TokenCounter,
    config_nombre: str,
    model_id: str,
    dimension: int,
    normalized: bool,
    allow_ocr_warning: bool,
    index_pages: tuple[int, ...] = (),
    provenance: ExtractionProvenance | None = None,
) -> dict[str, Any]:
    """Todo lo que, si cambia, produce fragmentos o vectores distintos."""
    provenance = provenance or ExtractionProvenance("digital")
    return {
        "pipeline_version": PIPELINE_VERSION,
        "extractor": "pymupdf",
        "extractor_version": extraction_version,
        "cleaner_version": CLEANER_VERSION,
        "chunk_size_tokens": chunking.chunk_size_tokens,
        "chunk_overlap_tokens": chunking.chunk_overlap_tokens,
        "tokenizer": counter.name,
        "embedding_config": config_nombre,
        "embedding_model": model_id,
        "embedding_dimension": dimension,
        "normalization": normalized,
        "allow_ocr_warning": allow_ocr_warning,
        "paginas_indice_manual": list(index_pages),
        "origen_extraccion": provenance.origin,
        "ocr_provenance": _display_path(provenance.provenance_path) if provenance.provenance_path else None,
        "fuente_documental_original": _display_path(provenance.source_path) if provenance.source_path else None,
        "sha256_fuente_original": provenance.source_sha256,
    }


def ingest_document(
    pdf_path: str | Path,
    metadata: DocumentMetadata,
    embedding_service: DocumentEncoder,
    *,
    conn: psycopg.Connection | None = None,
    chunking: ChunkingConfig | None = None,
    token_counter: TokenCounter | None = None,
    config_name: str = "alia",
    approved_dir: Path | None = APPROVED_DIR,
    reindex: bool = False,
    allow_ocr_warning: bool = False,
    progress: Progress | None = None,
) -> IngestionReport:
    """Ingiere un PDF aprobado. Con `conn=None` abre y confirma su propia conexión.

    Si se pasa `conn`, el llamador decide cuándo confirmar (útil en pruebas).
    """
    if conn is None:
        with connect() as own_conn:
            return ingest_document(
                pdf_path, metadata, embedding_service, conn=own_conn, chunking=chunking,
                token_counter=token_counter, config_name=config_name, approved_dir=approved_dir,
                reindex=reindex, allow_ocr_warning=allow_ocr_warning, progress=progress,
            )

    say = progress or (lambda _message: None)
    started = time.perf_counter()
    path = validate_pdf_file(pdf_path)
    if approved_dir is not None:
        ensure_approved(path, approved_dir)
    chunking = chunking or ChunkingConfig.from_env()
    config = ModelConfigRepository(conn).get_active(config_name)
    ensure_encoder_matches(embedding_service, config)
    counter = token_counter or build_token_counter(embedding_service)
    sha256 = sha256_file(path)
    archivo = _display_path(path)
    provenance = detect_extraction_provenance(path)
    parametros = ingestion_parameters(
        EXTRACTOR_VERSION, chunking, counter, config.nombre, config.model_id,
        config.dimension, config.normalizado, allow_ocr_warning, metadata.paginas_indice,
        provenance,
    )
    versions = VersionRepository(conn)
    documents = DocumentRepository(conn)

    # --- Duplicados: se decide antes de cualquier trabajo costoso.
    existing = versions.find_by_hash(sha256)
    if existing is not None:
        existing_doc = documents.get(existing.documento_id)
        if (existing_doc.titulo, existing_doc.entidad, existing.version) != (
            metadata.titulo, metadata.entidad, metadata.version
        ):
            raise DuplicateDocumentError(
                f"Este archivo (SHA-256 {sha256[:12]}…) ya está registrado como "
                f"'{existing_doc.titulo}' ({existing_doc.entidad}), versión {existing.version}. "
                "No se registra el mismo archivo con otros metadatos."
            )
        last = IngestionRepository(conn).latest_for_version(existing.id, config.id)
        up_to_date = last is not None and last.parametros == parametros and existing.estado == "activa"
        if up_to_date and not reindex:
            say("El mismo archivo ya está indexado con la misma configuración: no se duplica.")
            return IngestionReport(
                status="ya_indexado", metadata=metadata, archivo=archivo, sha256=sha256,
                documento_id=existing.documento_id, version_id=existing.id, estado=existing.estado,
                model_id=config.model_id, dimension=config.dimension,
                device=getattr(embedding_service, "device", None),
                parametros=last.parametros, metricas=last.metricas,
            )
        if not reindex:
            raise DuplicateDocumentError(
                f"Este archivo ya está registrado (versión {existing.version}, estado {existing.estado}) "
                "pero con otra configuración de ingestión o sin ingesta completa. "
                "Use --reindex para regenerar sus fragmentos y embeddings."
            )
    else:
        documento = documents.find(metadata.titulo, metadata.entidad)
        if documento is not None and versions.find(documento.id, metadata.version) is not None:
            raise VersionConflictError(
                f"'{metadata.titulo}' ya tiene una versión '{metadata.version}' con otro archivo. "
                "Un archivo distinto requiere una etiqueta de versión nueva."
            )

    # --- Extracción y validación.
    say("Extrayendo PDF...")
    t0 = time.perf_counter()
    extraction = extract_pdf(path)
    t_extraction = time.perf_counter() - t0
    say(f"{extraction.page_count} páginas ({extraction.pages_with_text} con texto)")
    _validate_extraction(extraction, allow_ocr_warning)
    warnings = extraction.problems()

    # --- Limpieza y segmentación.
    say("Generando chunks...")
    t0 = time.perf_counter()
    paragraphs, cleaning = clean_document(extraction, index_pages=set(metadata.paginas_indice))
    chunks = chunk_paragraphs(paragraphs, counter, chunking)
    t_chunking = time.perf_counter() - t0
    if not chunks:
        raise ExtractionRejectedError("La limpieza no dejó texto que segmentar.")
    say(f"{len(chunks)} fragmentos")

    # --- Embeddings (fuera de la transacción de escritura).
    say("Generando embeddings...")
    t0 = time.perf_counter()
    vectors_list = []
    for start in range(0, len(chunks), EMBEDDING_PROGRESS_BATCH):
        batch = [chunk.text for chunk in chunks[start:start + EMBEDDING_PROGRESS_BATCH]]
        vectors_list.append(np.asarray(embedding_service.encode_documents(batch)))
        say(f"{min(start + EMBEDDING_PROGRESS_BATCH, len(chunks))} / {len(chunks)}")
    embeddings = np.concatenate(vectors_list)
    t_embeddings = time.perf_counter() - t0
    if embeddings.shape != (len(chunks), config.dimension):
        raise IngestionError(f"Forma de embeddings inesperada: {embeddings.shape}.")

    # --- Publicación atómica.
    say("Guardando...")
    t0 = time.perf_counter()
    vector_repo = VectorRepository(conn, config)
    fragments = FragmentRepository(conn)
    with conn.transaction():
        if existing is not None:
            version = existing
            removed = fragments.delete_for_version(version.id)
            say(f"Reindexando: {removed} fragmentos anteriores reemplazados")
        else:
            documento, _ = documents.get_or_create(metadata.titulo, metadata.entidad, metadata.url_origen)
            version = versions.create(
                documento.id, metadata.version, "borrador",
                vigencia=metadata.vigencia, ruta_archivo=archivo, hash_archivo=sha256,
            )
        for index, (chunk, vector) in enumerate(zip(chunks, embeddings, strict=True), start=1):
            fragment = fragments.create(
                version.id, chunk.order, chunk.text, chunk.section,
                pagina_inicio=chunk.page_start, pagina_fin=chunk.page_end, token_count=chunk.token_count,
                tipo_contenido=chunk.content_type,
            )
            vector_repo.save_embedding(fragment.id, vector)
            if index % EMBEDDING_PROGRESS_BATCH == 0 or index == len(chunks):
                say(f"{index} / {len(chunks)}")
        t_storage = time.perf_counter() - t0
        metricas = _metrics(
            extraction, cleaning, chunks, len(embeddings),
            t_extraction, t_chunking, t_embeddings, t_storage, time.perf_counter() - started,
        )
        IngestionRepository(conn).create(version.id, config.id, archivo, sha256, parametros, metricas)
        version = versions.activate(version.id)

    say("Indexación completada.")
    return IngestionReport(
        status="reindexado" if existing is not None else "indexado",
        metadata=metadata, archivo=archivo, sha256=sha256,
        documento_id=version.documento_id, version_id=version.id, estado=version.estado,
        model_id=config.model_id, dimension=config.dimension,
        device=getattr(embedding_service, "device", None),
        parametros=parametros, metricas=metricas, chunks=chunks, warnings=warnings,
    )


def _validate_extraction(extraction: ExtractionResult, allow_ocr_warning: bool) -> None:
    if not extraction.is_valid:
        raise ExtractionRejectedError(" ".join(extraction.problems()))
    if extraction.requires_ocr and not allow_ocr_warning:
        raise ExtractionRejectedError(
            " ".join(extraction.problems())
            + f" Páginas sin texto: {_page_list(extraction.empty_pages)}."
        )


def _metrics(
    extraction: ExtractionResult,
    cleaning: CleaningReport,
    chunks: list[Chunk],
    embeddings: int,
    t_extraction: float,
    t_chunking: float,
    t_embeddings: float,
    t_storage: float,
    t_total: float,
) -> dict[str, Any]:
    tokens = [chunk.token_count for chunk in chunks]
    return {
        "paginas": extraction.page_count,
        "paginas_con_texto": extraction.pages_with_text,
        "paginas_sin_texto": extraction.empty_pages,
        "paginas_posible_ocr": extraction.ocr_pages,
        "caracteres": extraction.total_chars,
        "chunks": len(chunks),
        "chunks_con_seccion": sum(chunk.section is not None for chunk in chunks),
        "chunks_multipagina": sum(chunk.page_end > chunk.page_start for chunk in chunks),
        "chunks_indice": sum(chunk.content_type == "indice" for chunk in chunks),
        "tokens_min": min(tokens),
        "tokens_max": max(tokens),
        "tokens_promedio": round(statistics.fmean(tokens), 1),
        "tokens_mediana": statistics.median(tokens),
        "tokens_total": sum(tokens),
        "embeddings": embeddings,
        "titulos_detectados": cleaning.headings,
        "origen_extraccion": cleaning.extraction_origin,
        "estrategia_titulos": cleaning.heading_strategy,
        "candidatos_tipograficos_ocr_descartados": cleaning.ocr_typography_only_rejected,
        "rotulos_repetidos_ocr_neutralizados": cleaning.ocr_repeated_heading_texts,
        "paginas_orientacion_ocr_no_lineal": cleaning.ocr_unreliable_orientation_pages,
        "patrones_eliminados": cleaning.removed_patterns,
        "detalle_patrones_eliminados": cleaning.removed_pattern_details,
        "paginas_indice": cleaning.index_pages,
        "lineas_eliminadas": cleaning.removed_lines,
        "uniones_guion": cleaning.hyphen_joins,
        "uniones_entre_paginas": cleaning.cross_page_joins,
        "tiempo_extraccion_s": round(t_extraction, 3),
        "tiempo_limpieza_chunking_s": round(t_chunking, 3),
        "tiempo_embeddings_s": round(t_embeddings, 3),
        "tiempo_guardado_s": round(t_storage, 3),
        "tiempo_total_s": round(t_total, 3),
    }


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return str(resolved.relative_to(PROJECT_ROOT)) if resolved.is_relative_to(PROJECT_ROOT) else path.name


def _page_list(pages: list[int], limit: int = 20) -> str:
    shown = ", ".join(map(str, pages[:limit]))
    return shown + (f" … (+{len(pages) - limit})" if len(pages) > limit else "")
