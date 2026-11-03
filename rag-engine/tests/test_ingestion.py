"""Pruebas rápidas de la ingestión: PDFs sintéticos, sin BD, sin modelo, sin descargas."""

import hashlib
import json

import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
from transformers import PreTrainedTokenizerFast

from pdf_factory import CLINICAL_PAGES, build_pdf, build_scanned_pdf
from src.ingestion import (
    ChunkingConfig,
    DocumentMetadata,
    HFTokenCounter,
    InvalidPdfError,
    MetadataError,
    NotApprovedError,
    Paragraph,
    WhitespaceTokenCounter,
    chunk_paragraphs,
    clean_document,
    extract_pdf,
    sha256_file,
)
from src.ingestion.chunker import split_sentences
from src.ingestion.cleaner import normalize_text
from src.ingestion.pdf_extractor import ExtractedPage, ExtractionResult, TextBlock, TextLine
from src.ingestion.pipeline import ensure_approved


WORDS = WhitespaceTokenCounter()


@pytest.fixture
def clinical_pdf(tmp_path):
    return build_pdf(tmp_path / "guia.pdf", CLINICAL_PAGES, header="GUÍA SINTÉTICA DE CUIDADOS")


def make_page(number: int, lines: list[tuple[str, float]], *, size: float = 11, bold: bool = False) -> ExtractedPage:
    """Página construida a mano: cada línea es (texto, y0) en una página de 842 pt."""
    blocks = tuple(TextBlock((TextLine(text, size, bold, y0, y0 + 12),)) for text, y0 in lines)
    text = "\n\n".join(block.text for block in blocks)
    return ExtractedPage(page=number, text=text, blocks=blocks, height=842, image_count=0)


def make_extraction(pages: list[ExtractedPage], *, origin: str = "digital") -> ExtractionResult:
    return ExtractionResult(
        path=None, page_count=len(pages), pages=tuple(pages), extraction_origin=origin
    )


# ------------------------------------------------------------- extracción


def test_digital_pdf_extracts_every_page_with_1_based_numbers(clinical_pdf) -> None:
    result = extract_pdf(clinical_pdf)
    assert result.page_count == 4
    assert [page.page for page in result.pages] == [1, 2, 3, 4]
    assert result.pages_with_text == 4
    assert result.is_valid and not result.requires_ocr
    assert result.total_chars == sum(page.char_count for page in result.pages) > 0


def test_page_text_stays_on_its_source_page(clinical_pdf) -> None:
    pages = extract_pdf(clinical_pdf).pages
    assert "Manejo de náuseas y vómitos" in pages[1].text
    assert "náuseas" not in pages[2].text
    assert "higiene de manos" in pages[2].text
    assert "Página 3 de 4" in pages[2].text  # la extracción no limpia: eso es tarea del cleaner


def test_scanned_pdf_is_flagged_and_invalid(tmp_path) -> None:
    result = extract_pdf(build_scanned_pdf(tmp_path / "escaneado.pdf", page_count=3))
    assert result.pages_with_text == 0
    assert result.ocr_pages == [1, 2, 3]
    assert not result.is_valid
    assert any("escaneado" in problem for problem in result.problems())


def test_partially_scanned_pdf_requires_ocr(tmp_path) -> None:
    import pymupdf

    text_pdf = build_pdf(tmp_path / "texto.pdf", CLINICAL_PAGES)
    scanned = build_scanned_pdf(tmp_path / "img.pdf", page_count=2)
    merged = pymupdf.open(text_pdf)
    merged.insert_pdf(pymupdf.open(scanned))
    merged.save(tmp_path / "mixto.pdf")
    result = extract_pdf(tmp_path / "mixto.pdf")
    assert result.empty_pages == [5, 6] and result.ocr_pages == [5, 6]
    assert result.is_valid and result.requires_ocr  # 2/6 páginas sin texto >= 20 %


@pytest.mark.parametrize("name, content", [("falso.pdf", b"no soy un pdf"), ("nota.txt", b"%PDF-1.7")])
def test_invalid_files_are_rejected(tmp_path, name, content) -> None:
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(InvalidPdfError):
        extract_pdf(path)
    with pytest.raises(InvalidPdfError, match="No existe"):
        extract_pdf(tmp_path / "inexistente.pdf")


def test_sha256_is_computed_over_original_bytes(clinical_pdf) -> None:
    raw = clinical_pdf.read_bytes()
    assert sha256_file(clinical_pdf) == hashlib.sha256(raw).hexdigest()
    altered = clinical_pdf.with_name("alterado.pdf")
    altered.write_bytes(raw + b"\n%")
    assert sha256_file(altered) != sha256_file(clinical_pdf)


