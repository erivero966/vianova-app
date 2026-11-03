"""OCR conservador y trazable para PDFs escaneados aprobados.

Este módulo no indexa. Produce un derivado técnico en ``corpus/ocr`` y una
ficha de procedencia pendiente de revisión manual. El original nunca se abre
en modo escritura ni se entrega a OCRmyPDF como ruta de salida.
"""

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from typing import Any

from .config import PROJECT_ROOT
from .ingestion.pdf_extractor import ExtractionResult, extract_pdf, sha256_file, validate_pdf_file


APPROVED_DIR = PROJECT_ROOT / "corpus" / "aprobados"
OCR_DIR = PROJECT_ROOT / "corpus" / "ocr"
FEDORA_INSTALL_COMMAND = "sudo dnf install ocrmypdf tesseract-osd tesseract-langpack-spa"
LANGUAGE = "spa"


class OcrError(RuntimeError):
    """Error seguro y presentable de la etapa OCR."""


class OcrDependencyError(OcrError):
    """Falta una herramienta o dato lingüístico del sistema."""


class OcrInputError(OcrError):
    """El archivo no pertenece al corpus aprobado o no requiere OCR."""


class OcrOutputError(OcrError):
    """OCRmyPDF falló o el derivado no superó la validación automática."""


@dataclass(frozen=True)
class OcrTools:
    ocrmypdf_path: str
    ocrmypdf_version: str
    tesseract_path: str
    tesseract_version: str
    languages: tuple[str, ...]
    language_option: str


@dataclass(frozen=True)
class OcrReport:
    original: Path
    output: Path
    provenance: Path
    sha256_original: str
    sha256_ocr: str
    tools: OcrTools
    original_extraction: ExtractionResult
    output_extraction: ExtractionResult
    sample_pages: tuple[int, ...]


def check_ocr_tools() -> OcrTools:
    """Comprueba ejecutables, versiones, español y flags usados realmente."""
    ocrmypdf = shutil.which("ocrmypdf")
    tesseract = shutil.which("tesseract")
    missing = [name for name, path in (("ocrmypdf", ocrmypdf), ("tesseract", tesseract)) if not path]
    if missing:
        raise OcrDependencyError(
            f"Faltan dependencias del sistema: {', '.join(missing)}.\n"
            f"En Fedora ejecute manualmente:\n{FEDORA_INSTALL_COMMAND}"
        )

    ocr_version = _command_line([ocrmypdf, "--version"], "No se pudo obtener la versión de OCRmyPDF")
    tess_version = _command_line([tesseract, "--version"], "No se pudo obtener la versión de Tesseract")
    lang_result = _run_capture([tesseract, "--list-langs"], "No se pudieron consultar los idiomas de Tesseract")
    language_text = "\n".join(part for part in (lang_result.stdout, lang_result.stderr) if part)
    languages = tuple(
        line.strip() for line in language_text.splitlines()
        if line.strip() and not line.lower().startswith("list of available languages")
    )
    if LANGUAGE not in languages:
        raise OcrDependencyError(
            "Tesseract está instalado, pero falta el idioma español 'spa'.\n"
            f"En Fedora ejecute manualmente:\n{FEDORA_INSTALL_COMMAND}"
        )
    if "osd" not in languages:
        raise OcrDependencyError(
            "Tesseract tiene 'spa', pero falta 'osd', necesario para --rotate-pages.\n"
            f"En Fedora ejecute manualmente:\n{FEDORA_INSTALL_COMMAND}"
        )

    help_text = _run_capture([ocrmypdf, "--help"], "No se pudo consultar la ayuda de OCRmyPDF").stdout
    required_flags = ["--rotate-pages", "--deskew"]
    missing_flags = [flag for flag in required_flags if flag not in help_text]
    if missing_flags:
        raise OcrDependencyError(
            f"OCRmyPDF {ocr_version} no anuncia flags requeridos: {', '.join(missing_flags)}. "
            "Actualice OCRmyPDF antes de procesar documentos."
        )
    if "--language" in help_text:
        language_option = "--language"
    elif "-l " in help_text or "-l," in help_text:
        language_option = "-l"
    else:
        raise OcrDependencyError(
            f"OCRmyPDF {ocr_version} no anuncia una opción compatible para seleccionar idioma."
        )
    return OcrTools(
        ocrmypdf_path=ocrmypdf,
        ocrmypdf_version=ocr_version,
        tesseract_path=tesseract,
        tesseract_version=tess_version,
        languages=languages,
        language_option=language_option,
    )


