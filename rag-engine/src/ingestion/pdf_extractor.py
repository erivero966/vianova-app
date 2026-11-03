"""Extracción página a página de PDFs con texto digital (PyMuPDF). Sin OCR.

Cada página conserva su número físico 1-based, su texto y sus bloques con
posición y tipografía, que luego usan la limpieza (encabezados/pies) y la
detección de secciones. Nunca se concatena el PDF en un único string.
"""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import unicodedata
from typing import Literal

import pymupdf

from ..config import PROJECT_ROOT


EXTRACTOR_NAME = "pymupdf"
# Binding PyMuPDF + motor MuPDF: ambos influyen en el texto extraído.
EXTRACTOR_VERSION = f"{pymupdf.VersionBind} (MuPDF {pymupdf.VersionFitz})"

# Una página con menos caracteres útiles se considera "sin texto".
MIN_PAGE_CHARS = 30
# Fracción de páginas sin texto a partir de la cual se exige revisión/OCR.
OCR_PAGE_RATIO = 0.20
# Fracción máxima de caracteres ilegibles (U+FFFD, uso privado, control).
MAX_GARBAGE_RATIO = 0.05


class InvalidPdfError(ValueError):
    """El archivo no existe, no es un PDF o no puede abrirse."""


ExtractionOrigin = Literal["digital", "ocr"]


@dataclass(frozen=True)
class ExtractionProvenance:
    origin: ExtractionOrigin
    provenance_path: Path | None = None
    source_path: Path | None = None
    source_sha256: str | None = None


@dataclass(frozen=True)
class TextLine:
    text: str
    size: float
    bold: bool
    y0: float
    y1: float
    direction: tuple[float, float] = (1.0, 0.0)


@dataclass(frozen=True)
class TextBlock:
    lines: tuple[TextLine, ...]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass(frozen=True)
class ExtractedPage:
    page: int  # 1-based, página física del PDF
    text: str
    blocks: tuple[TextBlock, ...]
    height: float
    image_count: int

    @property
    def char_count(self) -> int:
        return sum(1 for char in self.text if not char.isspace())

    @property
    def is_empty(self) -> bool:
        return self.char_count < MIN_PAGE_CHARS

    @property
    def possibly_needs_ocr(self) -> bool:
        """Página casi sin texto pero con imágenes: probablemente escaneada."""
        return self.is_empty and self.image_count > 0


