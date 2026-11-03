"""Pruebas de la capa PostgreSQL + pgvector.

Las pruebas sin marcador validan reglas que fallan antes de llegar a SQL y
corren con `pytest -q`. Las marcadas `integration` requieren el contenedor
(`docker compose up -d`) y se ejecutan con `pytest -q -m integration`.
"""

from datetime import datetime, timezone
import os
import subprocess
import sys
from uuid import uuid4

import numpy as np
from psycopg import errors
import pytest

from conftest import unit_vector
from src.config import PROJECT_ROOT, DatabaseSettings
from src.database import (
    ConfiguracionModelo,
    DocumentRepository,
    FragmentInput,
    FragmentRepository,
    SearchResult,
    VectorRepository,
    VersionRepository,
    connect,
    index_document,
)
from src.database.indexing import content_hash
from src.embeddings.registry import EMBEDDING_MODELS
from src.sample_corpus import SAMPLE_QUERY, SAMPLE_TEXTS


def make_config(**overrides) -> ConfiguracionModelo:
    values = dict(
        id=uuid4(),
        nombre="alia",
        model_id=EMBEDDING_MODELS["alia"],
        dimension=768,
        normalizado=True,
        activo=True,
        parametros={"tabla_embeddings": "embedding_fragmento_alia"},
        creado_en=datetime.now(timezone.utc),
    )
    values.update(overrides)
    return ConfiguracionModelo(**values)


class FakeEncoder:
    """Codificador determinista de 768d: evita cargar ALIA en pruebas de BD."""

    def __init__(self, config: ConfiguracionModelo, fail_on_encode: bool = False) -> None:
        self.model_name = config.model_id
        self.dimension = config.dimension
        self.fail_on_encode = fail_on_encode

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        if self.fail_on_encode:
            raise RuntimeError("Fallo simulado del modelo")
        return np.stack([unit_vector(sum(map(ord, text))) for text in texts])


# ---------------------------------------------------------------- unitarias


def test_database_settings_require_password(monkeypatch) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        DatabaseSettings.from_env()


def test_database_settings_hide_password_in_repr(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "secreto-local")
    assert "secreto-local" not in repr(DatabaseSettings.from_env())


def test_vector_repository_rejects_unregistered_table() -> None:
    config = make_config(parametros={"tabla_embeddings": "documento; DROP TABLE documento"})
    with pytest.raises(ValueError, match="no registrada"):
        VectorRepository(None, config)


def test_vector_repository_rejects_mixed_dimensions() -> None:
    # Un modelo de 1024d no puede apuntar a la tabla VECTOR(768) de ALIA.
    with pytest.raises(ValueError, match="VECTOR\\(768\\)"):
        VectorRepository(None, make_config(nombre="bge-m3", dimension=1024))


@pytest.mark.parametrize(
    "vector, message",
    [
        (np.ones(384, dtype=np.float32) / np.sqrt(384), "forma"),
        (np.full(768, np.nan, dtype=np.float32), "NaN"),
        (np.ones(768, dtype=np.float32), "normalizados"),
    ],
)
def test_invalid_vectors_are_rejected_before_sql(vector, message) -> None:
    repo = VectorRepository(None, make_config())  # sin conexión: no debe usarse
    with pytest.raises(ValueError, match=message):
        repo.save_embedding(uuid4(), vector)
    with pytest.raises(ValueError, match=message):
        repo.search_similar(vector)


def test_top_k_must_be_positive() -> None:
    with pytest.raises(ValueError, match="top_k"):
        VectorRepository(None, make_config()).search_similar(unit_vector(1), top_k=0)


def test_similarity_is_one_minus_cosine_distance() -> None:
    result = SearchResult(uuid4(), 1, "t", None, uuid4(), "d", None, uuid4(), "1.0", distancia=0.25)
    assert result.similitud == pytest.approx(0.75)


def test_index_rejects_encoder_from_other_model() -> None:
    config = make_config()
    encoder = FakeEncoder(make_config(model_id="otro/modelo"))
    with pytest.raises(ValueError, match="no coincide"):
        index_document(
            None, encoder, config, titulo="t", entidad=None, version="1", fragments=[FragmentInput("x")]
        )


def test_content_hash_is_deterministic() -> None:
    fragments = [FragmentInput(text) for text in SAMPLE_TEXTS]
    assert content_hash(fragments) == content_hash(list(fragments))
    assert content_hash(fragments) != content_hash(fragments[:2])


# ------------------------------------------------------------- integración

integration = pytest.mark.integration


def create_active_version(db, titulo: str = "Documento de prueba"):
    documento = DocumentRepository(db).create(titulo, "Entidad de prueba")
    versions = VersionRepository(db)
    version = versions.activate(versions.create(documento.id, "1.0").id)
    return documento, version


