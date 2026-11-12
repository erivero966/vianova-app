"""Integración backend Vianova -> rag-engine -> Ollama (POST /api/rag/search).

El motor RAG y Ollama se simulan con httpx.MockTransport: no se necesita GPU, PostgreSQL, el puerto 8001
ni cargar qwen2.5:7b.
"""
import json

import httpx
import pytest

from app import config
from app.rag import engine_client, grounded, ollama_client
from conftest import register

pytestmark = pytest.mark.integracion

NCI = "National Cancer Institute (NCI)"
QUERY = "Mi familiar tiene náuseas después de la quimioterapia"
TEXT_1 = ("Náuseas y vómitos\n\nAlgunos tipos de quimioterapia pueden causar náuseas, vómitos o ambos. "
          "Las náuseas ocurren cuando se siente asco.")


def rag_result(rank, section="Náuseas y vómitos", page=65, text=None, score=None):
    return {"rank": rank, "fragment_id": f"frag-{rank}", "score": score if score is not None else 0.7 - rank / 100,
            "distance": 0.3 + rank / 100, "text": text or f"Texto del fragmento {rank}",
            "document": "La quimioterapia y usted: Apoyo para las personas con cáncer",
            "entity": NCI, "version": "2019", "section": section, "page_start": page, "page_end": page}


