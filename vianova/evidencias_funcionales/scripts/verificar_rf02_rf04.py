"""Verificación reproducible ampliada de RF-02 y RF-04 sobre API, UI y SQLite."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidencias_funcionales"
LOGS = OUT / "logs"
SHOTS = OUT / "capturas"
DATA = OUT / "runtime_data" / "ampliada"
PORT = 8876
BASE = f"http://127.0.0.1:{PORT}"
PERU = timezone(timedelta(hours=-5))
results: list[dict] = []


def fingerprint() -> str:
    h = hashlib.sha256()
    files = sorted((ROOT / "backend" / "app").rglob("*.py")) + sorted((ROOT / "frontend" / "src").rglob("*"))
    for path in files:
        if path.is_file():
            h.update(str(path.relative_to(ROOT)).encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def db_one(sql: str, params=()):
    with sqlite3.connect(DATA / "vianova.db") as db:
        return db.execute(sql, params).fetchone()


def db_all(sql: str, params=()):
    with sqlite3.connect(DATA / "vianova.db") as db:
        return db.execute(sql, params).fetchall()


def add(case_id: str, rf: str, preconditions: str, inputs: str, steps: str,
        expected: str, observed: str, status: str, evidence: str):
    results.append({
        "id": case_id, "requerimiento": rf, "precondiciones": preconditions,
        "datos_entrada": inputs, "pasos": steps, "resultado_esperado": expected,
        "resultado_observado": observed, "estado": status, "evidencia": evidence,
    })
    print(f"[{status:13}] {case_id}: {observed}")


def api(client: httpx.Client, method: str, path: str, token: str | None = None, body=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        return client.request(method, BASE + path, headers=headers, json=body)
    except httpx.ReadError:
        # Una excepción no controlada (HTTP 500) puede cerrar la conexión
        # keep-alive; se abre otra para continuar documentando los demás casos.
        return httpx.request(method, BASE + path, headers=headers, json=body, timeout=10)


def start_server():
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, APP_ENV="pruebas", VIANOVA_DATA_DIR=str(DATA), LLM_PROVIDER="local")
    env.pop("DATABASE_URL", None)
    log = (LOGS / "servidor_verificacion.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
        cwd=ROOT / "backend", env=env, stdout=log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    for _ in range(80):
        try:
            if httpx.get(BASE + "/api/health", timeout=1).status_code == 200:
                return process, log
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("El servidor aislado no inició")


def login_ui(page, email: str, password: str):
    page.goto(BASE + "/#/")
    page.evaluate("localStorage.clear()")
    page.reload()
    page.get_by_label("Correo").fill(email)
    page.get_by_label("Contraseña").fill(password)
    page.get_by_role("button", name="Ingresar", exact=True).last.click()
    page.wait_for_selector("main#contenido")


def screenshot(page, name: str):
    path = SHOTS / name
    page.screenshot(path=str(path), full_page=True)
    return str(path.relative_to(ROOT))


def main() -> int:
    process, server_log = start_server()
    try:
        with httpx.Client(timeout=10) as client:
            email, password = "verificacion.rf@ficticio.pe", "Verificacion2026!"
            reg = api(client, "POST", "/api/auth/register", body={
                "full_name": "Cuidadora Verificación", "email": email,
                "password": password, "consent_study": True,
            })
            assert reg.status_code == 200, reg.text
            token = reg.json()["token"]

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 390, "height": 844}, locale="es-PE",
                    timezone_id="America/Lima", has_touch=True, is_mobile=True,
                )
                page = context.new_page()
                page.set_default_timeout(10_000)
                login_ui(page, email, password)

                # RF02-01: tres tipos.
                base_tasks = [
                    {"kind": "medicamento", "title": "Medicamento ficticio A", "instructions": "Según receta ficticia", "start_at": "2026-10-20T09:00:00", "recurrence": "unica"},
                    {"kind": "cita", "title": "Control ficticio", "instructions": "Llevar resumen", "start_at": "2026-10-20T10:00:00", "recurrence": "diaria", "end_date": "2026-10-21T23:59:00"},
                    {"kind": "actividad", "title": "Cambio de posición ficticio", "instructions": "Actividad de prueba", "start_at": "2026-10-20T22:30:00", "recurrence": "cada_n_horas", "every_hours": 3, "end_date": "2026-10-21T04:30:00"},
                ]
                created = []
                for payload in base_tasks:
                    r = api(client, "POST", "/api/tasks", token, payload)
                    assert r.status_code == 200, r.text
                    created.append(r.json())
                listed = api(client, "GET", "/api/tasks", token).json()
                ok = all(any(x["id"] == t["id"] and x["kind"] == t["kind"] and x["title"] == t["title"] and x["instructions"] == t["instructions"] for x in listed) for t in created)
                page.goto(BASE + "/#/agenda")
                page.get_by_role("heading", name="Agenda de cuidado").wait_for()
                page.get_by_label("Día").fill("2026-10-20")
                page.wait_for_timeout(600)
                ev = screenshot(page, "RF02-01_tres_tipos.png")
                add("RF02-01", "RF-02", "Cuidador autenticado; BD aislada", json.dumps(base_tasks, ensure_ascii=False),
                    "POST /api/tasks para medicamento, cita y actividad; GET /api/tasks; abrir Agenda.",
                    "Los tres se guardan y muestran con sus datos.",
                    f"Se recuperaron {len(listed)} tareas activas; tipos y campos coinciden={ok}.", "APROBADO" if ok else "FALLIDO", ev)

                # RF02-02: expectativas calculadas de forma independiente.
                med, cita, cross = created
                d20 = api(client, "GET", "/api/tasks/agenda?date=2026-10-20T00:00:00", token).json()["items"]
                d21 = api(client, "GET", "/api/tasks/agenda?date=2026-10-21T00:00:00", token).json()["items"]
                got_cross = [i["occurrence_at"][:19] for i in d20 + d21 if i["task"]["id"] == cross["id"]]
                expected_cross = ["2026-10-20T22:30:00", "2026-10-21T01:30:00", "2026-10-21T04:30:00"]
                got_med = [i["occurrence_at"][:19] for i in d20 if i["task"]["id"] == med["id"]]
                got_cita = [i["occurrence_at"][:19] for i in d20 + d21 if i["task"]["id"] == cita["id"]]
                expected_cita = ["2026-10-20T10:00:00", "2026-10-21T10:00:00"]
                ok = got_cross == expected_cross and got_med == ["2026-10-20T09:00:00"] and got_cita == expected_cita and len(got_cross) == len(set(got_cross))
                add("RF02-02", "RF-02", "Zona horaria America/Lima (UTC-5); tareas RF02-01", "Intervalo 2026-10-20..21; cada 3 h desde 22:30 hasta 04:30",
                    "Calcular manualmente las horas esperadas y compararlas con GET /api/tasks/agenda de ambos días.",
                    f"Cruce de medianoche exacto: {expected_cross}; sin duplicados.",
                    f"Única={got_med}; diaria={got_cita}; cada 3 h={got_cross}.", "APROBADO" if ok else "FALLIDO", "logs/resultados_ampliados.json")

                # RF02-03: nueva autenticación y recarga.
                relog = api(client, "POST", "/api/auth/login", body={"email": email, "password": password})
                token2 = relog.json().get("token", "")
                persisted = api(client, "GET", "/api/tasks", token2).json()
                page.reload(); page.get_by_role("heading", name="Agenda de cuidado").wait_for()
                ok = relog.status_code == 200 and {t["id"] for t in created}.issubset({t["id"] for t in persisted})
                add("RF02-03", "RF-02", "Tareas ya creadas", "Nueva sesión del mismo cuidador",
                    "Recargar UI, volver a autenticar por API y consultar tareas.", "Tareas y estados persisten.",
                    f"Nueva sesión HTTP {relog.status_code}; IDs persistentes={ok}.", "APROBADO" if ok else "FALLIDO", "logs/resultados_ampliados.json")
                token = token2

                # RF02-04 y RF02-05.
                occ_med, occ_cita = "2026-10-20T09:00:00", "2026-10-20T10:00:00"
                r_done = api(client, "POST", f"/api/tasks/{med['id']}/complete", token, {"occurrence_at": occ_med, "status": "hecha"})
                r_skip = api(client, "POST", f"/api/tasks/{cita['id']}/complete", token, {"occurrence_at": occ_cita, "status": "omitida"})
                page.goto(BASE + "/#/agenda"); page.get_by_label("Día").fill("2026-10-20"); page.wait_for_timeout(600)
                ev = screenshot(page, "RF02-04_estados_hecha_omitida.png")
                ag = api(client, "GET", "/api/tasks/agenda?date=2026-10-20", token).json()["items"]
                states = {(i["task"]["id"], i["occurrence_at"][:19]): i["status"] for i in ag}
                ok = r_done.status_code == r_skip.status_code == 200 and states[(med["id"], occ_med)] == "hecha" and states[(cita["id"], occ_cita)] == "omitida"
                add("RF02-04", "RF-02", "Dos ocurrencias sin cumplimiento", f"{occ_med}=hecha; {occ_cita}=omitida",
                    "Registrar ambos estados; recargar agenda y consultar API.", "Solo cambian las ocurrencias seleccionadas y persisten.",
                    f"Estados recuperados: hecha={states.get((med['id'], occ_med))}; omitida={states.get((cita['id'], occ_cita))}.", "APROBADO" if ok else "FALLIDO", ev)

                before_comp = db_one("SELECT count(*) FROM task_completions WHERE task_id=? AND datetime(occurrence_at)=datetime(?)", (med["id"], occ_med))[0]
                before_logs = db_one("SELECT count(*) FROM event_logs WHERE tipo_evento='tarea_completada' AND id_recurso=?", (f"TAR-{med['id']:04d}",))[0]
                duplicate = api(client, "POST", f"/api/tasks/{med['id']}/complete", token, {"occurrence_at": occ_med, "status": "hecha"})
                after_comp = db_one("SELECT count(*) FROM task_completions WHERE task_id=? AND datetime(occurrence_at)=datetime(?)", (med["id"], occ_med))[0]
                after_logs = db_one("SELECT count(*) FROM event_logs WHERE tipo_evento='tarea_completada' AND id_recurso=?", (f"TAR-{med['id']:04d}",))[0]
                ok = duplicate.status_code == 400 and before_comp == after_comp == 1 and before_logs == after_logs == 1
                add("RF02-05", "RF-02", "Ocurrencia ya marcada", occ_med,
                    "Repetir POST directo /complete y contar cumplimientos/registros antes y después.",
                    "Segundo intento rechazado sin duplicados.",
                    f"HTTP {duplicate.status_code}; cumplimientos {before_comp}->{after_comp}; logs {before_logs}->{after_logs}.", "APROBADO" if ok else "FALLIDO", "logs/resultados_ampliados.json")

                # RF02-06.
                deact_payload = {"kind": "actividad", "title": "Actividad recurrente a desactivar", "start_at": "2026-10-19T00:30:00", "recurrence": "cada_n_horas", "every_hours": 4}
                deact = api(client, "POST", "/api/tasks", token, deact_payload).json()
                api(client, "POST", f"/api/tasks/{deact['id']}/complete", token, {"occurrence_at": "2026-10-19T00:30:00", "status": "hecha"})
                rd = api(client, "DELETE", f"/api/tasks/{deact['id']}", token)
                active_ids = {x["id"] for x in api(client, "GET", "/api/tasks", token).json()}
                future = api(client, "GET", "/api/tasks/agenda?date=2026-10-22", token).json()["items"]
                hist = db_one("SELECT status FROM task_completions WHERE task_id=? AND datetime(occurrence_at)=datetime(?)", (deact["id"], "2026-10-19T00:30:00"))
                row = db_one("SELECT active FROM tasks WHERE id=?", (deact["id"],))
                page.goto(BASE + "/#/agenda"); page.wait_for_timeout(500)
                ev = screenshot(page, "RF02-06_tarea_desactivada.png")
                ok = rd.status_code == 200 and row == (0,) and deact["id"] not in active_ids and not any(i["task"]["id"] == deact["id"] for i in future) and hist == ("hecha",)
                add("RF02-06", "RF-02", "Tarea recurrente con un cumplimiento", json.dumps(deact_payload, ensure_ascii=False),
                    "DELETE /api/tasks/{id}; consultar tareas, agenda futura y SQLite.",
                    "Inactiva, sin ocurrencias futuras y con historial conservado.",
                    f"HTTP {rd.status_code}; active={row}; futura=0; historial={hist}.", "APROBADO" if ok else "FALLIDO", ev)

                # RF02-07: se considera rechazo correcto solo 4xx controlado.
                count_before = db_one("SELECT count(*) FROM tasks")[0]
                invalid_date = api(client, "POST", "/api/tasks", token, {"kind": "cita", "title": "Fecha inválida", "start_at": "no-es-fecha", "recurrence": "unica"})
                invalid_rec = api(client, "POST", "/api/tasks", token, {"kind": "cita", "title": "Recurrencia inválida", "start_at": "2026-10-20T12:00:00", "recurrence": "semanal"})
                empty = api(client, "POST", "/api/tasks", token, {"kind": "cita", "title": "", "start_at": "2026-10-20T12:00:00", "recurrence": "unica"})
                count_after = db_one("SELECT count(*) FROM tasks")[0]
                page.goto(BASE + "/#/agenda"); page.get_by_role("button", name="+ Nueva").click(); page.wait_for_timeout(200)
                required = page.get_by_label("Nombre", exact=False).first.get_attribute("required") is not None
                ev = screenshot(page, "RF02-07_validacion_formulario.png")
                ok = all(400 <= s < 500 for s in (invalid_date.status_code, invalid_rec.status_code, empty.status_code)) and count_before == count_after and required
                add("RF02-07", "RF-02", "Cuidador autenticado", "Fecha 'no-es-fecha'; recurrencia 'semanal'; título vacío",
                    "Enviar entradas inválidas a API; revisar obligatoriedad HTML; comparar cantidad en BD.",
                    "UI solicita corregir; API responde 4xx; no guarda.",
                    f"HTTP fecha={invalid_date.status_code}, recurrencia={invalid_rec.status_code}, vacío={empty.status_code}; filas {count_before}->{count_after}; required={required}.", "APROBADO" if ok else "FALLIDO", ev)

                # RF02-08.
                log_row = db_one("SELECT tipo_evento,id_recurso,hora_programada,resultado FROM event_logs WHERE tipo_evento='tarea_completada' AND id_recurso=?", (f"TAR-{med['id']:04d}",))
                ok = log_row is not None and log_row[1] == f"TAR-{med['id']:04d}" and str(log_row[2]).startswith(occ_med.replace("T", " "))
                add("RF02-08", "RF-02", "Cumplimiento RF02-04 guardado", f"Tarea {med['id']}, ocurrencia {occ_med}",
                    "Consultar event_logs directamente en SQLite.", "Registro de uso asociado a tarea y ocurrencia.",
                    f"Fila: {log_row}.", "APROBADO" if ok else "FALLIDO", "logs/consulta_sqlite.json")

                # RF04-01: texto y expectativas predefinidas.
                text_input = "Anoche vomitó tres veces con intensidad 6 de 10"
                before_events = db_one("SELECT count(*) FROM care_events")[0]
                parsed_r = api(client, "POST", "/api/events/parse", token, {"text": text_input})
                parsed = parsed_r.json()
                after_parse = db_one("SELECT count(*) FROM care_events")[0]
                page.goto(BASE + "/#/registrar"); page.locator("textarea").first.fill(text_input); page.get_by_role("button", name="Revisar").click()
                page.get_by_role("heading", name="Revise antes de guardar").wait_for()
                ev = screenshot(page, "RF04-01_propuesta_texto.png")
                expected_fields = {"symptom": "vomito", "frequency": 3, "intensity": 6, "moment": "anoche"}
                ok = all(parsed.get(k) == v for k, v in expected_fields.items()) and before_events == after_parse
                add("RF04-01", "RF-04", "Cuidador autenticado; conteo inicial conocido", text_input,
                    "POST /events/parse y abrir propuesta en UI sin confirmar.", f"Propuesta {expected_fields}; cero persistencia.",
                    f"Propuesta={{{', '.join(f'{k}: {parsed.get(k)!r}' for k in expected_fields)}}}; registros {before_events}->{after_parse}.", "APROBADO" if ok else "FALLIDO", ev)

                # RF04-02: selección rápida.
                page.get_by_role("button", name="Cancelar").click()
                count_before = db_one("SELECT count(*) FROM care_events")[0]
                page.get_by_role("button", name="Dolor", exact=True).click()
                page.get_by_role("heading", name="Revise antes de guardar").wait_for()
                ev = screenshot(page, "RF04-02_seleccion_rapida.png")
                selected = page.locator(".confirm-card select").nth(1).input_value()
                count_after = db_one("SELECT count(*) FROM care_events")[0]
                ok = selected == "dolor" and count_before == count_after
                add("RF04-02", "RF-04", "Pantalla Registrar abierta", "Botón rápido Dolor",
                    "Pulsar Dolor; inspeccionar propuesta y BD antes de confirmar.", "Propuesta de dolor y confirmación obligatoria.",
                    f"Síntoma seleccionado={selected}; registros {count_before}->{count_after}.", "APROBADO" if ok else "FALLIDO", ev)

                # RF04-03: corrección visible y guardado.
                page.locator('input[type="range"]').fill("4")
                page.get_by_label("Nota (opcional)").fill("Nota ficticia corregida desde la interfaz")
                page.get_by_role("button", name="Confirmar y guardar").click()
                page.get_by_text("Registro guardado").wait_for()
                saved = api(client, "GET", "/api/events?days=30", token).json()[0]
                ev = screenshot(page, "RF04-03_valor_corregido_guardado.png")
                ok = saved["symptom"] == "dolor" and saved["intensity"] == 4 and saved["text"] == "Nota ficticia corregida desde la interfaz" and saved["channel"] == "seleccion"
                add("RF04-03", "RF-04", "Propuesta rápida pendiente", "Cambiar intensidad a 4 y nota ficticia",
                    "Editar propuesta; Confirmar y guardar; consultar API.", "Se guarda el valor corregido.",
                    f"Guardado: síntoma={saved['symptom']}, intensidad={saved['intensity']}, canal={saved['channel']}.", "APROBADO" if ok else "FALLIDO", ev)

                # RF04-04: cancelar.
                count_before = db_one("SELECT count(*) FROM care_events")[0]
                page.get_by_role("button", name="Náuseas", exact=True).click()
                page.get_by_role("button", name="Cancelar").click()
                count_after = db_one("SELECT count(*) FROM care_events")[0]
                ev = screenshot(page, "RF04-04_cancelacion_sin_guardar.png")
                ok = count_before == count_after and page.get_by_role("heading", name="Selección rápida").is_visible()
                add("RF04-04", "RF-04", "Formulario sin propuesta", "Seleccionar Náuseas y cancelar",
                    "Comparar care_events antes/después.", "No se crea registro.",
                    f"Registros {count_before}->{count_after}; formulario inicial visible.", "APROBADO" if ok else "FALLIDO", ev)

                # RF04-05.
                count_before = db_one("SELECT count(*) FROM care_events")[0]
                false_r = api(client, "POST", "/api/events", token, {"kind": "sintoma", "symptom": "fatiga", "confirmed": False})
                missing_r = api(client, "POST", "/api/events", token, {"kind": "sintoma", "symptom": "fatiga"})
                count_after = db_one("SELECT count(*) FROM care_events")[0]
                ok = false_r.status_code == missing_r.status_code == 400 and count_before == count_after
                add("RF04-05", "RF-04", "Cuidador autenticado", "confirmed=false y campo confirmed ausente",
                    "POST directo /api/events; contar filas.", "Ambos rechazados sin persistencia.",
                    f"HTTP false={false_r.status_code}, ausente={missing_r.status_code}; filas {count_before}->{count_after}.", "APROBADO" if ok else "FALLIDO", "logs/resultados_ampliados.json")

                # RF04-06.
                valid_payload = {"kind": "observacion", "text": "Observación ficticia persistente", "channel": "texto", "confirmed": True, "occurred_at": "2026-10-19T07:15:00"}
                valid_r = api(client, "POST", "/api/events", token, valid_payload)
                event_id = valid_r.json()["event"]["id"]
                page.reload(); page.get_by_role("heading", name="Registrar").wait_for()
                relog = api(client, "POST", "/api/auth/login", body={"email": email, "password": password}).json()["token"]
                persisted_events = api(client, "GET", "/api/events?days=30", relog).json()
                found = next((e for e in persisted_events if e["id"] == event_id), None)
                ok = valid_r.status_code == 200 and found and found["text"] == valid_payload["text"] and found["channel"] == "texto" and found["occurred_at"].startswith("2026-10-19T07:15:00")
                add("RF04-06", "RF-04", "Propuesta válida confirmada", json.dumps(valid_payload, ensure_ascii=False),
                    "Guardar; recargar UI; iniciar nueva sesión y consultar API.", "Contenido, fecha y canal persisten.",
                    f"Evento {event_id} recuperado tras recarga/sesión: {bool(found)}.", "APROBADO" if ok else "FALLIDO", "logs/resultados_ampliados.json")
                token = relog

                # RF04-07: simulación del contrato Web Speech; no prueba micrófono real.
                context.close()
                voice_context = browser.new_context(viewport={"width": 390, "height": 844}, locale="es-PE", timezone_id="America/Lima")
                voice_context.add_init_script("""
                    class MockRecognition {
                      start() { setTimeout(() => { this.onresult({results: [[{transcript: 'vomitó dos veces esta mañana'}]]}); this.onend(); }, 30); }
                      stop() { if (this.onend) this.onend(); }
                    }
                    Object.defineProperty(window, 'webkitSpeechRecognition', {value: MockRecognition});
                """)
                page = voice_context.new_page(); page.set_default_timeout(10_000); login_ui(page, email, password)
                page.goto(BASE + "/#/registrar"); page.get_by_role("button", name="Dictar").click()
                page.get_by_role("heading", name="Revise antes de guardar").wait_for()
                ev = screenshot(page, "RF04-07_dictado_simulado.png")
                page.get_by_role("button", name="Confirmar y guardar").click(); page.get_by_text("Registro guardado").wait_for()
                voice_saved = api(client, "GET", "/api/events?days=30", token).json()[0]
                simulated_ok = voice_saved["channel"] == "voz" and voice_saved["symptom"] == "vomito"
                add("RF04-07", "RF-04", "Reconocimiento Web Speech simulado; sin micrófono físico", "Transcripción simulada: 'vomitó dos veces esta mañana'",
                    "Inyectar respuesta simulada, revisar propuesta y confirmar.", "Dictado real en navegador/dispositivo compatible.",
                    f"Manejo de respuesta simulado correcto={simulated_ok}; no se probó audio ni permiso real.", "NO VERIFICADO", ev)
                voice_context.close()

                # RF04-08: error de permiso simulado, sin guardado.
                deny_context = browser.new_context(viewport={"width": 390, "height": 844}, locale="es-PE", timezone_id="America/Lima")
                deny_context.add_init_script("""
                    class DeniedRecognition {
                      start() { setTimeout(() => { this.onerror({error: 'not-allowed'}); this.onend(); }, 30); }
                      stop() { if (this.onend) this.onend(); }
                    }
                    Object.defineProperty(window, 'webkitSpeechRecognition', {value: DeniedRecognition});
                """)
                page = deny_context.new_page(); page.set_default_timeout(10_000); login_ui(page, email, password)
                page.goto(BASE + "/#/registrar")
                count_before = db_one("SELECT count(*) FROM care_events")[0]
                page.get_by_role("button", name="Dictar").click()
                page.get_by_text("Debe permitir el uso del micrófono.").wait_for()
                ev = screenshot(page, "RF04-08_permiso_denegado_simulado.png")
                count_after = db_one("SELECT count(*) FROM care_events")[0]
                fallback_ok = page.locator("textarea").first.is_editable() and count_before == count_after
                add("RF04-08", "RF-04", "Denegación Web Speech simulada; sin diálogo real del SO", "error='not-allowed'",
                    "Simular denegación; observar mensaje, escritura disponible y BD.", "Informa el error, permite escribir y no guarda.",
                    f"Fallback simulado correcto={fallback_ok}; filas {count_before}->{count_after}; permiso real no probado.", "NO VERIFICADO", ev)
                deny_context.close()

                # RF04-09: regla exacta de configuración.
                alert_payload = {"kind": "sintoma", "symptom": "fiebre", "value": 38.5, "unit": "°C", "text": "Dato ficticio para verificar aviso", "channel": "texto", "confirmed": True}
                alert_r = api(client, "POST", "/api/events", token, alert_payload)
                alert_data = alert_r.json()
                alert = next((a for a in alert_data["alerts"] if a["rule_id"] == "R-FIEBRE-38"), None)
                relation = db_one("SELECT event_id,rule_id,doc_id FROM alerts WHERE event_id=?", (alert_data["event"]["id"],))
                ok = alert is not None and relation == (alert_data["event"]["id"], "R-FIEBRE-38", "DEMO-01")
                page = browser.new_page(viewport={"width": 390, "height": 844}); login_ui(page, email, password); page.goto(BASE + "/#/avisos"); page.get_by_text("38 °C", exact=False).first.wait_for()
                ev = screenshot(page, "RF04-09_aviso_regla_fiebre.png")
                add("RF04-09", "RF-04", "Regla rules.json R-FIEBRE-38: fiebre min_value=38.0; fuente DEMO-01", json.dumps(alert_payload, ensure_ascii=False),
                    "Guardar evento confirmado; revisar respuesta, UI y relación alerts.event_id.", "Genera y relaciona el aviso configurado.",
                    f"Regla={alert['rule_id'] if alert else None}; relación SQLite={relation}.", "APROBADO" if ok else "FALLIDO", ev)
                page.close()

                # RF04-10: cifrado en reposo y recuperación autorizada.
                secret_text = "Nota ficticia sensible RF04-10"
                enc_r = api(client, "POST", "/api/events", token, {"kind": "observacion", "text": secret_text, "channel": "texto", "confirmed": True})
                enc_id = enc_r.json()["event"]["id"]
                stored = db_one("SELECT text_enc FROM care_events WHERE id=?", (enc_id,))[0]
                recovered = next(e for e in api(client, "GET", "/api/events?days=30", token).json() if e["id"] == enc_id)["text"]
                ok = stored != secret_text and secret_text not in stored and recovered == secret_text and len(stored) > len(secret_text)
                add("RF04-10", "RF-04", "Usuario autorizado; clave gestionada por la app (no expuesta)", secret_text,
                    "Guardar nota; inspeccionar text_enc en SQLite; recuperarla por API autenticada.", "Texto cifrado en BD y descifrado para usuario autorizado.",
                    f"Plano ausente en text_enc={secret_text not in stored}; longitud cifrada={len(stored)}; recuperación coincide={recovered == secret_text}.", "APROBADO" if ok else "FALLIDO", "logs/consulta_sqlite.json")

                browser.close()

            # Evidencia SQL sin incluir ciphertext, tokens ni claves.
            sql_evidence = {
                "database": str(DATA / "vianova.db"),
                "tasks": db_all("SELECT id,kind,title,recurrence,every_hours,active FROM tasks ORDER BY id"),
                "completions": db_all("SELECT task_id,occurrence_at,status FROM task_completions ORDER BY task_id,occurrence_at"),
                "event_logs_relevantes": db_all("SELECT tipo_evento,id_recurso,hora_programada,resultado FROM event_logs WHERE tipo_evento IN ('tarea_completada','registro_evento') ORDER BY fecha_hora"),
                "care_events": db_all("SELECT id,kind,symptom,intensity,value,frequency,channel,occurred_at,length(text_enc) FROM care_events ORDER BY id"),
                "alerts": db_all("SELECT id,event_id,rule_id,doc_id FROM alerts ORDER BY id"),
            }
            (LOGS / "consulta_sqlite.json").write_text(json.dumps(sql_evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

        metadata = {
            "fecha": datetime.now(PERU).isoformat(timespec="seconds"),
            "zona_horaria": "America/Lima (UTC-5)",
            "sistema_operativo": platform.platform(),
            "python": platform.python_version(),
            "navegador": "Chrome for Testing 156.0.8078.4 (Playwright Chromium 1248, headless)",
            "base_datos": "SQLite aislada",
            "ruta_base": str(DATA / "vianova.db"),
            "huella_codigo_sha256": fingerprint(),
            "commit": "No disponible: el directorio entregado no contiene metadatos Git",
        }
        output = {"metadata": metadata, "casos": results}
        (LOGS / "resultados_ampliados.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1 if any(r["estado"] == "FALLIDO" for r in results) else 0
    finally:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=10)
        server_log.close()


if __name__ == "__main__":
    raise SystemExit(main())
