"""Pruebas de seguridad: autenticación, autorización por rol, sesión, entradas maliciosas, cifrado y cabeceras."""
import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import config
from conftest import register, login

pytestmark = pytest.mark.seguridad

# Matriz de autorización: (método, ruta, roles permitidos)
MATRIZ = [
    ("GET", "/api/profile", {"cuidador"}),
    ("GET", "/api/tasks/agenda", {"cuidador"}),
    ("GET", "/api/alerts", {"cuidador"}),
    ("GET", "/api/privacy/consents", {"cuidador"}),
    ("GET", "/api/corpus", {"curador"}),
    ("GET", "/api/research/indicators", {"curador", "investigador"}),
    ("GET", "/api/research/logs.csv", {"curador", "investigador"}),
    ("GET", "/api/research/validation", {"curador", "investigador"}),
    ("GET", "/api/admin/users", {"admin"}),
    ("GET", "/api/admin/audit", {"admin"}),
    ("GET", "/api/admin/config", {"admin", "curador", "investigador"}),
]


@pytest.fixture(scope="module")
def tokens(client):
    return {"cuidador": register(client),
            "curador": login(client, "curador@vianova.local", "Curador2026!"),
            "investigador": login(client, "investigador@vianova.local", "Investigador2026!"),
            "admin": login(client, "admin@vianova.local", "Admin2026!")}


@pytest.mark.parametrize("metodo,ruta,permitidos", MATRIZ)
def test_matriz_de_autorizacion(client, tokens, metodo, ruta, permitidos):
    assert client.request(metodo, ruta).status_code == 401                    # sin sesión
    for rol, h in tokens.items():
        code = client.request(metodo, ruta, headers=h).status_code
        assert (code == 200) == (rol in permitidos), f"{rol} {ruta} -> {code}"


def test_token_alterado_es_rechazado(client, tokens):
    tok = tokens["cuidador"]["Authorization"].split()[1]
    head, payload, sig = tok.split(".")
    data = json.loads(base64.urlsafe_b64decode(payload + "=="))
    data["role"] = "admin"
    forged = head + "." + base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=") + "." + sig
    assert client.get("/api/admin/users", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_firmado_con_otra_clave_o_alg_none(client):
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    otro = jwt.encode({"sub": "1", "role": "admin", "exp": exp}, "clave-del-atacante", algorithm="HS256")
    none = jwt.encode({"sub": "1", "role": "admin", "exp": exp}, None, algorithm="none")
    for t in (otro, none):
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_token_expirado(client):
    t = jwt.encode({"sub": "1", "role": "curador", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                   config.JWT_SECRET, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_bloqueo_por_fuerza_bruta(client):
    register(client, "fuerzabruta@ficticio.pe")
    codes = [client.post("/api/auth/login", json={"email": "fuerzabruta@ficticio.pe", "password": f"x{i}"}).status_code
             for i in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    # incluso con la contraseña correcta, mientras dure el bloqueo
    assert client.post("/api/auth/login", json={"email": "fuerzabruta@ficticio.pe", "password": "clave-segura-1"}).status_code == 429


def test_mensaje_de_login_no_revela_si_el_correo_existe(client):
    a = client.post("/api/auth/login", json={"email": "noexiste@ficticio.pe", "password": "x"}).json()
    b = client.post("/api/auth/login", json={"email": "curador@vianova.local", "password": "x"}).json()
    assert a == b


def test_contrasena_debil_rechazada(client):
    r = client.post("/api/auth/register", json={"full_name": "Ana", "email": "debil@ficticio.pe", "password": "123",
                                                "consent_study": True})
    assert r.status_code == 422


@pytest.mark.parametrize("payload", ["' OR '1'='1", "admin@vianova.local' --", "\"; DROP TABLE users; --"])
def test_inyeccion_sql_en_login(client, payload):
    assert client.post("/api/auth/login", json={"email": payload, "password": payload}).status_code in (401, 429)
    assert client.post("/api/auth/login", json={"email": "curador@vianova.local", "password": "Curador2026!"}).status_code == 200


def test_inyeccion_sql_en_parametros(client, tokens):
    r = client.get("/api/recommendations?q=' OR 1=1; DROP TABLE documents; --", headers=tokens["cuidador"])
    assert r.status_code == 200
    assert client.get("/api/corpus", headers=tokens["curador"]).json()["documents"]


def test_xss_se_almacena_como_texto_y_api_responde_json(client, tokens):
    h = tokens["cuidador"]
    xss = "<script>alert('x')</script>"
    client.post("/api/events", headers=h, json={"kind": "observacion", "text": xss, "confirmed": True})
    r = client.get("/api/events", headers=h)
    assert r.headers["content-type"].startswith("application/json")
    assert "script-src 'self'" in client.get("/").headers.get("content-security-policy", "")


def test_acceso_a_recursos_de_otro_usuario(client):
    a, b = register(client), register(client)
    t = client.post("/api/tasks", headers=a, json={"kind": "actividad", "title": "Caminar", "start_at": "2026-10-16T09:00:00",
                                                  "recurrence": "unica"}).json()
    assert client.delete(f"/api/tasks/{t['id']}", headers=b).status_code == 404
    al = client.post("/api/events", headers=a, json={"kind": "sintoma", "symptom": "fiebre", "value": 39, "unit": "°C",
                                                   "confirmed": True}).json()["alerts"][0]
    assert client.post(f"/api/alerts/{al['id']}/ack", headers=b).status_code == 404


def test_contrasenas_y_texto_libre_no_estan_en_claro_en_la_base(client):
    register(client, "claro@ficticio.pe", password="MiClaveUnica2026")
    db_file = config.DATA_DIR / "vianova.db"
    raw = db_file.read_bytes()
    assert b"MiClaveUnica2026" not in raw
    assert b"<script>alert" not in raw            # el texto libre del caso XSS se guardó cifrado


def test_cabeceras_de_seguridad(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer" and h["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in h["content-security-policy"]


def test_registros_de_uso_no_guardan_contenido_de_consultas(client, tokens):
    secreto = "consulta privada sobre llagas en la boca de mi madre"
    client.post("/api/assistant/ask", headers=tokens["cuidador"], json={"query": secreto})
    csv_text = client.get("/api/research/logs.csv", headers=tokens["investigador"]).text
    assert "privada" not in csv_text and "madre" not in csv_text


def test_administrador_no_puede_degradarse_a_si_mismo(client, tokens):
    me = client.get("/api/auth/me", headers=tokens["admin"]).json()
    assert client.put(f"/api/admin/users/{me['id']}", headers=tokens["admin"], json={"active": False}).status_code == 400


def test_carga_de_archivo_no_permitida(client, tokens):
    import io
    form = {"doc_id": "MAL-01", "institution": "x", "title": "x", "crit_oficial": "true", "crit_vigente": "true",
            "crit_idioma": "true", "crit_pertinente": "true"}
    r = client.post("/api/corpus", headers=tokens["curador"], data=form,
                    files={"file": ("malo.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")})
    assert r.status_code == 400


def test_produccion_exige_secretos(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.delenv("VIANOVA_FERNET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        config.check_production()
