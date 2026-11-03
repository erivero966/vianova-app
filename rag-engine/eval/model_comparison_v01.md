# Comparación preliminar de embeddings dense — corpus v0.1 (Fase 4A)

Fecha: 2026-11-03. Modelos comparados: `SINAI/ALIA-MrBERT-es-biomedical-embeddings`, `Qwen/Qwen3-Embedding-0.6B` y `BAAI/bge-m3` (solo dense).

> **Evaluación preliminar, no gold standard clínico.** De los 480 juicios por posición, 179 son humanos (heredados de la revisión ALIA) y 301 son `asistido_preliminar`. Los resultados describen este corpus de 3 documentos y 15 consultas. **No seleccionan un modelo definitivo para Vianova.**

## 1. Contexto experimental

| Elemento | Valor |
|---|---|
| Documentos activos | 3 NCI digitales: *La quimioterapia y usted* (2019), *Consejos de alimentación* (2024), *La radioterapia y usted* (2016) |
| Chunks persistidos | 428 en total: Quimioterapia 130, Alimentación 167, Radioterapia 131 |
| Chunks evaluados | **419** `tipo_contenido = contenido` de versiones `activa` (los 9 de índice quedan excluidos por el filtro normal) |
| Chunking | 450 tokens, solapamiento 75. Se reutilizan los fragmentos persistidos; no se extrajo, limpió ni segmentó nada de nuevo |
| Consultas | MD01–MD15 de `eval/consultas_multidocumento_v01.json`, sin modificar. Q04 histórica aparte (`eval/q04_model_comparison.md`) |
| Retrieval | pgvector exacto (`<=>`, coseno), Top-10, sin índice ANN (verificado en cada corrida), sin reranker, BM25, búsqueda híbrida ni LLM |
| Hardware | NVIDIA GeForce RTX 4060 Laptop GPU (8 GB) con CUDA. PyTorch 2.14.1, sentence-transformers 6.2.0, transformers 5.20.2, Python 3.13.13 |
| Base de datos | PostgreSQL 16 + pgvector (`pgvector/pgvector:0.8.7-pg16`), una tabla por modelo |

**Mismo dataset para los tres modelos.** Las tres corridas comprueban contra `eval/experimentos/corpus_v01_manifest.json` (SHA-256 `c650d146…7d82`):

- el hash del estado de `documento`, `version_documento`, `fragmento` e `ingesta`;
- el SHA-256 de los PDFs y de los archivos protegidos;
- la lista ordenada de los 419 IDs (`chunks_ids_sha256 = 1a401463…e2a6`).

Cada resultado crudo registra ese hash. La cobertura por ID es la misma en los tres modelos: 419 esperados, 419 presentes, 0 faltantes, 0 sobrantes, 0 duplicados (§9).

## 2. Modelos

| Modelo | Revisión (commit HF) | Dimensión observada | dtype | max_seq_length | Normalización | Query instruction | Document instruction |
|---|---|---:|---|---:|---|---|---|
| ALIA | `95d6c927ac774b120156357dadd665c1e71adf54` | 768 | float32 | 8192 | L2, coseno | prompt `query` del model card = `""` (comportamiento baseline) | ninguna |
| Qwen3 | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | 1024 | float32 | 32768 | L2, coseno | `Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:` (prompt `query` oficial de `config_sentence_transformers.json`, igual para todas las consultas) | ninguna (`document: ""`) |
| BGE-M3 | `5617a9f61b028005a4858fdac845db406aefb181` | 1024 | float32 | 8192 | L2, coseno (módulo Normalize) | ninguna | ninguna |

