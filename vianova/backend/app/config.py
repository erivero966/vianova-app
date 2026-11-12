"""Configuración central del sistema Vianova (variables de entorno con valores por defecto).

Ambientes separados (política de seguridad de la información):
    APP_ENV=desarrollo  → datos ficticios, base propia en data/entornos/desarrollo
    APP_ENV=pruebas     → datos ficticios, base propia en data/entornos/pruebas (calidad / QA)
    APP_ENV=produccion  → datos reales; exige secretos y contraseñas definidos por variables de entorno
Los datos de un ambiente nunca se copian a otro.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
SHARED_DIR = BASE_DIR / "data"                              # recursos comunes versionados (corpus y reglas)

APP_ENV = os.getenv("APP_ENV", "desarrollo").strip().lower()
if APP_ENV not in ("desarrollo", "pruebas", "produccion"):
    raise RuntimeError("APP_ENV debe ser 'desarrollo', 'pruebas' o 'produccion'")
IS_PRODUCTION = APP_ENV == "produccion"

DATA_DIR = Path(os.getenv("VIANOVA_DATA_DIR", SHARED_DIR / "entornos" / APP_ENV))
_local_corpus = DATA_DIR / "corpus"
CORPUS_DIR = Path(os.getenv("VIANOVA_CORPUS_DIR", _local_corpus if _local_corpus.exists() else SHARED_DIR / "corpus"))
_local_rules = DATA_DIR / "rules.json"
RULES_FILE = Path(os.getenv("VIANOVA_RULES_FILE", _local_rules if _local_rules.exists() else SHARED_DIR / "rules.json"))
FRONTEND_DIST = Path(os.getenv("VIANOVA_FRONTEND_DIST", BASE_DIR.parent / "frontend" / "dist"))
EVAL_RESULTS_DIR = Path(os.getenv("VIANOVA_EVAL_RESULTS", BASE_DIR.parent / "eval" / "resultados"))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'vianova.db'}")

# Seguridad
def _secret() -> str:
    env = os.getenv("JWT_SECRET")
    if env:
        return env
    if IS_PRODUCTION:
        raise RuntimeError("En producción JWT_SECRET debe definirse como variable de entorno")
    import secrets
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    f = DATA_DIR / ".jwt_secret"
    if not f.exists():
        f.write_text(secrets.token_urlsafe(48))
    return f.read_text().strip()


JWT_SECRET = _secret()
JWT_HOURS = int(os.getenv("JWT_HOURS", "12"))
ENCRYPTION_KEY_FILE = DATA_DIR / ".fernet.key"

# Usuarios iniciales (cámbielos en producción)
ADMIN_EMAIL = os.getenv("VIANOVA_ADMIN_EMAIL", "curador@vianova.local")
ADMIN_PASSWORD = os.getenv("VIANOVA_ADMIN_PASSWORD", "Curador2026!")
RESEARCHER_EMAIL = os.getenv("VIANOVA_RESEARCHER_EMAIL", "investigador@vianova.local")
RESEARCHER_PASSWORD = os.getenv("VIANOVA_RESEARCHER_PASSWORD", "Investigador2026!")
SYSADMIN_EMAIL = os.getenv("VIANOVA_SYSADMIN_EMAIL", "admin@vianova.local")
SYSADMIN_PASSWORD = os.getenv("VIANOVA_SYSADMIN_PASSWORD", "Admin2026!")

# Versión del consentimiento informado vigente
CONSENT_VERSION = os.getenv("VIANOVA_CONSENT_VERSION", "v1.0-2026")

# RAG
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local").lower()        # local | anthropic | openai
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
# Umbral de abstención τ: similitud mínima del fragmento más relevante (calibrar con eval/run_eval.py)
RAG_TAU = float(os.getenv("RAG_TAU", "0.12"))
# Cobertura mínima de palabras de contenido de la consulta en el fragmento recuperado
RAG_MIN_COVERAGE = float(os.getenv("RAG_MIN_COVERAGE", "0.34"))
# Embeddings densos (LSA) y peso del componente denso en el puntaje híbrido
RAG_EMBED_DIM = int(os.getenv("RAG_EMBED_DIM", "64"))
RAG_DENSE_WEIGHT = float(os.getenv("RAG_DENSE_WEIGHT", "0.3"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))

# Motor RAG externo (rag-engine: BGE-M3 + PostgreSQL/pgvector). El backend actúa como intermediario.
RAG_API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8001").rstrip("/")
RAG_API_TIMEOUT = float(os.getenv("RAG_API_TIMEOUT", "15"))
RAG_API_TOP_K = int(os.getenv("RAG_API_TOP_K", "3"))
# Abstención mínima antes de generar: similitud coseno del mejor fragmento (BGE-M3). Calibrado a mano con
# consultas dentro/fuera del corpus NCI (fuera: <= 0.49; dentro: >= 0.52). No es un resultado de evaluación.
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.50"))

# Generación local con Ollama (sin servicios externos)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))

# Recomendador: pesos w1..w4 (deben sumar 1)
W_SEM = float(os.getenv("W_SEM", "0.45"))
W_CTX = float(os.getenv("W_CTX", "0.25"))
W_REG = float(os.getenv("W_REG", "0.20"))
W_PREF = float(os.getenv("W_PREF", "0.10"))

# Indicadores: tolerancia para considerar una tarea "a tiempo"
ON_TIME_TOLERANCE_MIN = int(os.getenv("ON_TIME_TOLERANCE_MIN", "60"))

# Zona horaria de Perú
TZ_OFFSET_HOURS = -5


def check_production() -> None:
    """En producción no se aceptan valores por defecto ni datos de demostración."""
    if not IS_PRODUCTION:
        return
    problems = []
    if not os.getenv("VIANOVA_FERNET_KEY"):
        problems.append("VIANOVA_FERNET_KEY")
    if (ADMIN_PASSWORD == "Curador2026!" or RESEARCHER_PASSWORD == "Investigador2026!"
            or SYSADMIN_PASSWORD == "Admin2026!"):
        problems.append("contraseñas iniciales por defecto")
    if DATABASE_URL.startswith("sqlite"):
        problems.append("DATABASE_URL (use PostgreSQL)")
    if problems:
        raise RuntimeError("Configuración de producción incompleta: " + ", ".join(problems))
