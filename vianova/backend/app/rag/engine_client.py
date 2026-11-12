"""Cliente del motor RAG externo (rag-engine: BGE-M3 + PostgreSQL/pgvector, búsqueda exacta).

El backend actúa como intermediario: el frontend nunca llama al motor directamente.
Solo recuperación: no hay generación, resumen ni LLM. Se conserva la trazabilidad de cada fragmento.
"""
import logging

import httpx

from .. import config

logger = logging.getLogger(__name__)

# Campos que se entregan al frontend (sin distance, fragment_id ni model: son técnicos).
FIELDS = ("rank", "score", "text", "document", "entity", "version", "section", "page_start", "page_end")

# Permite inyectar httpx.MockTransport en las pruebas sin tocar la red.
TRANSPORT: httpx.BaseTransport | None = None


class RagEngineError(RuntimeError):
    """El motor RAG no respondió o respondió algo inutilizable."""


def search(query: str, top_k: int | None = None) -> dict:
    """POST {RAG_API_URL}/api/rag/search y normaliza la respuesta para el frontend."""
    top_k = top_k or config.RAG_API_TOP_K
    try:
        with httpx.Client(base_url=config.RAG_API_URL, timeout=config.RAG_API_TIMEOUT,
                          transport=TRANSPORT) as client:
            resp = client.post("/api/rag/search", json={"query": query, "top_k": top_k})
        resp.raise_for_status()
        data = resp.json()
        results = [{k: r.get(k) for k in FIELDS} for r in data["results"]]
    except httpx.HTTPStatusError as exc:
        logger.warning("rag-engine respondió %s", exc.response.status_code)
        raise RagEngineError(f"rag-engine HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.warning("rag-engine no disponible en %s: %s", config.RAG_API_URL, exc)
        raise RagEngineError("rag-engine no disponible") from exc
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("Respuesta inválida de rag-engine: %s", exc)
        raise RagEngineError("respuesta inválida de rag-engine") from exc
    results.sort(key=lambda r: r["rank"] or 0)
    return {"query": data.get("query", query), "model": data.get("model", ""), "results": results}