- Las dimensiones se obtuvieron **ejecutando** cada modelo en GPU (documento y query); no se tomaron de la documentación. Los probes están en `eval/experimentos/probe_*.json`.
- **Qwen3** usa pooling por último token y su tokenizer rellena por la derecha (`padding_side = right`). Para descartar errores de pooling se codificó el mismo texto solo y dentro de un batch con un texto largo: diferencia máxima 3.06e-7.
- **BGE-M3** se usó solo como dense: módulos Transformer → CLS pooling → Normalize de sentence-transformers. Los pesos sparse (`sparse_linear.pt`) y ColBERT (`colbert_linear.pt`) **no se descargaron**, así que no pueden haberse activado.
- Pesos descargados en las revisiones fijadas y verificados: el SHA-256 de `model.safetensors` (Qwen3) y de `pytorch_model.bin` (BGE-M3) coincide con el blob LFS.
- Ningún texto se truncó. Máximo de tokens por documento con el tokenizer de cada modelo: muy por debajo de `max_seq_length` (450 en ALIA); `textos_truncados = 0`, comprobado antes de codificar.

## 3. Rendimiento técnico

Batch 16 para los tres modelos; no hubo que reducirlo. Tiempos medidos con `torch.cuda.synchronize()`.

| Modelo | Embeddings | Carga (s) | Generación (s) | Emb/s | 15 consultas (s) | VRAM pico allocated / reserved |
|---|---:|---:|---:|---:|---:|---:|
| ALIA | 419 (reproducidos y verificados) | 0.43 | 4.68 | 89.5 | 0.147 | 864 / 898 MiB |
| Qwen3 | 419 nuevos | 0.98 | 20.71 | 20.2 | 0.480 | 2756 / 3142 MiB |
| BGE-M3 | 419 nuevos | 1.88 | 10.24 | 40.9 | 0.368 | 2534 / 2724 MiB |

- La carga se midió con los pesos ya en el cache local; no incluye la descarga.
- El tiempo de consultas incluye codificar la query y ejecutar la búsqueda exacta en PostgreSQL.
- **ALIA no se regeneró.** Los 419 vectores se recalcularon solo para medir el tiempo y comprobar que coinciden con los persistidos (diferencia máxima 1.96e-5); no se sobrescribió ninguno.

## 4. Procedencia de juicios

| Tipo | Pares (consulta, fragmento) únicos | Juicios por posición (3 modelos × 16 consultas × Top-10 = 480) |
|---|---:|---:|
| `humano` | 75 | 179 |
| `asistido_preliminar` | 210 (85 heredados + 125 nuevos) | 301 |

- **Unidad de juicio**: el par (consulta, fragmento). Un juicio humano se **reutiliza tal cual** cuando otro modelo recupera el mismo fragmento para la misma consulta. Nunca se crea un juicio asistido sobre un par con juicio humano; `src/experiments.judgment_index` aborta si ocurre. Un juicio no se reutiliza entre consultas distintas.
- **Humanos**: los 75 de la revisión manual ALIA (`eval/resultados/alia_multidocumento_v01_revisado.json`), contrastados con `evaluacion_manual_multidocumento_v01.json`. Se conservan inmutables.
- **Asistidos heredados (85)**: `eval/experimentos/juicios_asistidos_v01.json`, con los ranks 6–10 de ALIA y el Top-10 de Q04.
- **Asistidos nuevos (125)**: `eval/experimentos/juicios_asistidos_v01_qwen3_bge_m3.json`. Se hicieron después del retrieval, leyendo el texto completo de cada fragmento frente a la consulta y con el mismo criterio que la revisión humana. Ese criterio exige aporte práctico o sustantivo y rechaza definiciones, introducciones, cuestionarios sin respuesta, remisiones y la mera coincidencia léxica.
- **Casos límite**: 9 pares asistidos nuevos llevan `[límite]` en el motivo; 4 de ellos son «Sí». Su efecto se mide en §5.3.
- **Anotación descriptiva separada**: `eval/experimentos/anotacion_intro_consejo_v01.json` clasifica el tipo de fragmento del Top-5 (`consejo_practico`, `definicion_causas`, `introduccion_general`, `preguntas_sin_respuesta`, `lista_indice`, `otro_tema`). **No modifica ningún juicio de pertinencia.**
- Artefacto unificado: `eval/resultados/model_comparison_v01/judgments.json`. Cada fila incluye `consulta_id`, `modelo`, `fragmento_id`, `rank`, `pertinente`, `tipo_juicio`, `motivo`, `fuente_juicio`, `fragmento_referencia`, `texto_sha256`, `documento`, `pagina`, `seccion` y `categoria`.

