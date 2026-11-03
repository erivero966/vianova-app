#!/usr/bin/env python3
"""Exporta evidencia de chunks sin embeddings, retrieval ni escrituras en la BD.

Reutiliza extracción, limpieza y segmentación existentes. La clasificación de
títulos es solamente diagnóstica y nunca se entrega al pipeline.
"""

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime
import html
import json
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.embeddings.registry import EMBEDDING_MODELS
from src.ingestion import ChunkingConfig, HFTokenCounter, chunk_paragraphs, clean_document, extract_pdf, sha256_file
from src.ingestion.cleaner import CLEANER_VERSION


def heading_label(text: str) -> tuple[str, str]:
    """Etiquetas orientativas del informe, no reglas de limpieza."""
    words = re.findall(r"[^\W\d_]+", text, re.UNICODE)
    if any(re.search(r"[a-záéíóúüñ][A-ZÁÉÍÓÚÜÑ]", word) for word in words):
        return "probablemente ruido OCR", "Mayúsculas intercaladas dentro de palabra."
    if re.match(r"^[|>+]|^Y[”\"]", text) or any(
        len(word) >= 4 and not re.search(r"[aeiouáéíóúüAEIOUÁÉÍÓÚÜ]", word) for word in words
    ):
        return "probablemente ruido OCR", "Símbolos iniciales o palabra sin vocales; verificar visualmente."
    if re.search(r"\b(?:código|emisor|institucional|departamento|instituto)\b", text, re.I):
        return "dudoso", "Posible rótulo administrativo o encabezado repetido."
    if len(words) < 2:
        return "dudoso", "Palabra aislada: puede ser título o artefacto."
    if text.endswith((" DE", " DEL", " EN", " LA")):
        return "dudoso", "Posible título truncado o continuación entre bloques."
    if text.isupper() and len(words) >= 2:
        return "probablemente válido", "Frase breve en mayúsculas; pendiente de comprobación contextual."
    return "dudoso", "No hay evidencia textual suficiente para decidir automáticamente."


def collect(pdf: Path) -> dict:
    extraction = extract_pdf(pdf)
    paragraphs, cleaning = clean_document(extraction)
    config = ChunkingConfig.from_env()
    counter = HFTokenCounter.from_pretrained(EMBEDDING_MODELS["alia"])
    chunks = chunk_paragraphs(paragraphs, counter, config)
    headings = [p for p in paragraphs if p.kind == "heading"]
    counts = Counter(p.text for p in headings)
    title_rows = []
    for number, heading in enumerate(headings, 1):
        label, reason = heading_label(heading.text)
        title_rows.append({
            "id": f"H{number:03d}", "titulo": heading.text,
            "pagina": heading.page_start, "apariciones": counts[heading.text],
            "clasificacion_inicial": label, "motivo": reason,
            "chunks_con_texto": [f"C{c.order:03d}" for c in chunks
                                if c.page_start <= heading.page_start <= c.page_end and heading.text in c.text],
            "chunks_con_seccion": [f"C{c.order:03d}" for c in chunks if c.section == heading.text],
        })
    return {
        "generado_en": datetime.now(ZoneInfo("America/Lima")).isoformat(timespec="seconds"),
        "pdf": str(pdf.resolve()), "sha256_pdf": sha256_file(pdf),
        "original": str(extraction.source_path) if extraction.source_path else None,
        "sha256_original": extraction.source_sha256,
        "sha256_provenance": sha256_file(extraction.provenance_path) if extraction.provenance_path else None,
        "extractor": extraction.extractor_version, "cleaner_version": CLEANER_VERSION,
        "tokenizer": counter.name, "config": asdict(config),
        "limpieza": asdict(cleaning),
        "paginas": [{"pagina": p.page, "caracteres": p.char_count, "texto": p.text,
                     "chunks": [f"C{c.order:03d}" for c in chunks if c.page_start <= p.page <= c.page_end]}
                    for p in extraction.pages],
        "paginas_con_texto": extraction.pages_with_text,
        "caracteres": extraction.total_chars, "ratio_ilegibles": extraction.garbage_ratio,
        "titulos": title_rows,
        "chunks": [{"id": f"C{c.order:03d}", **asdict(c)} for c in chunks],
    }


def cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown(data: dict, json_name: str, manual_name: str) -> str:
    chunks = data["chunks"]
    tokens = [c["token_count"] for c in chunks]
    lines = [
        "# Revisión documental de chunks OCR", "",
        f"[Conclusiones de la revisión manual]({manual_name}) · [Datos completos reproducibles]({json_name})", "",
        "Este inventario no constituye aprobación para ingesta. La clasificación inicial de títulos es heurística, "
        "exclusiva de este informe, y puede contener falsos positivos.", "",
        f"Generación: {data['generado_en']}", "",
        f"PDF: `{data['pdf']}`", f"SHA-256: `{data['sha256_pdf']}`", "",
        f"Fuente original: `{data['original']}`", f"SHA-256 original: `{data['sha256_original']}`", "",
        f"SHA-256 ficha: `{data['sha256_provenance']}`", "",
        f"Origen: **{data['limpieza']['extraction_origin']}**. Estrategia: `{data['limpieza']['heading_strategy']}`.",
        f"Extractor {data['extractor']}; limpieza {data['cleaner_version']}; tokenizer `{data['tokenizer']}`.",
        f"Configuración: {data['config']['chunk_size_tokens']} tokens, solapamiento {data['config']['chunk_overlap_tokens']}.", "",
        f"Páginas: {len(data['paginas'])}; con texto: {data['paginas_con_texto']}; caracteres: {data['caracteres']}; "
        f"ilegibles Unicode: {data['ratio_ilegibles']:.2%} (no mide exactitud del reconocimiento).",
        f"Títulos: {len(data['titulos'])} apariciones; {len({h['titulo'] for h in data['titulos']})} textos distintos.",
        f"Chunks: {len(chunks)}; con sección: {sum(c['section'] is not None for c in chunks)}; "
        f"multipágina: {sum(c['page_end'] > c['page_start'] for c in chunks)}.",
    ]
    if tokens:
        lines.append(f"Tokens mín/promedio/máx: {min(tokens)} / {sum(tokens)/len(tokens):.1f} / {max(tokens)}.")
    lines.extend(["", "Las páginas son físicas, 1-based. Un rango expresa procedencia; no garantiza que todas "
                  "las páginas intermedias aporten texto. Los IDs Cxxx son temporales y dependen de hashes/configuración.",
                  "", "## Inventario de títulos", ""])
    for group in ("probablemente válido", "probablemente ruido OCR", "dudoso"):
        selected = [h for h in data["titulos"] if h["clasificacion_inicial"] == group]
        lines.extend([f"### {group} ({len(selected)} apariciones)", "",
                      "| ID | Título | Página | Apariciones exactas | Chunks con texto | Motivo |",
                      "|---|---|---:|---:|---|---|"])
        for h in selected:
            lines.append("| " + " | ".join(map(cell, [h["id"], h["titulo"], h["pagina"], h["apariciones"],
                                                       ", ".join(h["chunks_con_texto"]), h["motivo"]])) + " |")
        lines.append("")
    lines.extend(["## Cobertura por página", "", "| Página | Caracteres | IDs con rango que intersecta la página |",
                  "|---:|---:|---|"])
    for p in data["paginas"]:
        lines.append(f"| {p['pagina']} | {p['caracteres']} | {', '.join(p['chunks'])} |")
    lines.extend(["", "## Inventario completo de chunks", "",
                  "Se muestran los primeros 500 caracteres (o todo el texto si es menor). "
                  "El desplegable y el JSON conservan el texto completo para revisar también los finales.", ""])
    for c in chunks:
        lines.extend([f"### {c['id']}", "",
                      f"Página inicio: {c['page_start']} · Página fin: {c['page_end']} · Tokens: {c['token_count']} · "
                      f"tipo_contenido: `{c['content_type']}`", "", f"Sección: {cell(c['section'] or '—')}", "",
                      "<pre>" + html.escape(c["text"][:500]) + ("…" if len(c["text"]) > 500 else "") + "</pre>", "",
                      "<details><summary>Texto completo</summary>", "",
                      "<pre>" + html.escape(c["text"]) + "</pre>", "", "</details>", ""])
    return "\n".join(lines) + "\n"


def default_output(pdf: Path) -> Path:
    # Alias de entrega solicitado; afecta solo al nombre del informe, nunca al procesamiento.
    names = {"inen_paciente_oncologico_inmunodeprimido_2020_ocr": "ocr_inen_inmunodeprimido"}
    stem = names.get(pdf.stem, pdf.stem)
    return PROJECT_ROOT / "eval" / f"{stem}_chunks_review.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--paginas-visuales", help="Páginas físicas del original a renderizar, separadas por comas.")
    args = parser.parse_args()
    output = (args.salida or default_output(args.pdf)).resolve()
    if not output.is_relative_to(PROJECT_ROOT / "eval") or output.suffix != ".md":
        parser.error("La salida debe ser un archivo .md dentro de eval/.")
    json_path = output.with_suffix(".json")
    if output.exists() or json_path.exists():
        parser.error("El informe o JSON ya existe; use --salida con otro nombre para conservar la revisión.")
    data = collect(args.pdf)
    pages = sorted(set(int(p.strip()) for p in args.paginas_visuales.split(","))) if args.paginas_visuales else []
    if pages and (min(pages) < 1 or max(pages) > len(data["paginas"])):
        parser.error("Página visual fuera del documento.")
    output.parent.mkdir(parents=True, exist_ok=True)
    manual_name = output.stem.removesuffix("_chunks_review") + "_revision_manual.md"
    output.write_text(markdown(data, json_path.name, manual_name), encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if pages:
        import pymupdf

        image_dir = output.parent / (output.stem.removesuffix("_chunks_review") + "_evidencia")
        image_dir.mkdir(exist_ok=True)
        with pymupdf.open(data["original"] or args.pdf) as doc:
            for page in pages:
                target = image_dir / f"original_p{page:03d}.png"
                if not target.exists():
                    doc[page - 1].get_pixmap(dpi=150).save(target)
        print(f"Páginas originales renderizadas: {image_dir}")
    print(f"Informe: {output}\nDatos completos: {json_path}\nChunks: {len(data['chunks'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
