"""Congelación y verificaciones de comparaciones dense, sin tocar el corpus."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from psycopg.rows import dict_row
from psycopg import sql

from .config import PROJECT_ROOT
from .database.indexing import ensure_encoder_matches


MODEL_TABLES = {"alia": "embedding_fragmento_alia", "qwen3": "embedding_fragmento_qwen3",
                "bge-m3": "embedding_fragmento_bge_m3"}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), default=str).encode()).hexdigest()


def file_hash(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def corpus_state(conn) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM documento ORDER BY id")
        docs = cur.fetchall()
        cur.execute("SELECT * FROM version_documento ORDER BY id")
        versions = cur.fetchall()
        cur.execute("SELECT * FROM fragmento ORDER BY id")
        fragments = cur.fetchall()
        cur.execute("SELECT * FROM ingesta ORDER BY id")
        ingests = cur.fetchall()
    # Uniform representation also when reloaded from JSON.
    return json.loads(json.dumps(dict(documentos=docs, versiones=versions,
                                     fragmentos=fragments, ingestas=ingests), default=str))


def freeze(conn, path: Path) -> dict:
    if path.exists():
        result = json.loads(path.read_text())
        verify(conn, result)
        return result
    state = corpus_state(conn)
    active = [v for v in state["versiones"] if v["estado"] == "activa"]
    active_ids = {v["id"] for v in active}
    chunks = [f for f in state["fragmentos"] if f["version_id"] in active_ids
              and f["tipo_contenido"] == "contenido"]
    if len(active) != 3 or len(chunks) != 419:
        raise ValueError("Se esperaba el corpus v01: tres versiones activas y 419 fragmentos.")
    for v in active:
        if file_hash(PROJECT_ROOT / v["ruta_archivo"]) != v["hash_archivo"]:
            raise ValueError("El PDF no coincide con la versión persistida.")
        ing = max((i for i in state["ingestas"] if i["version_id"] == v["id"]),
                  key=lambda i: i["creado_en"])
        if (ing["parametros"]["chunk_size_tokens"], ing["parametros"]["chunk_overlap_tokens"]) != (450, 75):
            raise ValueError("Configuración de chunks incompatible.")
    query_path = PROJECT_ROOT / "eval/consultas_multidocumento_v01.json"
    historical = PROJECT_ROOT / "eval/consultas_baseline.json"
    q04 = next(q for q in json.loads(historical.read_text())["consultas"] if q["id"] == "Q04")
    if q04["texto"] != "signos de infección durante la quimioterapia":
        raise ValueError("Q04 histórico cambió.")
    protected = list((PROJECT_ROOT / "corpus").rglob("*.pdf"))
    protected += list((PROJECT_ROOT / "corpus").rglob("*.json"))
    protected += [p for p in (PROJECT_ROOT / "eval").rglob("*") if p.is_file()
                  and "experimentos" not in p.parts]
    protected += list((PROJECT_ROOT / "sql").glob("*.sql"))
    result = {"experimento": "corpus_v01_dense_models", "fecha_utc": datetime.now(timezone.utc).isoformat(),
              "corpus_state_sha256": digest(state), "documentos": state["documentos"],
              "versiones_activas": active, "chunk_size": 450, "overlap": 75,
              "chunks": [{**c, "texto_sha256": hashlib.sha256(c["texto"].encode()).hexdigest(),
                          "registro_sha256": digest(c)} for c in chunks],
              "chunks_ids_sha256": digest([c["id"] for c in chunks]),
              "consultas": json.loads(query_path.read_text())["consultas"], "Q04": q04,
              "retrieval": {"tipo": "pgvector exacto", "distancia": "coseno <=>",
                            "top_k": [1, 3, 5, 10], "filtros": ["version.estado=activa", "fragmento.tipo_contenido=contenido"]},
              "archivos_protegidos": {str(p.relative_to(PROJECT_ROOT)): file_hash(p) for p in protected}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    return result


def verify(conn, manifest: dict) -> None:
    if digest(corpus_state(conn)) != manifest["corpus_state_sha256"]:
        raise ValueError("El corpus/documentos/versiones/chunks/ingestas cambió desde la congelación.")
    for path, expected in manifest["archivos_protegidos"].items():
        if file_hash(PROJECT_ROOT / path) != expected:
            raise ValueError(f"Cambió un archivo congelado: {path}")


def verify_coverage(conn, repository, manifest: dict) -> list[str]:
    rows = conn.execute(sql.SQL("""SELECT f.id::text FROM {} e
        JOIN fragmento f ON f.id=e.fragmento_id
        JOIN version_documento v ON v.id=f.version_id
        WHERE e.configuracion_id=%s AND v.estado='activa' AND f.tipo_contenido='contenido'
        ORDER BY f.id""").format(sql.Identifier(repository.table_name)), (repository.config.id,)).fetchall()
    ids = [r[0] for r in rows]
    if ids != [c["id"] for c in manifest["chunks"]]:
        raise ValueError("El conjunto de fragmentos embebidos no coincide con el manifest.")
    return ids


def search_selected(service, repository, text: str, top_k: int = 10):
    ensure_encoder_matches(service, repository.config)
    return repository.search_similar(service.encode_query(text), top_k=top_k)


def metrics(first_ranks: list[int | None]) -> dict:
    if not first_ranks:
        raise ValueError("No hay consultas evaluadas.")
    if any(r is not None and not 1 <= r <= 10 for r in first_ranks):
        raise ValueError("La evaluación está truncada a Top-10.")
    return {**{f"Hit@{k}": sum(r is not None and r <= k for r in first_ranks)/len(first_ranks)
               for k in (1, 3, 5, 10)},
            "MRR@10": sum(1/r if r else 0 for r in first_ranks)/len(first_ranks)}


JUDGMENT_TYPES = ("humano", "asistido_preliminar")


def judgment_index(human: list[dict], assisted: list[dict]) -> dict[tuple[str, str], dict]:
    """(consulta_id, fragmento_id) -> juicio; un juicio humano nunca se reemplaza."""
    index = {}
    for kind, items in (("humano", human), ("asistido_preliminar", assisted)):
        for item in items:
            key = (item["consulta_id"], item["fragmento_id"])
            if key in index:
                previous = index[key]
                if previous["tipo_juicio"] == "humano" and kind == "asistido_preliminar":
                    raise ValueError(f"Juicio asistido sobre un par con juicio humano: {key}")
                if previous["pertinente"] != item["pertinente"]:
                    raise ValueError(f"Juicios contradictorios para {key}")
                continue
            index[key] = {**item, "tipo_juicio": kind}
    return index


def judge_ranking(query_id: str, fragment_ids: list[str], index: dict) -> list[dict]:
    missing = [f for f in fragment_ids if (query_id, f) not in index]
    if missing:
        raise ValueError(f"{query_id}: faltan juicios para {missing}")
    return [index[(query_id, f)] for f in fragment_ids]


def first_relevant(judgments: list[dict], kinds=JUDGMENT_TYPES) -> int | None:
    """Rango (1-based) del primer pertinente considerando solo `kinds`."""
    return next((i for i, j in enumerate(judgments, 1)
                 if j["pertinente"] and j["tipo_juicio"] in kinds), None)
