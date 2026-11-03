"""Casos de prueba funcionales: al menos uno por requerimiento funcional (RF-01 a RF-15).
Cada prueba lleva el código del caso (CF-xx) y el requerimiento que verifica."""
import io
import json

import pytest

from conftest import register, login

pytestmark = pytest.mark.funcional


def test_CF01_rf01_registro_perfil_consentimiento(client):
    """CF-01 · RF-01: el cuidador crea su cuenta con consentimiento y registra el perfil del paciente."""
    assert client.post("/api/auth/register", json={"full_name": "Sin Consentimiento", "email": "nocons@ficticio.pe",
                                                   "password": "clave-segura-1", "consent_study": False}).status_code == 400
    h = register(client)
    p = client.put("/api/profile", headers=h, json={"patient_alias": "mamá", "relationship_to_patient": "hija",
                                                    "patient_age": 64, "cancer_type": "mama",
                                                    "treatments": ["quimioterapia", "inventado"], "mobility": "ayuda_parcial",
                                                    "interaction_pref": "voz"}).json()
    assert p["treatments"] == ["quimioterapia"] and p["cancer_type"] == "mama"
    assert client.get("/api/auth/me", headers=h).json()["has_profile"]


def test_CF02_rf02_agenda_crear_ver_completar(client, cuidador):
    """CF-02 · RF-02: crear un medicamento cada 8 h, verlo en la agenda y marcarlo como hecho."""
    t = client.post("/api/tasks", headers=cuidador, json={"kind": "medicamento", "title": "Antiemético",
                                                         "instructions": "según receta", "start_at": "2026-01-01T06:00:00",
                                                         "recurrence": "cada_n_horas", "every_hours": 8}).json()
    ag = client.get("/api/tasks/agenda", headers=cuidador).json()["items"]
    assert len(ag) == 3 and all(i["task"]["id"] == t["id"] for i in ag)
    r = client.post(f"/api/tasks/{t['id']}/complete", headers=cuidador, json={"occurrence_at": ag[0]["occurrence_at"][:19]})
    assert r.status_code == 200
    assert client.get("/api/tasks/agenda", headers=cuidador).json()["items"][0]["status"] == "hecha"


def test_CF03_rf03_recordatorio_emitido_y_registrado(client, cuidador, investigador):
    """CF-03 · RF-03: el cliente reporta el recordatorio emitido y queda en los registros (Tabla 8)."""
    t = client.post("/api/tasks", headers=cuidador, json={"kind": "cita", "title": "Control", "start_at": "2026-10-16T10:00:00",
                                                         "recurrence": "unica"}).json()
    r = client.post("/api/logs/client", headers=cuidador, json={"tipo_evento": "recordatorio_emitido", "modulo": "recordatorios",
                                                               "id_recurso": f"TAR-{t['id']:04d}", "hora_programada": "2026-10-16T10:00:00"})
    assert r.status_code == 200
    assert client.post("/api/logs/client", headers=cuidador, json={"tipo_evento": "consulta_rag"}).status_code == 400
    assert "recordatorio_emitido" in client.get("/api/research/logs.csv?start=2020-01-01T00:00:00", headers=investigador).text


def test_CF04_rf04_registro_por_voz_requiere_confirmacion(client, cuidador):
    """CF-04 · RF-04: la transcripción se interpreta, se muestra para confirmar y solo se guarda confirmada."""
    prop = client.post("/api/events/parse", headers=cuidador, json={"text": "vomitó tres veces en la mañana"}).json()
    assert prop["symptom"] == "vomito" and prop["frequency"] == 3
    prop["channel"] = "voz"
    assert client.post("/api/events", headers=cuidador, json=prop).status_code == 400
    prop["confirmed"] = True
    assert client.post("/api/events", headers=cuidador, json=prop).status_code == 200
    assert client.get("/api/events", headers=cuidador).json()[0]["symptom"] == "vomito"