def process_scanned_pdf(source: str | Path, output_dir: str | Path | None = None) -> OcrReport:
    """Genera y valida un derivado OCR sin publicar nada en la base vectorial."""
    original = validate_pdf_file(source).resolve()
    approved = APPROVED_DIR.resolve()
    if not original.is_relative_to(approved):
        raise OcrInputError(
            f"El original debe estar dentro de {APPROVED_DIR.relative_to(PROJECT_ROOT)}/; "
            "no se procesan candidatos ni rutas arbitrarias."
        )

    original_extraction = extract_pdf(original)
    if original_extraction.is_valid and not original_extraction.requires_ocr:
        raise OcrInputError(
            f"{original.name} ya contiene texto extraíble suficiente; OCR no es necesario."
        )
    if not original_extraction.requires_ocr and original_extraction.pages_with_text > 0:
        raise OcrInputError(
            f"{original.name} no alcanzó el umbral que exige OCR. Revise el diagnóstico con inspect_pdf.py."
        )

    tools = check_ocr_tools()
    destination_dir = Path(output_dir if output_dir is not None else OCR_DIR).resolve()
    expected_dir = OCR_DIR.resolve()
    if destination_dir != expected_dir:
        raise OcrInputError(f"Los derivados OCR solo pueden escribirse en {_display_path(OCR_DIR)}/.")
    destination_dir.mkdir(parents=True, exist_ok=True)
    output = destination_dir / f"{original.stem}_ocr.pdf"
    provenance = destination_dir / f"{original.stem}_ocr.provenance.json"
    if output.exists() or provenance.exists():
        existing = output if output.exists() else provenance
        raise OcrOutputError(
            f"La salida ya existe y no se sobrescribirá: {_display_path(existing)}. "
            "Revísela o retírela explícitamente antes de repetir el OCR."
        )

    original_hash = sha256_file(original)
    with tempfile.TemporaryDirectory(prefix=".ocr-", dir=destination_dir) as temp_dir:
        temporary_output = Path(temp_dir) / output.name
        command = [
            tools.ocrmypdf_path,
            tools.language_option,
            LANGUAGE,
            "--rotate-pages",
            "--deskew",
            str(original),
            str(temporary_output),
        ]
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            raise OcrOutputError(
                f"OCRmyPDF terminó con código {result.returncode}; no se publicó ningún derivado."
            )
        if not temporary_output.is_file():
            raise OcrOutputError("OCRmyPDF informó éxito, pero no produjo el PDF esperado.")

        output_extraction = extract_pdf(temporary_output)
        _validate_ocr_output(original_extraction, output_extraction)
        if sha256_file(original) != original_hash:
            raise OcrOutputError("El SHA-256 del original cambió durante el proceso; se descartó el derivado.")

        output_hash = sha256_file(temporary_output)
        pages = suggested_sample_pages(output_extraction.page_count)
        trace = _build_trace(
            original,
            output,
            original_hash,
            output_hash,
            tools,
            original_extraction,
            output_extraction,
            pages,
        )
        temporary_trace = Path(temp_dir) / provenance.name
        temporary_trace.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        # Publicación al final: nunca se expone un PDF parcial o no validado.
        temporary_output.replace(output)
        temporary_trace.replace(provenance)

    return OcrReport(
        original=original,
        output=output,
        provenance=provenance,
        sha256_original=original_hash,
        sha256_ocr=output_hash,
        tools=tools,
        original_extraction=original_extraction,
        output_extraction=output_extraction,
        sample_pages=pages,
    )