## 5. Retrieval (MD01–MD15)

Una consulta cuenta como acierto en Hit@k si hay al menos un fragmento pertinente en el Top-k. MRR = media de 1/rank del primer pertinente dentro del Top-10, con 0 si no hay ninguno.

### 5.1 Evaluación preliminar completa (humano + `asistido_preliminar`)

| Métrica | ALIA | Qwen3 | BGE-M3 |
|---|---:|---:|---:|
| Hit@1 | 6/15 (0.400) | 10/15 (0.667) | **11/15 (0.733)** |
| Hit@3 | 9/15 (0.600) | 12/15 (0.800) | **13/15 (0.867)** |
| Hit@5 | 13/15 (0.867) | 12/15 (0.800) | **15/15 (1.000)** |
| Hit@10 | 13/15 (0.867) | 13/15 (0.867) | **15/15 (1.000)** |
| MRR@10 | 0.556 | 0.741 | **0.816** |
| Embeddings | 419 | 419 | 419 |
| Dimensión | 768 | 1024 | 1024 |
| Tiempo embeddings | 4.68 s | 20.71 s | 10.24 s |
| VRAM pico (allocated) | 864 MiB | 2756 MiB | 2534 MiB |

ALIA reproduce exactamente su baseline humano previo: Top-1 6/15, Top-3 9/15, Top-5 13/15.

### 5.2 Baseline humano disponible

Para **ALIA**, las cifras de Hit@1/3/5 son 100 % humanas: su Top-5 coincide 15/15 con la revisión manual y cubre 75/75 posiciones. Los ranks 6–10 de ALIA son asistidos, así que su Hit@10 ya no es solo humano.

Para Qwen3 y BGE-M3 solo hay juicio humano en las posiciones donde recuperan los mismos fragmentos que ALIA. El cálculo siguiente cuenta como pertinentes **solo** los positivos humanos y trata lo no juzgado por humanos como no pertinente. Es una **cota inferior**, no una métrica humana completa.

| Métrica (solo positivos humanos) | ALIA | Qwen3 | BGE-M3 |
|---|---:|---:|---:|
| Cobertura humana Top-1 / Top-5 | 15/15 · 75/75 | 10/15 · 35/75 | 9/15 · 37/75 |
| Hit@1 | 6/15 | 7/15 | 7/15 |
| Hit@3 | 9/15 | 10/15 | 11/15 |
| Hit@5 | 13/15 | 12/15 | 13/15 |
| Hit@10 | 13/15 | 13/15 | 13/15 |
| MRR@10 | 0.556 | 0.604 | 0.593 |

Incluso con esta cota inferior, Qwen3 y BGE-M3 empatan o superan a ALIA en Hit@1 y Hit@3.

### 5.3 Sensibilidad a los juicios límite

| Escenario | ALIA H@1/3/5/10 · MRR | Qwen3 | BGE-M3 |
|---|---|---|---|
| Juicios tal como están | 6/9/13/13 · 0.556 | 10/12/12/13 · 0.741 | 11/13/15/15 · 0.816 |
| Estricto (límite «Sí» → «No») | 6/9/13/13 · 0.556 | 10/12/12/13 · 0.741 | 10/13/15/15 · 0.782 |
| Laxo (límite «No» → «Sí») | 6/9/13/13 · 0.556 | 10/12/12/13 · 0.741 | 11/13/15/15 · 0.819 |

Solo cambia el Hit@1 de BGE-M3, por un caso: MD06, rank 1, opciones médicas para el apetito. El orden entre modelos no cambia.

## 6. Resultado por consulta

Rank del primer fragmento pertinente dentro del Top-10 («—» = ninguno). Entre paréntesis, el primero con juicio **humano**, cuando difiere.

