"""Generación de respuestas restringida al contexto recuperado.

- Modo local (por defecto): respuesta extractiva con las oraciones más pertinentes de los fragmentos.
- Modo anthropic / openai: el modelo redacta en lenguaje sencillo usando SOLO los fragmentos; si responde
  NO_EVIDENCIA, el sistema se abstiene. Ante cualquier error del servicio externo se usa el modo local (RNF-F01).
"""
import httpx
from .. import config
from .text import sentences, tokens, expand_query

SYSTEM_PROMPT = (
    "Eres un asistente informativo para cuidadores informales de pacientes con cáncer en el Perú. "
    "Responde en español sencillo, en un máximo de 120 palabras, usando ÚNICAMENTE la información de los fragmentos "
    "proporcionados, y cita entre corchetes el número del fragmento que usaste, por ejemplo [1]. "
    "No indiques dosis, diagnósticos, pronósticos ni cambios de tratamiento. "
    "Si los fragmentos no contienen información suficiente para responder, responde exactamente: NO_EVIDENCIA"
)


def extractive(query: str, hits, max_sentences: int = 4) -> tuple[str, list[int]]:
    qset = set(tokens(expand_query(query)))
    scored = []
    for hi, h in enumerate(hits):
        for si, s in enumerate(sentences(h.text)):
            st = set(tokens(s))
            overlap = len(qset & st) / (len(st) ** 0.5 + 1)
            scored.append((overlap + h.score, hi, si, s))
    scored.sort(key=lambda x: -x[0])
    chosen = sorted(scored[:max_sentences], key=lambda x: (x[1], x[2]))
    used = sorted({c[1] for c in chosen})
    text = " ".join(c[3] for c in chosen)
    return text, used


def _context(hits) -> str:
    return "\n\n".join(f"[{i + 1}] ({h.section}) {h.text}" for i, h in enumerate(hits))


def llm(query: str, hits) -> str | None:
    """Devuelve el texto del modelo, 'NO_EVIDENCIA' o None si no hay proveedor disponible."""
    user_msg = f"Fragmentos:\n{_context(hits)}\n\nPregunta del cuidador: {query}"
    try:
        if config.LLM_PROVIDER == "anthropic" and config.ANTHROPIC_API_KEY:
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=30, headers={
                "x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": config.ANTHROPIC_MODEL, "max_tokens": 400, "system": SYSTEM_PROMPT,
                      "messages": [{"role": "user", "content": user_msg}]})
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"]).strip()
        if config.LLM_PROVIDER == "openai" and config.OPENAI_API_KEY:
            r = httpx.post("https://api.openai.com/v1/chat/completions", timeout=30, headers={
                "Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                json={"model": config.OPENAI_MODEL, "max_tokens": 400, "temperature": 0,
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_msg}]})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
    return None


def generate(query: str, hits) -> tuple[str | None, list[int], str]:
    """Devuelve (texto o None si se abstiene, índices de fragmentos usados, modo)."""
    if config.LLM_PROVIDER in ("anthropic", "openai"):
        out = llm(query, hits)
        if out is not None:
            if "NO_EVIDENCIA" in out:
                return None, [], config.LLM_PROVIDER
            used = sorted({int(n) - 1 for n in __import__("re").findall(r"\[(\d+)\]", out) if 0 < int(n) <= len(hits)})
            return out, used or [0], config.LLM_PROVIDER
    text, used = extractive(query, hits)
    return text, used, "local"