# ---------------------------------------------------------------- limpieza


def test_normalization_only_fixes_form() -> None:
    assert normalize_text("eﬁcaz  y seguro") == "eficaz y seguro"
    assert normalize_text("náuseas") == "náuseas"  # NFD -> NFC
    assert normalize_text("anti­eméticos​") == "antieméticos"
    assert normalize_text("5 mg/m² · 2 veces") == "5 mg/m² · 2 veces"  # sin NFKC: m² intacto


def test_repeated_headers_and_footers_are_removed_and_reported() -> None:
    pages = [
        make_page(n, [("MINISTERIO DE SALUD", 30), (f"Contenido propio de la página {n}.", 300),
                      (f"Página {n} de 4", 810)])
        for n in range(1, 5)
    ]
    paragraphs, report = clean_document(make_extraction(pages))
    texts = [paragraph.text for paragraph in paragraphs]
    assert texts == [f"Contenido propio de la página {n}." for n in range(1, 5)]
    assert report.removed_patterns == {"ministerio de salud": 4, "página # de #": 4}
    assert report.removed_lines == 8


def test_alternating_even_odd_footers_below_global_threshold_are_removed(tmp_path) -> None:
    pages = [[("p", f"Contenido clínico exclusivo de la página {n}.")] for n in range(1, 11)]
    footers = [
        ("PIE IMPAR" if n % 2 else "PIE PAR") if n not in (9, 10) else None
        for n in range(1, 11)
    ]
    pdf = build_pdf(tmp_path / "pies_alternos.pdf", pages, footer=footers)
    paragraphs, report = clean_document(extract_pdf(pdf))
    text = " ".join(p.text for p in paragraphs)
    assert "PIE PAR" not in text and "PIE IMPAR" not in text
    assert report.removed_patterns["pie par"] == 4
    assert report.removed_patterns["pie impar"] == 4
    assert all(detail["tipo"] == "header/footer" for detail in report.removed_pattern_details)


def test_repeated_header_below_old_global_threshold_uses_position(tmp_path) -> None:
    pages = [[("p", f"Texto diferente y completo para la página {n}.")] for n in range(1, 11)]
    headers = ["CINTA EDITORIAL"] * 4 + [None] * 6
    pdf = build_pdf(tmp_path / "cinta.pdf", pages, header=headers, footer=None)
    paragraphs, report = clean_document(extract_pdf(pdf))
    assert "CINTA EDITORIAL" not in " ".join(p.text for p in paragraphs)
    assert report.removed_patterns == {"cinta editorial": 4}


def test_repeated_text_in_body_or_short_documents_is_kept() -> None:
    body_repeat = [make_page(n, [("Lávese las manos.", 400), (f"Texto {n}.", 450)]) for n in range(1, 5)]
    paragraphs, report = clean_document(make_extraction(body_repeat))
    assert report.removed_patterns == {}
    assert sum(p.text == "Lávese las manos." for p in paragraphs) == 4

    two_pages = [make_page(n, [("ENCABEZADO", 30), (f"Texto {n}.", 400)]) for n in (1, 2)]
    _, report = clean_document(make_extraction(two_pages))
    assert report.removed_patterns == {}  # muy pocas páginas: no hay confianza suficiente


def test_hyphenated_line_breaks_are_rejoined_only_when_safe() -> None:
    lines = (TextLine("El trata-", 11, False, 300, 312), TextLine("miento dura seis ciclos.", 11, False, 313, 325),
             TextLine("Grupo A-", 11, False, 326, 338), TextLine("B incluye dos fármacos.", 11, False, 339, 351))
    page = ExtractedPage(1, "", (TextBlock(lines),), 842, 0)
    paragraphs, report = clean_document(make_extraction([page]))
    assert paragraphs[0].text == "El tratamiento dura seis ciclos. Grupo A- B incluye dos fármacos."
    assert report.hyphen_joins == 1


def test_paragraph_split_by_page_break_is_joined_with_both_pages() -> None:
    pages = [make_page(1, [("La quimioterapia puede producir cansancio y", 700)]),
             make_page(2, [("pérdida de apetito durante varias semanas.", 120)])]
    paragraphs, report = clean_document(make_extraction(pages))
    assert len(paragraphs) == 1
    assert paragraphs[0].text.endswith("y pérdida de apetito durante varias semanas.")
    assert (paragraphs[0].page_start, paragraphs[0].page_end) == (1, 2)
    assert report.cross_page_joins == 1


