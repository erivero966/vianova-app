#!/usr/bin/env python3
"""Indexa PDFs aprobados: extracción -> limpieza -> chunks -> ALIA -> pgvector.

Ejemplos:
  python scripts/ingest_pdf.py corpus/aprobados/guia.pdf
  python scripts/ingest_pdf.py corpus/aprobados/guia.pdf --metadata corpus/aprobados/guia.json
  python scripts/ingest_pdf.py --todos

Solo se aceptan PDFs dentro de corpus/aprobados/. Por defecto los metadatos se
leen del .json con el mismo nombre que el PDF.
"""

import argparse
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import DatabaseUnavailableError, apply_schema, connect
from src.embeddings import EmbeddingService
from src.ingestion import (
    APPROVED_DIR,
    ChunkingConfig,
    DocumentMetadata,
    IngestionError,
    IngestionReport,
    InvalidPdfError,
    MetadataError,
    default_metadata_path,
    ingest_document,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", nargs="?", type=Path)
    parser.add_argument("--metadata", type=Path, help="JSON de metadatos (por defecto: <pdf>.json).")
    parser.add_argument("--todos", action="store_true", help="Indexa todos los PDF de corpus/aprobados/.")
    parser.add_argument("--reindex", action="store_true",
                        help="Regenera fragmentos y embeddings de un archivo ya registrado.")
    parser.add_argument("--ignorar-advertencia-ocr", action="store_true",
                        help="Indexa aunque haya muchas páginas sin texto (queda registrado).")
    args = parser.parse_args()
    if bool(args.pdf) == args.todos:
        parser.error("Indique un PDF o --todos.")
    if args.todos and args.metadata:
        parser.error("--metadata solo se usa con un único PDF.")
    return args


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    pdfs = sorted(APPROVED_DIR.glob("*.pdf")) if args.todos else [args.pdf]
    if not pdfs:
        print(f"No hay PDFs en {APPROVED_DIR.relative_to(PROJECT_ROOT)}/.")
        return 1

    jobs = []
    for pdf in pdfs:
        metadata_path = args.metadata or default_metadata_path(pdf)
        try:
            jobs.append((pdf, DocumentMetadata.from_json(metadata_path)))
        except MetadataError as exc:
            print(f"{pdf.name}: {exc}")
            return 1

    try:
        with connect(register=False) as conn:
            apply_schema(conn)
    except (DatabaseUnavailableError, ValueError) as exc:
        print(exc)
        return 1

    service = EmbeddingService("alia")
    chunking = ChunkingConfig.from_env()
    failures = 0
    for pdf, metadata in jobs:
        print(f"\n=== {pdf.name} ===")
        try:
            report = ingest_document(
                pdf, metadata, service, chunking=chunking, reindex=args.reindex,
                allow_ocr_warning=args.ignorar_advertencia_ocr, progress=print,
            )
        except (IngestionError, InvalidPdfError) as exc:
            print(f"\nNO INDEXADO: {exc}")
            failures += 1
            continue
        print_report(report)
    return 1 if failures else 0


def print_report(report: IngestionReport) -> None:
    m, p = report.metricas, report.parametros
    print()
    print(f"Documento:\n{report.metadata.titulo}\n")
    print(f"Entidad:\n{report.metadata.entidad}\n")
    print(f"Versión:\n{report.metadata.version}\n")
    print(f"Archivo:\n{report.archivo}\n")
    print(f"SHA-256:\n{report.sha256}\n")
    print(f"Páginas:\n{m['paginas']} ({m['paginas_con_texto']} con texto)\n")
    print(f"Caracteres:\n{m['caracteres']}\n")
    print(f"Chunks:\n{m['chunks']} ({m['chunks_con_seccion']} con sección, {m['chunks_multipagina']} multipágina)\n")
    print(f"Tokens (min / promedio / mediana / max):\n{m['tokens_min']} / {m['tokens_promedio']} / "
          f"{m['tokens_mediana']} / {m['tokens_max']}\n")
    print(f"Chunking:\n{p['chunk_size_tokens']} tokens, solapamiento {p['chunk_overlap_tokens']} "
          f"(tokenizer {p['tokenizer']})\n")
    print(f"Limpieza:\n{m['lineas_eliminadas']} líneas de encabezado/pie eliminadas, "
          f"{m['uniones_guion']} palabras con guion reconstruidas, {m['titulos_detectados']} títulos\n")
    print(f"Origen de extracción:\n{m.get('origen_extraccion', 'digital')} "
          f"({m.get('estrategia_titulos', 'tipografia_digital')})\n")
    for detail in m.get("detalle_patrones_eliminados", []):
        print(f"Patrón eliminado: {detail['patron']}")
        print(f"Tipo: {detail['tipo']} ({detail['area']})")
        print(f"Número de apariciones: {detail['apariciones']}")
        print("Páginas afectadas: " + ", ".join(map(str, detail["paginas"])) + "\n")
    print(f"Índice:\n{m.get('chunks_indice', 0)} chunks; páginas "
          f"{', '.join(map(str, m.get('paginas_indice', []))) or 'ninguna'}\n")
    print("Modelo:\nALIA" + f" ({report.model_id})\n")
    print(f"Dimensión:\n{report.dimension}\n")
    print(f"Device:\n{report.device}\n")
    print(f"Embeddings generados:\n{m['embeddings']}\n")
    print(f"Tiempos (s):\nextracción {m['tiempo_extraccion_s']} | limpieza+chunking {m['tiempo_limpieza_chunking_s']} | "
          f"embeddings {m['tiempo_embeddings_s']} | guardado {m['tiempo_guardado_s']} | total {m['tiempo_total_s']}\n")
    for warning in report.warnings:
        print(f"ADVERTENCIA: {warning}")
    status = {"indexado": "", "reindexado": " (reindexado)", "ya_indexado": " (ya estaba indexado; sin cambios)"}
    print(f"Estado:\n{report.estado.upper()}{status[report.status]}")


if __name__ == "__main__":
    sys.exit(main())
