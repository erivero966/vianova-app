#!/usr/bin/env python3
"""Fase 4B: BGE-M3 Top-10 congelado -> BAAI/bge-reranker-v2-m3 -> Top-10 reordenado (offline).

Solo lee resultados congelados y juicios humanos; escribe en eval/resultados/reranker_bge_v01/ y
eval/reranker_bge_v01.md. No toca PostgreSQL, embeddings, corpus ni el prototipo.
    python scripts/rerank_bge_v01.py
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import reranking as rr  # noqa: E402

MODEL_ID = "BAAI/bge-reranker-v2-m3"
REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
OUT_DIR = PROJECT_ROOT / "eval" / "resultados" / "reranker_bge_v01"
REPORT = PROJECT_ROOT / "eval" / "reranker_bge_v01.md"
ALIAS_BASE, ALIAS_RR = "bge-m3", "bge-m3+reranker"


def gpu_used_mib() -> int | None:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, check=True).stdout
        return int(out.split()[0])
    except Exception:
        return None


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-length", type=int, default=1024,
                   help="Tokens máx. del par consulta+fragmento (los pares del corpus v0.1 caben sin truncar).")
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--dtype", default="float32", choices=["float32", "float16"])
    p.add_argument("--device", default="cuda")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    import torch
    import sentence_transformers
    import transformers

    # ---------------------------------------------------------------- entradas congeladas y verificadas
    judgments = json.loads(rr.JUDGMENTS.read_text(encoding="utf-8"))
    rel_bge = rr.BGE_RESULTS.relative_to(rr.PROJECT_ROOT).as_posix()
    sha_bge = rr.sha256_file(rr.BGE_RESULTS)
    if sha_bge != rr.expected_sha256(judgments, rel_bge):
        raise SystemExit(f"{rel_bge} no coincide con el SHA-256 validado en la evaluación humana.")
    bge = json.loads(rr.BGE_RESULTS.read_text(encoding="utf-8"))
    candidates = rr.load_frozen_candidates(bge)

    baseline = rr.evaluate(candidates, judgments, ALIAS_BASE)
    frozen = json.loads(rr.BASELINE_METRICS.read_text(encoding="utf-8"))
    for mode in ("strict", "lenient"):   # el baseline recalculado debe ser idéntico al consolidado en 4A.1
        if baseline[mode]["primer_pertinente_por_consulta"] != frozen[mode]["bge-m3"]["primer_pertinente_por_consulta"]:
            raise SystemExit(f"Baseline {mode} recalculado no coincide con metrics_human_reviewed.json.")
    if baseline["q04"] != frozen["q04"]["bge-m3"]:
        raise SystemExit("Baseline Q04 recalculado no coincide.")

    # ---------------------------------------------------------------- modelo
    device = args.device if torch.cuda.is_available() else "cpu"
    gpu_before = gpu_used_mib()
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    scorer = rr.CrossEncoderScorer(MODEL_ID, REVISION, device, args.max_length, args.batch_size, args.dtype)
    load_s = time.perf_counter() - t0
    param_devices = sorted({str(p.device) for p in scorer.model.parameters()})
    n_params = sum(p.numel() for p in scorer.model.parameters())

    # ---------------------------------------------------------------- reranking (2 pasadas: tiempos y reproducibilidad)
    passes, per_query_ms = [], []
    for i in range(2):
        times = {}

        def timed(query, texts, _t=times):
            s = time.perf_counter()
            out = scorer(query, texts)
            if device == "cuda":
                torch.cuda.synchronize()
            _t[query] = (time.perf_counter() - s) * 1000
            return out

        s = time.perf_counter()
        ranked = rr.rerank_all(candidates, timed)
        passes.append({"ranked": ranked, "total_s": time.perf_counter() - s})
        per_query_ms.append(times)
    ranked = passes[0]["ranked"]
    max_score_diff = max(abs(a["score_reranker"] - b["score_reranker"])
                         for q in ranked for a, b in zip(ranked[q], passes[1]["ranked"][q]))
    same_order = all([r["fragmento_id"] for r in ranked[q]] == [r["fragmento_id"] for r in passes[1]["ranked"][q]]
                     for q in ranked)
    peak_alloc = torch.cuda.max_memory_allocated() if device == "cuda" else None
    peak_reserved = torch.cuda.max_memory_reserved() if device == "cuda" else None
    gpu_after = gpu_used_mib()

    # Medición complementaria: fp16 (solo latencia y estabilidad del orden; las métricas oficiales son fp32).
    fp16 = None
    if device == "cuda" and args.dtype == "float32":
        del scorer.model
        torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
        half = rr.CrossEncoderScorer(MODEL_ID, REVISION, device, args.max_length, args.batch_size, "float16")
        rr.rerank_all({"MD01": candidates["MD01"]}, half)          # calentamiento
        times16 = []

        def timed16(query, texts):
            s = time.perf_counter()
            out = half(query, texts)
            torch.cuda.synchronize()
            times16.append((time.perf_counter() - s) * 1000)
            return out

        ranked16 = rr.rerank_all(candidates, timed16)
        same16 = sum([r["fragmento_id"] for r in ranked[q]] == [r["fragmento_id"] for r in ranked16[q]] for q in ranked)
        fp16 = {"media_ms_por_consulta": sum(times16) / len(times16), "max_ms_por_consulta": max(times16),
                "consultas_con_mismo_orden_que_fp32": same16, "consultas": len(ranked),
                "max_diff_score": max(abs(a["score_reranker"] - b["score_reranker"])
                                      for q in ranked for a, b in zip(sorted(ranked[q], key=lambda r: r["fragmento_id"]),
                                                                      sorted(ranked16[q], key=lambda r: r["fragmento_id"]))),
                "vram_pico_asignado_bytes": torch.cuda.max_memory_allocated()}
        del half

    after = rr.evaluate(ranked, judgments, ALIAS_RR)
    lookup = rr.pair_lookup(judgments)

    # ---------------------------------------------------------------- artefactos
    def rows_out(rows):
        out = []
        for r in rows:
            j = lookup[(r["consulta_id"], r["fragmento_id"])]
            out.append({k: r.get(k) for k in ("consulta_id", "rank", "rank_original", "fragmento_id", "documento",
                                              "version", "pagina_inicio", "pagina_fin", "seccion")}
                       | {"score_bge_m3": r.get("score_bge_m3", r["similitud"]), "distancia_bge_m3": r["distancia"],
                          "score_reranker": r.get("score_reranker"), "review_id": j["review_id"],
                          "tipo_juicio": j["tipo_juicio"], "grado_humano": j["grado_humano"],
                          "pertinente_estricto": j["pertinente_estricto"], "pertinente_laxo": j["pertinente_laxo"],
                          "q04_especifico_infeccion": j.get("q04_especifico_infeccion"), "texto": r["texto"]})
        return out

    queries = {q: rows[0]["consulta"] for q, rows in candidates.items()}
    rr.dump_json(OUT_DIR / "ranking_bge_m3_original.json",
                 {"fuente": rel_bge, "fuente_sha256": sha_bge, "consultas": queries,
                  "ranking": {q: rows_out(rows) for q, rows in candidates.items()}})
    rr.dump_json(OUT_DIR / "ranking_reranked.json",
                 {"modelo": MODEL_ID, "revision": REVISION, "consultas": queries,
                  "ranking": {q: rows_out(rows) for q, rows in ranked.items()}})

    def summary(m):
        return {k: v for k, v in m.items() if k not in ("por_consulta",)}

    diffs = {mode: {k: after[mode][k] - baseline[mode][k]
                    for k in ("Hit@1_count", "Hit@3_count", "Hit@5_count", "Hit@10_count", "MRR@10")}
             for mode in ("strict", "lenient")}
    q_strict = rr.compare_first_relevant(baseline["strict"], after["strict"])
    q_lenient = rr.compare_first_relevant(baseline["lenient"], after["lenient"])
    metrics = {
        "version": "4B-reranker-bge-v01", "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "consultas_metricas": "MD01-MD15 (Q04 se analiza por separado, como en 4A.1)",
        "reglas": judgments["reglas"],
        "baseline": {"strict": summary(baseline["strict"]), "lenient": summary(baseline["lenient"])},
        "reranker": {"strict": summary(after["strict"]), "lenient": summary(after["lenient"])},
        "diferencia": diffs,
        "por_consulta": {"strict": q_strict, "lenient": q_lenient},
        "q04": {"baseline": baseline["q04"], "reranker": after["q04"]},
        "md10_top5": {"baseline": baseline["md10_top5"], "reranker": after["md10_top5"]},
    }
    rr.dump_json(OUT_DIR / "metrics.json", metrics)

    all_ms = list(per_query_ms[1].values())
    run = {
        "fecha_utc": metrics["fecha_utc"],
        "modelo": {"model_id": MODEL_ID, "revision": REVISION, "parametros": n_params, "tipo": "cross-encoder",
                   "salida": "score de CrossEncoder.predict (activación por defecto de sentence-transformers)"},
        "configuracion": {"candidatos": "Top-10 BGE-M3 congelado (4A)", "top_k": rr.TOP_K, "max_length": args.max_length,
                          "batch_size": args.batch_size, "dtype": args.dtype, "device": device,
                          "desempate": "rank original BGE-M3", "pares_truncados": scorer.truncated_pairs,
                          "tokens_par_max": max(scorer.pair_token_lengths)},
        "entradas": {rel_bge: sha_bge,
                     rr.JUDGMENTS.relative_to(rr.PROJECT_ROOT).as_posix(): rr.sha256_file(rr.JUDGMENTS),
                     rr.BASELINE_METRICS.relative_to(rr.PROJECT_ROOT).as_posix(): rr.sha256_file(rr.BASELINE_METRICS)},
        "hardware": {"gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
                     "vram_total_bytes": torch.cuda.get_device_properties(0).total_memory if device == "cuda" else None,
                     "parametros_en": param_devices, "offload": param_devices != ["cuda:0"] and device == "cuda"},
        "tiempos": {"carga_modelo_s": load_s,
                    "pasada_1_total_s": passes[0]["total_s"], "pasada_2_total_s": passes[1]["total_s"],
                    "consultas": len(candidates), "pares": len(candidates) * rr.TOP_K,
                    "pasada_2_media_ms_por_consulta": sum(all_ms) / len(all_ms),
                    "pasada_2_max_ms_por_consulta": max(all_ms),
                    "pasada_1_primera_consulta_ms": next(iter(per_query_ms[0].values()))},
        "vram": {"torch_pico_asignado_bytes": peak_alloc, "torch_pico_reservado_bytes": peak_reserved,
                 "nvidia_smi_usado_antes_mib": gpu_before, "nvidia_smi_usado_despues_mib": gpu_after,
                 "nota": "nvidia-smi incluye otros procesos (API rag-engine con BGE-M3, Ollama)"},
        "reproducibilidad": {"mismo_orden_en_2_pasadas": same_order, "max_diff_score": max_score_diff},
        "complementario_fp16": fp16,
        "software": {"python": platform.python_version(), "torch": torch.__version__,
                     "transformers": transformers.__version__, "sentence-transformers": sentence_transformers.__version__},
    }
    rr.dump_json(OUT_DIR / "run.json", run)
    write_report(metrics, run, ranked, candidates, lookup)
    print(json.dumps({"strict": diffs["strict"], "lenient": diffs["lenient"]}, indent=1))
    print(f"Carga {load_s:.1f}s | pasada2 {passes[1]['total_s']:.2f}s | media {run['tiempos']['pasada_2_media_ms_por_consulta']:.0f} ms/consulta")
    return 0


def decision(m, run) -> str:
    """Criterio fijado antes del experimento: integrar solo si mejora claramente Hit@1 strict y/o MRR strict
    sin degradar significativamente el resto; una mejora marginal con mucha más latencia no se integra."""
    d = m["diferencia"]
    better = d["strict"]["Hit@1_count"] >= 2 or d["strict"]["MRR@10"] >= 0.05
    worse = min(d["strict"]["Hit@1_count"], d["strict"]["Hit@3_count"], d["lenient"]["Hit@1_count"],
                d["lenient"]["Hit@3_count"]) < 0 or d["lenient"]["MRR@10"] < -0.02
    q = m["por_consulta"]["strict"]
    n = {c: sum(1 for v in q.values() if v["cambio"] == c) for c in ("mejoró", "empeoró", "igual")}
    verdict = ("**Integrar** (cumple el criterio)." if better and not worse else
               "**No integrar todavía.** No mejora de forma clara Hit@1 strict ni MRR strict, y degrada otras métricas.")
    return (f"{verdict} Hit@1 strict {d['strict']['Hit@1_count']:+d}, MRR strict {d['strict']['MRR@10']:+.3f}, "
            f"MRR laxo {d['lenient']['MRR@10']:+.3f}. Por consulta (estricto): {n['mejoró']} mejoran, {n['empeoró']} empeoran, "
            f"{n['igual']} iguales: el reranker reordena mucho, pero sus aciertos y errores se compensan. "
            f"Coste añadido: ~{run['tiempos']['pasada_2_media_ms_por_consulta']:.0f} ms/consulta en fp32 "
            f"(~{(run.get('complementario_fp16') or {}).get('media_ms_por_consulta', float('nan')):.0f} ms en fp16) y ~2,4 GB de VRAM "
            "en una GPU de 8 GB ya compartida con BGE-M3 y qwen2.5:7b. Criterio usado: mejora de ≥ 2 consultas en Hit@1 "
            "strict o ≥ 0,05 de MRR strict, sin pérdidas en Hit@1/Hit@3 ni caída de MRR laxo > 0,02.\n")


def fmt_count(v):
    return f"{v}/15"


def write_report(m, run, ranked, candidates, lookup):
    b, a, d = m["baseline"], m["reranker"], m["diferencia"]
    L = ["# Fase 4B — Reranking BGE-M3 Top-10 con bge-reranker-v2-m3 (v0.1)\n",
         f"Fecha: {m['fecha_utc']}\n",
         "Experimento **offline**: se reordenan exactamente los 10 candidatos congelados de BGE-M3 (comparación 4A, "
         "`eval/resultados/model_comparison_v01/bge_m3.json`, SHA-256 verificado) y se evalúan con los juicios humanos "
         "consolidados en 4A.1 (sin juicios nuevos ni automáticos). No se modificó corpus, embeddings, PostgreSQL ni el prototipo.\n",
         f"- Modelo: `{run['modelo']['model_id']}` revisión `{run['modelo']['revision']}` "
         f"({run['modelo']['parametros'] / 1e6:.0f} M parámetros, cross-encoder).",
         f"- Configuración: `max_length={run['configuracion']['max_length']}`, dtype {run['configuracion']['dtype']}, "
         f"device {run['configuracion']['device']}, pares truncados: {run['configuracion']['pares_truncados']} "
         f"(par más largo: {run['configuracion']['tokens_par_max']} tokens). Empates: rank original.",
         "- Reglas: " + m["reglas"]["estricto"] + " / " + m["reglas"]["laxo"],
         "- Métricas sobre MD01-MD15; Q04 se analiza aparte (igual que 4A.1).\n"]
    for mode, title in (("strict", "estricto"), ("lenient", "laxo")):
        L += [f"## Métricas — criterio {title}\n", "| Métrica | BGE-M3 baseline | BGE-M3 + reranker | Diferencia |",
              "|---|---:|---:|---:|"]
        for k in (1, 3, 5, 10):
            key = f"Hit@{k}_count"
            L.append(f"| Hit@{k} {mode} | {fmt_count(b[mode][key])} | {fmt_count(a[mode][key])} | {d[mode][key]:+d} |")
        L.append(f"| MRR {mode} | {b[mode]['MRR@10']:.3f} | {a[mode]['MRR@10']:.3f} | {d[mode]['MRR@10']:+.3f} |\n")
    L += ["## Primer fragmento pertinente por consulta\n",
          "| Consulta | Estricto antes | Estricto después | Cambio | Laxo antes | Laxo después | Cambio |",
          "|---|---:|---:|---|---:|---:|---|"]
    for q, s in m["por_consulta"]["strict"].items():
        l = m["por_consulta"]["lenient"][q]
        L.append(f"| {q} | {s['antes'] or '—'} | {s['despues'] or '—'} | {s['cambio']} | {l['antes'] or '—'} | {l['despues'] or '—'} | {l['cambio']} |")
    qb, qa = m["q04"]["baseline"], m["q04"]["reranker"]
    L += ["\n## Q04 — signos de infección durante la quimioterapia\n",
          "| | Primer pertinente estricto | Primer pertinente laxo | Primer específico de infección | Fragmento histórico p. 62 |",
          "|---|---:|---:|---:|---:|",
          f"| BGE-M3 | {qb['primer_pertinente_estricto']} | {qb['primer_pertinente_laxo']} | {qb['primer_fragmento_especifico_infeccion']} | {qb['rank_fragmento_historico_p62']} |",
          f"| + reranker | {qa['primer_pertinente_estricto']} | {qa['primer_pertinente_laxo']} | {qa['primer_fragmento_especifico_infeccion']} | {qa['rank_fragmento_historico_p62']} |\n",
          "Top-10 Q04 reordenado:\n", "| Rank | Rank BGE-M3 | Score reranker | Grado | Específico | Documento · p. | Sección |",
          "|---:|---:|---:|---:|:-:|---|---|"]
    for r in ranked["Q04"]:
        j = lookup[("Q04", r["fragmento_id"])]
        L.append(f"| {r['rank']} | {r['rank_original']} | {r['score_reranker']:.3f} | {j['grado_humano']} | "
                 f"{j.get('q04_especifico_infeccion') or '—'} | {r['documento'][:28]} · {r['pagina_inicio']} | {(r['seccion'] or '—')[:50]} |")
    L += ["\n## MD10 — pérdida de peso\n", f"Consulta: «{candidates['MD10'][0]['consulta']}»\n",
          "| Rank | Rank BGE-M3 | Score reranker | Grado | Estricto | Sección | Observación humana |", "|---:|---:|---:|---:|:-:|---|---|"]
    for r in ranked["MD10"]:
        j = lookup[("MD10", r["fragmento_id"])]
        L.append(f"| {r['rank']} | {r['rank_original']} | {r['score_reranker']:.3f} | {j['grado_humano']} | "
                 f"{'Sí' if j['pertinente_estricto'] else 'No'} | {(r['seccion'] or '—')[:40]} | {(j.get('observacion_humana') or '')[:70]} |")
    t, v = run["tiempos"], run["vram"]
    L += ["\n## Rendimiento\n",
          f"- GPU: {run['hardware']['gpu']}; parámetros en {run['hardware']['parametros_en']} (offload: {'sí' if run['hardware']['offload'] else 'no'}).",
          f"- Carga del modelo: {t['carga_modelo_s']:.1f} s.",
          f"- {t['consultas']} consultas × 10 pares: pasada 1 {t['pasada_1_total_s']:.2f} s (incluye calentamiento; primera consulta "
          f"{t['pasada_1_primera_consulta_ms']:.0f} ms), pasada 2 {t['pasada_2_total_s']:.2f} s; media {t['pasada_2_media_ms_por_consulta']:.0f} ms/consulta "
          f"(máx. {t['pasada_2_max_ms_por_consulta']:.0f} ms).",
          f"- VRAM del proceso (torch): pico asignado {(v['torch_pico_asignado_bytes'] or 0) / 2**20:.0f} MiB, reservado "
          f"{(v['torch_pico_reservado_bytes'] or 0) / 2**20:.0f} MiB. nvidia-smi total: {v['nvidia_smi_usado_antes_mib']} → "
          f"{v['nvidia_smi_usado_despues_mib']} MiB (incluye otros procesos).",
          f"- Reproducibilidad: mismo orden en 2 pasadas: {run['reproducibilidad']['mismo_orden_en_2_pasadas']}; "
          f"diferencia máx. de score {run['reproducibilidad']['max_diff_score']:.2e}.",
          (f"- Complementario fp16: media {run['complementario_fp16']['media_ms_por_consulta']:.0f} ms/consulta "
           f"(máx. {run['complementario_fp16']['max_ms_por_consulta']:.0f} ms), mismo orden que fp32 en "
           f"{run['complementario_fp16']['consultas_con_mismo_orden_que_fp32']}/{run['complementario_fp16']['consultas']} consultas "
           f"(diferencia máx. de score {run['complementario_fp16']['max_diff_score']:.4f}); pico VRAM "
           f"{run['complementario_fp16']['vram_pico_asignado_bytes'] / 2**20:.0f} MiB. Las métricas oficiales son las de fp32.\n")
          if run.get("complementario_fp16") else "",
          "## Conclusión\n",
          decision(m, run),
          "## Limitaciones\n",
          "- 15 consultas: cada consulta vale 1/15 (6,7 puntos) de Hit@K; las diferencias deben leerse caso por caso.",
          "- El reranker solo puede reordenar los 10 candidatos de BGE-M3 (Hit@10 es un techo fijo, 15/15).",
          "- Juicios humanos únicos del proyecto (sin acuerdo inter-anotador).\n"]
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
