"""Procesamiento estadístico de la investigación (secciones 3.4.4 y 4.2 del informe).

Entrada: CSV con una fila por participante y las columnas
    codigo, zbi_pre_1..zbi_pre_22, zbi_post_1..zbi_post_22          (ítems ZBI-22, escala 1–5)
    us_1..us_15                                                      (opcional: cuestionario de usabilidad, 1–5)
Si solo dispone de totales, use las columnas codigo, zbi_pre, zbi_post.

Uso:
    python analysis/analisis_estadistico.py datos.csv
    python analysis/analisis_estadistico.py --demo        # genera y analiza datos SIMULADOS (solo para probar el script)

Pasos: depuración (rango 1–5, >10 % de ítems faltantes → excluido; omisiones menores → media personal),
puntaje total y categoría (Martín et al., 1996: ausente ≤46, leve 47–55, intensa ≥56), estadística descriptiva,
Shapiro-Wilk sobre D = pre − post, t de Student para muestras relacionadas o Wilcoxon, tamaño del efecto
(dz o r = Z/√N) y alfa de Cronbach.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ALPHA = 0.05


def categoria(total: float) -> str:
    return "ausente" if total <= 46 else ("leve" if total <= 55 else "intensa")


def cronbach_alpha(items: pd.DataFrame) -> float | None:
    items = items.dropna()
    k = items.shape[1]
    if k < 2 or len(items) < 3:
        return None
    var_items = items.var(axis=0, ddof=1).sum()
    var_total = items.sum(axis=1).var(ddof=1)
    return float(k / (k - 1) * (1 - var_items / var_total)) if var_total > 0 else None


def score_block(df: pd.DataFrame, prefix: str, n_items: int) -> tuple[pd.Series, pd.DataFrame]:
    cols = [f"{prefix}_{i}" for i in range(1, n_items + 1)]
    block = df[cols].apply(pd.to_numeric, errors="coerce")
    block = block.where((block >= 1) & (block <= 5))                    # fuera de rango → faltante
    missing = block.isna().sum(axis=1)
    block = block.apply(lambda r: r.fillna(r.mean()), axis=1)           # imputación por media personal
    total = block.sum(axis=1)
    total[missing > 0.10 * n_items] = np.nan                            # > 10 % faltantes → excluido
    return total, block


def magnitude_d(d):
    d = abs(d)
    return "grande" if d >= 0.8 else "mediano" if d >= 0.5 else "pequeño" if d >= 0.2 else "trivial"


def magnitude_r(r):
    r = abs(r)
    return "grande" if r >= 0.5 else "mediano" if r >= 0.3 else "pequeño" if r >= 0.1 else "trivial"


def demo_data(n=30, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        base = rng.normal(2.6, 0.45)
        change = rng.normal(0.30, 0.25)
        pre = np.clip(np.round(rng.normal(base, 0.7, 22)), 1, 5)
        post = np.clip(np.round(rng.normal(base - change, 0.7, 22)), 1, 5)
        us = np.clip(np.round(rng.normal(4.0, 0.7, 15)), 1, 5)
        r = {"codigo": f"CUI-{i + 1:03d}"}
        r.update({f"zbi_pre_{j + 1}": v for j, v in enumerate(pre)})
        r.update({f"zbi_post_{j + 1}": v for j, v in enumerate(post)})
        r.update({f"us_{j + 1}": v for j, v in enumerate(us)})
        rows.append(r)
    return pd.DataFrame(rows)


def analyze(df: pd.DataFrame, simulated: bool) -> dict:
    out = {"datos_simulados": simulated, "n_inicial": int(len(df))}
    if "zbi_pre_1" in df.columns:
        pre, pre_items = score_block(df, "zbi_pre", 22)
        post, post_items = score_block(df, "zbi_post", 22)
        out["alfa_cronbach_zbi_pre"] = cronbach_alpha(pre_items)
        out["alfa_cronbach_zbi_post"] = cronbach_alpha(post_items)
    else:
        pre, post = pd.to_numeric(df["zbi_pre"], errors="coerce"), pd.to_numeric(df["zbi_post"], errors="coerce")
    data = pd.DataFrame({"codigo": df["codigo"], "pre": pre, "post": post}).dropna()
    data["D"] = data["pre"] - data["post"]
    n = len(data)
    out["n_analizado"] = n
    desc = {}
    for col in ("pre", "post", "D"):
        s = data[col]
        desc[col] = {"media": round(s.mean(), 2), "de": round(s.std(ddof=1), 2), "mediana": round(s.median(), 2),
                     "ric": round(s.quantile(.75) - s.quantile(.25), 2), "min": float(s.min()), "max": float(s.max())}
    out["descriptivos"] = desc
    out["categorias_pre"] = data["pre"].map(categoria).value_counts().to_dict()
    out["categorias_post"] = data["post"].map(categoria).value_counts().to_dict()

    sw = stats.shapiro(data["D"])
    out["shapiro_wilk"] = {"W": round(float(sw.statistic), 4), "p": round(float(sw.pvalue), 4)}
    if sw.pvalue > ALPHA:
        t = stats.ttest_rel(data["pre"], data["post"])
        dz = data["D"].mean() / data["D"].std(ddof=1)
        out["prueba"] = {"nombre": "t de Student para muestras relacionadas", "t": round(float(t.statistic), 3),
                         "gl": n - 1, "p": float(t.pvalue), "dz": round(float(dz), 3), "magnitud": magnitude_d(dz)}
    else:
        w = stats.wilcoxon(data["pre"], data["post"], method="approx")
        z = stats.norm.isf(w.pvalue / 2) * np.sign(data["D"].median() or 1)
        r = z / math.sqrt(n)
        out["prueba"] = {"nombre": "Wilcoxon de rangos con signo", "W": float(w.statistic), "Z": round(float(z), 3),
                         "p": float(w.pvalue), "r": round(float(r), 3), "magnitud": magnitude_r(r)}
    p = out["prueba"]["p"]
    reduced = desc["post"]["media"] < desc["pre"]["media"]
    out["decision"] = ("Se rechaza H0" if p < ALPHA else "No se rechaza H0") + f" (p = {p:.4f}, α = {ALPHA})." + (
        " La sobrecarga media disminuyó tras la intervención." if p < ALPHA and reduced else "")

    us_cols = [f"us_{i}" for i in range(1, 16)]
    if all(c in df.columns for c in us_cols):
        us = df[us_cols].apply(pd.to_numeric, errors="coerce")
        dims = {"facilidad_uso": us_cols[0:5], "utilidad_percibida": us_cols[5:10], "confianza_transparencia": us_cols[10:15]}
        out["usabilidad"] = {k: {"media": round(us[c].mean(axis=1).mean(), 2), "mediana": round(us[c].mean(axis=1).median(), 2),
                                 "alfa_cronbach": cronbach_alpha(us[c])} for k, c in dims.items()}
        out["usabilidad"]["alfa_cronbach_total"] = cronbach_alpha(us)
    return out, data


def figures(data: pd.DataFrame, outdir: Path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.boxplot([data["pre"], data["post"]], tick_labels=["Pre-test (O1)", "Post-test (O2)"])
    for _, r in data.iterrows():
        ax.plot([1, 2], [r["pre"], r["post"]], color="#9bb", lw=.6, alpha=.6)
    ax.axhline(46.5, ls="--", lw=.8, color="#999"); ax.axhline(55.5, ls="--", lw=.8, color="#999")
    ax.set_ylabel("Puntaje ZBI-22"); ax.set_title("Sobrecarga del cuidador antes y después")
    fig.tight_layout()
    p = outdir / "zbi_pre_post.png"
    fig.savefig(p, dpi=150)
    return [str(p)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--salida", default=str(HERE / "resultados"))
    a = ap.parse_args()
    if not a.csv and not a.demo:
        ap.error("indique un CSV o use --demo")
    df = demo_data() if a.demo else pd.read_csv(a.csv)
    out, data = analyze(df, simulated=a.demo)
    outdir = Path(a.salida)
    outdir.mkdir(parents=True, exist_ok=True)
    out["figuras"] = figures(data, outdir)
    (outdir / "resultados_estadisticos.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    if a.demo:
        df.to_csv(HERE / "datos_demo" / "zbi_usabilidad_SIMULADO.csv", index=False)
        print("ATENCIÓN: datos SIMULADOS, solo para verificar el script. No los reporte como resultados.\n")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