| ID | Tema | ALIA | Qwen3 | BGE-M3 |
|---|---|---:|---:|---:|
| MD01 | náuseas | 1 | 1 | 1 |
| MD02 | vómitos | 2 | 1 (2) | 1 |
| MD03 | cansancio (quimio) | 1 | 1 | 1 |
| MD04 | diarrea | 4 | 9 | 3 |
| MD05 | estreñimiento | — | — | 5 (—) |
| MD06 | poco apetito | 3 | 1 (5) | 1 (2) |
| MD07 | dificultad para tragar | — | — | 2 (—) |
| MD08 | alimentación con náuseas | 2 | 1 | 1 |
| MD09 | llagas en la boca | 4 | 2 | 1 (3) |
| MD10 | pérdida de peso | 4 | 2 (4) | 5 |
| MD11 | efectos secundarios (radio) | 4 | 1 (2) | 1 (5) |
| MD12 | cansancio (radio) | 1 | 1 | 1 |
| MD13 | piel (radio) | 1 | 1 | 1 |
| MD14 | alimentación (radio) | 1 | 1 | 1 |
| MD15 | cuidados durante radioterapia | 1 | 1 | 1 |

- Los dos fallos de ALIA en el Top-10 son MD05 y MD07. En ambos el contenido correcto existe en la base (Quimioterapia p. 53–54; Alimentación p. 34–35). BGE-M3 recupera los dos: MD05 en el rank 5 (p. 53–54) y MD07 en el rank 2 (boca dolorida) y el rank 3 (garganta irritada). El apartado específico de deglución de Alimentación p. 34–35 lo recupera en el rank 4. Qwen3 falla las mismas dos consultas que ALIA.
- **Regresión de Qwen3 en MD04**: el primer pertinente baja del rank 4 de ALIA al 9. El Top-5 de Qwen3 lo ocupan definiciones, náuseas y suplementos.
- Las consultas de radioterapia MD12–MD15 están resueltas en el rank 1 por los tres modelos.

## 7. Casos especiales

### 7.1 Pérdida de peso (MD10)

> «Mi mamá está bajando de peso durante el tratamiento del cáncer. ¿Cómo puedo enriquecer sus comidas para ayudarla a mantener el peso?»

Intención: **evitar más pérdida de peso** enriqueciendo comidas con calorías y proteínas. El fragmento de Alimentación p. 42 («¿Qué más puedo hacer?», sobre **aumento** de peso y cómo limitarlo) va en la dirección semántica opuesta: comparte «peso», pero contradice la necesidad.

**ALIA**

| Rank | Doc · pág. | Sección | Pertinente | Tipo de contenido | Juicio |
|---:|---|---|---|---|---|
| 1 | A p. 3 | Acerca de esta publicación | No | introducción | humano |
| 2 | A p. 43 | ¿Por qué pasa? | No | causas de la pérdida de peso | humano |
| 3 | A p. 42 | ¿Qué más puedo hacer? | **No: dirección opuesta (aumento de peso)** | mención superficial de «peso» | humano |
| 4 | A p. 44 | Consejos para controlar los problemas de alimentación | **Sí** | mantener o recuperar peso con calorías y proteínas | humano |
| 5 | A p. 3 | problemas de alimentación | No | introducción | humano |

**Qwen3**

| Rank | Doc · pág. | Sección | Pertinente | Tipo de contenido | Juicio |
|---:|---|---|---|---|---|
| 1 | A p. 42 | ¿Qué más puedo hacer? | **No: dirección opuesta (aumento de peso)** | mención superficial de «peso» | humano |
| 2 | A p. 43 | ¿Cómo me alimento si tengo este problema? | **Sí** | apartado de pérdida de peso: maní, aceite, nueces, aguacate, proteína en polvo, batidos | asistido |
| 3 | A p. 7 | Las personas con cáncer tienen necesidades de alimentación diferentes | No | introducción (más proteínas y calorías, sin decir cómo) | asistido |
| 4 | A p. 44 | Consejos para controlar los problemas de alimentación | **Sí** | igual que el rank 4 de ALIA | humano |
| 5 | A p. 41 | ¿Cómo me alimento si tengo este problema? | **No: dirección opuesta** | aumento de peso: frutas y verduras bajas en calorías para sentirse lleno | asistido |

