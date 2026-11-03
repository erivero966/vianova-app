"""Pruebas rápidas de OCR: sin herramientas del sistema ni documentos reales."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from pdf_factory import build_pdf, build_scanned_pdf
import src.ocr as ocr
from src.ingestion import InvalidPdfError, extract_pdf


def fake_tools() -> ocr.OcrTools:
    return ocr.OcrTools(
        ocrmypdf_path="/usr/bin/ocrmypdf",
        ocrmypdf_version="16.0.0",
        tesseract_path="/usr/bin/tesseract",
        tesseract_version="5.4.1",
        languages=("osd", "spa"),
        language_option="--language",
    )


def setup_dirs(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    approved = tmp_path / "corpus" / "aprobados"
    output = tmp_path / "corpus" / "ocr"
    approved.mkdir(parents=True)
    monkeypatch.setattr(ocr, "APPROVED_DIR", approved)
    monkeypatch.setattr(ocr, "OCR_DIR", output)
    return approved, output


def test_missing_tools_reports_fedora_command(monkeypatch) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: None)
    with pytest.raises(ocr.OcrDependencyError, match="sudo dnf install ocrmypdf"):
        ocr.check_ocr_tools()


def test_missing_spanish_language_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(ocr.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_capture(command, _error):
        if "--list-langs" in command:
            return subprocess.CompletedProcess(command, 0, "List of available languages (1):\neng\n", "")
        return subprocess.CompletedProcess(command, 0, "16.0.0\n", "")

    monkeypatch.setattr(ocr, "_run_capture", fake_capture)
    with pytest.raises(ocr.OcrDependencyError, match="falta el idioma español 'spa'"):
        ocr.check_ocr_tools()


def test_digital_pdf_is_not_ocrd(monkeypatch, tmp_path) -> None:
    approved, _ = setup_dirs(monkeypatch, tmp_path)
    digital = build_pdf(
        approved / "digital.pdf",
        [[("p", "Documento digital con suficiente texto extraíble para evitar un OCR innecesario.")]],
        footer=None,
    )
    with pytest.raises(ocr.OcrInputError, match="OCR no es necesario"):
        ocr.process_scanned_pdf(digital)


def test_ocr_is_atomic_traced_and_never_overwrites_original(monkeypatch, tmp_path) -> None:
    approved, output_dir = setup_dirs(monkeypatch, tmp_path)
    original = build_scanned_pdf(approved / "escaneado.pdf", page_count=2)
    original_bytes = original.read_bytes()
    digital_template = build_pdf(
        tmp_path / "resultado.pdf",
        [
            [("h", "Cuidados oncológicos"), ("p", "Texto OCR suficiente de la primera página para validación automática.")],
            [("h", "Medicamentos"), ("p", "Dosis de 5 mg y volumen de 10 mL según indicación médica.")],
        ],
        footer=None,
    )
    calls: list[list[str]] = []

    def fake_run(command, check=False, **_kwargs):
        calls.append(command)
        shutil.copyfile(digital_template, command[-1])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(ocr, "check_ocr_tools", fake_tools)
    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    report = ocr.process_scanned_pdf(original)

    assert original.read_bytes() == original_bytes
    assert report.sha256_original == hashlib.sha256(original_bytes).hexdigest()
    assert report.output == output_dir / "escaneado_ocr.pdf"
    assert report.output.is_file() and report.provenance.is_file()
    assert "--rotate-pages" in calls[0] and "--deskew" in calls[0]
    assert "--force-ocr" not in calls[0]
    assert calls[0][-2] == str(original.resolve())
    assert calls[0][-1] != str(original.resolve())

    trace = json.loads(report.provenance.read_text(encoding="utf-8"))
    assert trace["sha256_original"] == report.sha256_original
    assert trace["sha256_ocr"] == report.sha256_ocr
    assert trace["fuente_documental"].endswith("escaneado.pdf")
    assert trace["force_ocr"] is False
    assert trace["revision_manual"]["estado"] == "pendiente"
    assert trace["revision_manual"]["indexable"] is False
    assert trace["validacion_automatica"]["paginas_con_texto_ocr"] == 2

    extraction = extract_pdf(report.output)
    assert extraction.extraction_origin == "ocr"
    assert extraction.provenance_path == report.provenance
    assert extraction.source_path == original.resolve()
    assert extraction.source_sha256 == report.sha256_original


def test_tampered_ocr_derivative_fails_closed(monkeypatch, tmp_path) -> None:
    approved, output_dir = setup_dirs(monkeypatch, tmp_path)
    original = build_scanned_pdf(approved / "escaneado.pdf", page_count=1)
    output_dir.mkdir(parents=True)
    derived = build_pdf(
        output_dir / "escaneado_ocr.pdf",
        [[("p", "Texto reconocido suficiente para comprobar la procedencia del documento.")]],
        footer=None,
    )
    trace = {
        "archivo_original": str(original),
        "sha256_original": ocr.sha256_file(original),
        "archivo_ocr": str(derived),
        "sha256_ocr": "0" * 64,
        "ocr_engine": "OCRmyPDF + Tesseract",
    }
    derived.with_suffix(".provenance.json").write_text(json.dumps(trace), encoding="utf-8")
    with pytest.raises(InvalidPdfError, match="SHA-256 del derivado no coincide"):
        extract_pdf(derived)


def test_existing_derivative_is_never_overwritten(monkeypatch, tmp_path) -> None:
    approved, output_dir = setup_dirs(monkeypatch, tmp_path)
    original = build_scanned_pdf(approved / "escaneado.pdf", page_count=1)
    output_dir.mkdir(parents=True)
    existing = output_dir / "escaneado_ocr.pdf"
    existing.write_bytes(b"contenido previo")
    monkeypatch.setattr(ocr, "check_ocr_tools", fake_tools)
    with pytest.raises(ocr.OcrOutputError, match="no se sobrescribirá"):
        ocr.process_scanned_pdf(original)
    assert existing.read_bytes() == b"contenido previo"


def test_failed_ocr_leaves_no_derivative(monkeypatch, tmp_path) -> None:
    approved, output_dir = setup_dirs(monkeypatch, tmp_path)
    original = build_scanned_pdf(approved / "escaneado.pdf", page_count=1)
    monkeypatch.setattr(ocr, "check_ocr_tools", fake_tools)
    monkeypatch.setattr(
        ocr.subprocess,
        "run",
        lambda command, check=False: subprocess.CompletedProcess(command, 7),
    )
    with pytest.raises(ocr.OcrOutputError, match="código 7"):
        ocr.process_scanned_pdf(original)
    assert not (output_dir / "escaneado_ocr.pdf").exists()


def test_suggested_sample_has_ten_distributed_pages() -> None:
    pages = ocr.suggested_sample_pages(66)
    assert len(pages) == 10
    assert pages[0] == 1 and pages[-1] == 66
    assert pages == tuple(sorted(set(pages)))