def test_CF05_rf05_recomendaciones_explicadas(client, cuidador):
    """CF-05 · RF-05: cada recomendación trae motivo(s), fuente, versión y desglose del puntaje."""
    client.put("/api/profile", headers=cuidador, json={"cancer_type": "colon", "treatments": ["radioterapia"]})
    items = client.get("/api/recommendations?q=cuidado de la piel", headers=cuidador).json()["items"]
    assert items and all(i["reasons"] and i["institution"] and i["version"] for i in items)
    assert set(items[0]["components"]) == {"sem", "ctx", "reg", "pref"}
    assert any("radioterapia" in " ".join(i["reasons"]).lower() for i in items)


def test_CF06_rf06_consulta_rag_responde_o_se_abstiene(client, cuidador):
    """CF-06 · RF-06: responde con fuente cuando hay evidencia y se abstiene cuando no la hay."""
    a = client.post("/api/assistant/ask", headers=cuidador, json={"query": "qué puede comer si tiene llagas en la boca"}).json()
    b = client.post("/api/assistant/ask", headers=cuidador, json={"query": "cuál es el mejor equipo de fútbol"}).json()
    assert a["status"] == "respondida" and a["sources"]
    assert b["status"] == "abstencion" and not b["sources"]


def test_CF07_rf07_trazabilidad_fuente_documento_y_traza(client, cuidador):
    """CF-07 · RF-07: la respuesta enlaza al documento con su versión y expone la traza del flujo RAG."""
    a = client.post("/api/assistant/ask", headers=cuidador, json={"query": "fiebre durante la quimioterapia"}).json()
    s = a["sources"][0]
    d = client.get(f"/api/documents/{s['doc_id']}", headers=cuidador).json()
    assert d["version"] == s["version"] and d["sections"]
    assert [p["paso"][:2] for p in a["trace"]["pasos"]] == ["1.", "2.", "3.", "4.", "5."]
    assert any(c["usado"] for c in a["trace"]["candidatos"])


def test_CF08_rf08_retroalimentacion(client, cuidador):
    """CF-08 · RF-08: la valoración útil/no útil se guarda y solo afecta al componente de preferencia."""
    items = client.get("/api/recommendations", headers=cuidador).json()["items"]
    doc = items[-1]["doc_id"]
    assert client.post("/api/recommendations/feedback", headers=cuidador, json={"doc_id": doc, "useful": True}).status_code == 200
    after = {i["doc_id"]: i for i in client.get("/api/recommendations?limit=10", headers=cuidador).json()["items"]}
    assert after[doc]["components"]["pref"] > 0
    assert client.post("/api/recommendations/feedback", headers=cuidador, json={"doc_id": "NO-EXISTE", "useful": True}).status_code == 404


def test_CF09_rf09_aviso_por_regla_con_fuente_e_historial(client, cuidador):
    """CF-09 · RF-09: un registro de fiebre ≥ 38 °C genera aviso con fuente y aparece en el historial."""
    r = client.post("/api/events", headers=cuidador, json={"kind": "sintoma", "symptom": "fiebre", "value": 38.5, "unit": "°C",
                                                          "confirmed": True}).json()
    assert r["alerts"][0]["rule_id"] == "R-FIEBRE-38" and r["alerts"][0]["source"]["doc_id"]
    aid = r["alerts"][0]["id"]
    client.post(f"/api/alerts/{aid}/ack", headers=cuidador)
    hist = client.get("/api/alerts?history=true", headers=cuidador).json()
    assert any(a["id"] == aid and a["acknowledged"] for a in hist)


def test_CF10_rf10_resumen_exportable(client, cuidador):
    """CF-10 · RF-10: el resumen para el equipo de salud se obtiene en pantalla y en CSV."""
    client.post("/api/events", headers=cuidador, json={"kind": "sintoma", "symptom": "fatiga", "intensity": 6, "confirmed": True})
    s = client.get("/api/summary", headers=cuidador)
    c = client.get("/api/summary.csv", headers=cuidador)
    assert s.status_code == 200 and c.status_code == 200 and "fatiga" in c.text.lower()


def test_CF11_rf11_importacion_wearable(client, cuidador):
    """CF-11 · RF-11: con autorización se importan lecturas válidas y se rechazan las inválidas."""
    data = "metrica,valor,fecha\nfrecuencia_cardiaca,80,2026-10-10T08:00:00\npasos,abc,2026-10-10T09:00:00\n".encode()
    client.post("/api/profile/devices-consent", headers=cuidador, json={"granted": True})
    r = client.post("/api/devices/import", headers=cuidador, files={"file": ("lecturas.csv", io.BytesIO(data), "text/csv")}).json()
    assert r["importadas"] == 1 and r["rechazadas"] == 1


