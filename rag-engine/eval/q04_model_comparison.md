# Q04 histórica — comparación dense ALIA / Qwen3 / BGE-M3 (corpus v0.1)

Fecha: 2026-11-03. Consulta **exacta, sin modificar**:

```text
signos de infección durante la quimioterapia
```

Misma configuración que el resto de la comparación: 419 fragmentos congelados (manifest `eval/experimentos/corpus_v01_manifest.json`), pgvector exacto con distancia coseno, sin reranker, BM25 ni LLM. Q04 **no** entra en las métricas de las 15 consultas MD01–MD15; es un diagnóstico separado.

Evidencia: `eval/experimentos/resultados_{alia,qwen3,bge-m3}_v01.json` (Top-10), `eval/experimentos/Q04_{alia,qwen3,bge-m3}_v01.json` (ranking completo de 419 posiciones generado por `scripts/diagnose_q04.py`, que verifica que el Top-10 repetido coincide con el persistido) y `eval/resultados/model_comparison_v01/judgments.json`.

## Dos métricas distintas

- **A. `rank_primer_fragmento_pertinente`**: primer fragmento del Top-10 juzgado pertinente (incluye juicios *parciales*). Todos los juicios de Q04 son `asistido_preliminar`: no existe juicio humano para Q04 sobre este corpus.
- **B. `rank_fragmento_objetivo_historico`**: posición, sobre el ranking completo de 419, del fragmento concreto `95e107ed-5b94-4ad3-8be6-b9af4bb40946` («Además de la fiebre, otras señales de infección son:», Quimioterapia p. 62). Es la lista explícita que el baseline de un solo documento usaba como referencia.

Se añade una vista intermedia, **A′**: primer fragmento cuyo tema es la infección en sí, es decir, la sección «Infección» de p. 58 o la lista de p. 62. A′ excluye el fragmento de síntomas tipo influenza, que solo es pertinente parcialmente.

| Modelo | A. primer pertinente (parcial incl.) | A′. primer fragmento específico de infección | B. fragmento histórico p. 62 | Similitud de B |
|---|---:|---:|---:|---:|
| ALIA | 1 (influenza, parcial) | 7 (p. 58 Infección) | **54** / 419 | 0.4065 |
| Qwen3 | 1 (influenza, parcial) | 9 (p. 58 Infección) | **22** / 419 | 0.5749 |
| BGE-M3 | 2 (p. 58 Infección, parcial) | 2 (p. 58 Infección) | **5** / 419 | 0.5549 |

Las similitudes no se comparan entre modelos: cada espacio vectorial tiene su propia escala.

Referencia histórica del baseline ALIA de un solo documento (`baseline_alia_450_75_cleaned.md`): la sección Infección quedaba en la posición 7 y la lista p. 62 en la 47. En el corpus v0.1 de tres documentos ALIA mantiene la sección Infección en la posición 7 y la lista baja a la 54. Los dos documentos nuevos desplazan la lista pero no cambian el patrón.

## Top-10 completo

Doc: Q = Quimioterapia, A = Alimentación, R = Radioterapia. Juicio: tipo `asistido_preliminar` en todas las filas.

### ALIA

| Rank | Doc | Pág. | Sección | Pertinente | Motivo |
|---:|---|---:|---|---|---|
| 1 | Q | 69 | Síntomas como los de influenza | Sí (parcial) | Síntomas tipo influenza que el texto atribuye también a posible infección; no es la lista específica. |
| 2 | Q | 5 | Preguntas y respuestas sobre la quimioterapia | No | Definición de quimioterapia. |
| 3 | Q | 19 | ¿Qué se puede hacer acerca de los efectos secundarios? | No | Orientación genérica. |
| 4 | Q | 18 | ¿Tendré efectos secundarios por la quimioterapia? | No | Probabilidad de efectos secundarios. |
| 5 | Q | 9 | ¿Cómo me sentiré durante la quimioterapia? | No | Sensaciones generales. |
| 6 | Q | 14 | Sobre el tratamiento con quimioterapia | No | Cuestionario sin respuestas. |
| 7 | Q | 58 | Infección | Sí (parcial) | Fiebre en neutropenia y aviso al equipo; sin la lista de otros signos. |
| 8 | Q | 18 | Los efectos secundarios | No | Lista general. |
| 9 | Q | 14 | Sobre los efectos secundarios | No | Cuestionario sin respuestas. |
| 10 | Q | 31 | Cambios en la boca y garganta | No | Daño oral general. |

