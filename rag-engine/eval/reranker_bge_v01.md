# Fase 4B — Reranking BGE-M3 Top-10 con bge-reranker-v2-m3 (v0.1)

Fecha: 2026-11-12T19:14:47.037511+00:00

Experimento **offline**: se reordenan exactamente los 10 candidatos congelados de BGE-M3 (comparación 4A, `eval/resultados/model_comparison_v01/bge_m3.json`, SHA-256 verificado) y se evalúan con los juicios humanos consolidados en 4A.1 (sin juicios nuevos ni automáticos). No se modificó corpus, embeddings, PostgreSQL ni el prototipo.

- Modelo: `BAAI/bge-reranker-v2-m3` revisión `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` (568 M parámetros, cross-encoder).
- Configuración: `max_length=1024`, dtype float32, device cuda, pares truncados: 0 (par más largo: 500 tokens). Empates: rank original.
- Reglas: Humano original Sí=pertinente/No=no; revisión 4A.1 solo grado 2=pertinente. / Humano original Sí=pertinente/No=no; revisión 4A.1 grados 1 o 2=pertinente.
- Métricas sobre MD01-MD15; Q04 se analiza aparte (igual que 4A.1).

## Métricas — criterio estricto

| Métrica | BGE-M3 baseline | BGE-M3 + reranker | Diferencia |
|---|---:|---:|---:|
| Hit@1 strict | 9/15 | 8/15 | -1 |
| Hit@3 strict | 12/15 | 13/15 | +1 |
| Hit@5 strict | 15/15 | 15/15 | +0 |
| Hit@10 strict | 15/15 | 15/15 | +0 |
| MRR strict | 0.729 | 0.722 | -0.007 |

## Métricas — criterio laxo

| Métrica | BGE-M3 baseline | BGE-M3 + reranker | Diferencia |
|---|---:|---:|---:|
| Hit@1 lenient | 11/15 | 10/15 | -1 |
| Hit@3 lenient | 15/15 | 14/15 | -1 |
| Hit@5 lenient | 15/15 | 15/15 | +0 |
| Hit@10 lenient | 15/15 | 15/15 | +0 |
| MRR lenient | 0.844 | 0.806 | -0.039 |

## Primer fragmento pertinente por consulta

| Consulta | Estricto antes | Estricto después | Cambio | Laxo antes | Laxo después | Cambio |
|---|---:|---:|---|---:|---:|---|
| MD01 | 1 | 1 | igual | 1 | 1 | igual |
| MD02 | 1 | 2 | empeoró | 1 | 1 | igual |
| MD03 | 1 | 2 | empeoró | 1 | 2 | empeoró |
| MD04 | 3 | 4 | empeoró | 3 | 4 | empeoró |
| MD05 | 5 | 3 | mejoró | 2 | 1 | mejoró |
| MD06 | 2 | 1 | mejoró | 1 | 1 | igual |
| MD07 | 2 | 4 | empeoró | 2 | 3 | empeoró |
| MD08 | 1 | 1 | igual | 1 | 1 | igual |
| MD09 | 1 | 1 | igual | 1 | 1 | igual |
| MD10 | 5 | 2 | mejoró | 3 | 2 | mejoró |
| MD11 | 5 | 1 | mejoró | 1 | 1 | igual |
| MD12 | 1 | 1 | igual | 1 | 1 | igual |
| MD13 | 1 | 2 | empeoró | 1 | 2 | empeoró |
| MD14 | 1 | 1 | igual | 1 | 1 | igual |
| MD15 | 1 | 1 | igual | 1 | 1 | igual |

## Q04 — signos de infección durante la quimioterapia

| | Primer pertinente estricto | Primer pertinente laxo | Primer específico de infección | Fragmento histórico p. 62 |
|---|---:|---:|---:|---:|
| BGE-M3 | 2 | 2 | 2 | 5 |
| + reranker | 1 | 1 | 1 | 9 |

Top-10 Q04 reordenado:

| Rank | Rank BGE-M3 | Score reranker | Grado | Específico | Documento · p. | Sección |
|---:|---:|---:|---:|:-:|---|---|
| 1 | 2 | 0.984 | 2 | S | La quimioterapia y usted: Ap · 58 | Infección |
| 2 | 3 | 0.978 | 0 | N | La quimioterapia y usted: Ap · 69 | Síntomas como los de influenza |
| 3 | 4 | 0.908 | 0 | S | La quimioterapia y usted: Ap · 58 | Qué hacer para controlar la infección: |
| 4 | 8 | 0.581 | 0 | N | La quimioterapia y usted: Ap · 35 | Los cambios menores en la piel incluyen: |
| 5 | 1 | 0.563 | 0 | N | La quimioterapia y usted: Ap · 29 | Cambios en el sistema nervioso |
| 6 | 7 | 0.401 | 0 | N | La quimioterapia y usted: Ap · 42 | Cambios urinarios, en los riñones o en la vejiga |
| 7 | 10 | 0.249 | 0 | N | Consejos de alimentación: an · 48 | Quimioterapia |
| 8 | 6 | 0.160 | 0 | N | La quimioterapia y usted: Ap · 6 | Seguridad en casa después de recibir tratamientos  |
| 9 | 5 | 0.115 | 2 | S | La quimioterapia y usted: Ap · 62 | Además de la fiebre, otras señales de infección so |
| 10 | 9 | 0.013 | 0 | N | La quimioterapia y usted: Ap · 35 | Cambios en la piel y las uñas |