def index_three_fragments(db, config):
    """Tres fragmentos con vectores controlados: el primero será el más cercano."""
    _, version = create_active_version(db)
    fragments = FragmentRepository(db)
    vectors = VectorRepository(db, config)
    rows = []
    for orden, seed in enumerate((10, 20, 30), start=1):
        fragment = fragments.create(version.id, orden, f"Fragmento {orden}", f"p. {orden}")
        vectors.save_embedding(fragment.id, unit_vector(seed))
        rows.append(fragment)
    return version, rows


@integration
def test_postgresql_connection_and_version(db) -> None:
    assert db.execute("SELECT 1").fetchone()[0] == 1
    assert int(db.execute("SHOW server_version_num").fetchone()[0]) >= 160000


@integration
def test_vector_extension_is_installed(db) -> None:
    row = db.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    assert row is not None


@integration
def test_create_document(db) -> None:
    repo = DocumentRepository(db)
    created = repo.create("Guía de cuidados", "Entidad de prueba", "https://example.org/guia")
    assert repo.get(created.id) == created
    assert repo.get_or_create("Guía de cuidados", "Entidad de prueba") == (created, False)


@integration
def test_create_version_and_validate_state(db) -> None:
    documento = DocumentRepository(db).create("Documento con versiones")
    versions = VersionRepository(db)
    version = versions.create(documento.id, "2024.1", vigencia="2024-2026", hash_archivo="abc")
    assert (version.documento_id, version.estado) == (documento.id, "borrador")
    with pytest.raises(ValueError, match="no válido"):
        versions.create(documento.id, "x", estado="publicada")
    with pytest.raises(errors.CheckViolation), db.transaction():
        db.execute(
            "INSERT INTO version_documento (documento_id, version, estado) VALUES (%s, 'y', 'publicada')",
            (documento.id,),
        )


@integration
def test_single_active_version_per_document(db) -> None:
    documento = DocumentRepository(db).create("Documento versionado")
    versions = VersionRepository(db)
    v1 = versions.activate(versions.create(documento.id, "1").id)
    v2 = versions.activate(versions.create(documento.id, "2").id)
    assert v2.estado == "activa"
    assert versions.find(documento.id, "1").estado == "retirada"
    with pytest.raises(errors.UniqueViolation), db.transaction():
        db.execute("UPDATE version_documento SET estado = 'activa' WHERE id = %s", (v1.id,))


@integration
def test_create_fragment(db) -> None:
    _, version = create_active_version(db)
    repo = FragmentRepository(db)
    fragment = repo.create(version.id, 1, "Texto del fragmento", "Sección 1")
    assert repo.list_for_version(version.id) == [fragment]


@integration
def test_embedding_is_stored_as_pgvector_768(db, alia_config) -> None:
    column_type = db.execute(
        """
        SELECT format_type(atttypid, atttypmod) FROM pg_attribute
        WHERE attrelid = 'embedding_fragmento_alia'::regclass AND attname = 'embedding'
        """
    ).fetchone()[0]
    assert column_type == "vector(768)"

    _, version = create_active_version(db)
    fragment = FragmentRepository(db).create(version.id, 1, "Texto")
    repo = VectorRepository(db, alia_config)
    assert repo.save_embedding(fragment.id, unit_vector(1)) is True
    stored_type, dims = db.execute(
        "SELECT pg_typeof(embedding)::text, vector_dims(embedding) FROM embedding_fragmento_alia "
        "WHERE fragmento_id = %s",
        (fragment.id,),
    ).fetchone()
    assert (stored_type, dims) == ("vector", 768)


@integration
def test_postgres_rejects_vectors_of_other_dimension(db, alia_config) -> None:
    _, version = create_active_version(db)
    fragment = FragmentRepository(db).create(version.id, 1, "Texto")
    with pytest.raises(errors.DataException), db.transaction():
        db.execute(
            "INSERT INTO embedding_fragmento_alia (fragmento_id, configuracion_id, embedding) "
            "VALUES (%s, %s, %s)",
            (fragment.id, alia_config.id, unit_vector(1, dimension=1024)),
        )


@integration
def test_embedding_round_trip(db, alia_config) -> None:
    _, version = create_active_version(db)
    fragment = FragmentRepository(db).create(version.id, 1, "Texto")
    repo = VectorRepository(db, alia_config)
    original = unit_vector(7)
    repo.save_embedding(fragment.id, original)
    recovered = repo.get_embedding(fragment.id)
    assert recovered.shape == (768,)
    np.testing.assert_allclose(recovered, original, rtol=0, atol=1e-7)
    assert repo.get_embedding(uuid4()) is None


