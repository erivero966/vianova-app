#!/usr/bin/env python3
"""Indexa los tres textos de ejemplo con ALIA y persiste sus embeddings en pgvector."""

import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import (
    DatabaseUnavailableError,
    FragmentInput,
    ModelConfigRepository,
    VectorRepository,
    apply_schema,
    connect,
    index_document,
)
from src.embeddings import EmbeddingService
from src.sample_corpus import SAMPLE_ENTITY, SAMPLE_TEXTS, SAMPLE_TITLE, SAMPLE_VERSION


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    try:
        conn = connect(register=False)
    except (DatabaseUnavailableError, ValueError) as exc:
        print(exc)
        return 1

    with conn:  # commit al salir sin errores; rollback ante excepción
        apply_schema(conn)  # idempotente: cubre volúmenes creados antes del esquema
        config = ModelConfigRepository(conn).get_active("alia")

        service = EmbeddingService("alia")
        print("Modelo: ALIA")
        print(f"Model ID: {service.model_name}")
        print(f"Device: {service.device}")
        print(f"Dimensión: {service.dimension}\n")

        fragments = [
            FragmentInput(texto, ubicacion=f"Fragmento de prueba {orden}")
            for orden, texto in enumerate(SAMPLE_TEXTS, start=1)
        ]
        report = index_document(
            conn,
            service,
            config,
            titulo=SAMPLE_TITLE,
            entidad=SAMPLE_ENTITY,
            version=SAMPLE_VERSION,
            fragments=fragments,
        )
        total_db = VectorRepository(conn, config).count_embeddings()

    print("Documento creado" if report.documento_creado else "Documento existente reutilizado")
    print("Versión activa creada" if report.version_creada else "Versión activa existente reutilizada")
    print(
        f"{report.total_fragmentos} fragmentos "
        f"({report.fragmentos_creados} nuevos, {report.fragmentos_actualizados} actualizados, "
        f"{report.fragmentos_sin_cambios} sin cambios)"
    )
    print(f"{report.embeddings_generados} embeddings generados")
    print(
        f"{report.embeddings_almacenados} embeddings almacenados "
        f"({report.embeddings_nuevos} nuevos, {report.embeddings_reemplazados} reemplazados)"
    )
    print(f"Total en embedding_fragmento_alia (ALIA): {total_db}")
    print("\nIndexación completada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
