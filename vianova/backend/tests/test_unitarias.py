"""Pruebas unitarias: funciones puras y módulos aislados (sin servidor HTTP)."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.nlp import extract
from app.rag.safety import check_scope, is_urgent
from app.rag.text import normalize, tokens, expand_query, coverage, sentences
from app.rag.corpus import parse_markdown, split_sections
from app.rag.generator import extractive
from app.schedule import occurrences
from app.security import hash_password, verify_password, encrypt, decrypt
from app.timeutil import parse, iso

pytestmark = pytest.mark.unitaria


# ---------------------------------------------------------------- procesamiento de lenguaje (registro por voz/texto)
@pytest.mark.parametrize("texto,campo,esperado", [
    ("anoche tuvo fiebre de 38,7 grados", "value", 38.7),
    ("anoche tuvo fiebre de 38,7 grados", "symptom", "fiebre"),
    ("anoche tuvo fiebre de 38,7 grados", "moment", "anoche"),
    ("vomitó tres veces en la mañana", "frequency", 3),
    ("vomitó tres veces en la mañana", "symptom", "vomito"),
    ("el dolor está en 7 de 10", "intensity", 7),
    ("tiene un dolor muy fuerte", "intensity", 8),
    ("está muy cansado hoy", "symptom", "fatiga"),
    ("tiene 39 de temperatura", "value", 39.0),
])
def test_extraccion_entidades(texto, campo, esperado):
    assert extract(texto)[campo] == esperado


def test_extraccion_texto_sin_sintoma_es_observacion():
    assert extract("hoy almorzó con la familia")["kind"] == "observacion"


def test_extraccion_temperatura_fuera_de_rango_se_ignora():
    assert extract("tiene 55 grados")["value"] is None


# ---------------------------------------------------------------- normalización y cobertura
def test_normalizar_quita_tildes_y_mayusculas():
    assert normalize("Náuseas  QUIMIO!") == "nauseas quimio"


def test_expansion_de_sinonimos_coloquiales():
    assert "quimioterapia" in expand_query("quimio")


def test_tokens_excluyen_palabras_vacias():
    assert "de" not in tokens("dolor de cabeza")


def test_cobertura_completa_y_nula():
    assert coverage("llagas boca", "Las llagas en la boca se alivian con...") == 1.0
    assert coverage("capital australia", "Las llagas en la boca") == 0.0


def test_division_en_oraciones_descarta_fragmentos_cortos():
    out = sentences("Ofrezca líquidos con frecuencia. Evite comidas muy condimentadas. Bien.")
    assert len(out) == 2                      # los fragmentos de 15 caracteres o menos no se usan como respuesta


# ---------------------------------------------------------------- reglas de alcance y urgencia (seguridad del contenido)
@pytest.mark.parametrize("consulta,motivo", [
    ("qué dosis de morfina le doy", "dosis"),
    ("puedo suspender la quimio", "cambio de tratamiento"),
    ("¿tendrá metástasis?", "diagnóstico"),
    ("qué significa el resultado de su hemograma", "interpretación de exámenes"),
])
def test_alcance_rechaza_consultas_clinicas(consulta, motivo):
    assert check_scope(consulta) == motivo


@pytest.mark.parametrize("consulta", ["tiene llagas en la boca", "cómo prevenir caídas en casa", "me siento agotada"])
def test_alcance_acepta_consultas_de_cuidado(consulta):
    assert check_scope(consulta) is None


@pytest.mark.parametrize("consulta", ["no puede respirar", "tuvo una convulsión", "vomitó sangre"])
def test_deteccion_de_urgencias(consulta):
    assert is_urgent(consulta)


# ---------------------------------------------------------------- corpus
def test_parse_markdown_lee_metadatos():
    meta, body = parse_markdown("---\nid: X-1\ntitle: Título\n---\n# Sección\nTexto.")
    assert meta["id"] == "X-1" and "Texto" in body


def test_split_sections_por_encabezado():
    secs = split_sections("## Uno\nTexto uno.\n\n## Dos\nTexto dos.")
    assert [s for s, _ in secs][:2] == ["Uno", "Dos"]


def test_generador_extractivo_cita_el_fragmento():
    hits = [SimpleNamespace(text="Ofrezca comidas pequeñas y frecuentes. Evite los olores fuertes al cocinar.",
                            section="Medidas", score=0.4, doc_id="D-1")]
    text, used = extractive("qué comer con náuseas", hits)
    assert used == [0] and "comidas pequeñas" in text


# ---------------------------------------------------------------- agenda / recurrencias
def _task(**kw):
    base = dict(recurrence="diaria", every_hours=None, end_date=None, start_at=datetime(2026, 10, 1, 8, 0))
    base.update(kw)
    return SimpleNamespace(**base)


def test_recurrencia_diaria():
    occ = occurrences(_task(), datetime(2026, 10, 5), datetime(2026, 10, 7, 23, 59))
    assert [o.day for o in occ] == [5, 6, 7] and all(o.hour == 8 for o in occ)


def test_recurrencia_cada_8_horas():
    occ = occurrences(_task(recurrence="cada_n_horas", every_hours=8), datetime(2026, 10, 2), datetime(2026, 10, 2, 23, 59))
    assert [o.hour for o in occ] == [0, 8, 16]


def test_recurrencia_respeta_fecha_fin():
    occ = occurrences(_task(end_date=datetime(2026, 10, 3, 23, 0)), datetime(2026, 10, 1), datetime(2026, 10, 10))
    assert len(occ) == 3


def test_tarea_unica_fuera_de_rango():
    assert occurrences(_task(recurrence="unica"), datetime(2026, 10, 2), datetime(2026, 10, 3)) == []


# ---------------------------------------------------------------- seguridad (funciones)
def test_hash_bcrypt_con_sal():
    h1, h2 = hash_password("Secreta123"), hash_password("Secreta123")
    assert h1 != h2 and h1.startswith("$2") and verify_password("Secreta123", h1) and not verify_password("otra", h1)


def test_cifrado_reversible_y_no_legible():
    tok = encrypt("dato sensible")
    assert "sensible" not in tok and decrypt(tok) == "dato sensible"


def test_fecha_iso_con_zona_peru():
    assert iso(parse("2026-10-16T08:00:00")).endswith("-05:00")


# ---------------------------------------------------------------- ambientes y respaldos (política de seguridad de la información)
def test_ambiente_de_pruebas_activo():
    from app import config
    assert config.APP_ENV == "pruebas" and not config.IS_PRODUCTION


def test_respaldo_rechaza_disco_externo():
    import backup
    with pytest.raises(backup.DestinoNoPermitido):
        backup.validar_destino("/media/usb/respaldos")
    with pytest.raises(backup.DestinoNoPermitido):
        backup.validar_destino("/run/media/usuario/DISCO/respaldos")
    assert backup.validar_destino("s3://bucket-institucional/vianova") == "nube"


def test_respaldo_cifrado_y_atado_al_ambiente(tmp_path, monkeypatch):
    import backup
    monkeypatch.setenv("VIANOVA_BACKUP_DEST", str(tmp_path))
    name = backup.crear()
    f = tmp_path / name.name
    assert f.exists() and b"SQLite" not in f.read_bytes()          # contenido cifrado
    assert name.name.startswith("vianova-pruebas-")


# ---------------------------------------------------------------- instrumento de pruebas de usuario (cálculo SUS)
def test_calculo_sus():
    import importlib.util, pathlib
    p = pathlib.Path(__file__).resolve().parents[2] / "pruebas" / "usuarios" / "analizar_usuarios.py"
    spec = importlib.util.spec_from_file_location("analizar_usuarios", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    mejor = {"participante": "X", **{f"i{i}": (5 if i % 2 else 1) for i in range(1, 11)}}
    neutro = {"participante": "Y", **{f"i{i}": 3 for i in range(1, 11)}}
    assert m.sus_score(mejor) == 100 and m.sus_score(neutro) == 50
    assert m.adjective(70) == "aceptable"
