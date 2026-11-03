"""Indexación idempotente de fragmentos ya preparados (sin PDF ni chunking)."""

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
from typing import Protocol
from uuid import UUID

import numpy as np
import psycopg

from .repositories import (
    ConfiguracionModelo,
    DocumentRepository,
    FragmentRepository,
    VersionRepository,
)
from .vector_repository import VectorRepository


class DocumentEncoder(Protocol):
    model_name: str
    dimension: int

    def encode_documents(self, texts: list[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class FragmentInput:
    texto: str
    ubicacion: str | None = None
    tipo_contenido: str = "contenido"


@dataclass(frozen=True)
class IndexReport:
    documento_id: UUID
    documento_creado: bool
    version_id: UUID
    version_creada: bool
    fragmentos_creados: int
    fragmentos_actualizados: int
    fragmentos_sin_cambios: int
    embeddings_generados: int
    embeddings_nuevos: int
    embeddings_reemplazados: int

    @property
    def total_fragmentos(self) -> int:
        return self.fragmentos_creados + self.fragmentos_actualizados + self.fragmentos_sin_cambios

    @property
    def embeddings_almacenados(self) -> int:
        return self.embeddings_nuevos + self.embeddings_reemplazados


def ensure_encoder_matches(encoder: DocumentEncoder, config: ConfiguracionModelo) -> None:
    if encoder.model_name != config.model_id or encoder.dimension != config.dimension:
        raise ValueError(
            f"El codificador ({encoder.model_name}, {encoder.dimension}d) no coincide con "
            f"la configuración '{config.nombre}' ({config.model_id}, {config.dimension}d)."
        )


def content_hash(fragments: Sequence[FragmentInput]) -> str:
    digest = hashlib.sha256()
    for fragment in fragments:
        digest.update(fragment.texto.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def index_document(
    conn: psycopg.Connection,
    encoder: DocumentEncoder,
    config: ConfiguracionModelo,
    *,
    titulo: str,
    entidad: str | None,
    version: str,
    fragments: Sequence[FragmentInput],
    url_origen: str | None = None,
    vigencia: str | None = None,
) -> IndexReport:
    """Crea/reutiliza documento, versión y fragmentos y guarda sus embeddings.

    Todo ocurre en una única transacción: ante cualquier error no queda
    nada a medias. Reejecutar con los mismos datos no crea duplicados.
    """
    if not fragments:
        raise ValueError("Se requiere al menos un fragmento.")
    ensure_encoder_matches(encoder, config)
    vectors = VectorRepository(conn, config)
    with conn.transaction():
        documento, documento_creado = DocumentRepository(conn).get_or_create(titulo, entidad, url_origen)
        versions = VersionRepository(conn)
        version_row, version_creada = versions.get_or_create(
            documento.id, version, vigencia=vigencia, hash_archivo=content_hash(fragments)
        )

        fragment_repo = FragmentRepository(conn)
        status_count = {"creado": 0, "actualizado": 0, "sin_cambios": 0}
        stored = []
        for orden, fragment in enumerate(fragments, start=1):
            row, status = fragment_repo.upsert(
                version_row.id, orden, fragment.texto, fragment.ubicacion, fragment.tipo_contenido
            )
            status_count[status] += 1
            stored.append(row)

        embeddings = encoder.encode_documents([row.texto for row in stored])
        nuevos = sum(vectors.save_embedding(row.id, vector) for row, vector in zip(stored, embeddings))

        # La versión solo se activa cuando ya tiene todos sus embeddings.
        if version_row.estado != "activa":
            version_row = versions.activate(version_row.id)

    return IndexReport(
        documento_id=documento.id,
        documento_creado=documento_creado,
        version_id=version_row.id,
        version_creada=version_creada,
        fragmentos_creados=status_count["creado"],
        fragmentos_actualizados=status_count["actualizado"],
        fragmentos_sin_cambios=status_count["sin_cambios"],
        embeddings_generados=len(embeddings),
        embeddings_nuevos=nuevos,
        embeddings_reemplazados=len(embeddings) - nuevos,
    )
