"""Extracción de entidades del registro por voz o texto libre (RF-03).

Devuelve una PROPUESTA estructurada que el cuidador debe confirmar o corregir antes de guardarla.
"""
import re
from .rag.text import normalize

SYMPTOMS = {
    "fiebre": ["fiebre", "calentura", "temperatura", "afiebrad", "febril"],
    "dolor": ["dolor", "duele", "adolorid", "molestia"],
    "nauseas": ["nausea", "asco", "ganas de vomitar"],
    "vomito": ["vomit", "devolvi", "devuelve"],
    "fatiga": ["fatiga", "cansad", "cansancio", "agotad", "sin fuerza", "debil"],
    "diarrea": ["diarrea", "suelto", "deposiciones liquidas"],
    "estrenimiento": ["estrenimiento", "estrenid", "no hace deposicion", "no ha ido al bano"],
    "disnea": ["falta de aire", "ahoga", "no puede respirar", "dificultad para respirar", "respira mal", "agitad"],
    "sangrado": ["sangr"],
    "mucositis": ["llaga", "afta", "mucositis", "boca lastimada", "herida en la boca"],
    "mareo": ["mare"],
    "insomnio": ["no durmio", "no duerme", "insomnio", "durmio mal", "desvel"],
    "ansiedad": ["ansios", "ansiedad", "nervios", "angusti", "preocupad"],
    "tos": ["tos"],
    "confusion": ["confundid", "desorientad", "confusion", "no reconoce"],
    "hinchazon": ["hinchad", "hinchazon", "inflamad"],
    "apetito": ["no quiere comer", "sin apetito", "no come", "inapetencia", "falta de apetito"],
}
MOMENTS = [
    ("esta manana", "esta mañana"), ("en la manana", "en la mañana"), ("esta tarde", "esta tarde"),
    ("esta noche", "esta noche"), ("anoche", "anoche"), ("en la noche", "en la noche"), ("ayer", "ayer"),
    ("ahora", "ahora"), ("hace un rato", "hace un rato"), ("al despertar", "al despertar"),
    ("despues de comer", "después de comer"), ("despues del almuerzo", "después del almuerzo"),
]
NUM_WORDS = {"uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
             "nueve": 9, "diez": 10}


def _num(tok: str) -> float | None:
    tok = tok.replace(",", ".")
    try:
        return float(tok)
    except ValueError:
        return NUM_WORDS.get(tok)


def extract(text: str) -> dict:
    t = normalize(text)
    found = []
    for sym, keys in SYMPTOMS.items():
        pos = min([t.find(k) for k in keys if k in t] or [-1])
        if pos >= 0:
            found.append((pos, sym))
    found.sort()
    symptom = found[0][1] if found else ""
    others = [s for _, s in found[1:]]

    value = unit = None
    m = re.search(r"(\d{2}(?:[\.,]\d)?)\s*(?:grados|°|º|c\b)", t)
    if m and 34 <= float(m.group(1).replace(",", ".")) <= 43:
        value, unit = float(m.group(1).replace(",", ".")), "°C"
        if not symptom:
            symptom = "fiebre"
    elif symptom == "fiebre":
        m = re.search(r"\b(3[4-9](?:[\.,]\d)?|4[0-2](?:[\.,]\d)?)\b", t)
        if m:
            value, unit = float(m.group(1).replace(",", ".")), "°C"

    intensity = None
    m = re.search(r"\b(\d{1,2}|" + "|".join(NUM_WORDS) + r")\s*(?:de|sobre|/)\s*(?:10|diez)\b", t)
    if not m:
        m = re.search(r"\b(?:intensidad|nivel|escala)\s*(?:de\s*)?(\d{1,2}|" + "|".join(NUM_WORDS) + r")\b", t)
    if m:
        n = _num(m.group(1))
        if n is not None and 0 <= n <= 10:
            intensity = int(n)
    if intensity is None:
        if re.search(r"\b(muy fuerte|insoportable|intenso|intensa|fuertisimo)\b", t):
            intensity = 8
        elif re.search(r"\b(fuerte)\b", t):
            intensity = 6
        elif re.search(r"\b(leve|poquito|un poco|ligero|ligera)\b", t):
            intensity = 2
        elif re.search(r"\b(moderado|moderada|regular)\b", t):
            intensity = 5

    frequency = None
    m = re.search(r"\b(\d{1,2}|" + "|".join(NUM_WORDS) + r")\s*veces\b", t)
    if m:
        frequency = int(_num(m.group(1)) or 0) or None

    moment = ""
    for k, label in MOMENTS:
        if k in t:
            moment = label
            break
    m = re.search(r"hace (\d{1,2}|" + "|".join(NUM_WORDS) + r") (hora|horas|minutos)", t)
    if m:
        moment = f"hace {m.group(1)} {m.group(2)}"

    kind = "sintoma" if symptom else "observacion"
    if not symptom and re.search(r"\b(le di|tomo|se tomo|le dimos|administre|cambie|banamos|bane|camino|caminamos)\b", t):
        kind = "actividad"
    return {"kind": kind, "symptom": symptom, "other_symptoms": others, "intensity": intensity, "value": value,
            "unit": unit or "", "frequency": frequency, "moment": moment, "text": text.strip()}
