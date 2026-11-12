"""Fase 4B (experimental, offline): reranking de los Top-10 congelados de BGE-M3.

No consulta PostgreSQL ni genera candidatos nuevos: reordena exactamente los 10 fragmentos que BGE-M3 devolvió
en la comparación 4A (eval/resultados/model_comparison_v01/bge_m3.json) y evalúa con los juicios humanos
consolidados, reutilizando las funciones de métricas de scripts/apply_human_review.py (mismas reglas strict/lenient).
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
import hashlib
import importlib.util
import json
from pathlib import Path

from .config import PROJECT_ROOT

COMPARISON_DIR = PROJECT_ROOT / "eval" / "resultados" / "model_comparison_v01"
BGE_RESULTS = COMPARISON_DIR / "bge_m3.json"
JUDGMENTS = COMPARISON_DIR / "judgments_human_reviewed.json"
BASELINE_METRICS = COMPARISON_DIR / "metrics_human_reviewed.json"
APPLY_SCRIPT = PROJECT_ROOT / "scripts" / "apply_human_review.py"
TOP_K = 10

ScoreFn = Callable[[str, Sequence[str]], Sequence[float]]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def human_review_module():
    """Importa scripts/apply_human_review.py para reutilizar compute_metrics/q04_analysis/md10_top5 sin copiarlas."""
    spec = importlib.util.spec_from_file_location("apply_human_review", APPLY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_sha256(judgments: dict, relative: str) -> str | None:
    for src in judgments.get("fuentes", {}).get("fuentes_validadas", []):
        if src["ruta"] == relative:
            return src["sha256"]
    return None


def load_frozen_candidates(data: dict) -> dict[str, list[dict]]:
    """Agrupa por consulta y valida: exactamente 10 candidatos, ranks 1..10, sin fragmentos repetidos."""
    by_query: dict[str, list[dict]] = defaultdict(list)
    for row in data["resultados"]:
        by_query[row["consulta_id"]].append(row)
    for qid, rows in by_query.items():
        rows.sort(key=lambda r: r["rank"])
        if [r["rank"] for r in rows] != list(range(1, TOP_K + 1)):
            raise ValueError(f"{qid}: se esperaban ranks 1..{TOP_K}, hay {[r['rank'] for r in rows]}.")
        if len({r["fragmento_id"] for r in rows}) != TOP_K:
            raise ValueError(f"{qid}: fragmentos repetidos en el Top-{TOP_K}.")
        if len({r["consulta"] for r in rows}) != 1:
            raise ValueError(f"{qid}: texto de consulta inconsistente.")
    return dict(by_query)


def rerank_query(rows: list[dict], score_fn: ScoreFn) -> list[dict]:
    """Reordena los candidatos de UNA consulta por score del reranker (desc.). Empates: rank original.

    Conserva todos los campos originales; añade rank_original, score_bge_m3 y score_reranker; reasigna rank.
    """
    query = rows[0]["consulta"]
    scores = [float(s) for s in score_fn(query, [r["texto"] for r in rows])]
    if len(scores) != len(rows):
        raise ValueError("El reranker devolvió un número de scores distinto al de candidatos.")
    scored = [dict(r, rank_original=r["rank"], score_bge_m3=r["similitud"], score_reranker=s)
              for r, s in zip(rows, scores)]
    scored.sort(key=lambda r: (-r["score_reranker"], r["rank_original"]))
    for new_rank, r in enumerate(scored, start=1):
        r["rank"] = new_rank
    if {r["fragmento_id"] for r in scored} != {r["fragmento_id"] for r in rows}:
        raise AssertionError("El reranking alteró el conjunto de candidatos.")
    return scored


def rerank_all(candidates: dict[str, list[dict]], score_fn: ScoreFn) -> dict[str, list[dict]]:
    return {qid: rerank_query(rows, score_fn) for qid, rows in sorted(candidates.items())}


def pair_lookup(judgments: dict) -> dict[tuple[str, str], dict]:
    return {(p["consulta_id"], p["fragmento_id"]): p for p in judgments["juicios_pares"]}


def as_model_data(ranked: dict[str, list[dict]]) -> dict:
    return {"resultados": [r for rows in ranked.values() for r in rows]}


def evaluate(ranked: dict[str, list[dict]], judgments: dict, alias: str) -> dict:
    """Métricas strict/lenient (MD01-MD15) + análisis Q04 y MD10 con las funciones de la evaluación humana 4A.1."""
    hr = human_review_module()
    lookup = pair_lookup(judgments)
    missing = [(q, r["fragmento_id"]) for q, rows in ranked.items() for r in rows if (q, r["fragmento_id"]) not in lookup]
    if missing:
        raise ValueError(f"Candidatos sin juicio humano: {missing}")
    model_data = {alias: as_model_data(ranked)}
    # q04_analysis lee las posiciones desde `ocurrencias` del modelo 'bge-m3': se sustituyen por las de este ranking.
    q04_ranks = {r["fragmento_id"]: r["rank"] for r in ranked.get("Q04", [])}
    q04_pairs = [dict(p, ocurrencias=[{"modelo": "bge-m3", "rank": q04_ranks[p["fragmento_id"]]}])
                 for p in judgments["juicios_pares"] if p["consulta_id"] == "Q04" and p["fragmento_id"] in q04_ranks]
    return {
        "strict": hr.compute_metrics(model_data, lookup, "strict")[alias],
        "lenient": hr.compute_metrics(model_data, lookup, "lenient")[alias],
        "q04": hr.q04_analysis(q04_pairs)["bge-m3"],
        "md10_top5": hr.md10_top5(model_data, lookup)[alias],
    }


def compare_first_relevant(before: dict, after: dict) -> dict[str, dict]:
    out = {}
    for qid in sorted(before["primer_pertinente_por_consulta"]):
        a, b = before["primer_pertinente_por_consulta"][qid], after["primer_pertinente_por_consulta"][qid]
        ra, rb = (a or 99), (b or 99)
        out[qid] = {"antes": a, "despues": b,
                    "cambio": "mejoró" if rb < ra else "empeoró" if rb > ra else "igual"}
    return out


class CrossEncoderScorer:
    """bge-reranker-v2-m3 vía sentence-transformers CrossEncoder. El score es el que devuelve `predict` (activación por
    defecto de la librería); cualquier activación monótona deja el mismo orden."""

    def __init__(self, model_id: str, revision: str, device: str, max_length: int, batch_size: int = 16,
                 dtype: str = "float32") -> None:
        import torch
        from sentence_transformers import CrossEncoder

        self.model_id, self.revision, self.device = model_id, revision, device
        self.max_length, self.batch_size, self.dtype = max_length, batch_size, dtype
        self.model = CrossEncoder(model_id, revision=revision, device=device, max_length=max_length,
                                  model_kwargs={"dtype": getattr(torch, dtype)})
        self.model.eval()
        self.tokenizer = self.model.tokenizer
        self.pair_token_lengths: list[int] = []

    def __call__(self, query: str, texts: Sequence[str]) -> list[float]:
        for t in texts:
            self.pair_token_lengths.append(len(self.tokenizer(query, t, truncation=False)["input_ids"]))
        scores = self.model.predict([(query, t) for t in texts], batch_size=self.batch_size,
                                    convert_to_numpy=True, show_progress_bar=False)
        return [float(s) for s in scores]

    @property
    def truncated_pairs(self) -> int:
        return sum(1 for n in self.pair_token_lengths if n > self.max_length)


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
