"""Reglas de alcance (RNF-ET01) y detección de signos de alarma en consultas.

Las reglas de seguridad tienen prioridad sobre cualquier puntuación del recomendador o del RAG.
"""
import re
from .text import normalize

SCOPE_MESSAGE = ("Esta consulta está fuera del alcance informativo del sistema: no puede indicar dosis, diagnósticos, "
                 "pronósticos ni cambios de tratamiento. Consulte esta duda con el equipo de salud que atiende al paciente.")

# Patrones sobre texto normalizado (sin tildes, minúsculas)
OUT_OF_SCOPE = [
    (r"\b(ignora\w*|olvida\w*|omite|salta\w*)\b.{0,25}\b(instrucciones|reglas|indicaciones|restricciones)\b", "manipulación de instrucciones"),
    (r"\b(actua como|eres un|haz de|finge ser|simula ser)\b.{0,15}\b(medico|doctor|oncologo|enfermer\w*)\b", "manipulación de instrucciones"),
    (r"\b(que|cuanta|cuantas|cuanto|cuantos)\b.{0,25}\b(dosis|mg|miligramos|gotas|ml|pastillas|tabletas|ampollas)\b", "dosis"),
    (r"\bdosis\b", "dosis"),
    (r"\bcuant\w*\b.{0,30}\b(le doy|le de|darle|le puedo dar|debo darle|le pongo)\b", "dosis"),
    (r"\b(morfina|tramadol|codeina|oxicodona|paracetamol|ibuprofeno|metamizol|ketorolaco|ondansetron|dexametasona|antibiotico\w*|insulina)\b.{0,30}\b(le doy|darle|le puedo dar|puedo darle|cuanto|cuanta|cada cuanto)\b", "medicación"),
    (r"\b(subir|aumentar|bajar|disminuir|duplicar|doblar|cambiar|suspender|dejar de dar|dejar de tomar|parar)\b.{0,30}\b(dosis|tratamiento|medicamento|medicina|quimio\w*|morfina|pastilla\w*|remedio\w*)\b", "cambio de tratamiento"),
    (r"\b(que|cual)\b.{0,15}\b(medicamento|medicina|pastilla|remedio|antibiotico|analgesico)\b.{0,20}\b(le doy|darle|le puedo dar|tomar|debo dar|recomiendas|recomienda)\b", "prescripción"),
    (r"\b(tiene|tendra|sera|es|habra|hay)\b.{0,20}\b(metastasis|cancer terminal|recaida)\b", "diagnóstico"),
    (r"^\W*(metastasis|recaida)\W*$", "diagnóstico"),
    (r"\bdiagnostic\w*\b", "diagnóstico"),
    (r"\b(cuanto (tiempo )?(de vida )?(le )?queda( de vida)?|tiempo de vida|pronostico|esperanza de vida|se va a morir|"
     r"va a sobrevivir|cuanto va a vivir|se va a curar)\b", "pronóstico"),
    (r"\b(interpreta\w*|que significa\w*)\b.{0,25}\b(examen|analisis|resultado|tomografia|biopsia|hemograma|laboratorio)\b", "interpretación de exámenes"),
]

URGENT = [
    r"\bno (puede|puedo) respirar\b", r"\bse (esta )?ahoga\w*\b", r"\bdolor (de|en el) pecho\b", r"\bconvulsi\w+\b",
    r"\bdesmay\w+\b", r"\binconsciente\b", r"\bno responde\b", r"\bsangr\w+ (mucho|bastante|abundante)\b",
    r"\bvomit\w+ sangre\b", r"\blabios morados\b", r"\bno respira\b", r"\bse puso morad\w\b",
]
URGENT_MESSAGE = ("Lo que describe puede ser una emergencia. Llame al servicio de emergencias o acuda de inmediato "
                  "al establecimiento de salud más cercano.")


def check_scope(query: str) -> str | None:
    q = normalize(query)
    for pat, reason in OUT_OF_SCOPE:
        if re.search(pat, q):
            return reason
    return None


def is_urgent(query: str) -> bool:
    q = normalize(query)
    return any(re.search(p, q) for p in URGENT)
