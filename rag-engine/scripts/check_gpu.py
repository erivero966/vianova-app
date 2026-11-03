#!/usr/bin/env python3
"""Comprueba la instalación real de CUDA y la selección del dispositivo."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import torch

from src.config import EmbeddingSettings
from src.embeddings.service import select_device


def main() -> None:
    settings = EmbeddingSettings.from_env()
    cuda_available = torch.cuda.is_available()
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA disponible: {'sí' if cuda_available else 'no'}")
    if cuda_available:
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        properties = torch.cuda.get_device_properties(0)
        total_gib = properties.total_memory / 1024**3
        free_bytes, _ = torch.cuda.mem_get_info(0)
        print(f"VRAM disponible: {free_bytes / 1024**3:.2f} GiB de {total_gib:.2f} GiB")
    else:
        print("GPU: no detectada por PyTorch")
        print("VRAM disponible: no disponible")
    print(f"Dispositivo seleccionado: {select_device(settings.device)}")


if __name__ == "__main__":
    main()
