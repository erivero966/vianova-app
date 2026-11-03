#!/usr/bin/env python3
"""Búsqueda vectorial exacta en PostgreSQL/pgvector (distancia coseno, <=>)."""

import argparse
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import DatabaseUnavailableError, ModelConfigRepository, VectorRepository, connect
from src.embeddings import EmbeddingService
from src.sample_corpus import SAMPLE_QUERY


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default=SAMPLE_QUERY, help="Pregunta en lenguaje natural.")
    parser.add_argument("-k", "--top-k", type=int, default=3)
    parser.add_argument("--explain", action="store_true", help="Muestra el plan real de PostgreSQL.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    try:
        conn = connect()
    except (DatabaseUnavailableError, ValueError) as exc:
        print(exc)
        return 1

    with conn:
        config = ModelConfigRepository(conn).get_active("alia")
        vectors = VectorRepository(conn, config)
        stored = vectors.count_embeddings()
        if stored == 0:
            print("No hay embeddings ALIA almacenados. Ejecute primero scripts/index_sample.py.")
            return 1

        service = EmbeddingService("alia")
        query_vector = service.encode_query(args.query)  # único vector en memoria: la consulta
        results = vectors.search_similar(query_vector, top_k=args.top_k)
        plan = vectors.explain_search(query_vector, top_k=args.top_k) if args.explain else []

    print(f"Pregunta:\n{args.query}\n")
    print(f"Modelo:\nALIA ({service.model_name}, {service.dimension}d, device={service.device})\n")
    print(f"Embeddings en PostgreSQL: {stored} | métrica: distancia coseno (<=>), búsqueda exacta")
    for position, result in enumerate(results, start=1):
        print(f"\nTOP {position}")
        print(f"Similitud: {result.similitud:.6f} (distancia coseno {result.distancia:.6f})")
        print(f"Documento: {result.titulo} [{result.entidad}]")
        print(f"Versión: {result.version}")
        print(f"Ubicación: {result.ubicacion}")
        print(f"Fragmento: {result.texto}")
    if plan:
        print("\nPlan de ejecución (EXPLAIN ANALYZE):")
        print("\n".join(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