## MD10 — pérdida de peso

Consulta: «Mi mamá está bajando de peso durante el tratamiento del cáncer. ¿Cómo puedo enriquecer sus comidas para ayudarla a mantener el peso?»

| Rank | Rank BGE-M3 | Score reranker | Grado | Estricto | Sección | Observación humana |
|---:|---:|---:|---:|:-:|---|---|
| 1 | 2 | 0.668 | 0 | No | ¿Qué más puedo hacer? | Habla de AUMENTO de peso y dieta para bajarlo: dirección opuesta a la  |
| 2 | 6 | 0.608 | 2 | Sí | ¿Cómo me alimento si tengo este problema | Responde directamente, horario fijo, comidas pequeñas, agregar proteín |
| 3 | 4 | 0.598 | 1 | No | ¿Deberé seguir una dieta especial mientr | Importancia de calorías y proteínas para mantener el peso, remite a un |
| 4 | 5 | 0.418 | 2 | Sí | Consejos para controlar los problemas de | Contenido sobre mantener/recuperar peso mediante alimentos ricos en ca |
| 5 | 3 | 0.379 | 1 | No | Formas de controlar los cambios de apeti | Opciones médicas ante la pérdida de peso (medicinas para el apetito, I |
| 6 | 9 | 0.347 | 1 | No | Formas de aprovechar al máximo los alime | Comer proteínas y calorías cuando se pueda y batidos de proteína, gene |
| 7 | 7 | 0.185 | 0 | No | Preparación para el tratamiento del cánc | Preparación antes del tratamiento, no aplica |
| 8 | 10 | 0.138 | 2 | Sí | Nota especial para los cuidadores | Nota para cuidadores, frutas y verduras con salsas para sumar calorías |
| 9 | 8 | 0.130 | 0 | No | Formas de controlarla | Consejos para la fatiga, solo un punto general sobre comer, no sobre e |
| 10 | 1 | 0.087 | 0 | No | — | Título suelto |

## Rendimiento

- GPU: NVIDIA GeForce RTX 4060 Laptop GPU; parámetros en ['cuda:0'] (offload: no).
- Carga del modelo: 1.7 s.
- 16 consultas × 10 pares: pasada 1 9.70 s (incluye calentamiento; primera consulta 718 ms), pasada 2 9.67 s; media 604 ms/consulta (máx. 620 ms).
- VRAM del proceso (torch): pico asignado 2393 MiB, reservado 2696 MiB. nvidia-smi total: 2324 → 5142 MiB (incluye otros procesos).
- Reproducibilidad: mismo orden en 2 pasadas: True; diferencia máx. de score 0.00e+00.
- Complementario fp16: media 161 ms/consulta (máx. 172 ms), mismo orden que fp32 en 16/16 consultas (diferencia máx. de score 0.0024); pico VRAM 2174 MiB. Las métricas oficiales son las de fp32.

## Conclusión

**No integrar todavía.** No mejora de forma clara Hit@1 strict ni MRR strict, y degrada otras métricas. Hit@1 strict -1, MRR strict -0.007, MRR laxo -0.039. Por consulta (estricto): 4 mejoran, 5 empeoran, 6 iguales: el reranker reordena mucho, pero sus aciertos y errores se compensan. Coste añadido: ~604 ms/consulta en fp32 (~161 ms en fp16) y ~2,4 GB de VRAM en una GPU de 8 GB ya compartida con BGE-M3 y qwen2.5:7b. Criterio usado: mejora de ≥ 2 consultas en Hit@1 strict o ≥ 0,05 de MRR strict, sin pérdidas en Hit@1/Hit@3 ni caída de MRR laxo > 0,02.

## Limitaciones

- 15 consultas: cada consulta vale 1/15 (6,7 puntos) de Hit@K; las diferencias deben leerse caso por caso.
- El reranker solo puede reordenar los 10 candidatos de BGE-M3 (Hit@10 es un techo fijo, 15/15).
- Juicios humanos únicos del proyecto (sin acuerdo inter-anotador).

