"""Procesa los resultados reales de las pruebas de usuario (ISO 9241-11): efectividad, eficiencia y satisfacción (SUS).
Uso: python analizar_usuarios.py   (lee resultados_participantes.csv y sus_respuestas.csv de esta carpeta)
"""
import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sus_score(row: dict) -> float:
    vals = [int(row[f"i{i}"]) for i in range(1, 11)]
    if any(v < 1 or v > 5 for v in vals):
        raise ValueError(f"Respuesta SUS fuera de rango en {row.get('participante')}")
    return 2.5 * sum((v - 1) if i % 2 == 0 else (5 - v) for i, v in enumerate(vals))


def adjective(s: float) -> str:          # Bangor, Kortum y Miller (2009)
    return ("excelente" if s >= 85 else "bueno" if s >= 72 else "aceptable" if s >= 68 else
            "regular" if s >= 51 else "deficiente")


def analizar(tareas: list[dict], sus: list[dict]) -> dict:
    out = {"n_participantes": len({r["participante"] for r in tareas} | {r["participante"] for r in sus}), "tareas": {}}
    by = {}
    for r in tareas:
        by.setdefault(r["tarea"], []).append(r)
    for t, rows in sorted(by.items()):
        ex = [float(r["exito(1/0.5/0)"]) for r in rows]
        tiempos = [float(r["tiempo_s"]) for r in rows if r["tiempo_s"]]
        out["tareas"][t] = {"n": len(rows), "exito_sin_ayuda_pct": round(100 * sum(e == 1 for e in ex) / len(ex), 1),
                            "efectividad_pct": round(100 * sum(ex) / len(ex), 1),
                            "tiempo_mediana_s": statistics.median(tiempos) if tiempos else None,
                            "errores_media": round(statistics.mean(int(r["errores"] or 0) for r in rows), 2)}
    if out["tareas"]:
        out["efectividad_global_pct"] = round(statistics.mean(v["efectividad_pct"] for v in out["tareas"].values()), 1)
        out["cumple_80_pct"] = all(v["exito_sin_ayuda_pct"] >= 80 for v in out["tareas"].values())
    if sus:
        scores = [sus_score(r) for r in sus]
        m = statistics.mean(scores)
        out["sus"] = {"n": len(scores), "media": round(m, 1), "de": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0,
                      "min": min(scores), "max": max(scores), "adjetivo": adjective(m), "cumple_68": m >= 68}
    return out


def main():
    leer = lambda f: list(csv.DictReader(open(HERE / f, encoding="utf-8"))) if (HERE / f).exists() else []
    tareas, sus = leer("resultados_participantes.csv"), leer("sus_respuestas.csv")
    if not tareas and not sus:
        print("Aún no hay resultados registrados. Complete los CSV después de las sesiones con participantes.")
        return
    res = analizar(tareas, sus)
    (HERE / "resultados_usuarios.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
