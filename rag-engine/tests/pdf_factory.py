"""Genera PDFs sintéticos pequeños con PyMuPDF (sin documentos médicos reales)."""

from collections.abc import Sequence
from pathlib import Path

import pymupdf


PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4 en puntos
LEFT, RIGHT = 72, 523
BODY_TOP = 100

# (tipo, texto): "h" título 16pt negrita, "p" párrafo 11pt, "li" elemento de lista.
Item = tuple[str, str]
RepeatingText = str | Sequence[str | None] | None


def build_pdf(
    path: Path,
    pages: Sequence[Sequence[Item]],
    *,
    header: RepeatingText = None,
    footer: RepeatingText = "Página {n} de {total}",
) -> Path:
    document = pymupdf.open()
    total = len(pages)
    for number, items in enumerate(pages, start=1):
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page_header = _page_text(header, number, total)
        page_footer = _page_text(footer, number, total)
        if page_header:
            page.insert_text((LEFT, 85), page_header, fontsize=9, fontname="helv")
        if page_footer:
            page.insert_text((LEFT, PAGE_HEIGHT - 30), page_footer, fontsize=9, fontname="helv")
        y = BODY_TOP
        for kind, text in items:
            fontsize, fontname = (16, "hebo") if kind == "h" else (11, "helv")
            content = f"- {text}" if kind == "li" else text
            rect = pymupdf.Rect(LEFT, y, RIGHT, PAGE_HEIGHT - 90)
            unused = page.insert_textbox(rect, content, fontsize=fontsize, fontname=fontname)
            if unused < 0:
                raise ValueError(f"El texto no cabe en la página {number}: {text[:40]}…")
            y += rect.height - unused + (8 if kind == "li" else 16)
    document.save(path)
    document.close()
    return path


def _page_text(value: RepeatingText, number: int, total: int) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else value[number - 1]
    return text.format(n=number, total=total) if text else None


def build_scanned_pdf(path: Path, page_count: int = 3) -> Path:
    """PDF con solo imágenes (simula un escaneo): no tiene texto extraíble."""
    document = pymupdf.open()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 80), False)
    pixmap.clear_with(200)
    for _ in range(page_count):
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_image(pymupdf.Rect(50, 50, 545, 792), pixmap=pixmap)
    document.save(path)
    document.close()
    return path


CLINICAL_PAGES: list[list[Item]] = [
    [
        ("h", "Introducción"),
        ("p", "Esta guía sintética describe cuidados generales para familiares de pacientes "
              "oncológicos. El contenido es ficticio y se usa solo para pruebas automáticas."),
        ("p", "Los cuidadores deben consultar siempre con el equipo tratante ante cualquier "
              "duda sobre la medicación o los síntomas del paciente."),
    ],
    [
        ("h", "Manejo de náuseas y vómitos"),
        ("p", "Las náuseas y los vómitos pueden presentarse como efectos adversos durante "
              "determinados tratamientos antineoplásicos. Conviene ofrecer comidas pequeñas y "
              "frecuentes, evitar olores intensos y mantener una hidratación adecuada."),
        ("li", "Registrar la frecuencia de los vómitos."),
        ("li", "Consultar si no tolera líquidos durante más de un día."),
    ],
    [
        ("h", "Higiene y prevención de infecciones"),
        ("p", "Una adecuada higiene de manos contribuye a disminuir el riesgo de infecciones. "
              "Se recomienda lavar las manos antes de preparar alimentos y después de usar el baño."),
    ],
    [
        ("h", "Actividad física"),
        ("p", "La actividad física debe adaptarse a las condiciones del paciente y a las "
              "indicaciones del equipo tratante. Caminar a diario puede ayudar a reducir la fatiga."),
    ],
]