@integration
def test_search_returns_top_k_ordered_by_cosine_distance(db, alia_config) -> None:
    _, rows = index_three_fragments(db, alia_config)
    repo = VectorRepository(db, alia_config)
    results = repo.search_similar(unit_vector(20), top_k=2)
    assert len(results) == 2
    assert results[0].fragmento_id == rows[1].id
    assert results[0].distancia == pytest.approx(0.0, abs=1e-6)
    assert results[0].distancia <= results[1].distancia
    assert len(repo.search_similar(unit_vector(20), top_k=10)) == 3


@integration
def test_index_fragments_are_kept_but_excluded_from_normal_search(db, alia_config) -> None:
    _, version = create_active_version(db, "Documento con índice")
    fragments = FragmentRepository(db)
    index = fragments.create(version.id, 1, "Índice: infección 18", tipo_contenido="indice")
    content = fragments.create(version.id, 2, "Contenido explicativo sobre infección")
    vectors = VectorRepository(db, alia_config)
    query = unit_vector(71)
    vectors.save_embedding(index.id, query)
    vectors.save_embedding(content.id, unit_vector(72))

    assert vectors.search_similar(query, top_k=1)[0].fragmento_id == content.id
    diagnostic = vectors.search_similar(query, top_k=1, incluir_indice=True)
    assert diagnostic[0].fragmento_id == index.id
    assert diagnostic[0].tipo_contenido == "indice"


@integration
def test_search_top1_is_nearest_fragment(db, alia_config) -> None:
    _, rows = index_three_fragments(db, alia_config)
    query = unit_vector(10) + 0.3 * unit_vector(99)
    query /= np.linalg.norm(query)
    top = VectorRepository(db, alia_config).search_similar(query, top_k=3)
    assert top[0].fragmento_id == rows[0].id
    assert top[0].similitud > top[1].similitud
    # La similitud calculada por pgvector coincide con el producto punto (vectores normalizados).
    assert top[0].similitud == pytest.approx(float(query @ unit_vector(10)), abs=1e-5)


@integration
def test_search_ignores_inactive_versions(db, alia_config) -> None:
    version, rows = index_three_fragments(db, alia_config)
    db.execute("UPDATE version_documento SET estado = 'retirada' WHERE id = %s", (version.id,))
    repo = VectorRepository(db, alia_config)
    assert repo.search_similar(unit_vector(10)) == []
    assert repo.search_similar(unit_vector(10), solo_activas=False)[0].fragmento_id == rows[0].id


@integration
def test_search_plan_is_exact_without_ann_index(db, alia_config) -> None:
    index_three_fragments(db, alia_config)
    plan = "\n".join(VectorRepository(db, alia_config).explain_search(unit_vector(10)))
    # PostgreSQL calcula la distancia para cada candidato y ordena (Sort): búsqueda exacta.
    assert "Sort Key: ((e.embedding <=> " in plan
    assert "hnsw" not in plan.lower() and "ivfflat" not in plan.lower()
    indexes = db.execute(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'embedding_fragmento_alia'"
    ).fetchall()
    assert not any("hnsw" in d.lower() or "ivfflat" in d.lower() for (d,) in indexes)


@integration
def test_duplicates_are_avoided(db, alia_config) -> None:
    _, version = create_active_version(db)
    fragments = FragmentRepository(db)
    fragment, status = fragments.upsert(version.id, 1, "Texto")
    assert status == "creado"
    assert fragments.upsert(version.id, 1, "Texto") == (fragment, "sin_cambios")
    assert fragments.upsert(version.id, 1, "Texto nuevo")[1] == "actualizado"
    with pytest.raises(errors.UniqueViolation), db.transaction():
        fragments.create(version.id, 1, "Otro texto con el mismo orden")

    repo = VectorRepository(db, alia_config)
    before = repo.count_embeddings()
    assert repo.save_embedding(fragment.id, unit_vector(1)) is True
    assert repo.save_embedding(fragment.id, unit_vector(2)) is False
    assert repo.count_embeddings() == before + 1
    np.testing.assert_allclose(repo.get_embedding(fragment.id), unit_vector(2), atol=1e-7)


@integration
def test_index_document_is_idempotent(db, alia_config) -> None:
    encoder = FakeEncoder(alia_config)
    fragments = [FragmentInput(text, f"Fragmento {i}") for i, text in enumerate(SAMPLE_TEXTS, 1)]
    kwargs = dict(titulo="Idempotencia", entidad="Prueba", version="1.0", fragments=fragments)
    repo = VectorRepository(db, alia_config)
    before = repo.count_embeddings()

    first = index_document(db, encoder, alia_config, **kwargs)
    second = index_document(db, encoder, alia_config, **kwargs)

    assert (first.documento_creado, first.fragmentos_creados, first.embeddings_nuevos) == (True, 3, 3)
    assert (second.documento_creado, second.version_creada) == (False, False)
    assert (second.fragmentos_sin_cambios, second.embeddings_nuevos, second.embeddings_reemplazados) == (3, 0, 3)
    assert second.version_id == first.version_id
    assert repo.count_embeddings() == before + 3
    assert VersionRepository(db).find(first.documento_id, "1.0").estado == "activa"