@dataclass(frozen=True)
class ExtractionResult:
    path: Path
    page_count: int
    pages: tuple[ExtractedPage, ...]
    extractor: str = EXTRACTOR_NAME
    extractor_version: str = EXTRACTOR_VERSION
    warnings: tuple[str, ...] = field(default=())
    extraction_origin: ExtractionOrigin = "digital"
    provenance_path: Path | None = None
    source_path: Path | None = None
    source_sha256: str | None = None

    @property
    def pages_with_text(self) -> int:
        return sum(not page.is_empty for page in self.pages)

    @property
    def empty_pages(self) -> list[int]:
        return [page.page for page in self.pages if page.is_empty]

    @property
    def ocr_pages(self) -> list[int]:
        return [page.page for page in self.pages if page.possibly_needs_ocr]

    @property
    def total_chars(self) -> int:
        return sum(page.char_count for page in self.pages)

    @property
    def avg_chars_per_page(self) -> float:
        return self.total_chars / self.page_count if self.page_count else 0.0

    @property
    def garbage_ratio(self) -> float:
        text = "".join(page.text for page in self.pages)
        visible = [char for char in text if not char.isspace()]
        if not visible:
            return 0.0
        return sum(_is_garbage(char) for char in visible) / len(visible)

    @property
    def requires_ocr(self) -> bool:
        if not self.page_count:
            return False
        return len(self.empty_pages) / self.page_count >= OCR_PAGE_RATIO

    @property
    def is_valid(self) -> bool:
        """Extracción claramente inválida: sin texto o con texto ilegible."""
        return self.pages_with_text > 0 and self.garbage_ratio <= MAX_GARBAGE_RATIO

    def problems(self) -> list[str]:
        problems = []
        if self.pages_with_text == 0:
            problems.append("El PDF no contiene texto extraíble (posible documento escaneado).")
        elif self.garbage_ratio > MAX_GARBAGE_RATIO:
            problems.append(
                f"{self.garbage_ratio:.1%} de los caracteres son ilegibles "
                "(fuentes sin mapa Unicode); la extracción no es fiable."
            )
        if self.requires_ocr:
            problems.append(
                f"{len(self.empty_pages)} de {self.page_count} páginas no tienen texto "
                f"(umbral {OCR_PAGE_RATIO:.0%}): el PDF puede contener páginas escaneadas. "
                "Se requiere revisión/OCR antes de indexar."
            )
        return problems


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """SHA-256 de los bytes originales del archivo."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_pdf_file(path: str | Path) -> Path:
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise InvalidPdfError(f"No existe el archivo: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise InvalidPdfError(f"Se esperaba un archivo .pdf: {pdf_path.name}")
    with open(pdf_path, "rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise InvalidPdfError(f"El archivo no tiene cabecera PDF: {pdf_path.name}")
    return pdf_path


def extract_pdf(path: str | Path) -> ExtractionResult:
    pdf_path = validate_pdf_file(path)
    provenance = detect_extraction_provenance(pdf_path)
    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:  # PyMuPDF lanza varios tipos según el daño.
        raise InvalidPdfError(f"PyMuPDF no pudo abrir {pdf_path.name}: {exc}") from exc
    with document:
        if document.needs_pass:
            raise InvalidPdfError(f"{pdf_path.name} está protegido con contraseña.")
        pages = tuple(_extract_page(page) for page in document)
    return ExtractionResult(
        path=pdf_path,
        page_count=len(pages),
        pages=pages,
        extraction_origin=provenance.origin,
        provenance_path=provenance.provenance_path,
        source_path=provenance.source_path,
        source_sha256=provenance.source_sha256,
    )


def detect_extraction_provenance(path: str | Path) -> ExtractionProvenance:
    """Reconoce OCR solo mediante una ficha válida y ligada criptográficamente.

    La ausencia de ficha significa PDF digital. Si la ficha existe pero está
    dañada o no corresponde al archivo, se falla de forma cerrada: nunca se
    degrada silenciosamente a la estrategia tipográfica digital.
    """
    pdf_path = validate_pdf_file(path).resolve()
    provenance_path = pdf_path.with_suffix(".provenance.json")
    if not provenance_path.exists():
        return ExtractionProvenance("digital")
    try:
        data = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidPdfError(f"Ficha OCR inválida {provenance_path.name}: {exc}") from exc

    required = ("archivo_original", "sha256_original", "archivo_ocr", "sha256_ocr", "ocr_engine")
    missing = [field for field in required if not isinstance(data.get(field), str) or not data[field].strip()]
    if missing:
        raise InvalidPdfError(
            f"Ficha OCR incompleta {provenance_path.name}; faltan: {', '.join(missing)}."
        )
    recorded_ocr = _trace_path(data["archivo_ocr"])
    if recorded_ocr != pdf_path:
        raise InvalidPdfError(
            f"La ficha {provenance_path.name} apunta a otro derivado: {data['archivo_ocr']}."
        )
    actual_ocr_hash = sha256_file(pdf_path)
    if data["sha256_ocr"].lower() != actual_ocr_hash:
        raise InvalidPdfError(
            f"El SHA-256 del derivado no coincide con {provenance_path.name}; no es confiable."
        )
    source_path = _trace_path(data["archivo_original"])
    if not source_path.is_file():
        raise InvalidPdfError(f"La fuente original registrada no existe: {data['archivo_original']}.")
    actual_source_hash = sha256_file(source_path)
    if data["sha256_original"].lower() != actual_source_hash:
        raise InvalidPdfError(
            f"El SHA-256 de la fuente original no coincide con {provenance_path.name}."
        )
    return ExtractionProvenance(
        "ocr", provenance_path, source_path, actual_source_hash
    )


def _trace_path(value: str) -> Path:
    path = Path(value)
    return (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def _extract_page(page: pymupdf.Page) -> ExtractedPage:
    # Orden nativo del flujo de contenido (sin sort=True): ordenar por
    # coordenadas mezclaría columnas en maquetaciones a dos columnas.
    data = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
    blocks = []
    for raw_block in data["blocks"]:
        if raw_block.get("type") != 0:  # 1 = imagen
            continue
        lines = []
        for raw_line in raw_block["lines"]:
            spans = [span for span in raw_line["spans"] if span["text"]]
            text = "".join(span["text"] for span in spans)
            if not text.strip():
                continue
            visible = [span for span in spans if span["text"].strip()]
            weighted = sum(len(span["text"].strip()) for span in visible) or 1
            size = sum(span["size"] * len(span["text"].strip()) for span in visible) / weighted
            bold = all(_is_bold(span) for span in visible)
            direction = tuple(float(value) for value in raw_line.get("dir", (1.0, 0.0)))
            lines.append(TextLine(
                text, round(size, 1), bold, raw_line["bbox"][1], raw_line["bbox"][3], direction
            ))
        if lines:
            blocks.append(TextBlock(tuple(lines)))
    text = "\n\n".join(block.text for block in blocks)
    return ExtractedPage(
        page=page.number + 1,
        text=text,
        blocks=tuple(blocks),
        height=float(page.rect.height),
        image_count=len(page.get_images(full=False)),
    )


def _is_bold(span: dict) -> bool:
    return bool(span["flags"] & pymupdf.TEXT_FONT_BOLD) or "bold" in span["font"].lower()


def _is_garbage(char: str) -> bool:
    if char == "�":
        return True
    category = unicodedata.category(char)
    # Viñetas de fuentes Symbol/Wingdings llegan como uso privado; se toleran
    # en la limpieza, pero un PDF lleno de ellas no tiene texto real.
    return category in {"Co", "Cc", "Cs"}