### Qwen3

| Rank | Doc | Pág. | Sección | Pertinente | Motivo |
|---:|---|---:|---|---|---|
| 1 | Q | 69 | Síntomas como los de influenza | Sí (parcial) | Igual que en ALIA. |
| 2 | Q | 29 | Cambios en el sistema nervioso | No | Otro efecto. |
| 3 | Q | 42 | Cambios urinarios, en los riñones o en la vejiga | No | Fiebre/escalofríos como síntomas urinarios, no como signos de infección. |
| 4 | Q | 15 | Su estado de ánimo durante la quimioterapia | No | Estado de ánimo. |
| 5 | A | 48 | Quimioterapia | No | Lista de problemas de alimentación. |
| 6 | Q | 35 | Los cambios menores en la piel incluyen: | No | Piel/alergia. |
| 7 | Q | 44 | Cansancio | No | Define cansancio. |
| 8 | R | 13 | Después de haber terminado la radioterapia, ¿en qué síntomas me deberé fijar? | No | Otro tratamiento y otra etapa. |
| 9 | Q | 58 | Infección | Sí (parcial) | Fiebre en neutropenia. |
| 10 | Q | 68 | Otros efectos secundarios | No | Ojos. |

### BGE-M3 (dense)

| Rank | Doc | Pág. | Sección | Pertinente | Motivo |
|---:|---|---:|---|---|---|
| 1 | Q | 29 | Cambios en el sistema nervioso | No | Otro efecto. |
| 2 | Q | 58 | Infección | Sí (parcial) | Fiebre en neutropenia y aviso al equipo. |
| 3 | Q | 69 | Síntomas como los de influenza | Sí (parcial) | Síntomas tipo influenza. |
| 4 | Q | 58 | Qué hacer para controlar la infección: | No [límite] | Prevención (lavado de manos, evitar enfermos); no enumera signos. |
| 5 | Q | 62 | Además de la fiebre, otras señales de infección son: | **Sí** | Fragmento histórico objetivo: lista explícita de señales. |
| 6 | Q | 6 | Seguridad en casa después de recibir tratamientos de quimioterapia | No | Fluidos corporales. |
| 7 | Q | 42 | Cambios urinarios, en los riñones o en la vejiga | No | Síntomas urinarios. |
| 8 | Q | 35 | Los cambios menores en la piel incluyen: | No | Piel. |
| 9 | Q | 35 | Cambios en la piel y las uñas | No | Piel. |
| 10 | A | 48 | Quimioterapia | No | Lista de alimentación. |

## Lectura

- Con la consulta original sin cambios, **BGE-M3 es el único modelo que sube la lista explícita de signos de infección (p. 62) al Top-5**: queda en la posición 5, frente a la 22 de Qwen3 y la 54 de ALIA. También es el que antes recupera la sección Infección (posición 2).
- ALIA y Qwen3 ponen primero el fragmento de síntomas tipo influenza, que es pertinente solo parcialmente. Debajo aparecen definiciones, cuestionarios sin respuesta y otros efectos secundarios.
- Por eso la métrica A (1 / 1 / 2) es **engañosa** si se lee sola. Las vistas A′ (7 / 9 / 2) y B (54 / 22 / 5) describen mejor el problema histórico.
- Solo se midió. No se aplicó reranking, expansión de consulta ni boost por sección.
