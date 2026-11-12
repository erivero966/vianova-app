"""Pruebas rápidas de la Fase 4B (sin descargar el reranker): reordenamiento y métricas sobre datos congelados."""
import json

import pytest

from src import reranking as rr


def frozen():
    return json.loads(rr.BGE_RESULTS.read_text(encoding="utf-8"))


def judgments():
    return json.loads(rr.JUDGMENTS.read_text(encoding="utf-8"))


def reverse_scorer(query, texts):
    """Scorer determinista: invierte el orden original (el último candidato recibe el score más alto)."""
    return [float(i) for i in range(len(texts))]


def row(qid, rank, frag, sim=0.5):
    return {"consulta_id": qid, "consulta": "q", "rank": rank, "fragmento_id": frag, "texto": f"t{rank}",
            "similitud": sim, "distancia": 1 - sim}


def test_fuente_congelada_es_la_validada_por_la_evaluacion_humana():
    rel = rr.BGE_RESULTS.relative_to(rr.PROJECT_ROOT).as_posix()
    assert rr.sha256_file(rr.BGE_RESULTS) == rr.expected_sha256(judgments(), rel)


def test_candidatos_congelados_16_consultas_por_10():
    cands = rr.load_frozen_candidates(frozen())
    assert sorted(cands) == [f"MD{i:02d}" for i in range(1, 16)] + ["Q04"]
    assert all(len(rows) == 10 for rows in cands.values())


def test_preserva_los_mismos_10_candidatos_e_ids():
    cands = rr.load_frozen_candidates(frozen())
    ranked = rr.rerank_all(cands, reverse_scorer)
    for qid, rows in cands.items():
        assert sorted(r["fragmento_id"] for r in ranked[qid]) == sorted(r["fragmento_id"] for r in rows)
        orig = {r["fragmento_id"]: r for r in rows}
        for r in ranked[qid]:   # trazabilidad intacta
            o = orig[r["fragmento_id"]]
            assert (r["documento"], r["pagina_inicio"], r["seccion"], r["texto"]) == \
                   (o["documento"], o["pagina_inicio"], o["seccion"], o["texto"])
            assert r["rank_original"] == o["rank"] and r["score_bge_m3"] == o["similitud"]


def test_no_modifica_los_candidatos_de_entrada():
    cands = rr.load_frozen_candidates(frozen())
    before = json.dumps(cands, sort_keys=True)
    rr.rerank_all(cands, reverse_scorer)
    assert json.dumps(cands, sort_keys=True) == before


def test_ordena_por_score_del_reranker_desc():
    rows = [row("X", i, f"f{i}") for i in range(1, 11)]
    scores = [0.1, 0.9, 0.3, 0.8, 0.2, 0.7, 0.4, 0.6, 0.5, 0.0]
    out = rr.rerank_query(rows, lambda q, t: scores)
    assert [r["score_reranker"] for r in out] == sorted(scores, reverse=True)
    assert [r["fragmento_id"] for r in out[:3]] == ["f2", "f4", "f6"]
    assert [r["rank"] for r in out] == list(range(1, 11))


def test_empates_conservan_el_orden_original():
    rows = [row("X", i, f"f{i}") for i in range(1, 11)]
    out = rr.rerank_query(rows, lambda q, t: [1.0] * 10)
    assert [r["fragmento_id"] for r in out] == [f"f{i}" for i in range(1, 11)]


def test_rechaza_scores_incompletos_y_candidatos_invalidos():
    rows = [row("X", i, f"f{i}") for i in range(1, 11)]
    with pytest.raises(ValueError):
        rr.rerank_query(rows, lambda q, t: [1.0] * 9)
    with pytest.raises(ValueError):
        rr.load_frozen_candidates({"resultados": rows[:9]})
    dup = rows[:9] + [row("X", 10, "f1")]
    with pytest.raises(ValueError):
        rr.load_frozen_candidates({"resultados": dup})


def test_metricas_baseline_reproducen_la_evaluacion_humana_4a1():
    cands = rr.load_frozen_candidates(frozen())
    m = rr.evaluate(cands, judgments(), "bge-m3")
    s, l = m["strict"], m["lenient"]
    assert (s["Hit@1_count"], s["Hit@3_count"], s["Hit@5_count"], s["Hit@10_count"]) == (9, 12, 15, 15)
    assert s["MRR@10"] == pytest.approx(0.7289, abs=1e-4)
    assert (l["Hit@1_count"], l["Hit@3_count"], l["Hit@5_count"], l["Hit@10_count"]) == (11, 15, 15, 15)
    assert l["MRR@10"] == pytest.approx(0.8444, abs=1e-4)
    assert m["q04"]["primer_pertinente_estricto"] == 2 and m["q04"]["rank_fragmento_historico_p62"] == 5
    assert s["primer_pertinente_por_consulta"]["MD10"] == 5


def test_metricas_siguen_el_nuevo_orden():
    """Si el scorer sube el primer pertinente estricto al rank 1 en todas las consultas, Hit@1 = 15/15 y MRR = 1."""
    j = judgments()
    lookup = rr.pair_lookup(j)
    cands = rr.load_frozen_candidates(frozen())

    def oracle(query, texts):
        qid = next(q for q, rows in cands.items() if rows[0]["consulta"] == query)
        by_text = {r["texto"]: r for r in cands[qid]}
        return [2.0 if lookup[(qid, by_text[t]["fragmento_id"])]["pertinente_estricto"] else 0.0 for t in texts]

    m = rr.evaluate(rr.rerank_all(cands, oracle), j, "oraculo")
    assert m["strict"]["Hit@1_count"] == 15 and m["strict"]["MRR@10"] == pytest.approx(1.0)
    cmp = rr.compare_first_relevant(rr.evaluate(cands, j, "b")["strict"], m["strict"])
    assert cmp["MD10"] == {"antes": 5, "despues": 1, "cambio": "mejoró"}
    assert cmp["MD01"]["cambio"] == "igual"


def test_reproducibilidad_basica():
    cands = rr.load_frozen_candidates(frozen())
    a, b = rr.rerank_all(cands, reverse_scorer), rr.rerank_all(cands, reverse_scorer)
    assert {q: [r["fragmento_id"] for r in rows] for q, rows in a.items()} == \
           {q: [r["fragmento_id"] for r in rows] for q, rows in b.items()}
