"""Respuesta generada con Ollama, restringida a los fragmentos recuperados por rag-engine.

Orden: reglas deterministas (safety.py, umbral de abstención) -> contexto -> qwen2.5:7b -> controles de salida.
El retrieval no se modifica: aquí solo se consumen sus Top-K.
"""
import re
import unicodedata

from .. import config
from . import ollama_client
from .safety import SCOPE_MESSAGE, check_scope
from .text import coverage

NO_INFO = "No encontré información suficiente en las fuentes disponibles para responder esta consulta."
GENERATION_FAILED = ("No fue posible generar una explicación en este momento. "
                     "Puedes revisar directamente la información recuperada de las fuentes.")

SYSTEM_PROMPT = f"""Eres Vianova, un asistente informativo para cuidadores informales de pacientes con cáncer.

Tu respuesta debe basarse EXCLUSIVAMENTE en las fuentes recuperadas que se te proporcionan.

Reglas obligatorias:

1. No uses conocimientos externos a las fuentes proporcionadas.
2. No inventes información ni completes datos ausentes.
3. No diagnostiques enfermedades.
4. No prescribas medicamentos, dosis ni tratamientos.
5. No indiques iniciar, suspender o modificar tratamientos.
6. No atribuyas causas que no aparezcan explícitamente en las fuentes.
7. No agregues recomendaciones que no estén respaldadas por las fuentes.
8. Utiliza lenguaje sencillo, claro y breve para un cuidador informal (máximo 150 palabras).
9. Si las fuentes indican cuándo debe contactar al equipo de salud, puedes explicarlo.
10. Si las fuentes no contienen información suficiente para responder, debes decir exactamente:

"{NO_INFO}"

11. No menciones que utilizaste embeddings, vectores, BGE-M3, pgvector ni procesos internos.
12. No cites una fuente que no haya sido proporcionada. Indica entre corchetes el número de la fuente que respalda cada idea, por ejemplo [1].
13. Evita afirmaciones absolutas.
14. Prioriza explicar qué dice la evidencia recuperada.
15. Si la consulta pide algo que las fuentes no cubren (por ejemplo qué hacer, un medicamento, una dosis o una causa), escribe una oración que empiece con "Las fuentes recuperadas no indican" y di qué falta. Escribe esa oración solo para lo que de verdad no aparece en las fuentes; si las fuentes sí lo responden, no la escribas. No completes lo que falta con tu propio conocimiento.
16. Cada oración debe poder comprobarse en las fuentes y terminar con la cita [n] de la fuente que la respalda.

Responde directamente a la consulta del cuidador, en español."""

REMINDER = ("Responde usando SOLO lo que dicen las FUENTES RECUPERADAS, con una cita [n] al final de cada oración. "
            "Si las fuentes no dicen qué hacer, qué medicamento usar o por qué ocurre algo, dilo con una oración que "
            "empiece con \"Las fuentes recuperadas no indican\" (solo si de verdad falta). No agregues información propia.")

# Cantidades con unidad de medicamento: si el modelo escribe una que no está en las fuentes, se descarta la respuesta.
DOSE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|cc|ui|gotas?|tabletas?|pastillas?|comprimidos?|capsulas?)\b")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _pages(s: dict) -> str:
    if s.get("page_start") is None:
        return "—"
    end = s.get("page_end")
    return f"{s['page_start']}-{end}" if end and end != s["page_start"] else str(s["page_start"])


def build_context(sources: list[dict]) -> str:
    """Solo metadatos de trazabilidad y texto: sin distance, fragment_id ni datos internos."""
    blocks = []
    for i, s in enumerate(sources, 1):
        blocks.append(
            f"FUENTE {i}\n"
            f"Entidad: {s.get('entity') or '—'}\n"
            f"Documento: {s.get('document') or '—'}\n"
            f"Versión: {s.get('version') or '—'}\n"
            f"Sección: {s.get('section') or '—'}\n"
            f"Página: {_pages(s)}\n\n"
            f"Contenido:\n{s.get('text') or ''}"
        )
    return "\n\n".join(blocks)


def build_messages(query: str, sources: list[dict]) -> list[dict]:
    user = f"FUENTES RECUPERADAS\n\n{build_context(sources)}\n\nCONSULTA DEL CUIDADOR\n{query}\n\n{REMINDER}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


