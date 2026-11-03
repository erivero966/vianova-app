"""Validación técnica del motor de recomendaciones y del flujo RAG (Técnica 4, Instrumento 6).

Uso:
    python eval/run_eval.py                      # evalúa con el τ configurado
    python eval/run_eval.py --tau 0.15           # evalúa con otro umbral
    python eval/run_eval.py --calibrar           # barre τ para elegir el umbral (usar un conjunto de calibración)
    python eval/run_eval.py --casos otro.json --k 5

Indicadores (sección 3.4.3 del informe):
    Precision@K = (1/|Q|) Σ |Pertinentes(q) ∩ TopK(q)| / K
    Trazabilidad (%) = respuestas con ≥1 fuente válida del corpus / respuestas emitidas × 100
    Abstención correcta (%) = consultas sin evidencia en las que el sistema se abstuvo / consultas sin evidencia × 100
Se reportan además Recall@K, acierto en la 1.ª posición, MRR y la tasa de falsas abstenciones.
"""
import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="vianova_eval_"))
shutil.copytree(ROOT / "backend" / "data" / "corpus", TMP / "corpus")
shutil.copy(ROOT / "backend" / "data" / "rules.json", TMP / "rules.json")
os.environ["VIANOVA_DATA_DIR"] = str(TMP)
os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("LLM_PROVIDER", "local")
sys.path.insert(0, str(ROOT / "backend"))

from app.main import init_db                       # noqa: E402
from app.db import SessionLocal                    # noqa: E402
from app.models import User, PatientProfile, Document   # noqa: E402
from app.rag.assistant import ask                  # noqa: E402
from app.recommender import recommend              # noqa: E402
from app import config                             # noqa: E402


def eval_user(db):
    u = User(code="EVAL-001", email="eval@vianova.local", full_name="Evaluación", password_hash="-", role="cuidador")
    db.add(u)
    db.flush()
    db.add(PatientProfile(user_id=u.id, treatments=[]))     # contexto neutro: se evalúa la pertinencia respecto a la consulta
    db.commit()
    db.refresh(u)
    return u


def run(db, user, cases, tau, k):
    rows = []
    incl = {d.id for d in db.query(Document).filter(Document.status == "incluido")}
    for c in cases:
        res = ask(db, c["consulta"], tau=tau)
        top = [r["doc_id"] for r in recommend(db, user, c["consulta"], k)] if c["tipo"] == "pertinencia" else []
        rel = set(c["pertinentes"])
        hits = [d for d in top if d in rel]
        rr = next((1 / (i + 1) for i, d in enumerate(top) if d in rel), 0.0)
        valid_src = any(s["doc_id"] in incl for s in res["sources"])
        rows.append({
            "id": c["id"], "tipo": c["tipo"], "consulta": c["consulta"], "esperado": c["esperado"],
            "pertinentes": ";".join(c["pertinentes"]), "top_k": ";".join(top), "pertinentes_en_top_k": len(hits),
            "precision_k": len(hits) / k if top else None, "recall_k": (len(hits) / len(rel)) if rel else None,
            "acierto_1": (1 if top and top[0] in rel else 0) if rel else None, "rr": rr if rel else None,
            "estado": res["status"], "fuente_mostrada": ";".join(s["doc_id"] for s in res["sources"]),
            "fuente_valida": valid_src, "similitud_max": res["top_score"],
            "veredicto": "superado" if (res["status"] == c["esperado"] or
                                        (c["esperado"] == "abstencion" and res["status"] == "fuera_de_alcance"))
            else "no superado",
        })
    return rows


def metrics(rows, k):
    pert = [r for r in rows if r["tipo"] == "pertinencia"]
    noev = [r for r in rows if r["tipo"] == "abstencion"]
    scope = [r for r in rows if r["tipo"] == "alcance"]
    answered = [r for r in rows if r["estado"] == "respondida"]
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    return {
        "n_casos": len(rows), "n_pertinencia": len(pert), "n_sin_evidencia": len(noev), "n_alcance": len(scope),
        f"precision_at_{k}": mean([r["precision_k"] for r in pert]),
        f"precision_at_{k}_maxima_posible": mean([min(len(r["pertinentes"].split(";")), k) / k for r in pert]),
        f"recall_at_{k}": mean([r["recall_k"] for r in pert]),
        "acierto_primera_posicion": mean([r["acierto_1"] for r in pert]),
        "mrr": mean([r["rr"] for r in pert]),
        "trazabilidad_pct": round(100 * sum(r["fuente_valida"] for r in answered) / len(answered), 1) if answered else None,
        "abstencion_correcta_pct": round(100 * sum(r["estado"] != "respondida" for r in noev) / len(noev), 1) if noev else None,
        "fuera_de_alcance_correcto_pct": round(100 * sum(r["estado"] == "fuera_de_alcance" for r in scope) / len(scope), 1) if scope else None,
        "falsas_abstenciones_pct": round(100 * sum(r["estado"] != "respondida" for r in pert) / len(pert), 1) if pert else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", default=str(ROOT / "eval" / "casos_prueba.json"))
    ap.add_argument("--tau", type=float, default=None)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--calibrar", action="store_true")
    ap.add_argument("--salida", default=str(ROOT / "eval" / "resultados"))
    a = ap.parse_args()
    cases = json.loads(Path(a.casos).read_text(encoding="utf-8"))["casos"]
    init_db()
    db = SessionLocal()
    user = eval_user(db)
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    if a.calibrar:
        print(f"{'tau':>6} {'respondidas_ok%':>16} {'abstencion_ok%':>15} {'balanceada':>11}")
        best = None
        for i in range(6, 36, 2):
            tau = i / 100
            m = metrics(run(db, user, cases, tau, a.k), a.k)
            ok_ans = 100 - m["falsas_abstenciones_pct"]
            bal = (ok_ans + m["abstencion_correcta_pct"]) / 2
            print(f"{tau:6.2f} {ok_ans:16.1f} {m['abstencion_correcta_pct']:15.1f} {bal:11.1f}")
            if best is None or bal > best[1]:
                best = (tau, bal)
        print(f"\nτ sugerido (exactitud balanceada máxima): {best[0]:.2f}  — fíjelo con RAG_TAU={best[0]:.2f}")
        return
    tau = config.RAG_TAU if a.tau is None else a.tau
    rows = run(db, user, cases, tau, a.k)
    m = metrics(rows, a.k)
    m["tau"] = tau
    m["k"] = a.k
    m["modo_generacion"] = config.LLM_PROVIDER
    (out / "metricas.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out / "ficha_casos_prueba.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(m, ensure_ascii=False, indent=1))
    fails = [r for r in rows if r["veredicto"] != "superado"]
    if fails:
        print(f"\nCasos no superados ({len(fails)}):")
        for r in fails:
            print(f"  {r['id']} [{r['tipo']}] {r['consulta']!r} -> {r['estado']} (sim={r['similitud_max']})")
    print(f"\nFicha completa: {out / 'ficha_casos_prueba.csv'}")


if __name__ == "__main__":
    main()
