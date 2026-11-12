# Comparación de modelos v0.1 — revisión humana consolidada

## Resumen

La revisión ciega humana se aplicó a los 214 pares que no tenían juicio humano original. Los 75 pares humanos previos se conservaron sin cambios. Las métricas se recalcularon sin modificar embeddings, rankings, consultas ni PostgreSQL.

- Pares únicos evaluados: **289**.
- Humanos originales: **75** (Sí=32, No=43).
- Revisión humana 4A.1: **214** (0=152, 1=37, 2=25).
- Escenario estricto: solo `2` cuenta como pertinente; los humanos binarios originales mantienen Sí/No.
- Escenario laxo: `1` y `2` cuentan como pertinentes; los humanos binarios originales mantienen Sí/No.

## Métricas finales con revisión humana

### Escenario estricto

| Modelo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| alia | 6/15 | 9/15 | 13/15 | 13/15 | 0.556 |
| qwen3 | 7/15 | 12/15 | 12/15 | 13/15 | 0.641 |
| bge-m3 | 9/15 | 12/15 | 15/15 | 15/15 | 0.729 |

### Escenario laxo

| Modelo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| alia | 6/15 | 9/15 | 13/15 | 13/15 | 0.556 |
| qwen3 | 10/15 | 13/15 | 13/15 | 14/15 | 0.774 |
| bge-m3 | 11/15 | 15/15 | 15/15 | 15/15 | 0.844 |

## Comparación contra la evaluación preliminar

| Modelo | Prelim. Hit@1 | Estricto Hit@1 | Laxo Hit@1 | Prelim. MRR | Estricto MRR | Laxo MRR |
|---|---:|---:|---:|---:|---:|---:|
| alia | 6/15 | 6/15 | 6/15 | 0.556 | 0.556 | 0.556 |
| qwen3 | 10/15 | 7/15 | 10/15 | 0.741 | 0.641 | 0.774 |
| bge-m3 | 11/15 | 9/15 | 11/15 | 0.816 | 0.729 | 0.844 |

Con criterio estricto, la revisión humana reduce especialmente los primeros puestos de Qwen3 y BGE-M3. ALIA conserva exactamente su baseline porque su Top-5 ya estaba cubierto por los juicios humanos originales. BGE-M3 continúa con las mejores métricas en ambos escenarios.

## Primer fragmento pertinente por consulta

### Estricto

| Consulta | ALIA | Qwen3 | BGE-M3 |
|---|---:|---:|---:|
| MD01 | 1 | 1 | 1 |
| MD02 | 2 | 2 | 1 |
| MD03 | 1 | 1 | 1 |
| MD04 | 4 | 9 | 3 |
| MD05 | — | — | 5 |
| MD06 | 3 | 2 | 2 |
| MD07 | — | — | 2 |
| MD08 | 2 | 1 | 1 |
| MD09 | 4 | 2 | 1 |
| MD10 | 4 | 2 | 5 |
| MD11 | 4 | 2 | 5 |
| MD12 | 1 | 1 | 1 |
| MD13 | 1 | 1 | 1 |
| MD14 | 1 | 1 | 1 |
| MD15 | 1 | 1 | 1 |

### Laxo

| Consulta | ALIA | Qwen3 | BGE-M3 |
|---|---:|---:|---:|
| MD01 | 1 | 1 | 1 |
| MD02 | 2 | 1 | 1 |
| MD03 | 1 | 1 | 1 |
| MD04 | 4 | 9 | 3 |
| MD05 | — | — | 2 |
| MD06 | 3 | 1 | 1 |
| MD07 | — | 2 | 2 |
| MD08 | 2 | 1 | 1 |
| MD09 | 4 | 2 | 1 |
| MD10 | 4 | 2 | 3 |
| MD11 | 4 | 1 | 1 |
| MD12 | 1 | 1 | 1 |
| MD13 | 1 | 1 | 1 |
| MD14 | 1 | 1 | 1 |
| MD15 | 1 | 1 | 1 |

## Cambios frente a los juicios asistidos

Entre los 210 pares que tenían un juicio `asistido_preliminar` y luego fueron revisados por una persona:
- IA No → humano 0: **147**.
- IA No → humano 1: **12**.
- IA Sí → humano 0: **3**.
- IA Sí → humano 1: **23**.
- IA Sí → humano 2: **25**.
Esto confirma que los juicios asistidos eran útiles como cribado preliminar, pero no sustituyen la revisión humana.

## Q04 — signos de infección durante la quimioterapia

| Modelo | Primer pertinente estricto | Primer pertinente laxo | Primer fragmento específico de infección | Fragmento histórico p. 62 |
|---|---:|---:|---:|---:|
| alia | 7 | 7 | 7 | 54 |
| qwen3 | 9 | 9 | 9 | 22 |
| bge-m3 | 2 | 2 | 2 | 5 |