def suggested_sample_pages(page_count: int, count: int = 10) -> tuple[int, ...]:
    """Distribuye el muestreo; el revisor debe añadir páginas clínicas/tablas."""
    if page_count <= 0 or count <= 0:
        return ()
    wanted = min(count, page_count)
    if wanted == 1:
        return (1,)
    pages = {1, page_count}
    for index in range(1, wanted - 1):
        pages.add(round(1 + index * (page_count - 1) / (wanted - 1)))
    candidate = 1
    while len(pages) < wanted:
        pages.add(candidate)
        candidate += 1
    return tuple(sorted(pages)[:wanted])


def _validate_ocr_output(original: ExtractionResult, output: ExtractionResult) -> None:
    if output.page_count != original.page_count:
        raise OcrOutputError(
            f"El derivado tiene {output.page_count} páginas y el original {original.page_count}; se descartó."
        )
    if not output.is_valid or output.pages_with_text == 0 or output.total_chars == 0:
        details = " ".join(output.problems()) or "no se extrajo texto"
        raise OcrOutputError(f"El derivado OCR no contiene una capa de texto válida: {details}")


def _build_trace(
    original: Path,
    output: Path,
    original_hash: str,
    output_hash: str,
    tools: OcrTools,
    original_extraction: ExtractionResult,
    output_extraction: ExtractionResult,
    pages: tuple[int, ...],
) -> dict[str, Any]:
    command = [
        "ocrmypdf", tools.language_option, LANGUAGE, "--rotate-pages", "--deskew",
        _display_path(original), _display_path(output),
    ]
    return {
        "archivo_original": _display_path(original),
        "sha256_original": original_hash,
        "archivo_ocr": _display_path(output),
        "sha256_ocr": output_hash,
        "tipo_derivado": "PDF técnico con capa de texto OCR",
        "fuente_documental": _display_path(original),
        "ocr_engine": "OCRmyPDF + Tesseract",
        "ocr_engine_version": f"OCRmyPDF {tools.ocrmypdf_version}; Tesseract {tools.tesseract_version}",
        "ocrmypdf_version": tools.ocrmypdf_version,
        "tesseract_version": tools.tesseract_version,
        "idioma": LANGUAGE,
        "fecha_procesamiento": datetime.now().astimezone().isoformat(timespec="seconds"),
        "comando": shlex.join(command),
        "force_ocr": False,
        "validacion_automatica": {
            "estado": "aprobada",
            "paginas_original": original_extraction.page_count,
            "paginas_ocr": output_extraction.page_count,
            "paginas_con_texto_original": original_extraction.pages_with_text,
            "paginas_con_texto_ocr": output_extraction.pages_with_text,
            "caracteres_original": original_extraction.total_chars,
            "caracteres_ocr": output_extraction.total_chars,
            "caracteres_ilegibles_ocr": output_extraction.garbage_ratio,
        },
        "revision_manual": {
            "estado": "pendiente",
            "indexable": False,
            "minimo_paginas": min(10, output_extraction.page_count),
            "paginas_sugeridas": list(pages),
            "seleccion_obligatoria": [
                "portada", "índice", "primera página de contenido", "páginas intermedias",
                "páginas con tablas", "páginas con signos o síntomas", "páginas finales",
            ],
            "elementos_a_verificar": [
                "mg", "ml", "mL", "%", "°", "números", "rangos", "siglas",
                "nombres de medicamentos", "títulos", "viñetas", "tablas",
            ],
        },
    }


def _run_capture(command: list[str], error: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, check=False, text=True, capture_output=True)
    except OSError as exc:
        raise OcrDependencyError(f"{error}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise OcrDependencyError(f"{error}: {detail or f'código {result.returncode}'}")
    return result


def _command_line(command: list[str], error: str) -> str:
    result = _run_capture(command, error)
    lines = (result.stdout or result.stderr).splitlines()
    value = lines[0].strip() if lines else "desconocida"
    executable = Path(command[0]).name.lower()
    if executable == "tesseract" and value.lower().startswith("tesseract "):
        value = value.split(maxsplit=1)[1]
    return value


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(PROJECT_ROOT):
        return str(resolved.relative_to(PROJECT_ROOT))
    return str(path)
