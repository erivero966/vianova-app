"""Cliente mínimo de la API local de Ollama (POST /api/chat, sin streaming).

Solo se usa el servidor local configurado en OLLAMA_URL; no hay llamadas a servicios externos.
"""
import logging

import httpx

from .. import config

logger = logging.getLogger(__name__)

# Permite inyectar httpx.MockTransport en las pruebas (no se carga Qwen).
TRANSPORT: httpx.BaseTransport | None = None

# Respuestas deterministas y acotadas; keep_alive mantiene el modelo en memoria durante la demo.
OPTIONS = {"temperature": 0, "num_ctx": 4096, "num_predict": 400}
KEEP_ALIVE = "30m"


class OllamaError(RuntimeError):
    """Ollama apagado, lento, con error HTTP o con una respuesta inutilizable."""


def chat(messages: list[dict]) -> str:
    payload = {"model": config.OLLAMA_MODEL, "stream": False, "messages": messages,
               "options": OPTIONS, "keep_alive": KEEP_ALIVE}
    try:
        with httpx.Client(base_url=config.OLLAMA_URL, timeout=config.OLLAMA_TIMEOUT, transport=TRANSPORT) as client:
            resp = client.post("/api/chat", json=payload)
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
    except httpx.TimeoutException as exc:
        logger.warning("Ollama superó el tiempo de espera (%ss)", config.OLLAMA_TIMEOUT)
        raise OllamaError("timeout") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Ollama respondió HTTP %s", exc.response.status_code)
        raise OllamaError(f"HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.warning("Ollama no disponible en %s: %s", config.OLLAMA_URL, exc)
        raise OllamaError("no disponible") from exc
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("Respuesta inválida de Ollama: %s", exc)
        raise OllamaError("respuesta inválida") from exc
    if not isinstance(content, str) or not content.strip():
        raise OllamaError("respuesta vacía")
    return content.strip()
