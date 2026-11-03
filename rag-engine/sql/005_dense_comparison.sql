-- Comparación dense: tabla separada por modelo, sin índices aproximados.
-- El runner comprueba la dimensión observada antes de registrar/indexar.
CREATE TABLE IF NOT EXISTS embedding_fragmento_qwen3 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fragmento_id UUID NOT NULL REFERENCES fragmento (id) ON DELETE CASCADE,
    configuracion_id UUID NOT NULL REFERENCES configuracion_modelo (id) ON DELETE RESTRICT,
    embedding VECTOR(1024) NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fragmento_id, configuracion_id)
);

CREATE TABLE IF NOT EXISTS embedding_fragmento_bge_m3 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fragmento_id UUID NOT NULL REFERENCES fragmento (id) ON DELETE CASCADE,
    configuracion_id UUID NOT NULL REFERENCES configuracion_modelo (id) ON DELETE RESTRICT,
    embedding VECTOR(1024) NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fragmento_id, configuracion_id)
);
