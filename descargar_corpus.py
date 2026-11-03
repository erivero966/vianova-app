#!/usr/bin/env python3
import json
import pathlib
import shutil
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"
DEST = pathlib.Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else ROOT / "descargados"
DEST.mkdir(parents=True, exist_ok=True)

with MANIFEST.open(encoding="utf-8") as f:
    data = json.load(f)

opener = urllib.request.build_opener()
opener.addheaders = [("User-Agent", "Mozilla/5.0")]

for src in data["fuentes"]:
    pdf_path = DEST / src["archivo"]
    json_path = DEST / (pdf_path.stem + ".json")
    print(f"\nDescargando: {src['titulo']}")
    print(src["url"])
    if pdf_path.exists() and pdf_path.stat().st_size > 10000:
        print(f"  PDF ya existe: {pdf_path}")
    else:
        try:
            with opener.open(src["url"], timeout=60) as r, pdf_path.open("wb") as out:
                shutil.copyfileobj(r, out)
        except Exception as e:
            print(f"  ERROR: {e}")
            if pdf_path.exists():
                pdf_path.unlink()
            continue
        print(f"  OK: {pdf_path.name} ({pdf_path.stat().st_size:,} bytes)")

    metadata = {
        "titulo": src["titulo"],
        "entidad": src["entidad"],
        "version": src["version"],
        "url_origen": src["url"],
        "vigencia": src["vigencia"]
    }
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"  Metadata: {json_path.name}")

print(f"\nDestino: {DEST}")
