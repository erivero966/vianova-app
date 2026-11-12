# Fase 4A.1 — archivos para copiar al repositorio

Copiar el contenido de esta carpeta sobre la raíz de `rag-engine`.

Archivos principales:

- `eval/revision_humana_model_comparison_v01.xlsx`: versión completada por el evaluador.
- `scripts/apply_human_review.py`: valida la planilla y recalcula métricas.
- `eval/resultados/model_comparison_v01/judgments_human_reviewed.json`.
- `eval/resultados/model_comparison_v01/metrics_human_reviewed.json`.
- `eval/model_comparison_v01_human_reviewed.md`.
- `eval/q04_model_comparison_human_reviewed.md`.
- `tests/test_apply_human_review.py`.

Para reproducir en el repositorio:

```bash
python scripts/apply_human_review.py
pytest -q tests/test_apply_human_review.py
```

El script solo lee resultados/planilla y escribe artefactos de evaluación. No genera embeddings, no ejecuta retrieval y no modifica PostgreSQL.
