"""Pruebas de carga, estrés y volumen (RNF-R01: mediana ≤ 2 s en CRUD y ≤ 10 s en consultas RAG).

1. Volumen: base de PRUEBAS con N cuidadores ficticios y D días de historial (seed_ficticio).
2. Carga: 1, 10, 25 y 50 usuarios concurrentes ejecutando el recorrido típico del cuidador.
3. Estrés: 100, 150 y 200 usuarios concurrentes sobre la consulta RAG hasta superar 1 % de errores o p95 > 10 s.
4. Volumen de lectura: indicadores y exportación de registros con toda la base cargada.
Uso: python pruebas/carga/run_carga.py [--usuarios 200 --dias 30]
"""
import argparse
import asyncio
import json
import os
import platform
import random
import signal
import statistics
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
import run_e2e as base   # noqa: E402

OUT = base.OUT
BASE = base.BASE
CONSULTAS = ["tiene llagas en la boca qué puede comer", "qué hago si tiene náuseas", "fiebre durante la quimioterapia",
             "cómo prevenir caídas en casa", "me siento agotada de cuidarlo", "cuidado de la piel en radioterapia",
             "qué hacer con la diarrea", "cuál es la capital de Australia"]


def pct(v, p):
    if not v:
        return None
    v = sorted(v)
    k = max(0, min(len(v) - 1, int(round(p / 100 * (len(v) - 1)))))
    return round(v[k] * 1000, 1)


def resume(samples):
    out = {}
    for ep, rows in samples.items():
        lat = [t for t, ok in rows if ok]
        out[ep] = {"n": len(rows), "errores": sum(not ok for _, ok in rows),
                   "p50_ms": pct(lat, 50), "p95_ms": pct(lat, 95), "max_ms": pct(lat, 100)}
    return out


async def call(cli, samples, ep, method, url, **kw):
    t = time.perf_counter()
    try:
        r = await cli.request(method, url, **kw)
        ok = r.status_code < 400
    except Exception:
        ok = False
    samples.setdefault(ep, []).append((time.perf_counter() - t, ok))


async def caregiver_flow(cli, token, samples, iters, rnd):
    h = {"Authorization": f"Bearer {token}"}
    for _ in range(iters):
        await call(cli, samples, "GET agenda (CRUD)", "GET", "/api/tasks/agenda", headers=h)
        await call(cli, samples, "GET recomendaciones", "GET", "/api/recommendations", headers=h)
        await call(cli, samples, "POST consulta RAG", "POST", "/api/assistant/ask", headers=h,
                   json={"query": rnd.choice(CONSULTAS)})
        await call(cli, samples, "POST registro (CRUD)", "POST", "/api/events", headers=h,
                   json={"kind": "sintoma", "symptom": rnd.choice(["fatiga", "dolor", "nauseas"]),
                         "intensity": rnd.randint(1, 8), "confirmed": True, "channel": "seleccion"})
        await call(cli, samples, "GET avisos (CRUD)", "GET", "/api/alerts", headers=h)


async def level(tokens, users, iters, seed=1):
    samples = {}
    rnd = random.Random(seed)
    limits = httpx.Limits(max_connections=users + 10, max_keepalive_connections=users + 10)
    async with httpx.AsyncClient(base_url=BASE, timeout=60, limits=limits) as cli:
        t0 = time.perf_counter()
        await asyncio.gather(*[caregiver_flow(cli, tokens[i % len(tokens)], samples, iters, rnd) for i in range(users)])
        dur = time.perf_counter() - t0
    total = sum(len(v) for v in samples.values())
    return {"usuarios": users, "iteraciones": iters, "solicitudes": total, "duracion_s": round(dur, 2),
            "rps": round(total / dur, 1), "errores": sum(not ok for v in samples.values() for _, ok in v),
            "endpoints": resume(samples)}


