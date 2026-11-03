-- Fase 3: trazabilidad por página de los fragmentos y registro de ingestas.
-- Migración nueva e idempotente; 001 y 002 no se modifican.

ALTER TABLE fragmento
    ADD COLUMN IF NOT EXISTS pagina_inicio INTEGER,
    ADD COLUMN IF NOT EXISTS pagina_fin    INTEGER,
    ADD COLUMN IF NOT EXISTS token_count   INTEGER;

-- Nulos permitidos: los fragmentos de la fase 2 no provienen de un PDF.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fragmento_pagina_inicio_valida') THEN
        ALTER TABLE fragmento ADD CONSTRAINT fragmento_pagina_inicio_valida
            CHECK (pagina_inicio IS NULL OR pagina_inicio >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fragmento_pagina_fin_valida') THEN
        ALTER TABLE fragmento ADD CONSTRAINT fragmento_pagina_fin_valida
            CHECK (pagina_fin IS NULL OR (pagina_inicio IS NOT NULL AND pagina_fin >= pagina_inicio));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fragmento_token_count_valido') THEN
        ALTER TABLE fragmento ADD CONSTRAINT fragmento_token_count_valido
            CHECK (token_count IS NULL OR token_count > 0);
    END IF;
END
$$;

-- El mismo archivo (mismos bytes) solo puede registrarse en una versión.
CREATE UNIQUE INDEX IF NOT EXISTS version_documento_hash_unico
    ON version_documento (hash_archivo) WHERE hash_archivo IS NOT NULL;

-- Una fila por ingesta completada: configuración usada y métricas, para
-- reproducibilidad y para comparar configuraciones de chunking.
CREATE TABLE IF NOT EXISTS ingesta (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id        UUID NOT NULL REFERENCES version_documento (id) ON DELETE CASCADE,
    configuracion_id  UUID NOT NULL REFERENCES configuracion_modelo (id) ON DELETE RESTRICT,
    archivo           TEXT NOT NULL,
    hash_archivo      TEXT NOT NULL,
    parametros        JSONB NOT NULL,
    metricas          JSONB NOT NULL,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ingesta_version_reciente ON ingesta (version_id, creado_en DESC);
