"""Acceso a las tablas vectoriales de pgvector.

Cada configuración de modelo escribe en su propia tabla `VECTOR(n)` (ver
`configuracion_modelo.parametros->>'tabla_embeddings'`). Un `VECTOR(768)` no
admite vectores de otra dimensión, por eso ALIA (768) y futuros modelos como
Qwen3 o BGE-M3 (1024) no comparten tabla.

La búsqueda se ejecuta íntegramente en PostgreSQL con el operador `<=>`
(distancia coseno de pgvector). Sin índice ANN, el plan es un recorrido
secuencial + ordenación: búsqueda exacta.

Con vectores normalizados (norma 1):
    distancia_coseno = 1 - cos(a, b)     ∈ [0, 2]
    similitud        = 1 - distancia     ∈ [-1, 1]  (= producto punto)
Menor distancia = más parecido; el ranking coincide con el de producto punto.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import re
from uuid import UUID

import numpy as np
import psycopg
from psycopg import sql
from psycopg.rows import class_row

from .repositories import ConfiguracionModelo


# Lista blanca de tablas vectoriales y su dimensión física. Al añadir un
# modelo con otra dimensión se crea su tabla en sql/ y se registra aquí.
VECTOR_TABLES: dict[str, int] = {
    "embedding_fragmento_alia": 768,
    "embedding_fragmento_qwen3": 1024,
    "embedding_fragmento_bge_m3": 1024,
}

VECTOR_TABLE_MODELS = {
    "embedding_fragmento_alia": "SINAI/ALIA-MrBERT-es-biomedical-embeddings",
    "embedding_fragmento_qwen3": "Qwen/Qwen3-Embedding-0.6B",
    "embedding_fragmento_bge_m3": "BAAI/bge-m3",
}

NORM_TOLERANCE = 1e-3


@dataclass(frozen=True)
class SearchResult:
    fragmento_id: UUID
    orden: int
    texto: str
    ubicacion: str | None
    documento_id: UUID
    titulo: str
    entidad: str | None
    version_id: UUID
    version: str
    distancia: float
    pagina_inicio: int | None = None
    pagina_fin: int | None = None
    token_count: int | None = None
    tipo_contenido: str = "contenido"

    @property
    def similitud(self) -> float:
        """Similitud coseno; equivale al producto punto con vectores normalizados."""
        return 1.0 - self.distancia


class VectorRepository:
    """Persistencia y búsqueda de embeddings de una configuración de modelo."""

    def __init__(self, conn: psycopg.Connection, config: ConfiguracionModelo) -> None:
        table = config.parametros.get("tabla_embeddings")
        if table not in VECTOR_TABLES:
            raise ValueError(f"Tabla vectorial no registrada para '{config.nombre}': {table!r}.")
        if VECTOR_TABLES[table] != config.dimension:
            raise ValueError(
                f"La configuración '{config.nombre}' declara {config.dimension} dimensiones "
                f"pero {table} almacena VECTOR({VECTOR_TABLES[table]})."
            )
        if VECTOR_TABLE_MODELS[table] != config.model_id:
            raise ValueError(f"La tabla {table} no corresponde al modelo {config.model_id}.")
        self._conn = conn
        self.config = config
        self.table_name = table
        self._table = sql.Identifier(table)

    @property
    def dimension(self) -> int:
        return self.config.dimension

    def save_embedding(self, fragmento_id: UUID, embedding: Sequence[float] | np.ndarray) -> bool:
        """Inserta o reemplaza el embedding. Devuelve True si la fila es nueva."""
        vector = self._as_vector(embedding)
        query = sql.SQL(
            """
            INSERT INTO {table} (fragmento_id, configuracion_id, embedding)
            VALUES (%s, %s, %s)
            ON CONFLICT (fragmento_id, configuracion_id)
            DO UPDATE SET embedding = EXCLUDED.embedding, creado_en = now()
            RETURNING (xmax = 0) AS insertado
            """
        ).format(table=self._table)
        row = self._conn.execute(query, (fragmento_id, self.config.id, vector)).fetchone()
        return bool(row[0])

    def get_embedding(self, fragmento_id: UUID) -> np.ndarray | None:
        query = sql.SQL(
            "SELECT embedding FROM {table} WHERE fragmento_id = %s AND configuracion_id = %s"
        ).format(table=self._table)
        row = self._conn.execute(query, (fragmento_id, self.config.id)).fetchone()
        if row is None:
            return None
        value = row[0]
        # pgvector >= 0.4 devuelve `Vector`; versiones anteriores, ndarray.
        to_numpy = getattr(value, "to_numpy", None)
        return np.asarray(to_numpy() if to_numpy else value, dtype=np.float32)

    def delete_embeddings_for_fragment(self, fragmento_id: UUID) -> int:
        query = sql.SQL(
            "DELETE FROM {table} WHERE fragmento_id = %s AND configuracion_id = %s"
        ).format(table=self._table)
        return self._conn.execute(query, (fragmento_id, self.config.id)).rowcount

    def count_embeddings(self) -> int:
        query = sql.SQL("SELECT count(*) FROM {table} WHERE configuracion_id = %s").format(
            table=self._table
        )
        return int(self._conn.execute(query, (self.config.id,)).fetchone()[0])

    def search_similar(
        self,
        query_embedding: Sequence[float] | np.ndarray,
        top_k: int = 3,
        *,
        solo_activas: bool = True,
        entidad: str | None = None,
        documento_id: UUID | None = None,
        incluir_indice: bool = False,
    ) -> list[SearchResult]:
        """Top-K por distancia coseno calculada y ordenada por PostgreSQL.

        Filtros opcionales (igualdad exacta): `entidad` y `documento_id`.
        """
        query, params = self._search_sql(
            query_embedding, top_k, solo_activas, entidad, documento_id, incluir_indice
        )
        with self._conn.cursor(row_factory=class_row(SearchResult)) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def explain_search(
        self,
        query_embedding: Sequence[float] | np.ndarray,
        top_k: int = 3,
        *,
        solo_activas: bool = True,
        entidad: str | None = None,
        documento_id: UUID | None = None,
        incluir_indice: bool = False,
    ) -> list[str]:
        """Plan real (EXPLAIN ANALYZE) de la consulta de búsqueda."""
        query, params = self._search_sql(
            query_embedding, top_k, solo_activas, entidad, documento_id, incluir_indice
        )
        rows = self._conn.execute(sql.SQL("EXPLAIN (ANALYZE, COSTS OFF) ") + query, params).fetchall()
        # El literal de 768 floats no aporta nada al leer el plan.
        return [re.sub(r"'\[[^\]]{60,}\]'", "'[...]'", row[0]) for row in rows]

    def _search_sql(
        self,
        query_embedding: Sequence[float] | np.ndarray,
        top_k: int,
        solo_activas: bool,
        entidad: str | None = None,
        documento_id: UUID | None = None,
        incluir_indice: bool = False,
    ) -> tuple[sql.Composed, dict[str, object]]:
        if top_k < 1:
            raise ValueError("top_k debe ser mayor que cero.")
        vector = self._as_vector(query_embedding)
        conditions = []
        if solo_activas:
            conditions.append(sql.SQL("AND v.estado = 'activa'"))
        if entidad is not None:
            conditions.append(sql.SQL("AND d.entidad = %(entidad)s"))
        if documento_id is not None:
            conditions.append(sql.SQL("AND d.id = %(documento_id)s"))
        if not incluir_indice:
            conditions.append(sql.SQL("AND f.tipo_contenido = 'contenido'"))
        query = sql.SQL(
            """
            SELECT f.id AS fragmento_id, f.orden, f.texto, f.ubicacion,
                   d.id AS documento_id, d.titulo, d.entidad,
                   v.id AS version_id, v.version,
                   e.embedding <=> %(query)s AS distancia,
                   f.pagina_inicio, f.pagina_fin, f.token_count, f.tipo_contenido
            FROM {table} AS e
            JOIN fragmento AS f ON f.id = e.fragmento_id
            JOIN version_documento AS v ON v.id = f.version_id
            JOIN documento AS d ON d.id = v.documento_id
            WHERE e.configuracion_id = %(config)s {filtros}
            ORDER BY e.embedding <=> %(query)s
            LIMIT %(top_k)s
            """
        ).format(table=self._table, filtros=sql.SQL(" ").join(conditions))
        params = {"query": vector, "config": self.config.id, "top_k": top_k,
                  "entidad": entidad, "documento_id": documento_id}
        return query, params

    def _as_vector(self, values: Sequence[float] | np.ndarray) -> np.ndarray:
        vector = np.asarray(values, dtype=np.float32)
        if vector.shape != (self.dimension,):
            raise ValueError(
                f"Se esperaba un vector de forma ({self.dimension},) para "
                f"'{self.config.nombre}' y se recibió {vector.shape}."
            )
        if not np.all(np.isfinite(vector)):
            raise ValueError("El embedding contiene valores NaN o infinitos.")
        if self.config.normalizado:
            norm = float(np.linalg.norm(vector))
            if abs(norm - 1.0) > NORM_TOLERANCE:
                raise ValueError(f"La configuración exige vectores normalizados; norma={norm:.6f}.")
        return vector