def test_CF12_rf12_corpus_y_configuracion(client, curador):
    """CF-12 · RF-12: el curador registra un documento con ficha de curaduría y consulta la configuración vigente."""
    md = "# Hidratación\nOfrezca líquidos en pequeños sorbos durante el día para prevenir la deshidratación por diarrea."
    form = {"doc_id": "PRUEBA-01", "institution": "Institución ficticia", "title": "Hidratación del paciente", "year": "2025",
            "version": "1.0", "topics": "diarrea,hidratacion", "crit_oficial": "true", "crit_vigente": "true",
            "crit_idioma": "true", "crit_pertinente": "true"}
    r = client.post("/api/corpus", headers=curador, data=form, files={"file": ("doc.md", io.BytesIO(md.encode()), "text/markdown")})
    assert r.status_code == 200, r.text
    cfg = client.get("/api/admin/config", headers=curador).json()
    assert cfg["rag"]["tau"] > 0 and cfg["reglas"]["sha256"] and cfg["indice"]["dimension_embeddings"] > 0
    client.put("/api/corpus/PRUEBA-01/status", headers=curador, json={"status": "retirado", "reason": "caso de prueba"})


def test_CF13_rf13_usuarios_roles_auditoria(client, admin):
    """CF-13 · RF-13: el administrador crea una cuenta interna, cambia su rol, la desactiva y queda auditado."""
    u = client.post("/api/admin/users", headers=admin, json={"full_name": "Curadora Ficticia", "email": "cur2@ficticio.pe",
                                                            "password": "ClaveLarga2026", "role": "curador"}).json()
    assert u["code"].startswith("CUR-")
    assert client.put(f"/api/admin/users/{u['id']}", headers=admin, json={"role": "investigador"}).json()["role"] == "investigador"
    assert client.put(f"/api/admin/users/{u['id']}", headers=admin, json={"active": False}).json()["active"] is False
    assert client.post("/api/auth/login", json={"email": "cur2@ficticio.pe", "password": "ClaveLarga2026"}).status_code == 401
    acciones = [a["action"] for a in client.get("/api/admin/audit", headers=admin).json()]
    assert "crear_usuario" in acciones and "modificar_usuario" in acciones


def test_CF14_rf14_indicadores_validacion_exportacion(client, investigador):
    """CF-14 · RF-14: el investigador obtiene indicadores, resultados de validación y exporta registros seudonimizados."""
    ind = client.get("/api/research/indicators", headers=investigador).json()
    assert "resumen" in ind and isinstance(ind["participantes"], list)
    assert client.get("/api/research/validation", headers=investigador).status_code == 200
    csv_text = client.get("/api/research/logs.csv", headers=investigador).text
    assert "@" not in csv_text


def test_CF15_rf15_privacidad_arco(client):
    """CF-15 · RF-15: el titular descarga sus datos, revoca la autorización de dispositivos y elimina su cuenta."""
    h = register(client, "arco@ficticio.pe")
    client.post("/api/profile/devices-consent", headers=h, json={"granted": True})
    exp = client.get("/api/privacy/export", headers=h).json()
    assert exp["cuenta"]["correo"] == "arco@ficticio.pe"
    assert client.post("/api/privacy/consents/revoke", headers=h, json={"kind": "dispositivos"}).status_code == 200
    assert client.get("/api/profile", headers=h).json()["devices_authorized"] is False
    assert client.post("/api/privacy/delete-account", headers=h, json={"password": "mala", "confirm": "ELIMINAR"}).status_code == 403
    assert client.post("/api/privacy/delete-account", headers=h, json={"password": "clave-segura-1", "confirm": "ELIMINAR"}).status_code == 200
    assert client.get("/api/profile", headers=h).status_code == 401
    assert client.post("/api/auth/login", json={"email": "arco@ficticio.pe", "password": "clave-segura-1"}).status_code == 401
