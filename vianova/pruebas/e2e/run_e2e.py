"""Pruebas de extremo a extremo (E2E), de configuración y de accesibilidad con Playwright (Chromium).

- Levanta el backend en el ambiente de PRUEBAS con una base temporal y datos FICTICIOS (seed_ficticio + seed_demo).
- Ejecuta un escenario por requerimiento funcional (RF-01 a RF-15) en un viewport de celular (390×844) y guarda
  las capturas de pantalla que se usan como evidencia en el informe (resultados/capturas/).
- Cuenta los toques necesarios por tarea crítica (indicador de carga de interacción, RNF-U01).
- Pruebas de configuración: 5 tamaños de pantalla, sin desbordamiento horizontal (RNF-PT01).
- Accesibilidad: axe-core (WCAG 2.1 A/AA) sobre cada pantalla.
Uso:  python pruebas/e2e/run_e2e.py [--ronda N]
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = ROOT / "pruebas" / "resultados"
SHOTS = OUT / "capturas"
AXE = ROOT / "pruebas" / "node_modules" / "axe-core" / "axe.min.js"
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 820}

results, a11y, taps_by_task = [], [], {}


def start_server(data_dir: Path):
    env = dict(os.environ, APP_ENV="pruebas", VIANOVA_DATA_DIR=str(data_dir), LLM_PROVIDER="local")
    env.pop("DATABASE_URL", None)
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    for script, args in (("seed_ficticio.py", ["--n", "12", "--dias", "21"]), ("seed_demo.py", [])):
        subprocess.run([sys.executable, script, *args], cwd=BACKEND, env=env, check=True, capture_output=True)
    log = open(OUT / "servidor_pruebas.log", "w")
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT)], cwd=BACKEND, env=env,
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1)
            return p
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("El servidor de pruebas no inició")


class Case:
    def __init__(self, cid, rf, name):
        self.cid, self.rf, self.name, self.taps, self.shots = cid, rf, name, 0, []


def run_case(page, cid, rf, name, fn, taps_task=None):
    c = Case(cid, rf, name)
    t0 = time.time()
    try:
        fn(page, c)
        status, err = "aprobado", ""
    except Exception as e:                       # noqa: BLE001
        status, err = "fallido", f"{type(e).__name__}: {e}"
        traceback.print_exc()
        try:
            page.screenshot(path=str(SHOTS / f"ERROR_{cid}.png"))
        except Exception:
            pass
    results.append({"id": cid, "rf": rf, "escenario": name, "estado": status, "error": err[:400],
                    "duracion_s": round(time.time() - t0, 2), "toques": c.taps, "capturas": c.shots})
    if taps_task:
        taps_by_task[taps_task] = c.taps
    print(f"[{status.upper():8}] {cid} {rf} {name} ({c.taps} toques)")


def tap(page, c, selector=None, *, role=None, name=None, exact=False):
    loc = page.get_by_role(role, name=name, exact=exact).first if role else page.locator(selector).first
    loc.click()
    c.taps += 1


def shot(page, c, fname, full=False):
    """Captura de pantalla. full=True captura hasta 1,5 alturas de pantalla (para que sea legible en el informe)."""
    page.wait_for_timeout(250)
    if full:
        vw, vh, h = page.evaluate("[innerWidth, innerHeight, document.documentElement.scrollHeight]")
        page.screenshot(path=str(SHOTS / fname), full_page=True, clip={"x": 0, "y": 0, "width": vw, "height": min(h, int(vh * 1.5))})
    else:
        page.screenshot(path=str(SHOTS / fname))
    c.shots.append(fname)
    run_axe(page, fname.replace(".png", ""))


def run_axe(page, screen):
    if not AXE.exists():
        return
    page.add_script_tag(path=str(AXE))
    res = page.evaluate("""async () => { const r = await axe.run(document, {runOnly: {type: 'tag',
        values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']}}); return r.violations.map(v => ({id: v.id, impact: v.impact,
        help: v.help, nodes: v.nodes.length, ejemplo: v.nodes[0] ? v.nodes[0].target.join(' ') : ''})) }""")
    a11y.append({"pantalla": screen, "violaciones": res})


def login(page, email, pw):
    page.goto(BASE + "/#/")
    page.evaluate("localStorage.clear()")
    page.reload()
    page.get_by_role("heading", name="Vianova").wait_for()
    page.get_by_label("Correo").fill(email)
    page.get_by_label("Contraseña").fill(pw)
    page.get_by_role("button", name="Ingresar", exact=True).last.click()
    page.wait_for_selector("main#contenido")


def go(page, route, heading):
    page.goto(BASE + "/#/" + route)
    page.get_by_role("heading", name=heading, exact=False).first.wait_for()


# ----------------------------------------------------------------------------- escenarios del cuidador
def e2e01(page, c):
    page.goto(BASE + "/#/")
    page.evaluate("localStorage.clear()")
    page.reload()
    page.get_by_role("heading", name="Vianova").wait_for()
    tap(page, c, role="tab", name="Crear cuenta")
    page.get_by_label("Nombre completo").fill("Lucía Ficticia Quispe")
    page.get_by_label("Correo").fill("lucia.e2e@ficticio.pe")
    page.get_by_label("Contraseña").fill("Ficticia2026!")
    page.locator("label.check input[type=checkbox]").check(); c.taps += 1
    shot(page, c, "RF01_registro_consentimiento.png")
    tap(page, c, "button.btn.primary.block")
    page.get_by_role("heading", name="Perfil y paciente").wait_for()
    page.get_by_label("¿Cómo llama al paciente?").fill("mamá")
    page.get_by_label("Parentesco").fill("hija")
    page.get_by_label("Edad del paciente").fill("63")
    page.get_by_label("Tipo de cáncer (según el diagnóstico médico)").fill("mama")
    tap(page, c, role="button", name="Quimioterapia")
    page.get_by_label("Movilidad del paciente").select_option("ayuda_parcial")
    shot(page, c, "RF01_perfil_paciente.png", full=True)
    tap(page, c, role="button", name="Guardar")
    page.get_by_role("heading", name="Buen", exact=False).wait_for()


def e2e_home(page, c):
    go(page, "inicio", "Buen")
    shot(page, c, "INICIO_cuidador.png")
    go(page, "mas", "Más opciones")
    shot(page, c, "MAS_menu.png", full=True)


def e2e02(page, c):
    go(page, "agenda", "Agenda de cuidado")
    shot(page, c, "RF02_agenda.png", full=True)
    tap(page, c, role="button", name="+ Nueva")
    page.get_by_label("Nombre", exact=False).first.fill("Ejercicios de respiración")
    shot(page, c, "RF02_nueva_tarea.png", full=True)
    tap(page, c, role="button", name="Guardar")
    expect(page.get_by_text("Ejercicios de respiración").first).to_be_visible()
    btn = page.get_by_role("button", name="Hecho").first
    if btn.count():
        btn.click(); c.taps += 1


def e2e03(page, c):
    # Tarea programada hace 2 minutos: al abrir la app debe aparecer el recordatorio emergente
    token = page.evaluate("localStorage.getItem('vianova_token')")
    t = time.localtime(time.time() - 120)
    body = json.dumps({"kind": "medicamento", "title": "Recordatorio E2E", "start_at": time.strftime("%Y-%m-%dT%H:%M:00", t),
                       "recurrence": "unica"}).encode()
    req = urllib.request.Request(BASE + "/api/tasks", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    urllib.request.urlopen(req)
    page.goto(BASE + "/#/recordatorios"); page.reload()
    page.get_by_role("heading", name="Recordatorios", exact=True).wait_for()
    toast = page.locator(".toast")
    toast.wait_for()
    assert "Recordatorio E2E" in toast.inner_text()
    expect(page.get_by_text("Recordatorio E2E").first).to_be_visible()
    shot(page, c, "RF03_recordatorios.png")
    if page.get_by_role("button", name="Enviar notificación de prueba").count():
        tap(page, c, role="button", name="Enviar notificación de prueba")


def e2e04(page, c):
    go(page, "registrar", "Registrar")
    page.locator("textarea").first.fill("Anoche tuvo fiebre de 38,5 grados y vomitó dos veces")
    tap(page, c, role="button", name="Revisar")
    page.get_by_role("button", name="Confirmar y guardar").wait_for()
    shot(page, c, "RF04_confirmacion_registro.png", full=True)
    tap(page, c, role="button", name="Confirmar y guardar")
    expect(page.get_by_text("Registro guardado")).to_be_visible()
    expect(page.get_by_role("alert").first).to_be_visible()
    shot(page, c, "RF04_RF09_registro_guardado_con_aviso.png")


def e2e05(page, c):
    go(page, "recomendaciones", "Recomendaciones")
    page.get_by_label("¿Sobre qué necesita orientación?").fill("alimentación y náuseas")
    tap(page, c, role="button", name="Buscar")
    page.wait_for_selector("article.rec")
    page.get_by_text("¿Cómo se calcula el orden?").click()
    shot(page, c, "RF05_recomendaciones.png")


def e2e06(page, c):
    go(page, "asistente", "Consultar")   # asistente con corpus de demostración (antes #/consultar)
    page.locator("textarea").fill("¿Qué puede comer si tiene llagas en la boca?")
    tap(page, c, role="button", name="Preguntar", exact=True)
    page.wait_for_selector("article.answer.respondida")
    shot(page, c, "RF06_consulta_respondida.png")
    page.locator("textarea").fill("¿Qué dosis de morfina le doy?")
    tap(page, c, role="button", name="Preguntar", exact=True)
    page.wait_for_selector("article.answer.fuera_de_alcance")
    page.locator("textarea").fill("¿Cuál es la capital de Australia?")
    tap(page, c, role="button", name="Preguntar", exact=True)
    page.wait_for_selector("article.answer.abstencion")
    page.evaluate("window.scrollTo(0,0)")
    shot(page, c, "RF06_abstencion_y_fuera_de_alcance.png", full=True)


def e2e07(page, c):
    page.goto(BASE + "/#/asistente"); page.reload()
    page.get_by_role("heading", name="Consultar").first.wait_for()
    page.locator("textarea").fill("¿Cómo cuido la piel durante la radioterapia?")
    tap(page, c, role="button", name="Preguntar", exact=True)
    page.wait_for_selector("article.answer.respondida")
    tap(page, c, "article.answer.respondida details.trace summary")
    y = page.locator("article.answer.respondida details.trace").first.evaluate("e => e.getBoundingClientRect().top + window.scrollY")
    vw, vh, h = page.evaluate("[innerWidth, innerHeight, document.documentElement.scrollHeight]")
    page.add_style_tag(content="nav.bottomnav{display:none!important}")   # evita que la barra fija tape la captura larga
    page.wait_for_timeout(250)
    page.screenshot(path=str(SHOTS / "RF07_traza_rag.png"), full_page=True,
                    clip={"x": 0, "y": max(0, y - 40), "width": vw, "height": min(int(vh * 1.7), h - max(0, y - 40))})
    c.shots.append("RF07_traza_rag.png"); run_axe(page, "RF07_traza_rag")
    page.reload(); page.get_by_role("heading", name="Consultar").first.wait_for()
    page.locator("textarea").fill("¿Cómo cuido la piel durante la radioterapia?")
    page.get_by_role("button", name="Preguntar", exact=True).click()
    page.wait_for_selector("article.answer.respondida")
    tap(page, c, "article.answer .source a")
    page.wait_for_selector("section.doc h1")
    shot(page, c, "RF07_documento_fuente.png")


def e2e08(page, c):
    go(page, "recomendaciones", "Recomendaciones")
    page.wait_for_selector("article.rec")
    tap(page, c, "article.rec .vote button")
    expect(page.get_by_text("¡Gracias!").first).to_be_visible()
    expect(page.get_by_text("valoración registrada")).to_be_visible()
    page.locator("article.rec").first.scroll_into_view_if_needed()
    shot(page, c, "RF08_retroalimentacion.png")


def e2e09(page, c):
    go(page, "avisos", "Avisos")
    page.wait_for_selector(".alert-card")
    shot(page, c, "RF09_historial_avisos.png")
    tap(page, c, role="button", name="Entendido")
    tap(page, c, role="button", name="Revisados")
    page.wait_for_selector(".alert-card")


def e2e10(page, c):
    go(page, "resumen", "Resumen para el equipo de salud")
    page.wait_for_timeout(500)
    shot(page, c, "RF10_resumen_exportable.png", full=True)
    with page.expect_download() as d:
        tap(page, c, role="button", name="Descargar CSV")
    assert d.value.suggested_filename.endswith(".csv")


def e2e11(page, c):
    go(page, "dispositivos", "Dispositivos")
    cb = page.locator("input[type=checkbox]").first
    if not cb.is_checked():
        cb.click(); c.taps += 1
        expect(cb).to_be_checked()
    page.locator("input[type=file]").set_input_files(str(ROOT / "samples" / "pulsera_demo.csv")); c.taps += 1
    page.get_by_text("importad", exact=False).first.wait_for()
    shot(page, c, "RF11_dispositivos_importacion.png", full=True)


def e2e15(page, c):
    go(page, "privacidad", "Privacidad y mis datos")
    shot(page, c, "RF15_privacidad_arco.png", full=True)
    with page.expect_download() as d:
        tap(page, c, role="button", name="Descargar mis datos")
    assert d.value.suggested_filename.endswith(".json")


# ----------------------------------------------------------------------------- escenarios del personal
def e2e12(page, c):
    login(page, "curador@vianova.local", "Curador2026!")
    page.get_by_role("heading", name="Corpus", exact=False).first.wait_for()
    shot(page, c, "RF12_corpus_curaduria.png")
    tap(page, c, role="link", name="Configuración")
    page.get_by_role("heading", name="Configuración del modelo").wait_for()
    shot(page, c, "RF12_configuracion_modelo.png", full=True)


def e2e13(page, c):
    login(page, "admin@vianova.local", "Admin2026!")
    page.get_by_role("heading", name="Usuarios y roles").wait_for()
    page.get_by_label("Nombre completo").fill("Investigadora Ficticia")
    page.get_by_label("Correo").fill("inv2.e2e@ficticio.pe")
    page.get_by_label("Contraseña inicial (mín. 10)").fill("ClaveLarga2026")
    page.get_by_label("Rol").last.select_option("investigador")
    tap(page, c, role="button", name="Crear cuenta")
    expect(page.get_by_text("creada", exact=False)).to_be_visible()
    shot(page, c, "RF13_usuarios_roles.png", full=True)
    tap(page, c, role="tab", name="Auditoría")
    shot(page, c, "RF13_auditoria.png")


def e2e14(page, c):
    login(page, "investigador@vianova.local", "Investigador2026!")
    page.get_by_role("heading", name="Investigación").wait_for()
    page.wait_for_selector("table")
    shot(page, c, "RF14_indicadores_investigacion.png")
    tap(page, c, role="link", name="Validación")
    page.get_by_role("heading", name="Validación técnica").wait_for()
    shot(page, c, "RF14_validacion_tecnica.png")


# ----------------------------------------------------------------------------- configuración (tamaños de pantalla)
VIEWPORTS = [("Teléfono pequeño 320×568", 320, 568), ("Teléfono 390×844", 390, 844), ("Android 412×915", 412, 915),
             ("Tableta 768×1024", 768, 1024), ("Escritorio 1366×768", 1366, 768)]
CONFIG_PAGES = [("inicio", "Buen"), ("agenda", "Agenda de cuidado"), ("registrar", "Registrar"), ("consultar", "¿En qué podemos ayudarte?"),
                ("recomendaciones", "Recomendaciones"), ("privacidad", "Privacidad")]


def config_tests(browser):
    out = []
    for label, w, h in VIEWPORTS:
        ctx = browser.new_context(viewport={"width": w, "height": h}, locale="es-PE", timezone_id="America/Lima")
        page = ctx.new_page()
        login(page, "demo@vianova.local", "Demo2026!")
        for route, heading in CONFIG_PAGES:
            go(page, route, heading)
            page.wait_for_timeout(200)
            sw, iw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
            nav = page.locator("nav.bottomnav").is_visible()
            out.append({"configuracion": label, "pantalla": route, "ancho_contenido": sw, "ancho_ventana": iw,
                        "sin_desborde": sw <= iw, "navegacion_visible": nav,
                        "estado": "aprobado" if sw <= iw and nav else "fallido"})
        if w in (320, 768, 1366):
            page.goto(BASE + "/#/inicio"); page.get_by_role("heading", name="Buen", exact=False).wait_for()
            page.wait_for_timeout(300)
            page.screenshot(path=str(SHOTS / f"CONFIG_{w}x{h}.png"))
        ctx.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ronda", type=int, default=2)
    a = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    for f in SHOTS.glob("*.png"):
        f.unlink()
    server = start_server(OUT / "tmp" / "datos_pruebas")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(bypass_csp=True, viewport=PHONE, device_scale_factor=2, locale="es-PE", timezone_id="America/Lima",
                                      permissions=["notifications"], has_touch=True, is_mobile=True,
                                      user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
                                                 "Chrome/131.0 Mobile Safari/537.36")
            ctx.set_default_timeout(10000)
            page = ctx.new_page()
            run_case(page, "E2E-01", "RF-01", "Crear cuenta con consentimiento y registrar perfil del paciente", e2e01, "Crear cuenta y perfil")
            login(page, "demo@vianova.local", "Demo2026!")
            run_case(page, "E2E-00", "—", "Pantalla de inicio y menú Más", e2e_home)
            run_case(page, "E2E-02", "RF-02", "Ver agenda, crear tarea y marcarla como hecha", e2e02, "Crear tarea en la agenda")
            run_case(page, "E2E-04", "RF-04", "Registrar síntoma por texto con confirmación", e2e04, "Registrar síntoma")
            run_case(page, "E2E-05", "RF-05", "Buscar recomendaciones explicadas", e2e05, "Buscar recomendación")
            run_case(page, "E2E-06", "RF-06", "Consulta con respuesta, fuera de alcance y abstención", e2e06)
            run_case(page, "E2E-07", "RF-07", "Traza RAG y documento fuente", e2e07, "Consultar y ver la fuente")
            run_case(page, "E2E-08", "RF-08", "Valorar una recomendación", e2e08, "Valorar recomendación")
            run_case(page, "E2E-09", "RF-09", "Historial de avisos y marcar como revisado", e2e09)
            run_case(page, "E2E-10", "RF-10", "Resumen para el equipo de salud y descarga CSV", e2e10, "Descargar resumen")
            run_case(page, "E2E-11", "RF-11", "Autorizar e importar datos de pulsera", e2e11)
            run_case(page, "E2E-15", "RF-15", "Privacidad: autorizaciones y descarga de datos", e2e15)
            run_case(page, "E2E-03", "RF-03", "Recordatorio emergente a la hora programada", e2e03)
            ctx.close()
            ctx = browser.new_context(bypass_csp=True, viewport=DESKTOP, locale="es-PE", timezone_id="America/Lima")
            ctx.set_default_timeout(10000)
            page = ctx.new_page()
            run_case(page, "E2E-12", "RF-12", "Corpus y configuración del modelo (curador)", e2e12)
            run_case(page, "E2E-13", "RF-13", "Crear cuenta interna y ver auditoría (administrador)", e2e13)
            run_case(page, "E2E-14", "RF-14", "Indicadores y validación técnica (investigador)", e2e14)
            ctx.close()
            conf = config_tests(browser)
            browser.close()
    finally:
        os.killpg(os.getpgid(server.pid), signal.SIGTERM)
    viol = {}
    for s in a11y:
        for v in s["violaciones"]:
            k = viol.setdefault(v["id"], {"id": v["id"], "impacto": v["impact"], "descripcion": v["help"], "pantallas": [], "nodos": 0})
            k["pantallas"].append(s["pantalla"]); k["nodos"] += v["nodes"]
    out = {"ronda": a.ronda, "fecha": time.strftime("%Y-%m-%d %H:%M"), "navegador": "Chromium (Playwright)",
           "e2e": results, "toques_por_tarea": taps_by_task, "configuracion": conf,
           "accesibilidad": {"pantallas_evaluadas": len(a11y), "violaciones": list(viol.values()), "detalle": a11y}}
    (OUT / f"e2e_ronda{a.ronda}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(r["estado"] == "aprobado" for r in results)
    cok = sum(r["estado"] == "aprobado" for r in conf)
    print(f"\nE2E: {ok}/{len(results)} aprobados · Configuración: {cok}/{len(conf)} · "
          f"Accesibilidad: {len(viol)} reglas incumplidas en {len(a11y)} pantallas")
    for v in viol.values():
        print(f"  [{v['impacto']}] {v['id']}: {v['descripcion']} ({v['nodos']} nodos; {', '.join(sorted(set(v['pantallas'])))[:120]})")


if __name__ == "__main__":
    main()
