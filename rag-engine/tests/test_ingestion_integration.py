"""Ingestión completa contra PostgreSQL real (`pytest -q -m integration`).

Usa la base aislada de pruebas; cada prueba se revierte al terminar. Salvo
la última, usan un codificador determinista y un contador por palabras para
no depender de la GPU; la última usa ALIA real (RUN_MODEL_TESTS=1).
"""

import os

import numpy as np
import pytest
from psycopg import errors

from conftest import unit_vector
from pdf_factory import CLINICAL_PAGES, build_pdf, build_scanned_pdf
from src.database import (
    DocumentRepository,
    FragmentRepository,
    IngestionRepository,
    SchemaDriftError,
    VectorRepository,
    VersionRepository,
    apply_schema,
)
from src.ingestion import (
    ChunkingConfig,
    DocumentMetadata,
    DuplicateDocumentError,
    ExtractionRejectedError,
    NotApprovedError,
    VersionConflictError,
    WhitespaceTokenCounter,
    ingest_document,
)
from test_vector_database import FakeEncoder


pytestmark = pytest.mark.integration

METADATA = DocumentMetadata(titulo="Guía sintética de cuidados", entidad="Entidad de prueba",
                            version="2025", url_origen=None, vigencia="vigente")
CHUNKING = ChunkingConfig(chunk_size_tokens=60, chunk_overlap_tokens=10)


class NanAtEncoder(FakeEncoder):
    """Devuelve un vector inválido en la posición indicada (falla al guardar)."""

    def __init__(self, config, bad_index: int) -> None:
        super().__init__(config)
        self.bad_index = bad_index
        self.seen = 0

    def encode_documents(self, texts):
        vectors = super().encode_documents(texts)
        for row in range(len(vectors)):
            if self.seen + row == self.bad_index:
                vectors[row] = np.nan
        self.seen += len(vectors)
        return vectors


@pytest.fixture
def approved(tmp_path):
    folder = tmp_path / "aprobados"
    folder.mkdir()
    return folder


@pytest.fixture
def clinical_pdf(approved):
    return build_pdf(approved / "guia.pdf", CLINICAL_PAGES, header="GUÍA SINTÉTICA DE CUIDADOS")


def ingest(db, pdf, alia_config, approved, *, encoder=None, metadata=METADATA, chunking=CHUNKING, **kwargs):
    return ingest_document(
        pdf, metadata, encoder or FakeEncoder(alia_config), conn=db, chunking=chunking,
        token_counter=WhitespaceTokenCounter(), approved_dir=approved, **kwargs,
    )


