#!/usr/bin/env python3
"""Demostración mínima de recuperación semántica con embeddings normalizados."""

import logging
from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.embeddings import EmbeddingService


DOCUMENTS = [
    "Las náuseas y los vómitos pueden presentarse como efectos adversos durante determinados tratamientos antineoplásicos.",
    "Una adecuada higiene de manos contribuye a disminuir el riesgo de infecciones.",
    "La actividad física debe adaptarse a las condiciones del paciente y a las indicaciones del equipo tratante.",
]
QUERY = "Mi familiar tiene náuseas después de la quimioterapia."


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("src.embeddings.service").setLevel(logging.INFO)
    service = EmbeddingService()
    document_vectors = service.encode_documents(DOCUMENTS)
    query_vector = service.encode_query(QUERY)
    scores = document_vectors @ query_vector
    ranking = np.argsort(scores)[::-1]

    print(f"\nPregunta: {QUERY}")
    print(f"Dimensión real: {service.dimension}")
    for position, index in enumerate(ranking, start=1):
        print(f"\nTOP {position}")
        print(f"Score: {scores[index]:.6f}")
        print(f"Texto: {DOCUMENTS[index]}")


if __name__ == "__main__":
    main()
