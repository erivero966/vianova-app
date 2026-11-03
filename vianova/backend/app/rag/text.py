"""Normalización de texto en español para la recuperación."""
import re
import unicodedata

STOPWORDS = set("""
a al algo algun alguna algunas alguno algunos ante antes aqui asi aun cada como con contra cual cuales cuando de del
desde donde dos el ella ellas ellos en entre era es esa esas ese eso esos esta estaba estado estan estar este esto estos
fue ha hace hacer han hasta hay la las le les lo los mas me mi mis mucho muy nada ni no nos o otra otro para pero poco por
porque que quien se sea segun ser si sin sobre son su sus tambien tan tanto te tener tengo tiene tienen todo todos tu un una
unas uno unos usted ustedes y ya yo debo debe puedo puede hago le lo mi mama papa familiar paciente esposo esposa hijo hija
""".split())

# Sinónimos coloquiales → término del corpus (expansión de consulta)
SYNONYMS = {
    "calentura": "fiebre", "temperatura": "fiebre", "afiebrado": "fiebre", "afiebrada": "fiebre", "febril": "fiebre",
    "ahogo": "falta aire respirar", "ahoga": "falta aire respirar", "disnea": "falta aire respirar",
    "llagas": "llagas boca mucositis", "aftas": "llagas boca mucositis", "mucositis": "llagas boca",
    "cansancio": "fatiga cansancio", "cansado": "fatiga", "cansada": "fatiga", "agotado": "fatiga", "agotada": "fatiga",
    "vomita": "vomitos", "vomito": "vomitos", "vomitar": "vomitos", "vomitando": "vomitos", "devuelve": "vomitos",
    "nauseas": "nauseas", "mareado": "mareo", "mareada": "mareo",
    "estrenido": "estrenimiento", "estrenida": "estrenimiento", "suelto": "diarrea",
    "pastillas": "medicamentos", "pastilla": "medicamentos", "remedios": "medicamentos", "medicinas": "medicamentos",
    "toma": "toma medicamentos", "olvide": "olvida toma", "olvido": "olvida toma",
    "comer": "alimentacion apetito", "come": "alimentacion apetito", "comida": "alimentacion alimentos",
    "agua": "liquidos hidratacion", "tomar": "beber",
    "duele": "dolor", "dolores": "dolor", "adolorido": "dolor",
    "quemadura": "piel radioterapia", "rayos": "radioterapia", "quimio": "quimioterapia",
    "estres": "sobrecarga cansancio cuidador", "agobiado": "sobrecarga", "agobiada": "sobrecarga", "triste": "tristeza",
    "duermo": "sueno", "dormir": "sueno", "tomo": "tomar", "comunico": "comunicarse comunicacion",
    "caer": "caidas", "cayo": "caida", "caiga": "caidas prevenir", "caerse": "caidas", "resbale": "caidas", "caidas": "caidas prevenir", "escaras": "lesiones presion piel",
    "doctor": "equipo salud", "medico": "equipo salud", "cita": "consulta",
    "sangra": "sangrado", "sangre": "sangrado", "desorientado": "confusion", "desorientada": "confusion",
}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize(s: str) -> str:
    s = strip_accents(s.lower())
    s = s.replace("ñ", "n")
    s = re.sub(r"[^a-z0-9°\.\, ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", normalize(s)) if t not in STOPWORDS and len(t) > 1]


def expand_query(q: str) -> str:
    toks = tokens(q)
    extra = [SYNONYMS[t] for t in toks if t in SYNONYMS]
    return " ".join(toks + extra)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 15]


# Palabras frecuentes que no aportan al tema de la consulta (no cuentan para la cobertura)
GENERIC = set("""como hago hacer hace cuando cual cuales mejor bien mal dia dias hora horas horario tiempo casa cambio cambiar
quiero saber puede pueden debo debe deberia normal todo toda mucho poco ahora hoy manana tarde noche hay esta estoy siento
cosa cosas algo forma manera ayuda informacion favor gracias cuanta cuanto cuantos cuantas donde queda sirve tengo tiene
correctamente pongo pido pedir puedo poner""".split())


def _stem_match(tok: str, vocab: set[str]) -> bool:
    if tok in vocab:
        return True
    if len(tok) >= 5:
        p = tok[:5]
        return any(v.startswith(p) for v in vocab if len(v) >= 5)
    return False


def coverage(query: str, text: str) -> float:
    """Proporción de palabras de contenido de la consulta (o de sus sinónimos) presentes en el texto."""
    vocab = set(tokens(text))
    qt = [t for t in tokens(query) if t not in GENERIC]
    if not qt:
        return 0.0
    hit = 0
    for t in qt:
        alts = [t] + (SYNONYMS[t].split() if t in SYNONYMS else [])
        if any(_stem_match(a, vocab) for a in alts):
            hit += 1
    return hit / len(qt)
