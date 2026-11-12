from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'apply_human_review.py'
spec = importlib.util.spec_from_file_location('apply_human_review', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _load():
    map_data = mod.load_json(ROOT / 'eval/revision_humana_model_comparison_v01_map.json')
    pending, old = mod.build_review_maps(ROOT / 'eval/revision_humana_model_comparison_v01.xlsx', map_data)
    pairs, lookup, _ = mod.combined_judgments(pending, old, map_data)
    models = {
        'alia': mod.load_json(ROOT / 'eval/resultados/model_comparison_v01/alia.json'),
        'qwen3': mod.load_json(ROOT / 'eval/resultados/model_comparison_v01/qwen3.json'),
        'bge-m3': mod.load_json(ROOT / 'eval/resultados/model_comparison_v01/bge_m3.json'),
    }
    return map_data, pending, old, pairs, lookup, models


def test_revision_completa_y_distribucion():
    _, pending, old, _, _, _ = _load()
    assert len(pending) == 214
    assert len(old) == 75
    vals = [int(r['juicio_humano']) for r in pending]
    assert vals.count(0) == 152
    assert vals.count(1) == 37
    assert vals.count(2) == 25


def test_metricas_estrictas_y_laxas():
    _, _, _, _, lookup, models = _load()
    strict = mod.compute_metrics(models, lookup, 'strict')
    lenient = mod.compute_metrics(models, lookup, 'lenient')
    assert (strict['alia']['Hit@1_count'], strict['qwen3']['Hit@1_count'], strict['bge-m3']['Hit@1_count']) == (6, 7, 9)
    assert (strict['alia']['Hit@5_count'], strict['qwen3']['Hit@5_count'], strict['bge-m3']['Hit@5_count']) == (13, 12, 15)
    assert (lenient['alia']['Hit@1_count'], lenient['qwen3']['Hit@1_count'], lenient['bge-m3']['Hit@1_count']) == (6, 10, 11)
    assert (lenient['alia']['Hit@3_count'], lenient['qwen3']['Hit@3_count'], lenient['bge-m3']['Hit@3_count']) == (9, 13, 15)


def test_q04_humano():
    _, _, _, pairs, _, _ = _load()
    q04 = mod.q04_analysis(pairs)
    assert q04['alia']['primer_pertinente_estricto'] == 7
    assert q04['qwen3']['primer_pertinente_estricto'] == 9
    assert q04['bge-m3']['primer_pertinente_estricto'] == 2
    assert q04['alia']['rank_fragmento_historico_p62'] == 54
    assert q04['qwen3']['rank_fragmento_historico_p62'] == 22
    assert q04['bge-m3']['rank_fragmento_historico_p62'] == 5


def test_mismos_289_pares_unicos():
    _, _, _, pairs, lookup, _ = _load()
    assert len(pairs) == 289
    assert len(lookup) == 289
