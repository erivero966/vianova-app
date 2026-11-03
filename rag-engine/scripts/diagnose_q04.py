#!/usr/bin/env python3
"""Localiza el fragmento histórico de signos de infección sin alterar el Top-K evaluado."""
import argparse
import json
from pathlib import Path
import sys
from dataclasses import asdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compare_models import load, OUT
from src.database import connect, ModelConfigRepository, VectorRepository
from src.experiments import MODEL_TABLES, verify, verify_coverage, search_selected, file_hash

TARGET = "95e107ed-5b94-4ad3-8be6-b9af4bb40946"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=MODEL_TABLES)
    args = parser.parse_args()
    output = OUT / f"Q04_{args.model}_v01.json"
    if output.exists():
        parser.error("El diagnóstico ya existe; no sobrescribir.")
    manifest = json.loads((OUT / "corpus_v01_manifest.json").read_text())
    raw = json.loads((OUT / f"resultados_{args.model}_v01.json").read_text())
    query = manifest["Q04"]["texto"]
    service, _ = load(args.model, raw["configuracion"]["revision"], 1)
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        verify(conn, manifest)
        repo = VectorRepository(conn, ModelConfigRepository(conn).get_active(args.model))
        ids = verify_coverage(conn, repo, manifest)
        hits = search_selected(service, repo, query, len(ids))
        if len(hits) != len(ids) or {str(h.fragmento_id) for h in hits} != set(ids):
            raise ValueError("Diagnóstico incompleto.")
        previous = next(q for q in raw["consultas"] if q["id"] == "Q04")
        if [str(h.fragmento_id) for h in hits[:10]] != previous["top_k_ids"]["10"]:
            raise ValueError("La repetición de Q04 cambió el Top-10.")
        rank, target = next((i,h) for i,h in enumerate(hits,1) if str(h.fragmento_id)==TARGET)
        verify(conn, manifest)
    result = {"consulta": query, "modelo": args.model, "fragmento_objetivo": TARGET,
              "criterio": "Lista explícita de otras señales de infección, Quimioterapia p. física 62",
              "posicion_objetivo": rank, "similitud": target.similitud,
              "fragmento": asdict(target), "total": len(hits),
              "nota": "Diagnóstico separado de posición exacta sobre 419; no amplía Top-10 ni las 15 consultas de métricas.",
              "manifest_sha256": file_hash(OUT / "corpus_v01_manifest.json"),
              "ranking_ids": [str(h.fragmento_id) for h in hits]}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+"\n")
    print(args.model, query, "posición", rank)


if __name__ == "__main__":
    main()
