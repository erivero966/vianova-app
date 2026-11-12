#!/usr/bin/env python3
"""Arranca la API del prototipo (equivale a `uvicorn src.api.app:app`)."""

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    # Un único worker: cada worker cargaría su propia copia de BGE-M3 en la GPU.
    uvicorn.run("src.api.app:app", host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