async def stress(tokens, users):
    samples = {}
    rnd = random.Random(users)
    async with httpx.AsyncClient(base_url=BASE, timeout=60, limits=httpx.Limits(max_connections=users + 10)) as cli:
        t0 = time.perf_counter()
        await asyncio.gather(*[call(cli, samples, "POST consulta RAG", "POST", "/api/assistant/ask",
                                    headers={"Authorization": f"Bearer {tokens[i % len(tokens)]}"},
                                    json={"query": rnd.choice(CONSULTAS)}) for i in range(users) for _ in range(3)])
        dur = time.perf_counter() - t0
    r = resume(samples)["POST consulta RAG"]
    r.update(usuarios=users, solicitudes=users * 3, duracion_s=round(dur, 2), rps=round(users * 3 / dur, 1),
             tasa_error_pct=round(100 * r["errores"] / (users * 3), 2))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usuarios", type=int, default=200)
    ap.add_argument("--dias", type=int, default=30)
    a = ap.parse_args()
    data_dir = OUT / "tmp" / "datos_carga"
    env = dict(os.environ, APP_ENV="pruebas", VIANOVA_DATA_DIR=str(data_dir), LLM_PROVIDER="local")
    env.pop("DATABASE_URL", None)
    import shutil, subprocess
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    t0 = time.time()
    subprocess.run([sys.executable, "seed_ficticio.py", "--n", str(a.usuarios), "--dias", str(a.dias)], cwd=base.BACKEND,
                   env=env, check=True, capture_output=True)
    seed_s = round(time.time() - t0, 1)
    log = open(OUT / "servidor_carga.log", "w")
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(base.PORT), "--log-level", "warning"],
                           cwd=base.BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        for _ in range(60):
            try:
                httpx.get(BASE + "/api/health", timeout=1); break
            except Exception:
                time.sleep(0.5)
        tokens = []
        t0 = time.perf_counter()
        for i in range(50):
            r = httpx.post(BASE + "/api/auth/login", json={"email": f"ficticio{i + 1:04d}@ficticio.pe", "password": "Ficticio2026!"})
            tokens.append(r.json()["token"])
        login_ms = round((time.perf_counter() - t0) / 50 * 1000, 1)
        carga = [asyncio.run(level(tokens, u, 4 if u > 1 else 10)) for u in (1, 10, 25, 50)]
        estres = []
        for u in (100, 150, 200):
            r = asyncio.run(stress(tokens, u))
            estres.append(r)
            if r["tasa_error_pct"] > 1 or (r["p95_ms"] or 0) > 10000:
                break
        hi = {"Authorization": "Bearer " + httpx.post(BASE + "/api/auth/login", json={
            "email": "investigador@vianova.local", "password": "Investigador2026!"}).json()["token"]}
        vol = {}
        for name, url in (("indicadores (todos los participantes)", "/api/research/indicators"),
                          ("exportar registros CSV (8 semanas)", "/api/research/logs.csv")):
            t = time.perf_counter(); r = httpx.get(BASE + url, headers=hi, timeout=120)
            vol[name] = {"ms": round((time.perf_counter() - t) * 1000, 1), "estado": r.status_code, "bytes": len(r.content)}
        import sqlite3
        con = sqlite3.connect(data_dir / "vianova.db")
        filas = {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in
                 ("users", "tasks", "task_completions", "care_events", "alerts", "event_logs", "chunks")}
        con.close()
    finally:
        os.killpg(os.getpgid(srv.pid), signal.SIGTERM)
    crud = [e for lv in carga for k, e in lv["endpoints"].items() if "CRUD" in k]
    rag = [lv["endpoints"]["POST consulta RAG"] for lv in carga]
    out = {
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
        "entorno": {"cpu": os.cpu_count(), "sistema": platform.platform(), "python": platform.python_version(),
                    "servidor": "uvicorn, 1 proceso, SQLite (ambiente de pruebas)"},
        "volumen": {"cuidadores_ficticios": a.usuarios, "dias_historial": a.dias, "filas": filas,
                    "tamano_bd_mb": round((data_dir / "vianova.db").stat().st_size / 1e6, 2), "tiempo_generacion_s": seed_s,
                    "lecturas": vol},
        "login_promedio_ms": login_ms,
        "carga": carga,
        "estres": estres,
        "rnf_r01": {"crud_mediana_max_ms": max(e["p50_ms"] for e in crud), "rag_mediana_max_ms": max(e["p50_ms"] for e in rag),
                    "cumple": max(e["p50_ms"] for e in crud) <= 2000 and max(e["p50_ms"] for e in rag) <= 10000},
    }
    (OUT / "carga_estres_volumen.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("volumen", "login_promedio_ms", "rnf_r01")}, ensure_ascii=False, indent=1))
    for lv in carga:
        print(f"{lv['usuarios']:>3} usuarios: {lv['rps']} sol/s, errores {lv['errores']}, " +
              ", ".join(f"{k.split(' (')[0]} p50={v['p50_ms']} p95={v['p95_ms']}" for k, v in lv["endpoints"].items()))
    for r in estres:
        print(f"ESTRÉS {r['usuarios']}: p50={r['p50_ms']} p95={r['p95_ms']} max={r['max_ms']} errores={r['tasa_error_pct']}% rps={r['rps']}")


if __name__ == "__main__":
    main()
