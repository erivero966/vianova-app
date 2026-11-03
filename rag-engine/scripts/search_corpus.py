#!/usr/bin/env python3
"""Búsqueda semántica sobre el corpus indexado: ALIA -> pgvector (búsqueda exacta, <=>)."""

import argparse
import logging
from pathlib import Path
import sys
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import DatabaseUnavailableError, ModelConfigRepository, VectorRepository, connect
from src.embeddings import EmbeddingService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Consulta en lenguaje natural.")
    parser.add_argument("-k", "--top-k", type=int, default=5)
    parser.add_argument("--entidad", help="Filtra por entidad exacta.")
    parser.add_argument("--documento-id", type=UUID, help="Filtra por documento.")
    parser.add_argument("--max-caracteres", type=int, default=0, help="Recorta el texto mostrado (0 = completo).")
    parser.add_argument("--explain", action="store_true", help="Muestra el plan real de PostgreSQL.")
    parser.add_argument("--incluir-indice", action="store_true",
                        help="Modo diagnóstico: incluye fragmentos clasificados como índice.")
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
        vectors = VectorRepository(conn, ModelConfigRepository(conn).get_active("alia"))
        if vectors.count_embeddings() == 0:
            print("No hay embeddings ALIA almacenados. Ejecute primero scripts/ingest_pdf.py.")
            return 1
        service = EmbeddingService("alia")
        query_vector = service.encode_query(args.query)  # único vector en Python: la consulta
        filters = {"entidad": args.entidad, "documento_id": args.documento_id,
                   "incluir_indice": args.incluir_indice}
        results = vectors.search_similar(query_vector, top_k=args.top_k, **filters)
        plan = vectors.explain_search(query_vector, top_k=args.top_k, **filters) if args.explain else []

    print(f"Consulta:\n{args.query}\n")
    print(f"Modelo: ALIA ({service.dimension}d, {service.device}) | pgvector, distancia coseno exacta")
    if not results:
        print("\nSin resultados para los filtros indicados.")
    for position, r in enumerate(results, start=1):
        text = r.texto
        if args.max_caracteres and len(text) > args.max_caracteres:
            text = text[: args.max_caracteres] + "…"
        print(f"\nTOP {position}")
        print(f"Similitud: {r.similitud:.4f}")
        print(f"Distancia coseno: {r.distancia:.4f}\n")
        print(f"Documento:\n{r.titulo}\n")
        print(f"Entidad:\n{r.entidad}\n")
        print(f"Versión:\n{r.version}\n")
        print(f"Página (física del PDF):\ninicio {_page(r.pagina_inicio)} | fin {_page(r.pagina_fin)}\n")
        print(f"Sección:\n{r.ubicacion or '(no determinada)'}\n")
        print(f"Tipo de contenido:\n{r.tipo_contenido}\n")
        print(f"Texto:\n{text}")
    if plan:
        print("\nPlan de ejecución (EXPLAIN ANALYZE):")
        print("\n".join(plan))
    return 0


def _page(page: int | None) -> str:
    return "—" if page is None else str(page)


if __name__ == "__main__":
    sys.exit(main())