**BGE-M3**

| Rank | Doc · pág. | Sección | Pertinente | Tipo de contenido | Juicio |
|---:|---|---|---|---|---|
| 1 | A p. 7 | (solo encabezado) | No | título sin contenido | asistido |
| 2 | A p. 42 | ¿Qué más puedo hacer? | **No: dirección opuesta (aumento de peso)** | mención superficial de «peso» | humano |
| 3 | Q p. 28 | Formas de controlar los cambios de apetito | No | opciones médicas (medicinas, sonda, IV), no enriquecimiento | asistido |
| 4 | R p. 10 | ¿Deberé seguir una dieta especial mientras reciba radioterapia? | No [límite] | importancia de calorías y proteínas; remite a una tabla | asistido |
| 5 | A p. 44 | Consejos para controlar los problemas de alimentación | **Sí** | igual que el rank 4 de ALIA | humano |

**Lectura de MD10**

- **Ninguno de los tres modelos distingue la dirección semántica.** El fragmento de aumento de peso aparece en el Top-3 de los tres: rank 3 en ALIA, **rank 1 en Qwen3** y rank 2 en BGE-M3. Qwen3 coloca además otro fragmento de aumento de peso (p. 41) en el rank 5.
- La consulta no contiene una negación literal, pero «bajando de peso» y «mantener el peso» se oponen a «aumento de peso». Los embeddings dense parecen codificar el tema («peso + alimentación») más que la dirección.
- Primer pertinente: ALIA 4, **Qwen3 2**, BGE-M3 5. Solo Qwen3 recupera el apartado de enriquecimiento de p. 43 que el baseline ALIA había localizado fuera de su Top-5. Es la única consulta en la que BGE-M3 queda por detrás de los otros dos.

### 7.2 Introducciones / definiciones frente a consejos prácticos

- **Primer relevante** = primer fragmento juzgado pertinente.
- **Primer accionable** = primer fragmento pertinente cuya categoría es `consejo_practico`.
- **No accionables delante** = número de introducciones, definiciones o causas, cuestionarios sin respuesta y listas o remisiones situados por encima del primer accionable (o en todo el Top-10 si no hay ninguno).

Se muestran las consultas en las que ALIA tenía al menos un no accionable delante.

| ID | ALIA rel. / acc. / no acc. delante | Qwen3 | BGE-M3 |
|---|---|---|---|
| MD02 vómitos | 2 / 2 / 1 | 1 / 1 / 0 | 1 / 1 / 0 |
| MD04 diarrea | 4 / 4 / 2 | 9 / 9 / 4 | 3 / 3 / 2 |
| MD05 estreñimiento | — / — / 4 | — / — / 3 | 5 / 5 / 2 |
| MD06 poco apetito | 3 / 3 / 2 | 1 / 1 / 0 | 1 / 1 / 0 |
| MD07 tragar | — / — / 5 | — / — / 7 | 2 / 2 / 0 |
| MD08 alimentación con náuseas | 2 / 2 / 1 | 1 / 1 / 0 | 1 / 1 / 0 |
| MD09 llagas | 4 / 4 / 2 | 2 / 2 / 0 | 1 / 1 / 0 |
| MD10 pérdida de peso | 4 / 4 / 2 | 2 / 2 / 0 | 5 / 5 / 2 |
| MD15 cuidados radioterapia | 1 / 2 / 1 | 1 / 2 / 1 | 1 / 2 / 1 |