@pytest.fixture
def engine(monkeypatch):
    """Motor RAG simulado: registra cada request y devuelve lo configurado en `state`."""
    state = {"requests": [], "status": 200, "error": None,
             "results": [rag_result(1, text=TEXT_1), rag_result(2, "Diarrea", 48), rag_result(3)]}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        if state["error"]:
            raise state["error"]
        body = json.loads(request.content)
        return httpx.Response(state["status"], json={"query": body["query"], "model": "BAAI/bge-m3",
                                                    "top_k": body["top_k"], "results": state["results"]})

    monkeypatch.setattr(engine_client, "TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(config, "RAG_API_URL", "http://rag.test:8001")
    return state


@pytest.fixture(autouse=True)
def ollama(monkeypatch):
    """Ollama simulado (autouse: ninguna prueba llega al Qwen real)."""
    state = {"requests": [], "status": 200, "error": None, "body": None,
             "content": "Algunos tipos de quimioterapia pueden causar náuseas y vómitos [1]."}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        if state["error"]:
            raise state["error"]
        body = state["body"] if state["body"] is not None else {"message": {"role": "assistant", "content": state["content"]}}
        return httpx.Response(state["status"], json=body)

    monkeypatch.setattr(ollama_client, "TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(config, "OLLAMA_URL", "http://ollama.test:11434")
    return state


def search(client, query=QUERY, headers=None):
    return client.post("/api/rag/search", headers=headers or register(client), json={"query": query})


# ----------------------------------------------------------------------------- retrieval y trazabilidad
def test_respuesta_generada_con_fuentes_y_trazabilidad(client, engine, ollama):
    r = search(client)
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == QUERY
    assert body["answer"] == "Algunos tipos de quimioterapia pueden causar náuseas y vómitos [1]."
    assert body["answer_status"] == "respondida"
    assert [s["rank"] for s in body["sources"]] == [1, 2, 3]
    first = body["sources"][0]
    assert first == {"rank": 1, "score": pytest.approx(0.69), "text": TEXT_1,
                     "document": "La quimioterapia y usted: Apoyo para las personas con cáncer", "entity": NCI,
                     "version": "2019", "section": "Náuseas y vómitos", "page_start": 65, "page_end": 65, "used": True}
    assert [s["used"] for s in body["sources"]] == [True, False, False]     # solo la fuente citada [1]
    assert not {"distance", "fragment_id", "model"} & set(first) and "model" not in body
    assert body["urgent"] is False


def test_propaga_request_al_motor_con_top_k_3(client, engine):
    search(client, "  diarrea durante la quimioterapia  ")
    [req] = engine["requests"]
    assert req.method == "POST"
    assert str(req.url) == "http://rag.test:8001/api/rag/search"
    assert json.loads(req.content) == {"query": "diarrea durante la quimioterapia", "top_k": 3}


# ----------------------------------------------------------------------------- llamada a Ollama
def test_llama_a_ollama_una_vez_con_qwen_y_sin_streaming(client, engine, ollama):
    search(client)
    assert len(engine["requests"]) == 1
    [req] = ollama["requests"]
    assert str(req.url) == "http://ollama.test:11434/api/chat"
    payload = json.loads(req.content)
    assert payload["model"] == "qwen2.5:7b" == config.OLLAMA_MODEL
    assert payload["stream"] is False
    system, user = payload["messages"]
    assert system["role"] == "system" and "EXCLUSIVAMENTE en las fuentes recuperadas" in system["content"]
    assert grounded.NO_INFO in system["content"]
    assert user["role"] == "user" and QUERY in user["content"]


def test_contexto_incluye_trazabilidad_y_excluye_datos_tecnicos(engine):
    sources = engine["results"]
    ctx = grounded.build_context(sources)
    assert ctx.startswith("FUENTE 1\nEntidad: National Cancer Institute (NCI)\n"
                          "Documento: La quimioterapia y usted: Apoyo para las personas con cáncer\n"
                          "Versión: 2019\nSección: Náuseas y vómitos\nPágina: 65\n\nContenido:\n" + TEXT_1)
    assert "FUENTE 2" in ctx and "FUENTE 3" in ctx and "Página: 48" in ctx
    for technical in ("frag-1", "distance", "score", "0.69", "embedding", "BAAI", "pgvector"):
        assert technical not in ctx


# ----------------------------------------------------------------------------- fallos de Ollama
@pytest.mark.parametrize("error", [httpx.ConnectError("conexión rechazada"), httpx.ReadTimeout("timeout")])
def test_ollama_caido_o_lento_conserva_las_fuentes(client, engine, ollama, error):
    ollama["error"] = error
    r = search(client)
    assert r.status_code == 200
    body = r.json()
    assert body["answer_status"] == "sin_generacion"
    assert body["answer"] == grounded.GENERATION_FAILED
    assert len(body["sources"]) == 3 and body["sources"][0]["text"] == TEXT_1
    assert "ollama.test" not in r.text and "11434" not in r.text and "timeout" not in r.text.lower()


@pytest.mark.parametrize("status, body", [(500, None), (200, {"error": "model not found"}), (200, {"message": {"content": ""}})])
def test_ollama_error_o_respuesta_invalida(client, engine, ollama, status, body):
    ollama["status"], ollama["body"] = status, body
    r = search(client)
    assert r.status_code == 200
    assert r.json()["answer_status"] == "sin_generacion"
    assert "model not found" not in r.text


def test_timeout_configurado(monkeypatch, engine, ollama):
    seen = {}

    class Spy(httpx.Client):
        def __init__(self, **kw):
            seen["timeout"] = kw["timeout"]
            super().__init__(**kw)

    monkeypatch.setattr(ollama_client.httpx, "Client", Spy)
    monkeypatch.setattr(config, "OLLAMA_TIMEOUT", 7.0)
    ollama_client.chat([{"role": "user", "content": "hola"}])
    assert seen["timeout"] == 7.0


# ----------------------------------------------------------------------------- abstención
def test_sin_resultados_no_llama_a_ollama(client, engine, ollama):
    engine["results"] = []
    body = search(client, "capital de Australia").json()
    assert body["answer"] == grounded.NO_INFO and body["answer_status"] == "abstencion"
    assert body["sources"] == []
    assert ollama["requests"] == []


def test_similitud_baja_se_abstiene_sin_llamar_a_ollama(client, engine, ollama):
    engine["results"] = [rag_result(i, score=0.30) for i in (1, 2, 3)]
    body = search(client, "capital de Australia").json()
    assert body["answer"] == grounded.NO_INFO and body["answer_status"] == "abstencion"
    assert len(body["sources"]) == 3 and not any(s["used"] for s in body["sources"])
    assert ollama["requests"] == []


def test_abstencion_declarada_por_el_modelo(client, engine, ollama):
    ollama["content"] = f'"{grounded.NO_INFO}"'
    body = search(client).json()
    assert body["answer_status"] == "abstencion" and body["answer"] == grounded.NO_INFO


# ----------------------------------------------------------------------------- seguridad
def test_urgencia_se_conserva_aunque_el_modelo_la_ignore(client, engine, ollama):
    ollama["content"] = "Algunos tipos de quimioterapia pueden causar náuseas [1]."
    body = search(client, "no puede respirar después de la quimioterapia").json()
    assert body["urgent"] is True and "emergencia" in body["urgent_message"]


def test_fuera_de_alcance_tiene_prioridad_sobre_el_llm(client, engine, ollama):
    body = search(client, "qué dosis de morfina le doy").json()
    assert body["answer_status"] == "fuera_de_alcance"
    assert "fuera del alcance" in body["answer"]
    assert ollama["requests"] == []
    assert len(body["sources"]) == 3


def test_descarta_dosis_inventadas(client, engine, ollama):
    ollama["content"] = "Puede tomar 8 mg de ondansetrón cada 8 horas [1]."
    body = search(client).json()
    assert body["answer_status"] == "sin_generacion"
    assert "8 mg" not in body["answer"]


def test_elimina_oraciones_sin_respaldo(client, engine, ollama):
    ollama["content"] = ("Algunos tipos de quimioterapia pueden causar náuseas y vómitos [1]. "
                         "Estimulan los centros del sistema nervioso que controlan el reflejo [1].\n"
                         "- Beber jengibre y mantener buena hidratación.")
    body = search(client).json()
    assert body["answer_status"] == "respondida"
    assert body["answer"] == "Algunos tipos de quimioterapia pueden causar náuseas y vómitos [1]."


def test_limite_de_fuentes_sin_coletilla_inventada():
    text, kept, removed = grounded.verify(
        "Las fuentes recuperadas no indican qué medicamento usar, pero recomiendan consultar al médico [1].", TEXT_1)
    assert text == "Las fuentes recuperadas no indican qué medicamento usar."


def test_no_cita_fuentes_inexistentes():
    assert grounded.cited("Dato [1]. Otro [2, 7]. Más [9]", 3) == [1, 2]


# ----------------------------------------------------------------------------- errores y validación
@pytest.mark.parametrize("error", [httpx.ConnectError("conexión rechazada"), httpx.ReadTimeout("timeout")])
def test_rag_caido_devuelve_503_sin_detalles_tecnicos(client, engine, ollama, error):
    engine["error"] = error
    r = search(client, "náuseas")
    assert r.status_code == 503
    assert r.json() == {"detail": "No se pudo consultar la base de conocimiento en este momento. Inténtalo nuevamente."}
    assert "rag.test" not in r.text and "8001" not in r.text
    assert ollama["requests"] == []


def test_rag_responde_error_http_devuelve_503(client, engine):
    engine["status"] = 503
    assert search(client, "náuseas").status_code == 503


@pytest.mark.parametrize("query", ["", "   "])
def test_query_vacia_no_llama_al_motor_ni_a_ollama(client, engine, ollama, query):
    r = search(client, query)
    assert r.status_code == 422
    assert engine["requests"] == [] and ollama["requests"] == []


def test_requiere_sesion_de_cuidador(client, engine, curador):
    assert client.post("/api/rag/search", json={"query": "náuseas"}).status_code == 401
    assert client.post("/api/rag/search", headers=curador, json={"query": "náuseas"}).status_code == 403
    assert engine["requests"] == []
