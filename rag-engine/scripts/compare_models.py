#!/usr/bin/env python3
"""Comparación dense sobre fragmentos persistidos y congelados; nunca ingiere PDFs."""

import argparse
from dataclasses import asdict
import importlib.metadata
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import torch
from psycopg.types.json import Jsonb
from psycopg import sql
from sentence_transformers import SentenceTransformer

from src.database import connect, ModelConfigRepository, VectorRepository
from src.embeddings import EmbeddingService
from src.experiments import (MODEL_TABLES, file_hash, freeze, verify, verify_coverage, search_selected)

OUT = ROOT / "eval/experimentos"


def sync():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def load(alias, revision, batch_size):
    captured = {}
    def loader(model_id, device):
        model = SentenceTransformer(model_id, device=device, revision=revision,
                                    local_files_only=True, model_kwargs={"dtype": torch.float32})
        captured["model"] = model
        return model
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    sync()
    start = time.perf_counter()
    service = EmbeddingService(alias, device="cuda", batch_size=batch_size, model_loader=loader)
    sync()
    elapsed = time.perf_counter() - start
    model = captured["model"]
    prompt = model.prompts.get("query", "") if alias != "bge-m3" else ""
    if alias in ("alia", "qwen3") and "query" not in model.prompts:
        raise ValueError("Falta el prompt query publicado por el modelo.")
    if model.default_prompt_name is not None:
        raise ValueError("Se esperaba que los documentos no tuvieran prompt implícito.")
    meta = {"nombre": alias, "model_id": service.model_name, "revision": revision,
            "dimension": service.dimension, "normalizado": True, "query_prompt": prompt,
            "document_prompt": "", "device": service.device, "dtype": str(model.dtype),
            "batch_size": batch_size, "max_seq_length": service.max_seq_length,
            "padding_side": service.tokenizer.padding_side,
            "tiempo_carga_s": elapsed, "representacion": "dense",
            "gpu": torch.cuda.get_device_name() if service.device == "cuda" else None,
            "vram_total_bytes": torch.cuda.get_device_properties(0).total_memory if service.device == "cuda" else 0,
            "software": {name: importlib.metadata.version(name) for name in
                         ("torch", "sentence-transformers", "transformers", "numpy", "psycopg", "pgvector")}}
    return service, meta