- Las introducciones de Alimentación (p. 3) ocupaban el Top-1 de ALIA en MD06, MD07 y MD10. **No aparecen en el Top-1 de Qwen3 ni de BGE-M3.** Aun así, el Top-1 de BGE-M3 en MD10 es otro fragmento sin contenido: un encabezado de p. 7. En MD07, el Top-1 de Qwen3 y de BGE-M3 son las opciones médicas para el apetito (Quimioterapia p. 28), que no responden a la consulta.
- Siguen apareciendo otras introducciones en ranks intermedios: Alimentación p. 7–8 («Preparación…», «Las personas con cáncer…», «Los efectos secundarios…»). En Qwen3 son frecuentes en MD06, MD07, MD08 y MD10.
- Los «no accionables delante» aumentan en Qwen3 para MD04 (4) y MD07 (7). BGE-M3 tiene el menor total.
- En MD15 el rank 1 de los tres modelos es «¿Cómo aprovecho al máximo la radioterapia?»: autocuidado general que la revisión humana juzgó pertinente; el consejo concreto llega en el rank 2.
- MD11 («qué efectos secundarios y de qué depende») es informativa, no pide consejos. Por eso no se le aplica el criterio «accionable».
- Solo se midió; no se implementó reranking ni boost.

### 7.3 Recuperación multidocumento (Top-5)

| Indicador | ALIA | Qwen3 | BGE-M3 |
|---|---:|---:|---:|
| Fuente esperada presente en el Top-5 | 15/15 | 15/15 | 15/15 |
| Fuente esperada con al menos un pertinente en el Top-5 | 11/15 | 12/15 | **14/15** |
| Consultas con más de un documento en el Top-5 | 8/15 | 9/15 | **13/15** |
| Fragmentos de otro documento en el Top-5 (pertinentes) | 15 (7) | 13 (5) | 21 (11) |

BGE-M3 mezcla documentos con más frecuencia, y aproximadamente la mitad de esos fragmentos cruzados son pertinentes. Por ejemplo, MD12 (cansancio en radioterapia) obtiene en el rank 1 el control del cansancio de Quimioterapia, juzgado pertinente parcial. El criterio exige mantener visible la procedencia: un consejo de otro tratamiento es un complemento, no una equivalencia.

### 7.4 Q04 histórica

Resumen (detalle y Top-10 completos en `eval/q04_model_comparison.md`):

| Modelo | A. primer pertinente (parcial incl.) | A′. primer fragmento específico de infección | B. fragmento histórico p. 62 (de 419) |
|---|---:|---:|---:|
| ALIA | 1 | 7 | 54 |
| Qwen3 | 1 | 9 | 22 |
| BGE-M3 | 2 | 2 | **5** |

La consulta no se modificó. En el corpus anterior (un documento), ALIA colocaba la sección Infección en la posición 7 y la lista p. 62 en la 47.

## 8. Conclusión preliminar

- **En el corpus v0.1, BGE-M3 (dense) obtuvo las mejores métricas**: Hit@1 11/15, Hit@3 13/15, Hit@5 15/15, Hit@10 15/15 y MRR 0.816. También es el que acerca más el fragmento histórico de Q04 (posición 5).
- **Qwen3** supera a ALIA en Hit@1 (10 frente a 6) y en MRR (0.741 frente a 0.556), pero no en Hit@5 (12 frente a 13). Además empeora MD04 y es el que más arriba coloca el contenido de dirección opuesta en MD10.
- **ALIA** es el más rápido y ligero (89.5 emb/s, ~0.9 GiB de VRAM), pero tiene el peor Top-1.
- Las diferencias se apoyan en parte en juicios asistidos. Con la cota inferior solo humana (§5.2) los tres modelos quedan mucho más cerca.
- **No se declara un ganador para Vianova.** La selección requiere un corpus mayor, más consultas, un gold standard revisado y, idealmente, revisión clínica.

## 9. Verificación de PostgreSQL (2026-11-03)

