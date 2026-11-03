"""Segmentación por tokens que respeta la estructura del documento.

Prioridades, de mayor a menor:
1. un título siempre abre un fragmento nuevo (y no arrastra solapamiento
   de la sección anterior);
2. los párrafos y elementos de lista se agregan enteros mientras quepan;
3. un párrafo demasiado largo se divide por oraciones;
4. solo una oración que por sí sola excede el tamaño se corta por tokens.

El solapamiento se construye con oraciones completas del final del fragmento
anterior, sin superar `chunk_overlap_tokens`. Un fragmento puede cruzar páginas
y conserva `page_start`/`page_end`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
import os
import re

from .cleaner import ContentType, Paragraph
from .tokenizer import TokenCounter


DEFAULT_CHUNK_SIZE = 450
DEFAULT_CHUNK_OVERLAP = 75

_ABBREVIATIONS = {
    "dr", "dra", "sr", "sra", "srta", "ud", "uds", "etc", "ej", "p", "pág", "págs", "fig", "figs",
    "tab", "núm", "nº", "vol", "aprox", "art", "cap", "ed", "al", "vs", "máx", "mín", "min",
    "max", "approx", "lic", "enf", "prof", "dpto", "av", "cf", "op", "cit",
}
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[¿¡\"«(\[]?[A-ZÁÉÍÓÚÑÜ0-9•])")


@dataclass(frozen=True)
class ChunkingConfig:
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE
    chunk_overlap_tokens: int = DEFAULT_CHUNK_OVERLAP

    def __post_init__(self) -> None:
        if self.chunk_size_tokens < 8:
            raise ValueError("CHUNK_SIZE_TOKENS debe ser al menos 8.")
        if not 0 <= self.chunk_overlap_tokens < self.chunk_size_tokens:
            raise ValueError("CHUNK_OVERLAP_TOKENS debe estar entre 0 y CHUNK_SIZE_TOKENS - 1.")

    @classmethod
    def from_env(cls) -> "ChunkingConfig":
        try:
            size = int(os.getenv("CHUNK_SIZE_TOKENS", str(DEFAULT_CHUNK_SIZE)))
            overlap = int(os.getenv("CHUNK_OVERLAP_TOKENS", str(DEFAULT_CHUNK_OVERLAP)))
        except ValueError as exc:
            raise ValueError("CHUNK_SIZE_TOKENS y CHUNK_OVERLAP_TOKENS deben ser enteros.") from exc
        return cls(size, overlap)


@dataclass(frozen=True)
class Chunk:
    order: int  # 1-based
    text: str
    page_start: int
    page_end: int
    section: str | None
    token_count: int
    content_type: ContentType = "contenido"


@dataclass(frozen=True)
class _Unit:
    text: str
    page_start: int
    page_end: int
    section: str | None
    tokens: int
    paragraph: int  # identifica el párrafo de origen para elegir el separador
    is_heading: bool
    content_type: ContentType
    heading_size: float | None


def split_sentences(text: str) -> list[str]:
    """Divide en oraciones sin cortar tras abreviaturas habituales ni iniciales."""
    sentences, start = [], 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        before = text[start:match.start()]
        last_word = re.split(r"\s+", before.strip())[-1].rstrip(".!?").lower() if before.strip() else ""
        if last_word in _ABBREVIATIONS or len(last_word) == 1 and last_word.isalpha():
            continue
        sentences.append(text[start:match.start()].strip())
        start = match.end()
    sentences.append(text[start:].strip())
    return [sentence for sentence in sentences if sentence]


def chunk_paragraphs(
    paragraphs: Sequence[Paragraph], counter: TokenCounter, config: ChunkingConfig
) -> list[Chunk]:
    units = _to_units(paragraphs, counter, config.chunk_size_tokens)
    chunks: list[Chunk] = []
    current: list[_Unit] = []
    carried = 0  # cuántas unidades iniciales de `current` son solapamiento

    def emit() -> None:
        text = _join(current)
        chunks.append(
            Chunk(
                order=len(chunks) + 1,
                text=text,
                page_start=min(unit.page_start for unit in current),
                page_end=max(unit.page_end for unit in current),
                section=current[0].section,
                token_count=counter.count(text),
                content_type=current[0].content_type,
            )
        )

    def finish_orphan_headings() -> None:
        """Conserva un rótulo final de la sección previa sin contaminar la nueva.

        Si cabe, se adjunta al chunk anterior; así un título mayor en la página
        siguiente marca frontera sin crear un chunk minúsculo solo para el
        rótulo que cerraba la sección anterior.
        """
        nonlocal current, carried
        if chunks and current and all(unit.is_heading for unit in current):
            previous = chunks[-1]
            combined = previous.text + "\n\n" + _join(current)
            if previous.content_type == current[0].content_type:
                if counter.count(combined) <= config.chunk_size_tokens:
                    chunks[-1] = Chunk(
                        previous.order, combined, min(previous.page_start, current[0].page_start),
                        max(previous.page_end, current[-1].page_end), previous.section,
                        counter.count(combined), previous.content_type,
                    )
                else:
                    emit()
                current, carried = [], 0

    for unit in units:
        new_units = current[carried:]
        if current and unit.content_type != current[0].content_type:
            if new_units:
                emit()
            current, carried = [], 0
        elif (unit.is_heading and new_units and all(existing.is_heading for existing in new_units)
              and unit.heading_size is not None
              and max(existing.heading_size or unit.heading_size for existing in new_units)
              < unit.heading_size - 0.5):
            finish_orphan_headings()
        elif unit.is_heading and any(not u.is_heading for u in new_units):
            emit()
            current, carried = [], 0
        elif unit.is_heading and not new_units:
            current, carried = [], 0  # no arrastrar solapamiento a otra sección
        elif current and counter.count(_join([*current, unit])) > config.chunk_size_tokens:
            if new_units:
                emit()
                current = _overlap_tail(current, unit, counter, config)
            else:  # el solapamiento no deja sitio: se descarta
                current = []
            carried = len(current)
        current.append(unit)

    if current[carried:]:
        emit()
    return chunks


def _to_units(paragraphs: Sequence[Paragraph], counter: TokenCounter, max_tokens: int) -> list[_Unit]:
    units: list[_Unit] = []
    section: str | None = None
    content_type: ContentType = "contenido"
    for index, paragraph in enumerate(paragraphs):
        if paragraph.content_type != content_type:
            section = None
            content_type = paragraph.content_type
        if paragraph.kind == "heading":
            section = paragraph.text
            pieces = [paragraph.text]
        else:
            pieces = [paragraph.text] if counter.count(paragraph.text) <= max_tokens else split_sentences(paragraph.text)
        for piece in pieces:
            for part in counter.split(piece, max_tokens) if counter.count(piece) > max_tokens else [piece]:
                units.append(
                    _Unit(
                        text=part,
                        page_start=paragraph.page_start,
                        page_end=paragraph.page_end,
                        section=section,
                        tokens=counter.count(part),
                        paragraph=index,
                        is_heading=paragraph.kind == "heading",
                        content_type=paragraph.content_type,
                        heading_size=paragraph.heading_size,
                    )
                )
    return units


def _overlap_tail(
    emitted: list[_Unit], following: _Unit, counter: TokenCounter, config: ChunkingConfig
) -> list[_Unit]:
    """Últimas oraciones del fragmento emitido que caben en el solapamiento."""
    tail: list[_Unit] = []
    for unit in reversed(emitted):
        if unit.is_heading:
            break
        candidate = [unit, *tail]
        if counter.count(_join(candidate)) > config.chunk_overlap_tokens:
            break
        tail = candidate
    # Paragraphs enteros pueden no admitir solapamiento; se reintenta por oraciones.
    if not tail and emitted and not emitted[-1].is_heading:
        last = emitted[-1]
        sentences = split_sentences(last.text)
        for sentence in reversed(sentences[1:]):
            candidate_text = " ".join([sentence, *(u.text for u in tail)])
            if counter.count(candidate_text) > config.chunk_overlap_tokens:
                break
            tail.insert(0, _Unit(sentence, last.page_end, last.page_end, last.section,
                                 counter.count(sentence), last.paragraph, False, last.content_type, None))
    while tail and counter.count(_join([*tail, following])) > config.chunk_size_tokens:
        tail.pop(0)
    return tail


def _join(units: Sequence[_Unit]) -> str:
    parts: list[str] = []
    for previous, unit in zip([None, *units], units):
        if previous is not None:
            parts.append(" " if previous.paragraph == unit.paragraph else "\n\n")
        parts.append(unit.text)
    return "".join(parts)
