#!/usr/bin/env python3
"""Inspecciona un PDF antes de indexarlo: páginas, texto, OCR, limpieza y chunks.

No escribe en la base de datos ni carga el modelo en GPU.
Código de salida: 0 = apto, 2 = requiere revisión/OCR o extracción inválida.
"""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.embeddings.registry import EMBEDDING_MODELS
from src.ingestion import (
    ChunkingConfig,
    HFTokenCounter,
    InvalidPdfError,
    chunk_paragraphs,
    clean_document,
    extract_pdf,
    sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--paginas", action="store_true", help="Tabla de caracteres por página.")
    parser.add_argument("--chunks", action="store_true",
                        help="Simula la segmentación con el tokenizer de ALIA (sin GPU ni BD).")
    parser.add_argument("--mostrar", type=int, default=3, help="Chunks de ejemplo a mostrar con --chunks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        extraction = extract_pdf(args.pdf)
    except InvalidPdfError as exc:
        print(f"ERROR: {exc}")
        return 2

    print(f"Archivo:\n{args.pdf.name}\n")
    print(f"SHA-256:\n{sha256_file(args.pdf)}\n")
    print(f"Extractor:\nPyMuPDF {extraction.extractor_version}\n")
    print(f"Origen de extracción:\n{extraction.extraction_origin}\n")
    if extraction.provenance_path:
        print(f"Trazabilidad OCR:\n{extraction.provenance_path.name}\n")
        print(f"Fuente documental:\n{extraction.source_path}\n")
    print(f"Páginas:\n{extraction.page_count}\n")
    print(f"Páginas con texto:\n{extraction.pages_with_text}\n")
    print(f"Páginas sin texto:\n{len(extraction.empty_pages)}" + (f"  ({_pages(extraction.empty_pages)})" if extraction.empty_pages else "") + "\n")
    print(f"Caracteres extraídos:\n{extraction.total_chars}\n")
    print(f"Promedio caracteres/página:\n{extraction.avg_chars_per_page:.0f}\n")
    print(f"Caracteres ilegibles:\n{extraction.garbage_ratio:.2%}\n")
    print(f"Posible OCR requerido:\n{'SÍ' if extraction.requires_ocr or not extraction.is_valid else 'NO'}"
          + (f"  (páginas con imagen y sin texto: {_pages(extraction.ocr_pages)})" if extraction.ocr_pages else ""))

    if args.paginas:
        print("\nPágina  Caracteres  Imágenes  Estado")
        for page in extraction.pages:
            state = "posible OCR" if page.possibly_needs_ocr else "vacía" if page.is_empty else "ok"
            print(f"{page.page:>6}  {page.char_count:>10}  {page.image_count:>8}  {state}")

    problems = extraction.problems()
    if problems:
        print("\nADVERTENCIA:")
        for problem in problems:
            print(f"- {problem}")
    if not extraction.is_valid:
        print("\nExtracción inválida: no se debe indexar este PDF.")
        return 2

    paragraphs, cleaning = clean_document(extraction)
    print("\nLimpieza:")
    print(f"  Origen: {cleaning.extraction_origin}")
    print(f"  Estrategia de títulos: {cleaning.heading_strategy}")
    print(f"  Títulos detectados: {cleaning.headings} (cuerpo de texto: {cleaning.body_font_size} pt)")
    if cleaning.extraction_origin == "ocr":
        print(f"  Candidatos descartados por depender solo de tipografía OCR: "
              f"{cleaning.ocr_typography_only_rejected}")
        print(f"  Rótulos repetidos neutralizados como estructura: "
              f"{cleaning.ocr_repeated_heading_texts}")
        print("  Páginas sin títulos por orientación OCR no lineal: " + (
            _pages(cleaning.ocr_unreliable_orientation_pages)
            if cleaning.ocr_unreliable_orientation_pages else "ninguna"
        ))
    print(f"  Palabras con guion reconstruidas: {cleaning.hyphen_joins}")
    print(f"  Párrafos unidos entre páginas: {cleaning.cross_page_joins}")
    print(f"  Líneas de encabezado/pie eliminadas: {cleaning.removed_lines}")
    for detail in cleaning.removed_pattern_details:
        pages = detail["paginas"]
        print(f"    - Patrón eliminado: «{detail['patron']}»")
        print(f"      Tipo: {detail['tipo']} ({detail['area']})")
        print(f"      Número de apariciones: {detail['apariciones']}")
        print(f"      Páginas afectadas: {_pages(pages)}")
    print(f"  Páginas clasificadas como índice: {_pages(cleaning.index_pages) if cleaning.index_pages else 'ninguna'}")
    headings = [p for p in paragraphs if p.kind == "heading"]
    if headings:
        print("  Primeros títulos:")
        for heading in headings[:10]:
            print(f"    p. {heading.page_start}: {heading.text}")

    if args.chunks:
        config = ChunkingConfig.from_env()
        counter = HFTokenCounter.from_pretrained(EMBEDDING_MODELS["alia"])
        chunks = chunk_paragraphs(paragraphs, counter, config)
        tokens = [c.token_count for c in chunks]
        print(f"\nChunking ({config.chunk_size_tokens} tokens, solapamiento {config.chunk_overlap_tokens}, "
              f"tokenizer {counter.name}):")
        print(f"  Chunks: {len(chunks)}")
        if chunks:
            print(f"  Tokens min/promedio/max: {min(tokens)} / {sum(tokens) / len(tokens):.1f} / {max(tokens)}")
            print(f"  Con sección: {sum(c.section is not None for c in chunks)} | "
                  f"multipágina: {sum(c.page_end > c.page_start for c in chunks)}")
            for chunk in chunks[: max(args.mostrar, 0)]:
                pages = f"{chunk.page_start}" if chunk.page_start == chunk.page_end else f"{chunk.page_start}-{chunk.page_end}"
                print(f"\n  [chunk {chunk.order}] páginas {pages} | {chunk.token_count} tokens | sección: {chunk.section or '—'}")
                print(f"  Tipo de contenido: {chunk.content_type}")
                print("  " + chunk.text[:400].replace("\n", "\n  ") + ("…" if len(chunk.text) > 400 else ""))

    return 2 if extraction.requires_ocr else 0


def _pages(pages: list[int], limit: int = 15) -> str:
    return ", ".join(map(str, pages[:limit])) + (" …" if len(pages) > limit else "")


if __name__ == "__main__":
    sys.exit(main())
