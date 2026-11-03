-- Fase 4: clasificación de fragmentos para conservar índices y excluirlos de
-- la recuperación normal sin perder trazabilidad ni capacidad diagnóstica.

ALTER TABLE fragmento
    ADD COLUMN IF NOT EXISTS tipo_contenido VARCHAR(20) NOT NULL DEFAULT 'contenido';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fragmento_tipo_contenido_valido') THEN
        ALTER TABLE fragmento ADD CONSTRAINT fragmento_tipo_contenido_valido
            CHECK (tipo_contenido IN ('contenido', 'indice'));
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS fragmento_tipo_contenido_idx
    ON fragmento (tipo_contenido);