# Verificación por oración: proporción mínima de palabras de contenido de la oración presentes en las fuentes
# (coincidencia por raíz, `text.coverage`). Las oraciones que no la alcanzan se eliminan de la respuesta.
MIN_SENTENCE_SUPPORT = 0.6
SOURCE_LIMIT = re.compile(r"\blas fuentes\b.{0,30}\bno (indican|contienen|explican|mencionan|incluyen|dicen|describen|especifican)\b")
LIMIT_TAIL = re.compile(r"[,;:]?\s+(?:pero|sin embargo|aunque|no obstante|por lo que|por eso|y se recomienda|y recomiendan|se recomienda|generalmente)\b", re.I)
CITATION = re.compile(r"\s*\[[\d,\s]+\]")


def _sentences(line: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?])\s+|(?<=\])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])", line) if x.strip()]


def verify(answer: str, context: str) -> tuple[str, int, int]:
    """Elimina oraciones sin respaldo en el contexto. Devuelve (texto, oraciones conservadas con contenido, eliminadas)."""
    kept_lines, kept, removed = [], 0, 0
    for line in answer.splitlines():
        if not line.strip():
            kept_lines.append("")
            continue
        prefix = re.match(r"\s*(?:[-*•]|\d+[.)])\s+", line)
        body = line[prefix.end():] if prefix else line
        out = []
        for sent in _sentences(body):
            plain = CITATION.sub("", sent).strip()
            if SOURCE_LIMIT.search(_norm(plain)):
                # Declarar un límite de las fuentes es válido, pero no lo que el modelo añada después
                # ("..., pero recomiendan ..."): esa parte no está respaldada y se corta.
                limit = LIMIT_TAIL.split(plain, maxsplit=1)[0].rstrip(" ,;:.")
                out.append(limit + ".")
            elif coverage(plain, context) >= MIN_SENTENCE_SUPPORT:
                out.append(sent); kept += 1
            else:
                removed += 1
        if out:
            kept_lines.append((prefix.group(0) if prefix else "") + " ".join(out))
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()
    return text, kept, removed


def cited(answer: str, n: int) -> list[int]:
    """Números de fuente citados en la respuesta ([1], [2], [1, 3]) que existen en el contexto."""
    nums = {int(x) for group in re.findall(r"\[([\d,\s]+)\]", answer) for x in re.findall(r"\d+", group)}
    return sorted(i for i in nums if 1 <= i <= n)


def answer(query: str, sources: list[dict]) -> dict:
    """Devuelve {status, answer, cited, llm_called}. status: respondida | abstencion | fuera_de_alcance | sin_generacion."""
    if not sources:
        return {"status": "abstencion", "answer": NO_INFO, "cited": [], "llm_called": False}
    if check_scope(query):                       # dosis, diagnóstico, pronóstico...: prioridad sobre el LLM
        return {"status": "fuera_de_alcance", "answer": SCOPE_MESSAGE, "cited": [], "llm_called": False}
    if (sources[0].get("score") or 0) < config.RAG_MIN_SCORE:
        return {"status": "abstencion", "answer": NO_INFO, "cited": [], "llm_called": False}
    try:
        text = ollama_client.chat(build_messages(query, sources))
    except ollama_client.OllamaError:
        return {"status": "sin_generacion", "answer": GENERATION_FAILED, "cited": [], "llm_called": True}
    if _norm(text).strip(' "“”.').startswith(_norm(NO_INFO).rstrip(".")):
        return {"status": "abstencion", "answer": NO_INFO, "cited": [], "llm_called": True}
    context = _norm(build_context(sources))
    if any(m.group(0) not in context for m in DOSE.finditer(_norm(text))):
        return {"status": "sin_generacion", "answer": GENERATION_FAILED, "cited": [], "llm_called": True}
    checked, kept, removed = verify(text, build_context(sources))
    if not kept:                                  # nada de la respuesta está respaldado por las fuentes
        return {"status": "abstencion", "answer": NO_INFO, "cited": [], "llm_called": True, "removed": removed}
    return {"status": "respondida", "answer": checked, "cited": cited(checked, len(sources)), "llm_called": True,
            "removed": removed}
