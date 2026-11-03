"""Repositorios relacionales: documento, versión, fragmento y configuración de modelo."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import psycopg
from psycopg.rows import class_row
from psycopg.types.json import Jsonb


ESTADOS_VERSION = ("borrador", "revision", "activa", "retirada")
FragmentStatus = Literal["creado", "actualizado", "sin_cambios"]


@dataclass(frozen=True)
class Documento:
    id: UUID
    titulo: str
    entidad: str | None
    url_origen: str | None
    creado_en: datetime


@dataclass(frozen=True)
class VersionDocumento:
    id: UUID
    documento_id: UUID
    version: str
    estado: str
    vigencia: str | None
    ruta_archivo: str | None
    hash_archivo: str | None
    creado_en: datetime


@dataclass(frozen=True)
class Fragmento:
    id: UUID
    version_id: UUID
    orden: int
    texto: str
    ubicacion: str | None
    creado_en: datetime
    pagina_inicio: int | None = None
    pagina_fin: int | None = None
    token_count: int | None = None
    tipo_contenido: str = "contenido"


@dataclass(frozen=True)
class Ingesta:
    id: UUID
    version_id: UUID
    configuracion_id: UUID
    archivo: str
    hash_archivo: str
    parametros: dict[str, Any]
    metricas: dict[str, Any]
    creado_en: datetime


@dataclass(frozen=True)
class ConfiguracionModelo:
    id: UUID
    nombre: str
    model_id: str
    dimension: int
    normalizado: bool
    activo: bool
    parametros: dict[str, Any]
    creado_en: datetime


class DocumentRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, titulo: str, entidad: str | None = None, url_origen: str | None = None) -> Documento:
        with self._conn.cursor(row_factory=class_row(Documento)) as cur:
            cur.execute(
                "INSERT INTO documento (titulo, entidad, url_origen) VALUES (%s, %s, %s) RETURNING *",
                (titulo, entidad, url_origen),
            )
            return cur.fetchone()

    def get(self, documento_id: UUID) -> Documento | None:
        with self._conn.cursor(row_factory=class_row(Documento)) as cur:
            cur.execute("SELECT * FROM documento WHERE id = %s", (documento_id,))
            return cur.fetchone()

    def find(self, titulo: str, entidad: str | None) -> Documento | None:
        with self._conn.cursor(row_factory=class_row(Documento)) as cur:
            cur.execute(
                "SELECT * FROM documento WHERE titulo = %s AND entidad IS NOT DISTINCT FROM %s "
                "ORDER BY creado_en LIMIT 1",
                (titulo, entidad),
            )
            return cur.fetchone()

    def get_or_create(
        self, titulo: str, entidad: str | None = None, url_origen: str | None = None
    ) -> tuple[Documento, bool]:
        existing = self.find(titulo, entidad)
        if existing is not None:
            return existing, False
        return self.create(titulo, entidad, url_origen), True


class VersionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(
        self,
        documento_id: UUID,
        version: str,
        estado: str = "borrador",
        *,
        vigencia: str | None = None,
        ruta_archivo: str | None = None,
        hash_archivo: str | None = None,
    ) -> VersionDocumento:
        _validate_estado(estado)
        with self._conn.cursor(row_factory=class_row(VersionDocumento)) as cur:
            cur.execute(
                """
                INSERT INTO version_documento
                    (documento_id, version, estado, vigencia, ruta_archivo, hash_archivo)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (documento_id, version, estado, vigencia, ruta_archivo, hash_archivo),
            )
            return cur.fetchone()

    def find(self, documento_id: UUID, version: str) -> VersionDocumento | None:
        with self._conn.cursor(row_factory=class_row(VersionDocumento)) as cur:
            cur.execute(
                "SELECT * FROM version_documento WHERE documento_id = %s AND version = %s",
                (documento_id, version),
            )
            return cur.fetchone()

    def find_by_hash(self, hash_archivo: str) -> VersionDocumento | None:
        with self._conn.cursor(row_factory=class_row(VersionDocumento)) as cur:
            cur.execute("SELECT * FROM version_documento WHERE hash_archivo = %s", (hash_archivo,))
            return cur.fetchone()

    def get_or_create(self, documento_id: UUID, version: str, **kwargs: Any) -> tuple[VersionDocumento, bool]:
        existing = self.find(documento_id, version)
        if existing is not None:
            return existing, False
        return self.create(documento_id, version, **kwargs), True

    def activate(self, version_id: UUID) -> VersionDocumento:
        """Activa la versión y retira la que estuviera activa en el mismo documento."""
        with self._conn.transaction(), self._conn.cursor(row_factory=class_row(VersionDocumento)) as cur:
            cur.execute(
                """
                UPDATE version_documento SET estado = 'retirada'
                WHERE estado = 'activa' AND id <> %(id)s
                  AND documento_id = (SELECT documento_id FROM version_documento WHERE id = %(id)s)
                """,
                {"id": version_id},
            )
            cur.execute(
                "UPDATE version_documento SET estado = 'activa' WHERE id = %s RETURNING *",
                (version_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise LookupError(f"No existe la versión {version_id}.")
        return row


class FragmentRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(
        self,
        version_id: UUID,
        orden: int,
        texto: str,
        ubicacion: str | None = None,
        *,
        pagina_inicio: int | None = None,
        pagina_fin: int | None = None,
        token_count: int | None = None,
        tipo_contenido: str = "contenido",
    ) -> Fragmento:
        with self._conn.cursor(row_factory=class_row(Fragmento)) as cur:
            cur.execute(
                "INSERT INTO fragmento (version_id, orden, texto, ubicacion, pagina_inicio, pagina_fin, "
                "token_count, tipo_contenido) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (version_id, orden, texto, ubicacion, pagina_inicio, pagina_fin, token_count, tipo_contenido),
            )
            return cur.fetchone()

    def delete_for_version(self, version_id: UUID) -> int:
        """Elimina los fragmentos de una versión (sus embeddings caen en cascada)."""
        return self._conn.execute("DELETE FROM fragmento WHERE version_id = %s", (version_id,)).rowcount

    def count_for_version(self, version_id: UUID) -> int:
        row = self._conn.execute("SELECT count(*) FROM fragmento WHERE version_id = %s", (version_id,)).fetchone()
        return int(row[0])

    def find(self, version_id: UUID, orden: int) -> Fragmento | None:
        with self._conn.cursor(row_factory=class_row(Fragmento)) as cur:
            cur.execute(
                "SELECT * FROM fragmento WHERE version_id = %s AND orden = %s",
                (version_id, orden),
            )
            return cur.fetchone()

    def upsert(
        self, version_id: UUID, orden: int, texto: str, ubicacion: str | None = None,
        tipo_contenido: str = "contenido",
    ) -> tuple[Fragmento, FragmentStatus]:
        """Crea o actualiza el fragmento identificado por (version_id, orden)."""
        existing = self.find(version_id, orden)
        if existing is None:
            return self.create(version_id, orden, texto, ubicacion, tipo_contenido=tipo_contenido), "creado"
        if (existing.texto, existing.ubicacion, existing.tipo_contenido) == (
            texto, ubicacion, tipo_contenido
        ):
            return existing, "sin_cambios"
        with self._conn.cursor(row_factory=class_row(Fragmento)) as cur:
            cur.execute(
                "UPDATE fragmento SET texto = %s, ubicacion = %s, tipo_contenido = %s "
                "WHERE id = %s RETURNING *",
                (texto, ubicacion, tipo_contenido, existing.id),
            )
            return cur.fetchone(), "actualizado"

    def list_for_version(self, version_id: UUID) -> list[Fragmento]:
        with self._conn.cursor(row_factory=class_row(Fragmento)) as cur:
            cur.execute("SELECT * FROM fragmento WHERE version_id = %s ORDER BY orden", (version_id,))
            return cur.fetchall()


class IngestionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(
        self,
        version_id: UUID,
        configuracion_id: UUID,
        archivo: str,
        hash_archivo: str,
        parametros: dict[str, Any],
        metricas: dict[str, Any],
    ) -> Ingesta:
        with self._conn.cursor(row_factory=class_row(Ingesta)) as cur:
            cur.execute(
                """
                INSERT INTO ingesta (version_id, configuracion_id, archivo, hash_archivo, parametros, metricas)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (version_id, configuracion_id, archivo, hash_archivo, Jsonb(parametros), Jsonb(metricas)),
            )
            return cur.fetchone()

    def latest_for_version(self, version_id: UUID, configuracion_id: UUID) -> Ingesta | None:
        with self._conn.cursor(row_factory=class_row(Ingesta)) as cur:
            cur.execute(
                "SELECT * FROM ingesta WHERE version_id = %s AND configuracion_id = %s "
                "ORDER BY creado_en DESC LIMIT 1",
                (version_id, configuracion_id),
            )
            return cur.fetchone()


class ModelConfigRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def get_by_name(self, nombre: str) -> ConfiguracionModelo | None:
        with self._conn.cursor(row_factory=class_row(ConfiguracionModelo)) as cur:
            cur.execute("SELECT * FROM configuracion_modelo WHERE nombre = %s", (nombre,))
            return cur.fetchone()

    def get_active(self, nombre: str) -> ConfiguracionModelo:
        config = self.get_by_name(nombre)
        if config is None or not config.activo:
            raise LookupError(f"No hay una configuración activa para el modelo '{nombre}'.")
        return config

    def register(
        self,
        nombre: str,
        model_id: str,
        dimension: int,
        normalizado: bool,
        parametros: dict[str, Any],
        activo: bool = True,
    ) -> ConfiguracionModelo:
        with self._conn.cursor(row_factory=class_row(ConfiguracionModelo)) as cur:
            cur.execute(
                """
                INSERT INTO configuracion_modelo (nombre, model_id, dimension, normalizado, activo, parametros)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (nombre) DO UPDATE SET
                    model_id = EXCLUDED.model_id, dimension = EXCLUDED.dimension,
                    normalizado = EXCLUDED.normalizado, activo = EXCLUDED.activo,
                    parametros = EXCLUDED.parametros
                RETURNING *
                """,
                (nombre, model_id, dimension, normalizado, activo, Jsonb(parametros)),
            )
            return cur.fetchone()


def _validate_estado(estado: str) -> None:
    if estado not in ESTADOS_VERSION:
        raise ValueError(f"Estado '{estado}' no válido. Opciones: {', '.join(ESTADOS_VERSION)}.")
