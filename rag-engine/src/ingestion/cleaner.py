"""Limpieza conservadora del texto extraído.

Solo corrige forma, nunca contenido:
- normalización Unicode NFC, ligaduras tipográficas, espacios especiales;
- espacios repetidos y saltos de línea internos de un párrafo;
- palabras partidas con guion al final de línea (minúscula + "-" / minúscula);
- encabezados y pies de página repetidos, solo con alta confianza.

No resume, no parafrasea, no reordena y no reconstruye tablas: el texto de
una tabla queda como líneas consecutivas en el orden que da el PDF.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re
import unicodedata
from typing import Literal

from .pdf_extractor import ExtractedPage, ExtractionResult, TextBlock, TextLine


CLEANER_VERSION = "3"

# Zona exterior donde una línea puede ser candidata de maquetación. Se mantiene
# una zona estricta del 10 % y se amplía hasta el 15 % solo cuando además hay
# recurrencia y una posición vertical estable.
STRICT_MARGIN_RATIO = 0.10
LAYOUT_MARGIN_RATIO = 0.125
# Un patrón se considera de maquetación si aparece en la zona de margen de al
# menos esta fracción de páginas con texto (y en un mínimo absoluto de páginas).
REPEAT_PAGE_RATIO = 0.50
REPEAT_MIN_PAGES = 3
POSITIONAL_REPEAT_RATIO = 0.30
PARITY_REPEAT_RATIO = 0.75
MAX_POSITION_SPREAD_RATIO = 0.025

# Un bloque es título si es corto, no termina como oración y su tipografía lo
# distingue del cuerpo (más grande o íntegramente en negrita).
HEADING_SIZE_RATIO = 1.15
HEADING_MAX_CHARS = 150
HEADING_MAX_WORDS = 16

# La capa OCR no conserva una tipografía semántica fiable. En ese origen se
# exigen señales textuales además de cualquier diferencia de tamaño/negrita.
OCR_HEADING_MAX_CHARS = 120
OCR_HEADING_MAX_WORDS = 12
OCR_HEADING_MAX_LINES = 2
OCR_UPPERCASE_RATIO = 0.70
OCR_TITLECASE_RATIO = 0.70
OCR_MAX_FONT_SIZE_RATIO = 3.0
OCR_REPEATED_HEADING_MIN_PAGES = 3
OCR_REPEATED_HEADING_PAGE_RATIO = 0.10
OCR_MIN_HORIZONTAL_LINE_RATIO = 0.50
_NUMBERED_HEADING = re.compile(r"^\s*(?:(?:\d+(?:\.\d+){0,4}|[IVXLCDM]+)[.)]?)[ \t]+", re.I)

_CHAR_MAP = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    "­": "", "​": "", "‌": "", "‍": "", "﻿": "",
    "": "•", "": "•", "": "•", "": "•", "▪": "•", "●": "•",
}
_CHAR_TABLE = str.maketrans(_CHAR_MAP)
_LIST_MARKER = re.compile(r"^\s*(?:[•\-–*·▪►✓]|\(?\d{1,2}[.)]|\(?[a-zA-Z][.)])\s+")
_HYPHEN_END = re.compile(r"([a-záéíóúüñ])-$")
_STARTS_LOWER = re.compile(r"^[a-záéíóúüñ]")
_SENTENCE_END = re.compile(r"[.!?:;)\]»\"”]$")
_SPACES = re.compile(r"[ \t]+")

ParagraphKind = Literal["heading", "paragraph", "list_item"]
ContentType = Literal["contenido", "indice"]


@dataclass(frozen=True)
class Paragraph:
    text: str
    kind: ParagraphKind
    page_start: int
    page_end: int
    content_type: ContentType = "contenido"
    heading_size: float | None = None


@dataclass
class CleaningReport:
    removed_patterns: dict[str, int] = field(default_factory=dict)  # patrón -> páginas
    removed_lines: int = 0
    hyphen_joins: int = 0
    cross_page_joins: int = 0
    headings: int = 0
    body_font_size: float | None = None
    removed_pattern_details: list[dict[str, object]] = field(default_factory=list)
    index_pages: list[int] = field(default_factory=list)
    extraction_origin: Literal["digital", "ocr"] = "digital"
    heading_strategy: str = "tipografia_digital"
    ocr_typography_only_rejected: int = 0
    ocr_repeated_heading_texts: int = 0
    ocr_unreliable_orientation_pages: list[int] = field(default_factory=list)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_CHAR_TABLE)
    return _SPACES.sub(" ", text).strip()


def clean_document(
    extraction: ExtractionResult, *, index_pages: set[int] | None = None
) -> tuple[list[Paragraph], CleaningReport]:
    report = CleaningReport()
    report.extraction_origin = extraction.extraction_origin
    report.heading_strategy = (
        "estructura_textual_ocr" if extraction.extraction_origin == "ocr" else "tipografia_digital"
    )
    # Toda página con algún texto se conserva: el umbral de "página vacía" solo
    # sirve para diagnosticar OCR, nunca para descartar contenido.
    pages = [page for page in extraction.pages if page.blocks]
    repeated = _detect_repeated_margin_lines(pages)
    report.removed_patterns = {pattern: item.count for pattern, item in repeated.items()}
    report.removed_pattern_details = [item.as_dict() for item in repeated.values()]

    kept: dict[int, list[TextBlock]] = {}
    for page in pages:
        blocks = []
        for block in page.blocks:
            lines = tuple(
                line for line in block.lines
                if not (_in_layout_margin(line, page) and _pattern(line.text) in repeated)
            )
            report.removed_lines += len(block.lines) - len(lines)
            if lines:
                blocks.append(TextBlock(lines))
        kept[page.page] = blocks

    detected_index_pages = _detect_index_pages(kept)
    if index_pages:
        unknown = sorted(set(index_pages) - set(kept))
        if unknown:
            raise ValueError(f"Páginas de índice fuera del documento: {unknown}.")
        detected_index_pages.update(index_pages)
    report.index_pages = sorted(detected_index_pages)

    report.body_font_size = _body_font_size(kept.values())
    repeated_ocr_headings = (
        _repeated_ocr_heading_texts(kept) if extraction.extraction_origin == "ocr" else set()
    )
    report.ocr_repeated_heading_texts = len(repeated_ocr_headings)
    reliable_ocr_pages = set(kept)
    if extraction.extraction_origin == "ocr":
        reliable_ocr_pages = _ocr_heading_reliable_pages(kept)
        report.ocr_unreliable_orientation_pages = sorted(set(kept) - reliable_ocr_pages)
    paragraphs: list[Paragraph] = []
    for page_number, blocks in kept.items():
        page_paragraphs = []
        for block in blocks:
            content_type: ContentType = "indice" if page_number in detected_index_pages else "contenido"
            page_paragraphs.extend(_block_to_paragraphs(
                block,
                page_number,
                report,
                content_type,
                extraction.extraction_origin,
                repeated_ocr_headings,
                page_number in reliable_ocr_pages,
            ))
        if page_paragraphs and paragraphs and _continues(paragraphs[-1], page_paragraphs[0]):
            previous, first = paragraphs.pop(), page_paragraphs.pop(0)
            text, hyphenated = _join_lines(previous.text, first.text)
            report.hyphen_joins += hyphenated
            report.cross_page_joins += 1
            paragraphs.append(Paragraph(
                text, "paragraph", previous.page_start, first.page_end, previous.content_type, None
            ))
        paragraphs.extend(page_paragraphs)
    report.headings = sum(paragraph.kind == "heading" for paragraph in paragraphs)
    return paragraphs, report


def _pattern(text: str) -> str:
    """Clave de comparación: minúsculas, dígitos -> '#', espacios colapsados."""
    return re.sub(r"\d+", "#", normalize_text(text).lower())


def _in_strict_margin(line: TextLine, page: ExtractedPage) -> bool:
    margin = page.height * STRICT_MARGIN_RATIO
    return line.y1 <= margin or line.y0 >= page.height - margin


def _in_layout_margin(line: TextLine, page: ExtractedPage) -> bool:
    margin = page.height * LAYOUT_MARGIN_RATIO
    return line.y1 <= margin or line.y0 >= page.height - margin


@dataclass(frozen=True)
class _RepeatedPattern:
    pattern: str
    pages: tuple[int, ...]
    area: Literal["header", "footer"]

    @property
    def count(self) -> int:
        return len(self.pages)

    def as_dict(self) -> dict[str, object]:
        return {
            "patron": self.pattern,
            "tipo": "header/footer",
            "area": self.area,
            "apariciones": self.count,
            "paginas": list(self.pages),
        }


def _detect_repeated_margin_lines(pages: list[ExtractedPage]) -> dict[str, _RepeatedPattern]:
    if len(pages) < REPEAT_MIN_PAGES:
        return {}
    occurrences: dict[tuple[str, str], list[tuple[int, float, bool]]] = defaultdict(list)
    for page in pages:
        for block in page.blocks:
            for line in block.lines:
                pattern = _pattern(line.text)
                if not pattern or not _in_layout_margin(line, page):
                    continue
                area = "header" if line.y1 <= page.height * LAYOUT_MARGIN_RATIO else "footer"
                y_ratio = (line.y0 + line.y1) / (2 * page.height)
                occurrences[(pattern, area)].append((page.page, y_ratio, _in_strict_margin(line, page)))

    text_pages = {page.page for page in pages}
    parity_pages = {
        parity: {number for number in text_pages if number % 2 == parity}
        for parity in (0, 1)
    }
    found: dict[str, _RepeatedPattern] = {}
    for (pattern, area), rows in occurrences.items():
        page_numbers = {row[0] for row in rows}
        if len(page_numbers) < REPEAT_MIN_PAGES:
            continue
        positions = [row[1] for row in rows]
        stable_position = max(positions) - min(positions) <= MAX_POSITION_SPREAD_RATIO
        global_ratio = len(page_numbers) / len(text_pages)
        parity_repeated = any(
            parity_pages[parity]
            and len(page_numbers & parity_pages[parity]) / len(parity_pages[parity]) >= PARITY_REPEAT_RATIO
            for parity in (0, 1)
        )
        strict_global = all(row[2] for row in rows) and global_ratio >= REPEAT_PAGE_RATIO
        positional_repeat = stable_position and global_ratio >= POSITIONAL_REPEAT_RATIO
        if strict_global or parity_repeated and stable_position or positional_repeat:
            item = _RepeatedPattern(pattern, tuple(sorted(page_numbers)), area)
            # Una misma clave textual en ambos márgenes es excepcional; se
            # conserva la evidencia con mayor número de páginas.
            if pattern not in found or item.count > found[pattern].count:
                found[pattern] = item
    return dict(sorted(found.items(), key=lambda item: -item[1].count))


_INDEX_HEADING = re.compile(r"^(?:índice|indice|contenido|tabla de contenidos)(?: general)?$", re.I)
_TOC_ENTRY = re.compile(r".{2,}?(?:\.{2,}|\s{2,})\s*\d{1,4}\s*$")


def _detect_index_pages(kept: dict[int, list[TextBlock]]) -> set[int]:
    """Clasifica índices con evidencia explícita y estructura título+número.

    La página se conserva. La clasificación solo evita que sus fragmentos
    participen en la recuperación normal.
    """
    detected: set[int] = set()
    for page_number, blocks in kept.items():
        lines = [normalize_text(line.text) for block in blocks for line in block.lines]
        lines = [line for line in lines if line]
        if not lines:
            continue
        heading = any(_INDEX_HEADING.fullmatch(line.rstrip(":")) for line in lines[:4])
        entries = sum(bool(_TOC_ENTRY.fullmatch(line)) for line in lines)
        entry_ratio = entries / len(lines)
        # Sin etiqueta explícita se exige una señal mucho más fuerte para no
        # confundir una tabla numérica con una tabla de contenidos.
        if (heading and entries >= 3) or (entries >= 8 and entry_ratio >= 0.60):
            detected.add(page_number)
    return detected


def _body_font_size(blocks_per_page) -> float | None:
    sizes: Counter[float] = Counter()
    for blocks in blocks_per_page:
        for block in blocks:
            for line in block.lines:
                sizes[line.size] += len(line.text.strip())
    return sizes.most_common(1)[0][0] if sizes else None


def _is_heading(block: TextBlock, body_size: float | None) -> bool:
    text = normalize_text(" ".join(line.text for line in block.lines))
    if not text or len(block.lines) > 3 or len(text) > HEADING_MAX_CHARS:
        return False
    if len(text.split()) > HEADING_MAX_WORDS or not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]", text):
        return False
    if re.search(r"[.,;]$", text):
        return False
    if _LIST_MARKER.match(text) and not re.match(r"^\d", text):  # viñeta, no "2. Título"
        return False
    size = sum(line.size for line in block.lines) / len(block.lines)
    larger = body_size is not None and size >= body_size * HEADING_SIZE_RATIO
    bold = all(line.bold for line in block.lines)
    return larger or bold


def _is_ocr_heading(
    block: TextBlock,
    body_size: float | None,
    repeated_texts: set[str] | None = None,
    *,
    reliable_orientation: bool = True,
) -> bool:
    """Título OCR: la tipografía nunca basta por sí sola.

    Se conservan títulos compactos en mayúsculas y encabezados numerados. Los
    títulos en formato oración requieren simultáneamente estructura compacta,
    capitalización de título y diferenciación tipográfica. Esto sacrifica
    sensibilidad para evitar miles de secciones falsas en texto clínico OCR.
    """
    if not reliable_orientation:
        return False
    text = normalize_text(" ".join(line.text for line in block.lines))
    words = text.split()
    if (
        not text
        or len(block.lines) > OCR_HEADING_MAX_LINES
        or len(text) > OCR_HEADING_MAX_CHARS
        or not words
        or len(words) > OCR_HEADING_MAX_WORDS
        or not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", text)
    ):
        return False
    if repeated_texts and _pattern(text) in repeated_texts:
        return False
    # Tesseract puede representar texto vertical/invertido de tablas y
    # diagramas con tamaños de fuente extremos. No forma una sección lineal.
    if not all(_is_horizontal_line(line) for line in block.lines):
        return False
    # Un punto/coma final es evidencia fuerte de oración. Los dos puntos sí
    # son habituales en rótulos, pero no bastan sin otra señal.
    if re.search(r"[.;,]$", text):
        return False
    if _LIST_MARKER.match(text) and not _NUMBERED_HEADING.match(text):
        return False

    letters = [char for char in text if char.isalpha()]
    uppercase_ratio = sum(char.isupper() for char in letters) / len(letters)
    all_caps = len(letters) >= 4 and uppercase_ratio >= OCR_UPPERCASE_RATIO
    numbered = bool(_NUMBERED_HEADING.match(text))
    colon = text.endswith(":")
    lexical_words = [re.sub(r"^[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+|[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+$", "", word)
                     for word in words]
    lexical_words = [word for word in lexical_words if word]
    titlecase_ratio = (
        sum(word[0].isupper() for word in lexical_words) / len(lexical_words)
        if lexical_words else 0.0
    )
    title_case = len(lexical_words) >= 2 and titlecase_ratio >= OCR_TITLECASE_RATIO
    compact = len(words) <= 8 and len(text) <= 80
    size = sum(line.size for line in block.lines) / len(block.lines)
    if body_size is not None and size > body_size * OCR_MAX_FONT_SIZE_RATIO:
        return False
    typography = (
        (body_size is not None and size >= body_size * HEADING_SIZE_RATIO)
        or all(line.bold for line in block.lines)
    )

    if all_caps and compact:
        return True
    if numbered and compact and (all_caps or title_case or typography):
        return True
    if colon and compact and (all_caps or title_case) and typography:
        return True
    return title_case and compact and typography


def _repeated_ocr_heading_texts(kept: dict[int, list[TextBlock]]) -> set[str]:
    """Rótulos repetidos en muchas páginas no deben abrir secciones OCR.

    No se eliminan del contenido aquí: solo se neutraliza su valor estructural.
    Esto tolera coordenadas OCR imprecisas sin aplicar una limpieza destructiva.
    """
    occurrences: dict[str, set[int]] = defaultdict(set)
    for page, blocks in kept.items():
        for block in blocks:
            text = normalize_text(" ".join(line.text for line in block.lines))
            if text and len(text) <= OCR_HEADING_MAX_CHARS:
                occurrences[_pattern(text)].add(page)
    threshold = max(
        OCR_REPEATED_HEADING_MIN_PAGES,
        round(len(kept) * OCR_REPEATED_HEADING_PAGE_RATIO),
    )
    return {text for text, pages in occurrences.items() if len(pages) >= threshold}


def _ocr_heading_reliable_pages(kept: dict[int, list[TextBlock]]) -> set[int]:
    """Páginas OCR con flujo mayoritariamente horizontal de izquierda a derecha."""
    reliable: set[int] = set()
    for page, blocks in kept.items():
        lines = [line for block in blocks for line in block.lines]
        if not lines:
            continue
        horizontal = sum(_is_horizontal_line(line) for line in lines)
        if horizontal / len(lines) >= OCR_MIN_HORIZONTAL_LINE_RATIO:
            reliable.add(page)
    return reliable


def _is_horizontal_line(line: TextLine) -> bool:
    return line.direction[0] >= 0.95 and abs(line.direction[1]) <= 0.20


def _block_to_paragraphs(
    block: TextBlock,
    page: int,
    report: CleaningReport,
    content_type: ContentType,
    extraction_origin: Literal["digital", "ocr"],
    repeated_ocr_headings: set[str],
    reliable_ocr_orientation: bool,
) -> list[Paragraph]:
    digital_heading = _is_heading(block, report.body_font_size)
    is_heading = (
        _is_ocr_heading(
            block,
            report.body_font_size,
            repeated_ocr_headings,
            reliable_orientation=reliable_ocr_orientation,
        )
        if extraction_origin == "ocr"
        else digital_heading
    )
    if extraction_origin == "ocr" and digital_heading and not is_heading:
        report.ocr_typography_only_rejected += 1
    if is_heading:
        heading_size = sum(line.size for line in block.lines) / len(block.lines)
        return [Paragraph(
            normalize_text(" ".join(l.text for l in block.lines)), "heading", page, page,
            content_type, heading_size
        )]
    items: list[tuple[ParagraphKind, str]] = []
    for line in block.lines:
        text = normalize_text(line.text)
        if not text:
            continue
        if _LIST_MARKER.match(text):
            items.append(("list_item", text))
        elif items:
            kind, previous = items[-1]
            joined, hyphenated = _join_lines(previous, text)
            report.hyphen_joins += hyphenated
            items[-1] = (kind, joined)
        else:
            items.append(("paragraph", text))
    return [Paragraph(text, kind, page, page, content_type) for kind, text in items]


def _join_lines(left: str, right: str) -> tuple[str, int]:
    """Une dos líneas; reconstruye 'trata-' + 'miento' solo entre minúsculas."""
    if _HYPHEN_END.search(left) and _STARTS_LOWER.match(right):
        return left[:-1] + right, 1
    return f"{left} {right}", 0


def _continues(previous: Paragraph, following: Paragraph) -> bool:
    """Párrafo cortado por un salto de página: sin cierre de oración + minúscula."""
    return (
        previous.kind == "paragraph"
        and following.kind == "paragraph"
        and following.page_start == previous.page_end + 1
        and following.content_type == previous.content_type
        and not _SENTENCE_END.search(previous.text)
        and bool(_STARTS_LOWER.match(following.text))
    )