def test_headings_detected_by_typography_not_invented(clinical_pdf) -> None:
    paragraphs, report = clean_document(extract_pdf(clinical_pdf))
    headings = [p.text for p in paragraphs if p.kind == "heading"]
    assert headings == ["Introducción", "Manejo de náuseas y vómitos",
                        "Higiene y prevención de infecciones", "Actividad física"]
    plain = [make_page(1, [("Texto corto sin formato", 300), ("Otra línea normal del cuerpo.", 330)])]
    assert all(p.kind != "heading" for p in clean_document(make_extraction(plain))[0])


def test_ocr_typography_alone_does_not_create_heading() -> None:
    page = ExtractedPage(
        1,
        "",
        (
            TextBlock((TextLine("Texto corto con formato", 18, True, 150, 170),)),
            TextBlock((TextLine(
                "Este es un párrafo normal suficientemente largo para fijar el tamaño del cuerpo.",
                10, False, 200, 215,
            ),)),
        ),
        842,
        1,
    )
    paragraphs, report = clean_document(make_extraction([page], origin="ocr"))
    assert all(paragraph.kind != "heading" for paragraph in paragraphs)
    assert report.heading_strategy == "estructura_textual_ocr"
    assert report.ocr_typography_only_rejected == 1


def test_ocr_accepts_compact_uppercase_structural_heading() -> None:
    page = ExtractedPage(
        1,
        "",
        (
            TextBlock((TextLine("OBJETIVOS", 12, False, 150, 165),)),
            TextBlock((TextLine(
                "El documento presenta objetivos generales para la atención y el cuidado.",
                10, False, 200, 215,
            ),)),
        ),
        842,
        1,
    )
    paragraphs, _ = clean_document(make_extraction([page], origin="ocr"))
    assert [paragraph.text for paragraph in paragraphs if paragraph.kind == "heading"] == ["OBJETIVOS"]


def test_ocr_rotated_text_never_opens_section() -> None:
    page = ExtractedPage(
        1,
        "",
        (
            TextBlock((TextLine("OBJETIVOS", 12, False, 150, 165, (0.0, -1.0)),)),
            TextBlock((TextLine(
                "Texto horizontal conservado como contenido del documento OCR.",
                10, False, 200, 215,
            ),)),
        ),
        842,
        1,
    )
    paragraphs, report = clean_document(make_extraction([page], origin="ocr"))
    assert all(paragraph.kind != "heading" for paragraph in paragraphs)
    assert report.ocr_unreliable_orientation_pages == []  # la página alcanza 50 % horizontal


def test_repeated_ocr_running_title_is_not_a_section() -> None:
    pages = []
    for number in range(1, 6):
        blocks = (
            TextBlock((TextLine("GUÍA TÉCNICA", 13, False, 120, 135),)),
            TextBlock((TextLine(
                f"Contenido diferente y suficientemente extenso de la página {number}.",
                10, False, 200, 215,
            ),)),
        )
        pages.append(ExtractedPage(number, "", blocks, 842, 1))
    paragraphs, report = clean_document(make_extraction(pages, origin="ocr"))
    assert all(paragraph.kind != "heading" for paragraph in paragraphs)
    assert report.ocr_repeated_heading_texts >= 1


def test_cleaning_preserves_every_content_word(clinical_pdf) -> None:
    extraction = extract_pdf(clinical_pdf)
    paragraphs, _ = clean_document(extraction)
    cleaned = " ".join(p.text for p in paragraphs).split()
    for page in extraction.pages:
        for block in page.blocks:
            for line in block.lines:
                if "GUÍA SINTÉTICA" in line.text or line.text.startswith("Página"):
                    continue
                for word in normalize_text(line.text).split():
                    assert word in cleaned


# ---------------------------------------------------------------- chunking