def ensure_vectors(vectors, count, dimension):
    if vectors.shape != (count, dimension) or not np.isfinite(vectors).all():
        raise ValueError("Dimensión/cantidad/valores del modelo inválidos.")
    if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
        raise ValueError("Embeddings no normalizados.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=MODEL_TABLES)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    alias = args.model
    target = OUT / (f"probe_{alias}.json" if args.probe else f"resultados_{alias}_v01.json")
    if target.exists():
        parser.error(f"Ya existe {target}; no sobrescribir el experimento.")
    with connect() as conn:
        manifest = freeze(conn, OUT / "corpus_v01_manifest.json")
    rev = json.loads((OUT / "model_revisions_v01.json").read_text())[alias]["revision"]
    service, meta = load(alias, rev, args.batch_size)
    chunks = manifest["chunks"]
    probe_doc = service.encode_documents([chunks[0]["texto"]])
    probe_query = service.encode_query(manifest["consultas"][0]["texto"])
    ensure_vectors(probe_doc, 1, service.dimension)
    ensure_vectors(probe_query[None, :], 1, service.dimension)
    meta["dimension_observada_documento"] = int(probe_doc.shape[1])
    meta["dimension_observada_query"] = int(probe_query.shape[0])
    print(json.dumps(meta, ensure_ascii=False), flush=True)
    if args.probe:
        target.write_text(json.dumps(meta, ensure_ascii=False, indent=2)+"\n")
        return

    # Detect truncation instead of silently changing the dataset for a tokenizer.
    texts = [c["texto"] for c in chunks]
    queries = manifest["consultas"] + [manifest["Q04"]]
    lengths = [len(service.tokenizer(t, truncation=False)["input_ids"]) for t in texts]
    q_lengths = [len(service.tokenizer(meta["query_prompt"] + q["texto"], truncation=False)["input_ids"])
                 for q in queries]
    if max(lengths + q_lengths) > service.max_seq_length:
        raise ValueError("Se truncaría algún texto; no ejecutar comparación sobre textos diferentes.")
    meta.update(tokens_documento_max=max(lengths), tokens_query_max=max(q_lengths), textos_truncados=0)
    sync()
    start = time.perf_counter()
    vectors = service.encode_documents(texts)
    sync()
    meta["tiempo_embeddings_s"] = time.perf_counter() - start
    meta["embeddings_por_segundo"] = len(texts) / meta["tiempo_embeddings_s"]
    ensure_vectors(vectors, len(chunks), service.dimension)
    print(f"{alias}: {len(vectors)} embeddings generados", flush=True)
    meta["vram_pico_embeddings_allocated_bytes"] = torch.cuda.max_memory_allocated() if service.device == "cuda" else 0
    meta["vram_pico_embeddings_reserved_bytes"] = torch.cuda.max_memory_reserved() if service.device == "cuda" else 0
    table = MODEL_TABLES[alias]
    with connect() as conn:
        verify(conn, manifest)
        # Protect the frozen dataset during the transaction which publishes vectors.
        conn.execute("LOCK TABLE documento, version_documento, fragmento, ingesta IN SHARE MODE")
        old = conn.execute("SELECT model_id,dimension FROM configuracion_modelo WHERE nombre=%s", (alias,)).fetchone()
        if old and old != (service.model_name, service.dimension):
            raise ValueError("La configuración existente no corresponde al modelo ejecutado.")
        params = {**meta, "tabla_embeddings": table, "metrica": "cosine",
                  "manifest_sha256": file_hash(OUT / "corpus_v01_manifest.json"),
                  "chunks_ids_sha256": manifest["chunks_ids_sha256"]}
        conn.execute("""INSERT INTO configuracion_modelo(nombre,model_id,dimension,normalizado,activo,parametros)
                     VALUES (%s,%s,%s,true,true,%s) ON CONFLICT(nombre) DO UPDATE
                     SET parametros=configuracion_modelo.parametros || EXCLUDED.parametros""",
                     (alias, service.model_name, service.dimension, Jsonb(params)))
        repo = VectorRepository(conn, ModelConfigRepository(conn).get_active(alias))
        start = time.perf_counter()
        if alias == "alia":
            # Preserve the baseline vectors, while timing the same 419 encodings and checking identity.
            previous = np.stack([repo.get_embedding(c["id"]) for c in chunks])
            meta["alia_diferencia_max_abs"] = float(np.max(np.abs(previous-vectors)))
            if not np.allclose(previous, vectors, atol=2e-5, rtol=1e-4):
                raise ValueError("ALIA reproducida difiere del baseline; no atribuirlo al modelo.")
            meta["persistencia"] = "419 existentes verificados, no sobrescritos; se conservan los demás embeddings históricos"
        else:
            if repo.count_embeddings():
                raise ValueError("La tabla/configuración ya contiene embeddings; no sobrescribir.")
            for chunk, vector in zip(chunks, vectors):
                repo.save_embedding(chunk["id"], vector)
            meta["persistencia"] = "419 nuevos embeddings; ningún fragmento creado/modificado"
        meta["tiempo_guardado_o_verificacion_s"] = time.perf_counter()-start
        ids = verify_coverage(conn, repo, manifest)
        meta["embeddings_elegibles"] = len(ids)
        # Store complete measured settings as well as model/revision and prompt.
        conn.execute("UPDATE configuracion_modelo SET parametros=parametros || %s WHERE id=%s",
                     (Jsonb(meta), repo.config.id))

    results = []
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        verify(conn, manifest)
        repo = VectorRepository(conn, ModelConfigRepository(conn).get_active(alias))
        verify_coverage(conn, repo, manifest)
        ann = conn.execute("SELECT indexdef FROM pg_indexes WHERE tablename=%s", (table,)).fetchall()
        if any("hnsw" in r[0].lower() or "ivfflat" in r[0].lower() for r in ann):
            raise ValueError("Hay índice ANN; no es la comparación exacta acordada.")
        for q in queries:
            sync()
            start = time.perf_counter()
            hits = search_selected(service, repo, q["texto"], 10)
            sync()
            seconds = time.perf_counter()-start
            if len(hits) != 10 or any(str(h.fragmento_id) not in ids for h in hits):
                raise ValueError("Resultados fuera del conjunto congelado.")
            results.append({**q, "tiempo_s": seconds,
                            "top_k_ids": {str(k): [str(h.fragmento_id) for h in hits[:k]] for k in (1,3,5,10)},
                            "resultados": [{"posicion": i, **asdict(h), "similitud": h.similitud}
                                           for i,h in enumerate(hits,1)]})
            print(alias,q["id"],hits[0].titulo,hits[0].pagina_inicio,round(hits[0].similitud,6),flush=True)
        plan = repo.explain_search(probe_query, top_k=10)
    meta["tiempo_consultas_15_s"] = sum(q["tiempo_s"] for q in results[:15])
    meta["tiempo_Q04_s"] = results[-1]["tiempo_s"]
    meta["vram_pico_total_allocated_bytes"] = torch.cuda.max_memory_allocated() if service.device=="cuda" else 0
    meta["vram_pico_total_reserved_bytes"] = torch.cuda.max_memory_reserved() if service.device=="cuda" else 0
    target.write_text(json.dumps({"configuracion":meta,
        "manifest_sha256":file_hash(OUT/"corpus_v01_manifest.json"),
        "chunks_ids_sha256":manifest["chunks_ids_sha256"], "ids_fragmentos_evaluados":ids,
        "explain":plan,"consultas":results},ensure_ascii=False,indent=2,default=str)+"\n")
    with connect() as conn:
        verify(conn,manifest)
        conn.execute("UPDATE configuracion_modelo SET parametros=parametros || %s WHERE nombre=%s",(Jsonb(meta),alias))


if __name__ == "__main__":
    main()
