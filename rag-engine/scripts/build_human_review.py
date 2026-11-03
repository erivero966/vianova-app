#!/usr/bin/env python3
"""Genera la planilla ciega de revisión humana (Fase 4A.1) a partir de artefactos persistidos.

Solo lectura de eval/: no accede a PostgreSQL ni modifica juicios, rankings ni métricas.
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.experiments import file_hash
from src.human_review import (PENDING_COLUMNS, REVIEWED_COLUMNS, SEED, collect_pairs, first_relevant_ranks,
                              ordered, previous_context, priority, write_xlsx)

CMP = ROOT / "eval/resultados/model_comparison_v01"
EXP = ROOT / "eval/experimentos"
OUT_XLSX = ROOT / "eval/revision_humana_model_comparison_v01.xlsx"
OUT_CSV = ROOT / "eval/revision_humana_model_comparison_v01_pendientes.csv"
OUT_CSV_DONE = ROOT / "eval/revision_humana_model_comparison_v01_ya_revisados.csv"
OUT_MAP = ROOT / "eval/revision_humana_model_comparison_v01_map.json"
MODEL_FILES = {"alia": "alia.json", "qwen3": "qwen3.json", "bge-m3": "bge_m3.json"}
# Sección «Infección» de La quimioterapia y usted (p. 58–62): candidatos Q04 fuera del Top-10.
Q04_SECTION = {"version": "56395d34-a7bf-409c-8605-5d5d7c0c8939", "paginas": (58, 62)}


def load(path):
    return json.loads(Path(path).read_text())


def build():
    manifest = load(EXP / "corpus_v01_manifest.json")
    chunks = {c["id"]: c for c in manifest["chunks"]}
    by_order = {(c["version_id"], c["orden"]): c for c in manifest["chunks"]}
    titles = {v["id"]: d["titulo"] for v in manifest["versiones_activas"]
              for d in manifest["documentos"] if d["id"] == v["documento_id"]}
    queries = {q["id"]: q["texto"] for q in manifest["consultas"]} | {"Q04": manifest["Q04"]["texto"]}
    judgments = load(CMP / "judgments.json")["juicios"]

    # Los Top-10 de cada modelo deben coincidir exactamente con las posiciones juzgadas.
    slots = {(j["modelo"], j["consulta_id"], j["rank"]): j["fragmento_id"] for j in judgments}
    for alias, name in MODEL_FILES.items():
        for r in load(CMP / name)["resultados"]:
            if slots.get((alias, r["consulta_id"], r["rank"])) != r["fragmento_id"]:
                raise ValueError(f"{name} y judgments.json no coinciden en {r['consulta_id']}#{r['rank']}")
    if len(slots) != 3 * 16 * 10:
        raise ValueError("Se esperaban 480 posiciones juzgadas.")

    pairs = collect_pairs(judgments)
    firsts = first_relevant_ranks(judgments)

    # Q04: añade la sección Infección completa con su rank en el ranking exacto de 419.
    lo, hi = Q04_SECTION["paginas"]
    section = [c["id"] for c in manifest["chunks"]
               if c["version_id"] == Q04_SECTION["version"] and lo <= c["pagina_inicio"] <= hi]
    for alias in MODEL_FILES:
        ranking = load(EXP / f"Q04_{alias}_v01.json")["ranking_ids"]
        for fid in section:
            rank = ranking.index(fid) + 1
            if rank <= 10:
                continue
            pair = pairs.setdefault(("Q04", fid), {"judgment": None, "occurrences": []})
            pair["occurrences"].append({"modelo": alias, "rank": rank, "en_top10": False})

    pending, reviewed = [], []
    for key, pair in pairs.items():
        qid, fid = key
        c = chunks[fid]
        base = {"consulta_id": qid, "consulta": queries[qid], "fragmento_id": fid, "documento": titles[c["version_id"]],
                "pagina_inicio": c["pagina_inicio"], "pagina_fin": c["pagina_fin"], "seccion": c["ubicacion"] or "",
                "texto": c["texto"]}
        j = pair["judgment"]
        if j is not None and j["tipo_juicio"] == "humano":
            reviewed.append({**base, "prioridad": 0, "_pair": pair,
                             "juicio_humano_original": "Sí" if j["pertinente"] else "No",
                             "motivo_original": j["motivo"]})
            continue
        if j is None:
            prio, reasons = 1, ["Q04_seccion_infeccion_fuera_top10"]
        else:
            prio, reasons = priority(key, pair, firsts)
        pending.append({**base, "prioridad": prio, "_pair": pair, "_reasons": reasons,
                        "contexto_anterior": previous_context(c, by_order),
                        "q04_especifico_infeccion": "", "juicio_humano": "", "observacion_humana": ""})

    pending, reviewed = ordered(pending), ordered(reviewed)
    for i, row in enumerate(pending, 1):
        row["review_id"] = f"R{i:03d}"
    for i, row in enumerate(reviewed, 1):
        row["review_id"] = f"H{i:03d}"
    return pending, reviewed, firsts, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true", help="regenerar aunque existan (borra respuestas)")
    args = parser.parse_args()
    if any(p.exists() for p in (OUT_XLSX, OUT_MAP)) and not args.overwrite:
        parser.error("La planilla ya existe; no se sobrescribe para no perder respuestas.")
    pending, reviewed, firsts, manifest = build()

    widths = {"review_id": 8, "prioridad": 8, "consulta_id": 9, "consulta": 40, "fragmento_id": 12, "documento": 28,
              "pagina_inicio": 7, "pagina_fin": 7, "seccion": 28, "contexto_anterior": 40, "texto": 90,
              "q04_especifico_infeccion": 12, "juicio_humano": 10, "observacion_humana": 40,
              "juicio_humano_original": 10, "motivo_original": 50}
    write_xlsx(OUT_XLSX, [
        {"name": "PENDIENTES_REVISION_HUMANA", "columns": PENDING_COLUMNS, "rows": pending, "widths": widths,
         "validations": {"juicio_humano": ["0", "1", "2"], "q04_especifico_infeccion": ["S", "N"]}},
        {"name": "YA_REVISADOS_HUMANO", "columns": REVIEWED_COLUMNS, "rows": reviewed, "widths": widths},
    ])
    for path, columns, rows in ((OUT_CSV, PENDING_COLUMNS, pending), (OUT_CSV_DONE, REVIEWED_COLUMNS, reviewed)):
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    sources = [CMP / n for n in (*MODEL_FILES.values(), "judgments.json")] + \
              [EXP / f"Q04_{a}_v01.json" for a in MODEL_FILES] + [EXP / "corpus_v01_manifest.json"]
    entries = {}
    for row in pending + reviewed:
        pair = row["_pair"]
        entries[row["review_id"]] = {
            "consulta_id": row["consulta_id"], "fragmento_id": row["fragmento_id"],
            "texto_sha256": hashlib.sha256(row["texto"].encode()).hexdigest(),
            "hoja": "PENDIENTES_REVISION_HUMANA" if row["review_id"].startswith("R") else "YA_REVISADOS_HUMANO",
            "prioridad": row["prioridad"] or None, "motivos_prioridad": row.get("_reasons", []),
            "ocurrencias": sorted(pair["occurrences"], key=lambda o: (o["modelo"], o["rank"])),
            "juicio_previo": pair["judgment"]}
    counts = {p: sum(1 for r in pending if r["prioridad"] == p) for p in (1, 2, 3, 4)}
    OUT_MAP.write_text(json.dumps({
        "version": "4A.1", "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "aviso": "MAPA INTERNO: no entregar al evaluador; contiene modelo, rank y juicios previos.",
        "semilla_aleatoria": SEED,
        "orden": "por prioridad; dentro de cada prioridad orden aleatorio random.Random(f'{semilla}-{prioridad}') "
                 "sobre la lista ordenada por (consulta_id, fragmento_id)",
        "reglas_prioridad": {
            "1": "rank <= primer pertinente actual (o sin pertinente en Top-10) en algún modelo; todo MD10 y Q04; "
                 "Q04 incluye la sección Infección (Quimioterapia p. 58-62) fuera del Top-10",
            "2": "casos límite ([límite] en el motivo asistido)",
            "3": "MD04 o fragmentos de introducción/definición/cuestionario/lista (introducciones vs consejos)",
            "4": "resto del Top-10"},
        "primer_pertinente_actual": {f"{m}|{q}": r for (m, q), r in sorted(firsts.items())},
        "fuentes_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in sources},
        "salidas_sha256": {str(p.relative_to(ROOT)): file_hash(p) for p in (OUT_XLSX, OUT_CSV, OUT_CSV_DONE)},
        "recuentos": {"pares_unicos": len(entries), "ya_revisados_humano": len(reviewed),
                      "pendientes": len(pending), "pendientes_por_prioridad": counts,
                      "pendientes_q04_fuera_top10": sum(1 for r in pending if r["_pair"]["judgment"] is None)},
        "entradas": entries}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"pares_unicos": len(entries), "ya_revisados_humano": len(reviewed),
                      "pendientes": len(pending), "por_prioridad": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