La revisión humana corrige la interpretación preliminar: los resultados de síntomas tipo influenza en rank 1 de ALIA/Qwen3 no cuentan como pertinentes. El primer fragmento claramente pertinente queda en rank 7 para ALIA, rank 9 para Qwen3 y rank 2 para BGE-M3. El fragmento histórico de la lista directa de signos (p. 62) queda en ranks 54, 22 y 5, respectivamente.

## MD10 — pérdida de peso

Los tres modelos siguen mostrando confusión con fragmentos sobre aumento de peso. La revisión humana marca esos fragmentos como no pertinentes. Primer pertinente estricto: ALIA rank 4, Qwen3 rank 2 y BGE-M3 rank 5. En el escenario laxo BGE-M3 obtiene un parcial en rank 3, pero su primer fragmento plenamente pertinente continúa en rank 5.

### alia

| Rank | Grado | Página | Sección | Observación humana |
|---:|---:|---:|---|---|
| 1 | 0 | 3 | Acerca de esta publicación | Introducción del folleto; no enseña a enriquecer comidas. |
| 2 | 0 | 43 | ¿Por qué pasa? | Causas de pérdida de peso; no da medidas. |
| 3 | 0 | 42 | ¿Qué más puedo hacer? | Habla de AUMENTO de peso y dieta para bajarlo: dirección opuesta a la consulta. |
| 4 | 2 | 44 | Consejos para controlar los problemas de alimentación | Contenido sobre mantener/recuperar peso mediante alimentos ricos en calorías/proteínas; pertinente, aunque sin lista detallada de ingredientes. |
| 5 | 0 | 3 | problemas de alimentación | Descripción de temas de la publicación; no contenido específico. |

### qwen3

| Rank | Grado | Página | Sección | Observación humana |
|---:|---:|---:|---|---|
| 1 | 0 | 42 | ¿Qué más puedo hacer? | Habla de AUMENTO de peso y dieta para bajarlo: dirección opuesta a la consulta. |
| 2 | 2 | 43 | ¿Cómo me alimento si tengo este problema? | Responde directamente, horario fijo, comidas pequeñas, agregar proteínas y calorías (mantequilla de maní, aceite de oliva, nueces, aguacate), batidos, proteína en polvo |
| 3 | 1 | 7 | Las personas con cáncer tienen necesidades de alimentación diferentes | Necesidad de proteínas y calorías adicionales (más carne, pescado, huevos, lácteos), general, sin formas concretas de enriquecer |
| 4 | 2 | 44 | Consejos para controlar los problemas de alimentación | Contenido sobre mantener/recuperar peso mediante alimentos ricos en calorías/proteínas; pertinente, aunque sin lista detallada de ingredientes. |
| 5 | 0 | 41 | ¿Cómo me alimento si tengo este problema? | Dieta para controlar el AUMENTO de peso (frutas, verduras bajas en calorías), dirección opuesta, puede confundir |

### bge-m3

| Rank | Grado | Página | Sección | Observación humana |
|---:|---:|---:|---|---|
| 1 | 0 | 7 | — | Título suelto |
| 2 | 0 | 42 | ¿Qué más puedo hacer? | Habla de AUMENTO de peso y dieta para bajarlo: dirección opuesta a la consulta. |
| 3 | 1 | 28 | Formas de controlar los cambios de apetito: | Opciones médicas ante la pérdida de peso (medicinas para el apetito, IV, sonda) y remisión, no dice cómo enriquecer las comidas |
| 4 | 1 | 10 | ¿Deberé seguir una dieta especial mientras reciba radioterapia? | Importancia de calorías y proteínas para mantener el peso, remite a una tabla y al dietista sin dar ejemplos, viene de La radioterapia y usted |
| 5 | 2 | 44 | Consejos para controlar los problemas de alimentación | Contenido sobre mantener/recuperar peso mediante alimentos ricos en calorías/proteínas; pertinente, aunque sin lista detallada de ingredientes. |

## Conclusión de esta fase

- **BGE-M3 dense** conserva el mejor desempeño en el corpus v0.1 tanto con criterio estricto como laxo.
- Esto no constituye una selección definitiva para Vianova: el banco contiene solo 15 consultas y 3 documentos.
- La diferencia entre estricto y laxo muestra que varios resultados altos son relacionados, pero incompletos. Por ello, una siguiente fase de reranking puede ser pertinente, especialmente para priorizar fragmentos plenamente accionables.
- El caso pérdida/aumento de peso sigue demostrando que similitud semántica alta no equivale a responder correctamente la intención.

## Integridad

- Semilla de la revisión ciega: `20261103`.
- Los resultados de retrieval originales no fueron modificados; solo se generaron artefactos derivados de evaluación humana.
- No se ejecutaron embeddings, búsquedas ni escrituras en PostgreSQL durante este recálculo.