| Tabla | Configuración | Filas totales | Elegibles (activa + contenido) | Coinciden con el manifest |
|---|---|---:|---:|---|
| `embedding_fragmento_alia` (768) | `alia` `089123fd-36ae-4d29-88e9-3cec64218adf` | 431 | 419 | 0 faltantes · 0 sobrantes · 0 duplicados |
| `embedding_fragmento_qwen3` (1024) | `qwen3` `2e19f115-7896-4c92-a53c-307af41d4072` | 419 | 419 | 0 · 0 · 0 |
| `embedding_fragmento_bge_m3` (1024) | `bge-m3` `ae83d20d-2782-43f8-9f3a-4fb12b8a6787` | 419 | 419 | 0 · 0 · 0 |

- Las 431 filas de ALIA son 419 elegibles, 9 fragmentos de índice y 3 del documento sintético retirado. Son históricas y no se tocaron. **En el experimento participan solo las 419 elegibles**, y su conjunto de IDs es idéntico en las tres tablas.
- Documentos: 3 NCI en estado `activa`; «Documento de prueba – fase 2 (pgvector)» en estado `retirada`. El INEN no está en la base (0 filas): sigue rechazado y fuera de retrieval según `corpus/manifest_curacion.json`.
- `schema_migracion`: de `001` a `005_dense_comparison.sql`. La 005 se aplicó el 2026-11-03 con SHA-256 `413987b1…a1d8`. Solo crea las dos tablas nuevas y no edita migraciones anteriores.
- Ninguna tabla tiene índice HNSW ni IVFFlat; cada corrida lo comprueba.
- La corrida heredada de ALIA **amplió** `configuracion_modelo.parametros` de `alia` mediante merge `||` con metadatos del experimento. No eliminó claves (se conserva `prompt_consulta = "query"`) y no cambió `model_id`, `dimension` ni `normalizado`.

## 9 bis. Tests (2026-11-03)

| Comando | Resultado |
|---|---|
| `pytest -q` | **74 passed**, 44 deselected (los de integración); 0 failed, 0 skipped |
| `HF_HUB_OFFLINE=1 RUN_MODEL_TESTS=1 pytest -q -m integration -rs` | **44 passed**, 74 deselected; 0 failed, 0 skipped |

Tests nuevos en `tests/test_experiments.py`:

- Procedencia de juicios: un juicio humano nunca se reemplaza, los juicios contradictorios abortan y los juicios son por consulta y completos.
- Con modelos reales: dimensión 1024 observada y norma 1 (Qwen3 y BGE-M3); la instrucción de query se aplica solo en Qwen3.
- Contra la base persistida: los 3 modelos usan exactamente los 419 IDs del manifest, cada uno en su tabla y configuración, con dimensión homogénea.
- Reproducibilidad: al recargar cada modelo en su revisión fijada y repetir las 15 consultas + Q04, se obtiene el **mismo Top-10 por ID** que el persistido.

Notas sobre la ejecución:

- `HF_HUB_OFFLINE=1` fue necesario porque en ese momento no había salida a internet. Tres tests heredados de ALIA construyen `EmbeddingService("alia")` sin `local_files_only`, y su conexión al Hub quedaba en `SYN-SENT`. Con la variable usan el cache local ya verificado.
- Primera corrida: 2 fallos, ambos en los tests y no en el experimento. (a) Mi test cargaba Qwen3 sin `dtype=float32`; en ese caso usa bfloat16 y la norma da 1.0021. Se corrigió para usar float32, igual que el experimento. (b) `test_ingestion_integration.py` fijaba la lista de migraciones 001–004 y se actualizó para incluir la 005.

## 10. Limitaciones

- 3 documentos, 419 chunks recuperables y 15 consultas: muestra pequeña. Una consulta equivale a 6.7 puntos de Hit@k.
- 301 de los 480 juicios por posición son `asistido_preliminar`, hechos por la misma IA que ejecutó el experimento. No es una evaluación independiente ni un gold standard clínico.
- No hay juicios humanos para Q04 en este corpus.
- Los juicios parciales cuentan como pertinentes. Los cruces entre tratamientos se aceptan como complemento parcial, igual que en la revisión humana.
- Un único Top-10 por modelo y consulta, una sola semilla y un solo hardware. No se calcularon intervalos de confianza.
- Los tiempos excluyen la descarga y dependen del estado térmico de la GPU portátil.

