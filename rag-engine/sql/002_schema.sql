-- Esquema del corpus y de los embeddings del RAG de Vianova.
-- Idempotente: lo ejecuta Docker al crear el volumen y también
-- src.database.connection.apply_schema() sobre bases ya existentes.
-- gen_random_uuid() es nativo desde PostgreSQL 13.

CREATE TABLE IF NOT EXISTS documento (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo      TEXT NOT NULL CHECK (btrim(titulo) <> ''),
    entidad     VARCHAR(200),
    url_origen  TEXT,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS version_documento (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    documento_id  UUID NOT NULL REFERENCES documento (id) ON DELETE RESTRICT,
    version       VARCHAR(50) NOT NULL,
    estado        VARCHAR(20) NOT NULL DEFAULT 'borrador'
                  CHECK (estado IN ('borrador', 'revision', 'activa', 'retirada')),
    vigencia      TEXT,
    ruta_archivo  TEXT,
    hash_archivo  TEXT,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (documento_id, version)
);

-- Como máximo una versión activa por documento.
CREATE UNIQUE INDEX IF NOT EXISTS version_documento_una_activa
    ON version_documento (documento_id) WHERE estado = 'activa';

CREATE TABLE IF NOT EXISTS fragmento (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id  UUID NOT NULL REFERENCES version_documento (id) ON DELETE CASCADE,
    orden       INTEGER NOT NULL CHECK (orden >= 0),
    texto       TEXT NOT NULL CHECK (btrim(texto) <> ''),
    ubicacion   TEXT,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (version_id, orden)
);

CREATE TABLE IF NOT EXISTS configuracion_modelo (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre       VARCHAR(50) NOT NULL UNIQUE,
    model_id     TEXT NOT NULL,
    dimension    INTEGER NOT NULL CHECK (dimension > 0),
    normalizado  BOOLEAN NOT NULL,
    activo       BOOLEAN NOT NULL DEFAULT true,
    -- tabla_embeddings: tabla vectorial física de esta configuración.
    parametros   JSONB NOT NULL DEFAULT '{}'::jsonb,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Una tabla vectorial por configuración/dimensión: un VECTOR(n) solo admite
-- vectores de n dimensiones. Qwen3 o BGE-M3 tendrán su propia tabla
-- (p. ej. embedding_fragmento_qwen3 VECTOR(1024)) en lugar de mezclarse aquí.
CREATE TABLE IF NOT EXISTS embedding_fragmento_alia (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fragmento_id      UUID NOT NULL REFERENCES fragmento (id) ON DELETE CASCADE,
    configuracion_id  UUID NOT NULL REFERENCES configuracion_modelo (id) ON DELETE RESTRICT,
    embedding         VECTOR(768) NOT NULL,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fragmento_id, configuracion_id)
);

-- Sin índice HNSW/IVFFlat a propósito: la búsqueda es exacta (baseline).

INSERT INTO configuracion_modelo (nombre, model_id, dimension, normalizado, activo, parametros)
VALUES (
    'alia',
    'SINAI/ALIA-MrBERT-es-biomedical-embeddings',
    768,
    true,
    true,
    '{"tabla_embeddings": "embedding_fragmento_alia", "metrica": "cosine", "prompt_consulta": "query"}'::jsonb
)
ON CONFLICT (nombre) DO NOTHING;
