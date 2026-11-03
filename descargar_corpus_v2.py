#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
from pathlib import Path

SOURCES = [
    {
        "filename": "nci_consejos_alimentacion_2024.pdf",
        "metadata_filename": "nci_consejos_alimentacion_2024.json",
        "titulo": "Consejos de alimentación: antes, durante y después del tratamiento del cáncer",
        "entidad": "National Cancer Institute (NCI)",
        "version": "2024",
        "vigencia": "por revisar",
        "url": "https://www.cancer.gov/espanol/cancer/sobrellevar/consejos-de-alimentacion.pdf",
        "referer": "https://www.cancer.gov/espanol/publicaciones/educacion-para-pacientes/consejos-de-alimentacion",
    },
    {
        "filename": "nci_radioterapia_y_usted.pdf",
        "metadata_filename": "nci_radioterapia_y_usted.json",
        "titulo": "La radioterapia y usted: Apoyo para las personas con cáncer",
        "entidad": "National Cancer Institute (NCI)",
        "version": "2016",
        "vigencia": "por revisar",
        "url": "https://www.cancer.gov/espanol/cancer/radioterapia-y-usted.pdf",
        "referer": "https://www.cancer.gov/espanol/publicaciones/educacion-para-pacientes/radioterapia-y-usted",
    },
    {
        "filename": "inen_paciente_oncologico_inmunodeprimido_2020.pdf",
        "metadata_filename": "inen_paciente_oncologico_inmunodeprimido_2020.json",
        "titulo": "Gestión del Cuidado de Enfermería en la atención del paciente oncológico inmunodeprimido",
        "entidad": "Instituto Nacional de Enfermedades Neoplásicas (INEN)",
        "version": "2020",
        "vigencia": "por revisar",
        "url": "https://portal.inen.sld.pe/wp-content/uploads/2020/09/RJ-288-2020-J-INEN-1.pdf",
        "referer": "https://portal.inen.sld.pe/guias-tecnicas/",
    },
    {
        "filename": "inen_agentes_antineoplasicos_2023.pdf",
        "metadata_filename": "inen_agentes_antineoplasicos_2023.json",
        "titulo": "Guía Técnica: Gestión del Cuidado de Enfermería Oncológica en la Administración de Agentes Antineoplásicos en el paciente con cáncer",
        "entidad": "Instituto Nacional de Enfermedades Neoplásicas (INEN)",
        "version": "2023",
        "vigencia": "por revisar",
        "url": "https://portal.inen.sld.pe/wp-content/uploads/2023/11/RJ-N%C2%B0-300-2023-J-INEN.pdf",
        "referer": "https://portal.inen.sld.pe/guias-tecnicas/",
    },
]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)

def validate_pdf(path: Path):
    if not path.exists():
        return False, "archivo no creado"
    size = path.stat().st_size
    if size < 10_000:
        return False, f"archivo demasiado pequeño ({size} bytes)"
    with path.open("rb") as f:
        magic = f.read(5)
    if magic != b"%PDF-":
        return False, f"no parece PDF (cabecera {magic!r})"
    return True, f"{size:,} bytes"

def download_with_curl(src, destination: Path):
    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)

    cmd = [
        "curl",
        "-L",
        "--fail",
        "--show-error",
        "--retry", "3",
        "--retry-delay", "2",
        "--retry-all-errors",
        "--connect-timeout", "15",
        "--max-time", "180",
        "--speed-time", "30",
        "--speed-limit", "1024",
        "-A", USER_AGENT,
        "-H", "Accept: application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "-H", "Accept-Language: es-PE,es;q=0.9,en;q=0.7",
        "-e", src["referer"],
        "-o", str(partial),
        src["url"],
    ]

    print(f"\nDescargando: {src['titulo']}")
    print(src["url"])

    result = subprocess.run(cmd)
    if result.returncode != 0:
        partial.unlink(missing_ok=True)
        return False, f"curl terminó con código {result.returncode}"

    ok, detail = validate_pdf(partial)
    if not ok:
        partial.unlink(missing_ok=True)
        return False, detail

    partial.replace(destination)
    return True, detail

def write_metadata(src, output_dir: Path):
    metadata = {
        "titulo": src["titulo"],
        "entidad": src["entidad"],
        "version": src["version"],
        "url_origen": src["url"],
        "vigencia": src["vigencia"],
    }
    path = output_dir / src["metadata_filename"]
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def main():
    if len(sys.argv) != 2:
        print("Uso:")
        print("  python descargar_corpus_v2.py /ruta/a/rag-engine/corpus/aprobados")
        raise SystemExit(2)

    if shutil.which("curl") is None:
        print("ERROR: no se encontró curl.")
        print("En Fedora instala con: sudo dnf install curl")
        raise SystemExit(1)

    output_dir = Path(sys.argv[1]).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    successes = 0
    failures = []

    for src in SOURCES:
        pdf_path = output_dir / src["filename"]

        if pdf_path.exists():
            ok, detail = validate_pdf(pdf_path)
            if ok:
                print(f"\nYA EXISTE: {pdf_path.name} ({detail})")
                write_metadata(src, output_dir)
                successes += 1
                continue
            print(f"\nArchivo existente inválido; se volverá a descargar: {pdf_path.name}")
            pdf_path.unlink(missing_ok=True)

        ok, detail = download_with_curl(src, pdf_path)

        if ok:
            write_metadata(src, output_dir)
            successes += 1
            print(f"OK: {pdf_path.name} — {detail}")
        else:
            failures.append((src["filename"], detail, src["url"]))
            print(f"FALLO: {src['filename']} — {detail}")
            print("Se continúa con el siguiente documento.")

    print("\n" + "=" * 70)
    print(f"Descargados correctamente: {successes}/{len(SOURCES)}")

    if failures:
        print("\nFallaron:")
        for name, error, url in failures:
            print(f"- {name}: {error}")
            print(f"  {url}")
        print("\nNo se crearon PDFs falsos ni parciales para los que fallaron.")
        raise SystemExit(1)

    print("\nCorpus descargado correctamente en:")
    print(output_dir)

if __name__ == "__main__":
    main()