## 11. Relevo entre agentes (trazabilidad)

**Trabajo recuperado al inicio** (dejado por otra IA)

- Código: `src/experiments.py` (congelación y verificación del corpus, cobertura por IDs, métricas); `scripts/compare_models.py` (probe, embeddings, Top-10, sin sobrescribir); `scripts/diagnose_q04.py`; protección modelo↔tabla en `src/database/vector_repository.py`; `sql/005_dense_comparison.sql` (**creada pero no aplicada**); 6 tests en `tests/test_experiments.py`.
- Ejecutado: manifest congelado; `model_revisions_v01.json`; probe y corrida completa de ALIA (`resultados_alia_v01.json`); diagnóstico Q04 de ALIA (posición 54); 85 juicios asistidos.
- Incompleto: los pesos de Qwen3 y BGE-M3 estaban a medio descargar y su proceso seguía activo. No había embeddings, resultados, juicios, informe ni artefactos `model_comparison_v01`.

**Trabajo completado en esta sesión**

- Aplicada la migración 005 con `scripts/migrate_database.py`.
- Descarga terminada por el proceso heredado (único). Se detuvo un segundo proceso propio que solo esperaba el lock, y no se borró nada del cache. Pesos verificados por SHA-256.
- Probe, embeddings, Top-10 y Q04 de Qwen3 y de BGE-M3; verificación por IDs de los tres modelos.
- Comprobación del pooling de Qwen3 con padding a la derecha.
- 125 juicios `asistido_preliminar` nuevos y 98 anotaciones de categoría.
- Consolidación, métricas, análisis de sensibilidad, informes y tests nuevos.

**Archivos heredados sin cambios**: `scripts/compare_models.py`, `scripts/diagnose_q04.py`, `sql/005_dense_comparison.sql`, `src/database/vector_repository.py`, `eval/experimentos/{corpus_v01_manifest.json, model_revisions_v01.json, model_cache_paths.json, probe_alia.*, run_alia.log, resultados_alia_v01.json, Q04_alia*, juicios_asistidos_v01.json}` y todos los baselines y evidencias anteriores de `eval/`.

**Archivos heredados modificados**: `src/experiments.py` (se añaden `judgment_index`, `judge_ranking` y `first_relevant`); `tests/test_experiments.py` (tests nuevos añadidos); `tests/test_ingestion_integration.py` (lista de migraciones esperadas con la 005); `README.md` (enlace a este informe).

**Archivos nuevos**

- `scripts/build_model_comparison.py`
- `eval/model_comparison_v01.md`, `eval/q04_model_comparison.md`
- `eval/experimentos/{probe_qwen3.json, probe_qwen3.log, probe_bge-m3.json, probe_bge-m3.log, run_qwen3.log, run_bge-m3.log, resultados_qwen3_v01.json, resultados_bge-m3_v01.json, Q04_qwen3_v01.json, Q04_qwen3.log, Q04_bge-m3_v01.json, Q04_bge-m3.log, juicios_asistidos_v01_qwen3_bge_m3.json, anotacion_intro_consejo_v01.json}`
- `eval/resultados/model_comparison_v01/{alia.json, qwen3.json, bge_m3.json, judgments.json, metrics.json}`

Base de datos: tablas `embedding_fragmento_qwen3` y `embedding_fragmento_bge_m3` (419 filas cada una) y configuraciones `qwen3` y `bge-m3` en `configuracion_modelo`.

## 12. Reproducir

```bash
python scripts/migrate_database.py                 # 005 ya registrada → «ninguna»
python scripts/compare_models.py <alias> --probe   # alias: alia | qwen3 | bge-m3 (se niega a sobrescribir)
python scripts/compare_models.py <alias> --batch-size 16
python scripts/diagnose_q04.py <alias>
python scripts/build_model_comparison.py           # consolida; solo lectura sobre la BD
RUN_MODEL_TESTS=1 pytest -q -m integration         # incluye la reproducción del Top-10 de los 3 modelos
```
