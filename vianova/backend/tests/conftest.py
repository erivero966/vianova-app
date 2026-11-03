"""Configuración común de las pruebas.

Las pruebas corren SIEMPRE en el ambiente de pruebas (APP_ENV=pruebas), con una base de datos temporal y datos
ficticios. Nunca usan la base de desarrollo ni la de producción.
"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

TMP = Path(tempfile.mkdtemp(prefix="vianova_pruebas_"))
SRC = Path(__file__).resolve().parent.parent / "data"
shutil.copytree(SRC / "corpus", TMP / "corpus")
shutil.copy(SRC / "rules.json", TMP / "rules.json")
os.environ["APP_ENV"] = "pruebas"
os.environ["VIANOVA_DATA_DIR"] = str(TMP)
os.environ.pop("DATABASE_URL", None)
os.environ["LLM_PROVIDER"] = "local"

from fastapi.testclient import TestClient   # noqa: E402
from app.main import app                     # noqa: E402

_n = [0]


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def register(client, email=None, password="clave-segura-1"):
    if email is None:
        _n[0] += 1
        email = f"ficticio{_n[0]:03d}@ficticio.pe"
    r = client.post("/api/auth/register", json={"full_name": "Cuidadora Ficticia", "email": email,
                                                "password": password, "consent_study": True})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def login(client, email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


@pytest.fixture
def cuidador(client):
    return register(client)


@pytest.fixture
def curador(client):
    return login(client, "curador@vianova.local", "Curador2026!")


@pytest.fixture
def investigador(client):
    return login(client, "investigador@vianova.local", "Investigador2026!")


@pytest.fixture
def admin(client):
    return login(client, "admin@vianova.local", "Admin2026!")