def long_section(sentences: int, page: int = 1, heading: str | None = "Sección A") -> list[Paragraph]:
    paragraphs = [Paragraph(heading, "heading", page, page)] if heading else []
    for i in range(sentences):
        paragraphs.append(Paragraph(f"Oración número {i} con varias palabras de relleno clínico.", "paragraph", page + i // 4, page + i // 4))
    return paragraphs


def test_chunks_respect_token_limit_and_keep_pages() -> None:
    config = ChunkingConfig(chunk_size_tokens=40, chunk_overlap_tokens=10)
    chunks = chunk_paragraphs(long_section(20), WORDS, config)
    assert len(chunks) > 1
    assert all(chunk.token_count <= 40 for chunk in chunks)
    assert all(chunk.token_count == WORDS.count(chunk.text) for chunk in chunks)
    assert [c.order for c in chunks] == list(range(1, len(chunks) + 1))
    assert chunks[0].page_start == 1 and chunks[-1].page_end == 5
    assert any(c.page_end > c.page_start for c in chunks)  # cruza páginas y lo registra
    assert all(c.section == "Sección A" for c in chunks)


def test_overlap_repeats_whole_sentences_within_limit() -> None:
    config = ChunkingConfig(chunk_size_tokens=40, chunk_overlap_tokens=10)
    chunks = chunk_paragraphs(long_section(12, heading=None), WORDS, config)
    for previous, current in zip(chunks, chunks[1:]):
        first_sentence = current.text.split("\n\n")[0]
        assert first_sentence in previous.text  # solapamiento por oración completa
        assert WORDS.count(first_sentence) <= 10
    no_overlap = chunk_paragraphs(long_section(12, heading=None), WORDS, ChunkingConfig(40, 0))
    assert sum(c.token_count for c in no_overlap) < sum(c.token_count for c in chunks)


def test_headings_start_new_chunk_without_overlap() -> None:
    paragraphs = long_section(3, heading="Náuseas") + long_section(3, heading="Higiene")
    chunks = chunk_paragraphs(paragraphs, WORDS, ChunkingConfig(200, 30))
    assert [c.section for c in chunks] == ["Náuseas", "Higiene"]
    assert chunks[1].text.startswith("Higiene\n\n")
    assert "Náuseas" not in chunks[1].text


def test_same_section_can_cross_three_physical_pages(tmp_path) -> None:
    pages = [
        [(("h" if n == 1 else "p"), "Cuidados continuados" if n == 1 else
          f"La explicación continúa en la página {n} con recomendaciones para el cuidado diario.")]
        for n in range(1, 4)
    ]
    pdf = build_pdf(tmp_path / "continuidad.pdf", pages, footer=None)
    paragraphs, _ = clean_document(extract_pdf(pdf))
    chunks = chunk_paragraphs(paragraphs, WORDS, ChunkingConfig(450, 75))
    assert len(chunks) == 1
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 3)


def test_real_section_change_never_mixes_infection_and_infertility() -> None:
    paragraphs = [
        Paragraph("Infección", "heading", 1, 1),
        Paragraph("Señales y cuidados para prevenir una infección.", "paragraph", 1, 1),
        Paragraph("Infecundidad", "heading", 2, 2),
        Paragraph("Información independiente sobre la fertilidad.", "paragraph", 2, 2),
    ]
    chunks = chunk_paragraphs(paragraphs, WORDS, ChunkingConfig(450, 75))
    assert [chunk.section for chunk in chunks] == ["Infección", "Infecundidad"]
    assert not any("Infección" in chunk.text and "Infecundidad" in chunk.text for chunk in chunks)


def test_larger_new_section_after_orphan_subtitle_stays_separate() -> None:
    paragraphs = [
        Paragraph("Infección", "heading", 1, 1, heading_size=24),
        Paragraph("Contenido de infección.", "paragraph", 1, 1),
        Paragraph("Teléfono para emergencias", "heading", 1, 1, heading_size=17),
        Paragraph("Infecundidad", "heading", 2, 2, heading_size=24),
        Paragraph("¿Qué es y por qué sucede?", "heading", 2, 2, heading_size=18),
        Paragraph("Contenido de infecundidad.", "paragraph", 2, 2),
    ]
    chunks = chunk_paragraphs(paragraphs, WORDS, ChunkingConfig(450, 75))
    assert len(chunks) == 2
    assert chunks[0].text.endswith("Teléfono para emergencias")
    assert chunks[1].text.startswith("Infecundidad")
    assert all(not ("Infección" in c.text and "Infecundidad" in c.text) for c in chunks)


def test_index_page_is_preserved_and_classified(tmp_path) -> None:
    pages = [
        [("h", "Índice"), ("p", "Náuseas y vómitos .......... 12"),
         ("p", "Infección ................... 18"), ("p", "Diarrea ..................... 24")],
        [("h", "Náuseas y vómitos"), ("p", "Explicación clínica desarrollada y útil.")],
    ]
    pdf = build_pdf(tmp_path / "indice.pdf", pages, footer=None)
    paragraphs, report = clean_document(extract_pdf(pdf))
    assert report.index_pages == [1]
    assert any(p.page_start == 1 and p.content_type == "indice" for p in paragraphs)
    assert any(p.page_start == 2 and p.content_type == "contenido" for p in paragraphs)
    chunks = chunk_paragraphs(paragraphs, WORDS, ChunkingConfig(450, 75))
    assert {chunk.content_type for chunk in chunks} == {"indice", "contenido"}


def test_long_paragraph_split_by_sentences_not_mid_sentence() -> None:
    text = " ".join(f"La oración {i} describe un cuidado distinto." for i in range(10))
    chunks = chunk_paragraphs([Paragraph(text, "paragraph", 3, 3)], WORDS, ChunkingConfig(20, 0))
    assert len(chunks) > 1
    assert all(chunk.text.endswith(".") for chunk in chunks)
    assert all(chunk.page_start == chunk.page_end == 3 for chunk in chunks)


def test_sentence_longer_than_limit_is_hard_split() -> None:
    sentence = " ".join(f"palabra{i}" for i in range(95))
    chunks = chunk_paragraphs([Paragraph(sentence, "paragraph", 1, 1)], WORDS, ChunkingConfig(30, 5))
    assert all(chunk.token_count <= 30 for chunk in chunks)
    assert " ".join(c.text for c in chunks).split()[:95] == sentence.split()


def test_sentence_splitter_respects_abbreviations() -> None:
    text = "Consulte al Dr. Pérez. Tome 5 mg. aprox. cada día. Vuelva en 2 semanas."
    assert split_sentences(text) == ["Consulte al Dr. Pérez.", "Tome 5 mg. aprox. cada día.", "Vuelva en 2 semanas."]


def test_chunking_config_from_env_and_validation(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE_TOKENS", "300")
    monkeypatch.setenv("CHUNK_OVERLAP_TOKENS", "50")
    assert ChunkingConfig.from_env() == ChunkingConfig(300, 50)
    with pytest.raises(ValueError):
        ChunkingConfig(100, 100)
    monkeypatch.setenv("CHUNK_SIZE_TOKENS", "muchos")
    with pytest.raises(ValueError, match="enteros"):
        ChunkingConfig.from_env()


def fake_fast_tokenizer() -> PreTrainedTokenizerFast:
    """Tokenizer fast de HF construido en memoria (sin descargas)."""
    vocab = {"[UNK]": 0, "dosis": 1, "diaria": 2, "de": 3, "ondansetrón": 4, ".": 5}
    backend = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    backend.pre_tokenizer = Whitespace()
    return PreTrainedTokenizerFast(tokenizer_object=backend, unk_token="[UNK]")


def test_hf_token_counter_counts_without_special_tokens_and_splits_on_words() -> None:
    counter = HFTokenCounter(fake_fast_tokenizer(), "fake")
    text = "dosis diaria de ondansetrón ."
    assert counter.count(text) == 5
    pieces = counter.split(text, 2)
    assert pieces == ["dosis diaria", "de ondansetrón", "."]
    assert all(counter.count(piece) <= 2 for piece in pieces)


# --------------------------------------------------------- metadatos/corpus


def test_metadata_requires_titulo_entidad_version(tmp_path) -> None:
    complete = {"titulo": "Guía", "entidad": "INEN", "version": "2025", "url_origen": "", "vigencia": "vigente"}
    metadata = DocumentMetadata.from_dict(complete)
    assert metadata.url_origen is None and metadata.vigencia == "vigente"
    for field in ("titulo", "entidad", "version"):
        with pytest.raises(MetadataError, match=field):
            DocumentMetadata.from_dict({**complete, field: "  "})
    with pytest.raises(MetadataError, match="no reconocidos"):
        DocumentMetadata.from_dict({**complete, "autor": "x"})
    path = tmp_path / "guia.json"
    path.write_text(json.dumps(complete), encoding="utf-8")
    assert DocumentMetadata.from_json(path) == metadata
    path.write_text("{roto", encoding="utf-8")
    with pytest.raises(MetadataError, match="JSON inválido"):
        DocumentMetadata.from_json(path)


def test_only_approved_directory_is_accepted(tmp_path) -> None:
    approved = tmp_path / "corpus" / "aprobados"
    approved.mkdir(parents=True)
    ensure_approved(approved / "guia.pdf", approved)
    for folder in ("candidatos", "rechazados"):
        with pytest.raises(NotApprovedError):
            ensure_approved(tmp_path / "corpus" / folder / "guia.pdf", approved)
    with pytest.raises(NotApprovedError):
        ensure_approved(approved / ".." / "candidatos" / "guia.pdf", approved)