@integration
def test_foreign_keys_are_enforced(db, alia_config) -> None:
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        FragmentRepository(db).create(uuid4(), 1, "Fragmento huérfano")
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        VectorRepository(db, alia_config).save_embedding(uuid4(), unit_vector(1))

    documento, version = create_active_version(db)
    fragment = FragmentRepository(db).create(version.id, 1, "Texto")
    repo = VectorRepository(db, alia_config)
    repo.save_embedding(fragment.id, unit_vector(1))
    # Un documento con versiones no se borra en cascada (trazabilidad).
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        db.execute("DELETE FROM documento WHERE id = %s", (documento.id,))
    # Borrar el fragmento elimina sus embeddings (ON DELETE CASCADE).
    db.execute("DELETE FROM fragmento WHERE id = %s", (fragment.id,))
    assert repo.get_embedding(fragment.id) is None


@integration
def test_delete_embeddings_for_fragment(db, alia_config) -> None:
    _, rows = index_three_fragments(db, alia_config)
    repo = VectorRepository(db, alia_config)
    before = repo.count_embeddings()
    assert repo.delete_embeddings_for_fragment(rows[0].id) == 1
    assert repo.delete_embeddings_for_fragment(rows[0].id) == 0
    assert repo.count_embeddings() == before - 1


@integration
def test_rollback_on_error_leaves_nothing_behind(db, alia_config) -> None:
    documents = DocumentRepository(db)
    with pytest.raises(errors.ForeignKeyViolation), db.transaction():
        documents.create("Documento que no debe persistir")
        FragmentRepository(db).create(uuid4(), 1, "FK inválida")
    assert documents.find("Documento que no debe persistir", None) is None

    fragments = [FragmentInput("Texto A"), FragmentInput("Texto B")]
    with pytest.raises(RuntimeError, match="Fallo simulado"):
        index_document(
            db, FakeEncoder(alia_config, fail_on_encode=True), alia_config,
            titulo="Indexación fallida", entidad="Prueba", version="1", fragments=fragments,
        )
    assert documents.find("Indexación fallida", "Prueba") is None


@integration
def test_embeddings_persist_across_processes(test_db_settings, alia_config) -> None:
    """Escribe y confirma en este proceso; otro proceso Python busca y lo encuentra."""
    marker = f"Persistencia {uuid4()}"
    with connect(test_db_settings) as conn:
        _, version = create_active_version(conn, titulo=marker)
        fragment = FragmentRepository(conn).create(version.id, 1, marker)
        VectorRepository(conn, alia_config).save_embedding(fragment.id, unit_vector(4242))
    try:
        child = """
from conftest import unit_vector
from src.database import ModelConfigRepository, VectorRepository, connect
with connect() as conn:
    repo = VectorRepository(conn, ModelConfigRepository(conn).get_active('alia'))
    print(repo.search_similar(unit_vector(4242), top_k=1)[0].texto)
"""
        env = {
            **os.environ,
            "POSTGRES_DB": test_db_settings.dbname,  # .env no sobrescribe variables ya definidas
            "PYTHONPATH": f"{PROJECT_ROOT}{os.pathsep}{PROJECT_ROOT / 'tests'}",
        }
        output = subprocess.run(
            [sys.executable, "-c", child], capture_output=True, text=True, env=env, check=True, cwd=PROJECT_ROOT
        ).stdout.strip()
        assert output == marker
    finally:
        with connect(test_db_settings) as conn:
            conn.execute("DELETE FROM version_documento WHERE id = %s", (version.id,))
            conn.execute("DELETE FROM documento WHERE titulo = %s", (marker,))


@integration
@pytest.mark.skipif(
    os.getenv("RUN_MODEL_TESTS") != "1",
    reason="Defina RUN_MODEL_TESTS=1 para usar ALIA real contra PostgreSQL.",
)
def test_real_alia_top1_from_pgvector(db, alia_config) -> None:
    from src.embeddings import EmbeddingService

    service = EmbeddingService("alia")
    fragments = [FragmentInput(text) for text in SAMPLE_TEXTS]
    index_document(
        db, service, alia_config, titulo="ALIA real", entidad="Prueba", version="1.0", fragments=fragments
    )
    results = VectorRepository(db, alia_config).search_similar(service.encode_query(SAMPLE_QUERY), top_k=3)
    assert len(results) == 3
    assert results[0].texto == SAMPLE_TEXTS[0]
