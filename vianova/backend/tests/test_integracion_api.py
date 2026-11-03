"""Pruebas de integración: API + base de datos + índice RAG (ejecutar: cd backend && pytest -q)."""
import io
import json

import pytest

from conftest import register, login

pytestmark = pytest.mark.integracion


def test_registro_exige_consentimiento(client):
    r = client.post("/api/auth/register", json={"full_name": "X Y", "email": "x@y.pe", "password": "12345678",
                                                "consent_study": False})
    assert r.status_code == 400


def test_roles_protegen_endpoints(client):
    h = register(client, "rol@test.pe")
    assert client.get("/api/corpus", headers=h).status_code == 403
    assert client.get("/api/research/indicators", headers=h).status_code == 403
    assert client.get("/api/profile").status_code == 401


def test_rag_responde_con_fuente(client):
    h = register(client, "rag@test.pe")
    r = client.post("/api/assistant/ask", headers=h, json={"query": "tiene llagas en la boca, qué puede comer"}).json()
    assert r["status"] == "respondida"
    assert r["sources"] and r["sources"][0]["doc_id"] == "DEMO-03"


def test_rag_se_abstiene_sin_evidencia(client):
    h = register(client, "abst@test.pe")
    r = client.post("/api/assistant/ask", headers=h, json={"query": "cuál es la capital de Australia"}).json()
    assert r["status"] == "abstencion" and r["sources"] == []


def test_fuera_de_alcance_dosis(client):
    h = register(client, "dosis@test.pe")
    r = client.post("/api/assistant/ask", headers=h, json={"query": "qué dosis de morfina le doy"}).json()
    assert r["status"] == "fuera_de_alcance"


def test_registro_requiere_confirmacion_y_genera_aviso(client):
    h = register(client, "voz@test.pe")
    prop = client.post("/api/events/parse", headers=h, json={"text": "anoche tuvo fiebre de 38,7 grados"}).json()
    assert prop["symptom"] == "fiebre" and prop["value"] == 38.7
    prop["channel"] = "voz"
    assert client.post("/api/events", headers=h, json=prop).status_code == 400      # sin confirmar
    prop["confirmed"] = True
    r = client.post("/api/events", headers=h, json=prop).json()
    assert r["alerts"] and r["alerts"][0]["rule_id"] == "R-FIEBRE-38"
    assert r["alerts"][0]["source"]["doc_id"] == "DEMO-01"
    recs = client.get("/api/recommendations", headers=h).json()["items"]
    assert recs[0]["doc_id"] == "DEMO-01" and recs[0]["priority"]


def test_tareas_y_registros_tabla8(client):
    h = register(client, "tareas@test.pe")
    t = client.post("/api/tasks", headers=h, json={"kind": "medicamento", "title": "Medicamento A",
                                                   "instructions": "según receta", "start_at": "2026-01-01T08:00:00",
                                                   "recurrence": "diaria"}).json()
    ag = client.get("/api/tasks/agenda", headers=h).json()["items"]
    assert len(ag) == 1
    r = client.post(f"/api/tasks/{t['id']}/complete", headers=h, json={"occurrence_at": ag[0]["occurrence_at"]})
    assert r.status_code == 200
    assert client.post(f"/api/tasks/{t['id']}/complete", headers=h,
                       json={"occurrence_at": ag[0]["occurrence_at"]}).status_code == 400   # sin duplicados
    hi = login(client, "investigador@vianova.local", "Investigador2026!")
    csv_text = client.get("/api/research/logs.csv", headers=hi).text
    header = csv_text.splitlines()[0].split(",")
    assert header == ["id_evento", "id_participante", "fecha_hora", "tipo_evento", "modulo", "id_recurso",
                      "hora_programada", "canal", "resultado", "fuente_id", "version_corpus", "duracion_ms"]
    assert "tarea_completada" in csv_text
    assert "cuidadora" not in csv_text.lower()      # seudonimizado: sin nombres ni correos


def test_texto_libre_cifrado_en_reposo(client):
    h = register(client, "cifrado@test.pe")
    client.post("/api/events", headers=h, json={"kind": "observacion", "text": "nota privada XYZ", "confirmed": True})
    from app.db import SessionLocal
    from app.models import CareEvent
    db = SessionLocal()
    ev = db.query(CareEvent).order_by(CareEvent.id.desc()).first()
    assert "XYZ" not in ev.text_enc
    db.close()


def test_dispositivos_requieren_autorizacion(client):
    h = register(client, "iot@test.pe")
    data = json.dumps({"dispositivo": "Pulsera demo", "lecturas": [
        {"metrica": "frecuencia_cardiaca", "valor": 82, "fecha": "2026-10-10T08:00:00"},
        {"metrica": "inventada", "valor": 1, "fecha": "2026-10-10T08:00:00"}]}).encode()
    files = {"file": ("demo.json", io.BytesIO(data), "application/json")}
    assert client.post("/api/devices/import", headers=h, files=files).status_code == 403
    client.post("/api/profile/devices-consent", headers=h, json={"granted": True})
    files = {"file": ("demo.json", io.BytesIO(data), "application/json")}
    r = client.post("/api/devices/import", headers=h, files=files).json()
    assert r == {"importadas": 1, "rechazadas": 1}


def test_curador_excluye_documento_y_rag_lo_deja_de_usar(client):
    hc = login(client, "curador@vianova.local", "Curador2026!")
    assert client.put("/api/corpus/DEMO-08/status", headers=hc, json={"status": "excluido"}).status_code == 400
    r = client.put("/api/corpus/DEMO-08/status", headers=hc, json={"status": "excluido", "reason": "prueba"})
    assert r.status_code == 200
    h = register(client, "excl@test.pe")
    a = client.post("/api/assistant/ask", headers=h, json={"query": "cuidado de la piel en radioterapia"}).json()
    assert all(s["doc_id"] != "DEMO-08" for s in a["sources"])
    client.put("/api/corpus/DEMO-08/status", headers=hc, json={"status": "incluido"})
