#!/usr/bin/env python3
"""Consolida resultados crudos, juicios y métricas de la comparación dense v01.

No carga modelos ni ejecuta búsquedas: solo lee los Top-10 persistidos en
eval/experimentos/ y los juicios existentes (humanos inmutables + asistidos).
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.database import connect
from src.experiments import (MODEL_TABLES, file_hash, first_relevant, judge_ranking,
                             judgment_index, metrics, verify)

EXP = ROOT / "eval/experimentos"
OUT = ROOT / "eval/resultados/model_comparison_v01"
HUMAN = ROOT / "eval/resultados/alia_multidocumento_v01_revisado.json"
HUMAN_BY_POSITION = ROOT / "eval/evaluacion_manual_multidocumento_v01.json"
ASSISTED = [EXP / "juicios_asistidos_v01.json", EXP / "juicios_asistidos_v01_qwen3_bge_m3.json"]
CATEGORIES = EXP / "anotacion_intro_consejo_v01.json"
FILE_NAMES = {"alia": "alia", "qwen3": "qwen3", "bge-m3": "bge_m3"}


def load(path):
    return json.loads(Path(path).read_text())


def human_judgments():
    reviewed, manual = load(HUMAN), load(HUMAN_BY_POSITION)
    by_position = {(q["id"], j["posicion"]): j["pertinente"] for q in manual["consultas"] for j in q["juicios"]}
    items = []
    for q in reviewed["consultas"]:
        for r in q["resultados"]:
            if by_position[(q["id"], r["posicion"])] != r["pertinente"]:
                raise ValueError("Las dos copias de la revisión humana no coinciden.")
            items.append({"consulta_id": q["id"], "fragmento_id": r["fragmento_id"], "pertinente": r["pertinente"],
                          "motivo": r["motivo"], "fuente_juicio": str(HUMAN.relative_to(ROOT)),
                          "posicion_al_revisar": r["posicion"], "modelo_al_revisar": "alia"})
    return items


def assisted_judgments():
    items = []
    for path in ASSISTED:
        for j in load(path)["juicios"]:
            items.append({**j, "fuente_juicio": str(path.relative_to(ROOT))})
    return items


def write(path, value, overwrite):
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n"
    if path.exists() and path.read_text() != text and not overwrite:
        raise SystemExit(f"{path} ya existe con otro contenido; use --overwrite conscientemente.")
    path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest = load(EXP / "corpus_v01_manifest.json")
    manifest_sha = file_hash(EXP / "corpus_v01_manifest.json")
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        verify(conn, manifest)
        configs = dict(conn.execute("SELECT nombre, id::text FROM configuracion_modelo").fetchall())
        stamps = {alias: conn.execute(f"SELECT max(creado_en) FROM {table} WHERE configuracion_id=%s",
                                      (configs[alias],)).fetchone()[0].isoformat()
                  for alias, table in MODEL_TABLES.items()}
    index = judgment_index(human_judgments(), assisted_judgments())
    categories = {(c["consulta_id"], c["fragmento_id"]): c for c in load(CATEGORIES)["anotaciones"]} \
        if CATEGORIES.exists() else {}
    OUT.mkdir(parents=True, exist_ok=True)
    query_ids = [q["id"] for q in manifest["consultas"]]
    summary = {"manifest_sha256": manifest_sha, "chunks_ids_sha256": manifest["chunks_ids_sha256"],
               "modelos": {}, "por_consulta": {q: {} for q in query_ids + ["Q04"]}}
    all_judgments = []
    for alias, name in FILE_NAMES.items():
        raw_path = EXP / f"resultados_{alias}_v01.json"
        raw = load(raw_path)
        if raw["manifest_sha256"] != manifest_sha or raw["chunks_ids_sha256"] != manifest["chunks_ids_sha256"]:
            raise ValueError(f"{alias}: resultados de otro corpus.")
        if [q["id"] for q in raw["consultas"]] != query_ids + ["Q04"]:
            raise ValueError(f"{alias}: consultas distintas.")
        cfg = raw["configuracion"]
        rows, firsts, firsts_human = [], [], []
        for q in raw["consultas"]:
            ids = [r["fragmento_id"] for r in q["resultados"]]
            judged = judge_ranking(q["id"], ids, index)
            for r, j in zip(q["resultados"], judged):
                rows.append({"consulta_id": q["id"], "consulta": q["texto"], "rank": r["posicion"],
                             "fragmento_id": r["fragmento_id"], "documento": r["titulo"],
                             "documento_id": r["documento_id"], "version": r["version"],
                             "version_id": r["version_id"], "pagina_inicio": r["pagina_inicio"],
                             "pagina_fin": r["pagina_fin"], "seccion": r["ubicacion"], "texto": r["texto"],
                             "distancia": r["distancia"], "similitud": r["similitud"],
                             "modelo": cfg["model_id"], "alias": alias, "configuracion_id": configs[alias]})
                cat = categories.get((q["id"], r["fragmento_id"])) or j
                all_judgments.append({"consulta_id": q["id"], "modelo": alias, "fragmento_id": r["fragmento_id"],
                                      "rank": r["posicion"], "pertinente": j["pertinente"],
                                      "tipo_juicio": j["tipo_juicio"], "motivo": j["motivo"],
                                      "fuente_juicio": j["fuente_juicio"],
                                      "fragmento_referencia": r["texto"][:240],
                                      "texto_sha256": hashlib.sha256(r["texto"].encode()).hexdigest(),
                                      "documento": r["titulo"], "pagina": [r["pagina_inicio"], r["pagina_fin"]],
                                      "seccion": r["ubicacion"],
                                      "categoria": cat.get("categoria")})
            first = first_relevant(judged)
            cats = [(categories.get((q["id"], f)) or j).get("categoria") for f, j in zip(ids, judged)]
            actionable = next((i for i, (j, c) in enumerate(zip(judged, cats), 1)
                               if j["pertinente"] and c == "consejo_practico"), None)
            summary["por_consulta"][q["id"]][alias] = {
                "primer_pertinente": first, "primer_pertinente_solo_humano": first_relevant(judged, ("humano",)),
                "tipos_top10": dict(Counter(j["tipo_juicio"] for j in judged)),
                "pertinentes_top5": sum(j["pertinente"] for j in judged[:5]),
                "primer_accionable": actionable, "categorias_top5": cats[:5],
                "no_accionables_antes_del_primer_accionable": sum(
                    1 for c in cats[:(actionable or 11) - 1] if c in
                    ("introduccion_general", "definicion_causas", "preguntas_sin_respuesta", "lista_indice")),
                "documentos_top5": dict(Counter(r["titulo"] for r in q["resultados"][:5]))}
            if q["id"] != "Q04":
                firsts.append(first)
                firsts_human.append(first_relevant(judged, ("humano",)))
        human_slots = {k: sum(1 for j in all_judgments if j["modelo"] == alias and j["consulta_id"] != "Q04"
                              and j["rank"] <= k and j["tipo_juicio"] == "humano") for k in (1, 3, 5, 10)}
        tecnico = {"model_id": cfg["model_id"], "revision": cfg["revision"], "dimension": cfg["dimension"],
                   "dtype": cfg["dtype"], "device": cfg["device"], "gpu": cfg["gpu"], "batch_size": cfg["batch_size"],
                   "max_seq_length": cfg["max_seq_length"], "embedding_count": cfg["embeddings_elegibles"],
                   "embedding_time_seconds": cfg["tiempo_embeddings_s"],
                   "embeddings_per_second": cfg["embeddings_por_segundo"], "load_time_seconds": cfg["tiempo_carga_s"],
                   "queries_time_seconds": cfg["tiempo_consultas_15_s"], "q04_time_seconds": cfg["tiempo_Q04_s"],
                   "vram_peak_allocated_bytes": cfg["vram_pico_total_allocated_bytes"],
                   "vram_peak_reserved_bytes": cfg["vram_pico_total_reserved_bytes"],
                   "query_instruction": cfg["query_prompt"], "document_instruction": cfg["document_prompt"],
                   "normalization": "L2 (normalize_embeddings=True); distancia coseno <=>",
                   "representation": "dense", "persistence": cfg["persistencia"],
                   "timestamp_embeddings_db": stamps[alias],
                   "timestamp_results": datetime.fromtimestamp(raw_path.stat().st_mtime, timezone.utc).isoformat()}
        q04 = load(EXP / f"Q04_{alias}_v01.json")
        q04_judged = judge_ranking("Q04", next(q for q in raw["consultas"] if q["id"] == "Q04")["top_k_ids"]["10"], index)
        summary["por_consulta"]["Q04"][alias].update(
            rank_primer_fragmento_pertinente=first_relevant(q04_judged),
            rank_fragmento_objetivo_historico=q04["posicion_objetivo"],
            similitud_objetivo=q04["similitud"], total_ranking=q04["total"])
        summary["modelos"][alias] = {
            "tecnico": tecnico,
            "model_id": cfg["model_id"], "revision": cfg["revision"], "configuracion_id": configs[alias],
            "metricas_preliminares_humano_mas_asistido": metrics(firsts),
            "metricas_solo_pertinentes_humanos_cota_inferior": metrics(firsts_human),
            "cobertura_humana_slots": {f"top{k}": f"{v}/{15 * k}" for k, v in human_slots.items()},
            "configuracion": cfg}
        write(OUT / f"{name}.json", {"modelo": cfg["model_id"], "alias": alias, "configuracion_id": configs[alias],
                                     "manifest_sha256": manifest_sha, "fuente_cruda": str(raw_path.relative_to(ROOT)),
                                     "fuente_cruda_sha256": file_hash(raw_path), "top_k": 10,
                                     "tecnico": tecnico,
                                     "resultados": rows}, args.overwrite)
    counts = Counter(j["tipo_juicio"] for j in all_judgments)
    unique = Counter(v["tipo_juicio"] for k, v in index.items())
    write(OUT / "judgments.json", {
        "criterio": load(HUMAN)["criterio_revision"],
        "regla": "Juicio por (consulta_id, fragmento_id). Humanos inmutables y reutilizados si otro modelo recupera el "
                 "mismo fragmento para la misma consulta; asistido_preliminar solo para pares sin juicio humano. "
                 "La asistencia se aplicó después del retrieval y no interviene en embeddings/ranking.",
        "recuento_por_slot": dict(counts), "recuento_pares_unicos": dict(unique),
        "fuentes": [str(HUMAN.relative_to(ROOT))] + [str(p.relative_to(ROOT)) for p in ASSISTED],
        "juicios": all_judgments}, args.overwrite)
    summary["procedencia"] = {"slots": dict(counts), "pares_unicos": dict(unique)}
    write(OUT / "metrics.json", summary, args.overwrite)
    for alias, m in summary["modelos"].items():
        print(alias, json.dumps(m["metricas_preliminares_humano_mas_asistido"]))
    print("procedencia", summary["procedencia"])


if __name__ == "__main__":
    main()