def test_schema_has_page_metadata_and_registered_migrations(db) -> None:
    columns = {name for (name,) in db.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'fragmento'")}
    assert {"pagina_inicio", "pagina_fin", "token_count", "ubicacion", "tipo_contenido"} <= columns
    applied = [name for (name,) in db.execute("SELECT archivo FROM schema_migracion ORDER BY archivo")]
    assert applied == ["001_extensions.sql", "002_schema.sql", "003_fragment_metadata.sql",
                       "004_content_type.sql"]


def test_modified_migration_is_detected(db) -> None:
    db.execute("UPDATE schema_migracion SET sha256 = 'otro' WHERE archivo = '002_schema.sql'")
    with pytest.raises(SchemaDriftError, match="002_schema.sql"):
        apply_schema(db)


def test_ingest_pdf_stores_pages_sections_tokens_and_embeddings(db, alia_config, approved, clinical_pdf) -> None:
    report = ingest(db, clinical_pdf, alia_config, approved)
    assert (report.status, report.estado) == ("indexado", "activa")
    assert len(report.sha256) == 64

    fragments = FragmentRepository(db).list_for_version(report.version_id)
    assert len(fragments) == report.metricas["chunks"] == len(report.chunks)
    assert all(f.pagina_inicio is not None and f.pagina_fin >= f.pagina_inicio for f in fragments)
    assert all(0 < f.token_count <= 60 for f in fragments)
    nausea = next(f for f in fragments if "antineoplásicos" in f.texto)
    assert (nausea.pagina_inicio, nausea.ubicacion) == (2, "Manejo de náuseas y vómitos")
    assert not any("Página" in f.texto or "GUÍA SINTÉTICA" in f.texto for f in fragments)

    vectors = VectorRepository(db, alia_config)
    assert all(vectors.get_embedding(f.id) is not None for f in fragments)
    version = VersionRepository(db).find(report.documento_id, "2025")
    assert (version.hash_archivo, version.ruta_archivo.endswith("guia.pdf")) == (report.sha256, True)

    ingesta = IngestionRepository(db).latest_for_version(report.version_id, alia_config.id)
    assert ingesta.parametros["chunk_size_tokens"] == 60
    assert ingesta.parametros["embedding_dimension"] == 768
    assert ingesta.metricas["paginas"] == 4
    assert set(ingesta.metricas["patrones_eliminados"]) == {"guía sintética de cuidados", "página # de #"}
    for key in ("tokens_min", "tokens_max", "tokens_promedio", "tiempo_extraccion_s",
                "tiempo_embeddings_s", "tiempo_total_s", "caracteres", "embeddings"):
        assert key in ingesta.metricas


def test_same_file_same_config_is_not_duplicated(db, alia_config, approved, clinical_pdf) -> None:
    first = ingest(db, clinical_pdf, alia_config, approved)
    vectors = VectorRepository(db, alia_config)
    count = vectors.count_embeddings()
    second = ingest(db, clinical_pdf, alia_config, approved)
    assert second.status == "ya_indexado"
    assert second.version_id == first.version_id
    assert vectors.count_embeddings() == count


def test_same_file_with_other_metadata_is_rejected(db, alia_config, approved, clinical_pdf) -> None:
    ingest(db, clinical_pdf, alia_config, approved)
    other = DocumentMetadata(titulo="Otro título", entidad="Otra", version="1")
    with pytest.raises(DuplicateDocumentError, match="ya está registrado"):
        ingest(db, clinical_pdf, alia_config, approved, metadata=other)


def test_changed_chunking_requires_reindex_and_replaces_fragments(db, alia_config, approved, clinical_pdf) -> None:
    first = ingest(db, clinical_pdf, alia_config, approved)
    other = ChunkingConfig(chunk_size_tokens=30, chunk_overlap_tokens=5)
    with pytest.raises(DuplicateDocumentError, match="--reindex"):
        ingest(db, clinical_pdf, alia_config, approved, chunking=other)
    vectors = VectorRepository(db, alia_config)
    before = vectors.count_embeddings() - first.metricas["chunks"]
    second = ingest(db, clinical_pdf, alia_config, approved, chunking=other, reindex=True)
    assert second.status == "reindexado" and second.version_id == first.version_id
    assert FragmentRepository(db).count_for_version(first.version_id) == second.metricas["chunks"]
    assert vectors.count_embeddings() == before + second.metricas["chunks"]


def test_version_label_cannot_be_reused_for_other_file(db, alia_config, approved, clinical_pdf) -> None:
    ingest(db, clinical_pdf, alia_config, approved)
    other_pdf = build_pdf(approved / "guia_mod.pdf", CLINICAL_PAGES[:2])
    with pytest.raises(VersionConflictError):
        ingest(db, other_pdf, alia_config, approved)


def test_new_version_retires_previous_one(db, alia_config, approved, clinical_pdf) -> None:
    v1 = ingest(db, clinical_pdf, alia_config, approved)
    v2_pdf = build_pdf(approved / "guia_2026.pdf", CLINICAL_PAGES[1:])
    v2 = ingest(db, v2_pdf, alia_config, approved,
                metadata=DocumentMetadata(METADATA.titulo, METADATA.entidad, "2026"))
    assert v2.documento_id == v1.documento_id
    assert VersionRepository(db).find(v1.documento_id, "2025").estado == "retirada"
    results = VectorRepository(db, alia_config).search_similar(unit_vector(1), top_k=50,
                                                               documento_id=v1.documento_id)
    assert {r.version for r in results} == {"2026"}


def test_failure_while_storing_rolls_back_everything(db, alia_config, approved, clinical_pdf) -> None:
    documents_before = db.execute("SELECT count(*) FROM documento").fetchone()[0]
    with pytest.raises(ValueError, match="NaN"):
        ingest(db, clinical_pdf, alia_config, approved, encoder=NanAtEncoder(alia_config, bad_index=3))
    assert DocumentRepository(db).find(METADATA.titulo, METADATA.entidad) is None
    assert db.execute("SELECT count(*) FROM documento").fetchone()[0] == documents_before
    assert db.execute("SELECT count(*) FROM version_documento WHERE estado = 'activa' "
                      "AND hash_archivo IS NOT NULL AND ruta_archivo LIKE %s", ("%guia.pdf",)).fetchone()[0] == 0
    # Tras el fallo se puede ingerir normalmente: no quedó nada a medias.
    assert ingest(db, clinical_pdf, alia_config, approved).status == "indexado"


def test_model_failure_writes_nothing(db, alia_config, approved, clinical_pdf) -> None:
    with pytest.raises(RuntimeError, match="Fallo simulado"):
        ingest(db, clinical_pdf, alia_config, approved, encoder=FakeEncoder(alia_config, fail_on_encode=True))
    assert DocumentRepository(db).find(METADATA.titulo, METADATA.entidad) is None


def test_scanned_pdf_is_rejected_without_writing(db, alia_config, approved) -> None:
    scanned = build_scanned_pdf(approved / "escaneado.pdf")
    with pytest.raises(ExtractionRejectedError, match="escaneado"):
        ingest(db, scanned, alia_config, approved)
    assert DocumentRepository(db).find(METADATA.titulo, METADATA.entidad) is None


def test_pdf_outside_approved_is_rejected(db, alia_config, tmp_path, approved) -> None:
    candidates = tmp_path / "candidatos"
    candidates.mkdir()
    pdf = build_pdf(candidates / "guia.pdf", CLINICAL_PAGES)
    with pytest.raises(NotApprovedError):
        ingest(db, pdf, alia_config, approved)


def test_search_filters_by_entity_and_document(db, alia_config, approved, clinical_pdf) -> None:
    report = ingest(db, clinical_pdf, alia_config, approved)
    vectors = VectorRepository(db, alia_config)
    query = unit_vector(5)
    assert vectors.search_similar(query, top_k=3, entidad="Entidad inexistente") == []
    by_entity = vectors.search_similar(query, top_k=3, entidad="Entidad de prueba")
    by_document = vectors.search_similar(query, top_k=3, documento_id=report.documento_id)
    assert by_entity and all(r.entidad == "Entidad de prueba" for r in by_entity)
    assert by_document and all(r.documento_id == report.documento_id for r in by_document)
    assert all(r.pagina_inicio is not None for r in by_document)


def test_fragment_page_constraints(db, alia_config) -> None:
    documento = DocumentRepository(db).create("Restricciones")
    version = VersionRepository(db).create(documento.id, "1")
    with pytest.raises(errors.CheckViolation), db.transaction():
        FragmentRepository(db).create(version.id, 1, "Texto", pagina_inicio=5, pagina_fin=3)
    with pytest.raises(errors.CheckViolation), db.transaction():
        FragmentRepository(db).create(version.id, 1, "Texto", pagina_inicio=0, pagina_fin=1)


@pytest.mark.skipif(os.getenv("RUN_MODEL_TESTS") != "1",
                    reason="Defina RUN_MODEL_TESTS=1 para ingerir con ALIA real.")
def test_real_alia_ingestion_and_top_k_from_pgvector(db, alia_config, approved, clinical_pdf) -> None:
    from src.embeddings import EmbeddingService

    service = EmbeddingService("alia")
    report = ingest_document(clinical_pdf, METADATA, service, conn=db,
                             chunking=ChunkingConfig(450, 75), approved_dir=approved)
    assert report.parametros["tokenizer"] == "SINAI/ALIA-MrBERT-es-biomedical-embeddings"
    results = VectorRepository(db, alia_config).search_similar(
        service.encode_query("náuseas después de la quimioterapia"), top_k=3,
        documento_id=report.documento_id,
    )
    assert results[0].pagina_inicio == 2
    assert results[0].ubicacion == "Manejo de náuseas y vómitos"
    assert "antineoplásicos" in results[0].texto
