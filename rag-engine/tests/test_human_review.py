"""Construcción de la planilla ciega de revisión humana (sin base de datos)."""

import json
import sys

import pytest

from src.config import PROJECT_ROOT
from src.human_review import (FORBIDDEN_COLUMNS, PENDING_COLUMNS, collect_pairs, first_relevant_ranks,
                              ordered, priority, read_xlsx_rows, write_xlsx)

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


def judgment(model, query, rank, frag, pertinent, kind="asistido_preliminar", motive="m", category=None):
    return {"modelo": model, "consulta_id": query, "rank": rank, "fragmento_id": frag, "pertinente": pertinent,
            "tipo_juicio": kind, "motivo": motive, "fuente_juicio": "f", "categoria": category}


def test_same_fragment_from_several_models_is_one_pair_with_all_occurrences():
    pairs = collect_pairs([judgment("alia", "MD01", 3, "a", True), judgment("qwen3", "MD01", 1, "a", True),
                           judgment("qwen3", "MD02", 2, "a", False)])
    assert set(pairs) == {("MD01", "a"), ("MD02", "a")}
    assert [(o["modelo"], o["rank"]) for o in pairs[("MD01", "a")]["occurrences"]] == [("alia", 3), ("qwen3", 1)]


def test_inconsistent_judgments_for_one_pair_are_rejected():
    with pytest.raises(ValueError, match="distintos"):
        collect_pairs([judgment("alia", "MD01", 1, "a", True), judgment("bge-m3", "MD01", 4, "a", False)])


def test_priority_rules():
    js = [judgment("alia", "MD01", 1, "x", False), judgment("alia", "MD01", 2, "p", True),
          judgment("alia", "MD01", 3, "lim", False, motive="[límite] dudoso"),
          judgment("alia", "MD01", 4, "intro", False, category="introduccion_general"),
          judgment("alia", "MD01", 5, "rest", False, category="otro_tema"),
          judgment("alia", "MD04", 3, "d", False), judgment("alia", "MD04", 1, "dp", True),
          judgment("alia", "MD05", 9, "none", False),
          judgment("alia", "MD10", 9, "w", False), judgment("alia", "MD10", 1, "wp", True)]
    pairs, firsts = collect_pairs(js), first_relevant_ranks(js)
    get = lambda q, f: priority((q, f), pairs[(q, f)], firsts)
    assert get("MD01", "x")[0] == get("MD01", "p")[0] == 1        # antes / en el primer pertinente
    assert get("MD05", "none") == (1, ["sin_pertinente_en_top10"])
    assert get("MD10", "w")[0] == 1                               # MD10 siempre prioridad 1
    assert get("MD01", "lim") == (2, ["caso_limite"])
    assert get("MD04", "d") == (3, ["caso_especial_MD04"])
    assert get("MD01", "intro") == (3, ["introduccion_vs_consejo"])
    assert get("MD01", "rest") == (4, ["resto_top10"])


def test_order_is_seeded_by_priority_and_independent_of_input_order():
    items = [{"prioridad": p, "consulta_id": f"MD{i:02d}", "fragmento_id": str(i)}
             for i, p in enumerate([2, 1, 1, 2, 1, 1, 1, 2])]
    a, b = ordered(items), ordered(list(reversed(items)))
    assert a == b
    assert [i["prioridad"] for i in a] == sorted(i["prioridad"] for i in items)
    assert ordered(items, seed=1) != a or len(items) < 3


def test_xlsx_roundtrip_and_validation(tmp_path):
    path = tmp_path / "x.xlsx"
    rows = [{"review_id": "R001", "texto": "Línea 1\n<b>& \x01ok", "juicio_humano": ""}]
    write_xlsx(path, [{"name": "S", "columns": ["review_id", "texto", "juicio_humano"], "rows": rows,
                       "validations": {"juicio_humano": ["0", "1", "2"]}}])
    back = read_xlsx_rows(path)
    assert back == [{"review_id": "R001", "texto": "Línea 1\n<b>& ok", "juicio_humano": ""}]
    import zipfile
    assert '"0,1,2"' in zipfile.ZipFile(path).read("xl/worksheets/sheet1.xml").decode()


@pytest.fixture(scope="module")
def built():
    if not (PROJECT_ROOT / "eval/resultados/model_comparison_v01/judgments.json").exists():
        pytest.skip("Faltan los artefactos de la comparación v01.")
    from build_human_review import build
    return build()


def test_real_build_counts_and_human_pairs_are_not_pending(built):
    pending, reviewed, _, _ = built
    judgments = json.loads((PROJECT_ROOT / "eval/resultados/model_comparison_v01/judgments.json").read_text())
    pairs = collect_pairs(judgments["juicios"])
    human = {k for k, v in pairs.items() if v["judgment"]["tipo_juicio"] == "humano"}
    assert {(r["consulta_id"], r["fragmento_id"]) for r in reviewed} == human and len(human) == 75
    keys = [(r["consulta_id"], r["fragmento_id"]) for r in pending]
    assert len(keys) == len(set(keys)) and not set(keys) & human
    assert set(pairs) - human <= set(keys)                       # los 210 asistidos están todos
    assert all(r["prioridad"] == 1 for r in pending if r["consulta_id"] in ("MD10", "Q04"))
    # Cada posición juzgada de los tres modelos vuelve a encontrarse en algún par.
    occ = {(o["modelo"], r["consulta_id"], o["rank"]) for r in pending + reviewed
           for o in r["_pair"]["occurrences"] if o["en_top10"]}
    assert len(occ) == 480


def test_visible_pending_sheet_is_blind(built):
    pending, _, _, _ = built
    assert not set(PENDING_COLUMNS) & FORBIDDEN_COLUMNS
    visible = [{c: r.get(c) for c in PENDING_COLUMNS} for r in pending]
    dump = json.dumps(visible, ensure_ascii=False)
    for marker in ("qwen", "bge", "alia", "asistido", "[límite]", "similitud"):
        assert marker not in dump.lower()
    assert all(v["juicio_humano"] == "" and v["observacion_humana"] == "" for v in visible)


def test_q04_includes_infection_section_beyond_top10(built):
    pending, _, _, _ = built
    q04 = [r for r in pending if r["consulta_id"] == "Q04"]
    target = next(r for r in q04 if r["fragmento_id"] == "95e107ed-5b94-4ad3-8be6-b9af4bb40946")
    assert sorted((o["modelo"], o["rank"]) for o in target["_pair"]["occurrences"]) == \
        [("alia", 54), ("bge-m3", 5), ("qwen3", 22)]
    section = [r for r in q04 if 58 <= r["pagina_inicio"] <= 62 and r["documento"].startswith("La quimioterapia")]
    assert len(section) == 7
