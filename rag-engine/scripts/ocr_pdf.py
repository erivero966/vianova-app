#!/usr/bin/env python3
"""Genera un derivado OCR trazable de un PDF escaneado aprobado; no indexa.

Uso:
  python scripts/ocr_pdf.py corpus/aprobados/documento.pdf
"""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion import InvalidPdfError
from src.ocr import OcrDependencyError, OcrError, process_scanned_pdf


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path, help="PDF original dentro de corpus/aprobados/.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = process_scanned_pdf(args.pdf)
    except OcrDependencyError as exc:
        print(f"ERROR DE DEPENDENCIAS:\n{exc}")
        return 3
    except (OcrError, InvalidPdfError) as exc:
        print(f"ERROR: {exc}")
        return 2

    before, after = report.original_extraction, report.output_extraction
    print("\nOCR completado; el documento NO fue indexado.\n")
    print(f"Archivo original:\n{report.original.relative_to(PROJECT_ROOT)}")
    print(f"SHA-256 original:\n{report.sha256_original}\n")
    print(f"Archivo OCR:\n{report.output.relative_to(PROJECT_ROOT)}")
    print(f"SHA-256 OCR:\n{report.sha256_ocr}\n")
    print(f"Motor OCR:\nOCRmyPDF {report.tools.ocrmypdf_version} + Tesseract {report.tools.tesseract_version}")
    print("Idioma:\nspa\n")
    print("Validación automática:")
    print(f"  Páginas: {after.page_count} (original: {before.page_count})")
    print(f"  Páginas con texto: {after.pages_with_text} (original: {before.pages_with_text})")
    print(f"  Caracteres: {after.total_chars} (original: {before.total_chars})")
    print(f"  Caracteres ilegibles: {after.garbage_ratio:.2%}")
    print(f"\nTrazabilidad:\n{report.provenance.relative_to(PROJECT_ROOT)}")
    print("\nSiguiente paso obligatorio (solo inspección; no indexa):")
    print(f"python scripts/inspect_pdf.py {report.output.relative_to(PROJECT_ROOT)} --paginas --chunks")
    print("\nMuestreo manual mínimo sugerido: " + ", ".join(map(str, report.sample_pages)))
    print("Compare visualmente original vs. OCR y registre errores antes de habilitar la ingesta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
