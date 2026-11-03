"""Ejecuta la suite automatizada del backend por tipo de prueba y consolida todos los resultados.

Entradas: pytest (unitarias, integración, funcionales, seguridad, IA), resultados E2E/configuración/accesibilidad
(e2e_rondaN.json), carga/estrés/volumen (carga_estres_volumen.json) y validación técnica del RAG (eval/resultados).
Salidas: pruebas/resultados/resumen_pruebas.json y pruebas/resultados/reporte_pruebas.md
Uso: python pruebas/consolidar.py [--ronda 2]
"""
import argparse
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "pruebas" / "resultados"
TIPOS = [("unitaria", "Unitarias"), ("integracion", "Integración (API + BD + índice)"), ("funcional", "Funcionales por RF"),
         ("seguridad", "Seguridad"), ("ia", "Componente de IA (RAG)")]


def run_pytest(marker: str, ronda: int) -> dict:
    xml = OUT / f"ronda{ronda}" / f"junit_{marker}.xml"
    xml.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-m", marker, f"--junitxml={xml}"], cwd=ROOT / "backend",
                   capture_output=True)
    root = ET.parse(xml).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    casos = []
    for tc in suite.iter("testcase"):
        fail = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
        casos.append({"caso": tc.get("name"), "archivo": tc.get("classname", "").split(".")[-1],
                      "estado": "fallido" if fail is not None else ("omitido" if tc.find("skipped") is not None else "aprobado"),
                      "tiempo_s": round(float(tc.get("time", 0)), 3),
                      "detalle": (fail.get("message", "")[:300] if fail is not None else "")})
    return {"total": len(casos), "aprobadas": sum(c["estado"] == "aprobado" for c in casos),
            "fallidas": sum(c["estado"] == "fallido" for c in casos), "casos": casos}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ronda", type=int, default=2)
    a = ap.parse_args()
    res = {"ronda": a.ronda, "fecha": time.strftime("%Y-%m-%d %H:%M"), "ambiente": "pruebas (datos ficticios)", "por_tipo": {}}
    for m, label in TIPOS:
        r = run_pytest(m, a.ronda)
        res["por_tipo"][label] = {k: r[k] for k in ("total", "aprobadas", "fallidas")}
        res.setdefault("detalle", {})[label] = r["casos"]
    e2e_f = OUT / f"e2e_ronda{a.ronda}.json"
    if e2e_f.exists():
        e2e = json.loads(e2e_f.read_text(encoding="utf-8"))
        res["por_tipo"]["Extremo a extremo (E2E)"] = {"total": len(e2e["e2e"]), "aprobadas": sum(x["estado"] == "aprobado" for x in e2e["e2e"]),
                                                     "fallidas": sum(x["estado"] != "aprobado" for x in e2e["e2e"])}
        res["por_tipo"]["Configuración (tamaños de pantalla)"] = {"total": len(e2e["configuracion"]),
                                                                  "aprobadas": sum(x["estado"] == "aprobado" for x in e2e["configuracion"]),
                                                                  "fallidas": sum(x["estado"] != "aprobado" for x in e2e["configuracion"])}
        v = e2e["accesibilidad"]
        res["por_tipo"]["Accesibilidad automática (axe-core)"] = {"total": v["pantallas_evaluadas"],
            "aprobadas": sum(not d["violaciones"] for d in v["detalle"]), "fallidas": sum(bool(d["violaciones"]) for d in v["detalle"])}
        res["e2e"] = e2e
    c = OUT / "carga_estres_volumen.json"
    if c.exists():
        res["carga"] = json.loads(c.read_text(encoding="utf-8"))
    m = ROOT / "eval" / "resultados" / "metricas.json"
    if m.exists():
        res["validacion_rag"] = json.loads(m.read_text(encoding="utf-8"))
    (OUT / "resumen_pruebas.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    L = [f"# Reporte consolidado de pruebas · ronda {a.ronda}", "", f"Fecha: {res['fecha']} · Ambiente: {res['ambiente']}", "",
         "| Tipo de prueba | Total | Aprobadas | Fallidas |", "|---|---:|---:|---:|"]
    for k, v in res["por_tipo"].items():
        L.append(f"| {k} | {v['total']} | {v['aprobadas']} | {v['fallidas']} |")
    tot = [sum(v[k] for v in res["por_tipo"].values()) for k in ("total", "aprobadas", "fallidas")]
    L.append(f"| **Total** | **{tot[0]}** | **{tot[1]}** | **{tot[2]}** |")
    if "carga" in res:
        cg = res["carga"]
        L += ["", "## Carga, estrés y volumen", "", f"Entorno: {cg['entorno']['servidor']}, {cg['entorno']['cpu']} CPU.", "",
              "| Usuarios | Solicitudes/s | Errores | Mediana CRUD máx. (ms) | Mediana RAG (ms) | p95 RAG (ms) |", "|---:|---:|---:|---:|---:|---:|"]
        for lv in cg["carga"]:
            crud = max(v["p50_ms"] for k, v in lv["endpoints"].items() if "CRUD" in k)
            rag = lv["endpoints"]["POST consulta RAG"]
            L.append(f"| {lv['usuarios']} | {lv['rps']} | {lv['errores']} | {crud} | {rag['p50_ms']} | {rag['p95_ms']} |")
        L += ["", "| Estrés (solicitudes RAG simultáneas) | p50 (ms) | p95 (ms) | Error (%) |", "|---:|---:|---:|---:|"]
        for r in cg["estres"]:
            L.append(f"| {r['usuarios']} usuarios × 3 | {r['p50_ms']} | {r['p95_ms']} | {r['tasa_error_pct']} |")
        L.append(f"\nRNF-R01 (mediana CRUD ≤ 2 s y RAG ≤ 10 s): **{'cumple' if cg['rnf_r01']['cumple'] else 'no cumple'}**.")
    if "validacion_rag" in res:
        v = res["validacion_rag"]
        L += ["", "## Validación técnica del RAG", "", f"Precision@5 {v['precision_at_5']} (máx. {v['precision_at_5_maxima_posible']}), "
              f"Recall@5 {v['recall_at_5']}, MRR {v['mrr']}, trazabilidad {v['trazabilidad_pct']} %, abstención correcta "
              f"{v['abstencion_correcta_pct']} %, fuera de alcance {v['fuera_de_alcance_correcto_pct']} %."]
    fallidos = [(k, x) for k, cs in res["detalle"].items() for x in cs if x["estado"] == "fallido"]
    if fallidos:
        L += ["", "## Casos fallidos", ""] + [f"- {k}: `{x['caso']}` — {x['detalle']}" for k, x in fallidos]
    (OUT / "reporte_pruebas.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
