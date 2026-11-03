"""Ejecuta sin modificar los casos existentes CF-02, CF-04, E2E-02 y E2E-04."""
from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidencias_funcionales"
LOGS = OUT / "logs"
SHOTS = OUT / "capturas" / "casos_existentes"
RUNTIME = OUT / "runtime_data" / "existentes"
LOGS.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(parents=True, exist_ok=True)


def run_pytest() -> int:
    cmd = [
        str(ROOT / "backend" / ".venv" / "bin" / "python"), "-m", "pytest", "-q",
        "tests/test_funcionales_rf.py::test_CF02_rf02_agenda_crear_ver_completar",
        "tests/test_funcionales_rf.py::test_CF04_rf04_registro_por_voz_requiere_confirmacion",
        f"--junitxml={LOGS / 'junit_CF02_CF04.xml'}",
    ]
    p = subprocess.run(cmd, cwd=ROOT / "backend", text=True, capture_output=True)
    text = "$ " + " ".join(cmd) + "\n" + p.stdout + p.stderr + f"\nCÓDIGO_SALIDA={p.returncode}\n"
    (LOGS / "pytest_CF02_CF04.txt").write_text(text, encoding="utf-8")
    print(text)
    return p.returncode


def load_e2e_module():
    path = ROOT / "pruebas" / "e2e" / "run_e2e.py"
    spec = importlib.util.spec_from_file_location("vianova_e2e_existente", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def run_e2e() -> int:
    mod = load_e2e_module()
    mod.OUT = OUT
    mod.SHOTS = SHOTS
    mod.results.clear()
    server = mod.start_server(RUNTIME)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                bypass_csp=True,
                viewport=mod.PHONE,
                locale="es-PE",
                timezone_id="America/Lima",
                has_touch=True,
                is_mobile=True,
            )
            ctx.set_default_timeout(10_000)
            page = ctx.new_page()
            mod.login(page, "demo@vianova.local", "Demo2026!")
            mod.run_case(page, "E2E-02", "RF-02", "Ver agenda, crear tarea y marcarla como hecha", mod.e2e02)
            mod.run_case(page, "E2E-04", "RF-04", "Registrar síntoma por texto con confirmación", mod.e2e04)
            ctx.close()
            browser.close()
    finally:
        os.killpg(os.getpgid(server.pid), signal.SIGTERM)
        server.wait(timeout=10)
    result = {
        "origen": "pruebas/e2e/run_e2e.py (funciones originales sin alterar)",
        "casos": mod.results,
        "codigo_salida": 0 if all(r["estado"] == "aprobado" for r in mod.results) else 1,
    }
    (LOGS / "e2e_existentes_RF02_RF04.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"[{r['estado'].upper()}] {r['id']} {r['escenario']} {r['error']}" for r in mod.results]
    lines.append(f"CÓDIGO_SALIDA={result['codigo_salida']}")
    (LOGS / "e2e_existentes_RF02_RF04.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return result["codigo_salida"]


if __name__ == "__main__":
    rc1 = run_pytest()
    rc2 = run_e2e()
    raise SystemExit(1 if rc1 or rc2 else 0)
