#!/usr/bin/env python3
"""Ejecuta el banco de consultas contra pgvector y guarda los resultados en JSON.

Solo recupera (ALIA -> pgvector, búsqueda exacta); no evalúa ni genera respuestas.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import DatabaseUnavailableError, ModelConfigRepository, VectorRepository, connect
from src.embeddings import EmbeddingService
from src.ingestion import ChunkingConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consultas", type=Path, default=PROJECT_ROOT / "eval" / "consultas_baseline.json")
    parser.add_argument("-k", "--top-k", type=int, default=5)
    parser.add_argument("--salida", type=Path, help="JSON de resultados (por defecto en eval/resultados/).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    queries = json.loads(args.consultas.read_text(encoding="utf-8"))["consultas"]
    try:
        conn = connect()
    except (DatabaseUnavailableError, ValueError) as exc:
        print(exc)
        return 1

    service = EmbeddingService("alia")
    chunking = ChunkingConfig.from_env()
    results = []
    with conn:
        vectors = VectorRepository(conn, ModelConfigRepository(conn).get_active("alia"))
        for query in queries:
            hits = vectors.search_similar(service.encode_query(query["texto"]), top_k=args.top_k)
            results.append({
                **query,
                "resultados": [
                    {
                        "posicion": position,
                        "similitud": round(hit.similitud, 6),
                        "distancia": round(hit.distancia, 6),
                        "documento": hit.titulo,
                        "entidad": hit.entidad,
                        "version": hit.version,
                        "pagina_inicio": hit.pagina_inicio,
                        "pagina_fin": hit.pagina_fin,
                        "seccion": hit.ubicacion,
                        "fragmento_id": str(hit.fragmento_id),
                        "texto": hit.texto,
                    }
                    for position, hit in enumerate(hits, start=1)
                ],
            })
            top = hits[0] if hits else None
            if top:
                print(f"{query['id']}  {top.similitud:.4f}  p{top.pagina_inicio}-{top.pagina_fin}  "
                      f"{(top.ubicacion or '—')[:45]:<45}  {top.texto[:70].replace(chr(10), ' ')}…")

    stamp = datetime.now(timezone.utc)
    output = args.salida or PROJECT_ROOT / "eval" / "resultados" / (
        f"alia_{chunking.chunk_size_tokens}_{chunking.chunk_overlap_tokens}_{stamp:%Y%m%dT%H%M%SZ}.json"
    )
    output.write_text(json.dumps({
        "fecha_utc": stamp.isoformat(),
        "modelo": service.model_name,
        "dimension": service.dimension,
        "device": service.device,
        "busqueda": "pgvector exacta, distancia coseno (<=>)",
        "chunk_size_tokens": chunking.chunk_size_tokens,
        "chunk_overlap_tokens": chunking.chunk_overlap_tokens,
        "top_k": args.top_k,
        "consultas": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    shown = output.resolve().relative_to(PROJECT_ROOT) if output.resolve().is_relative_to(PROJECT_ROOT) else output
    print(f"\nResultados guardados en {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
