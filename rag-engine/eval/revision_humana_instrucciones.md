# Instrucciones para la revisión humana de pertinencia (v01)

Archivo a completar: `eval/revision_humana_model_comparison_v01.xlsx`, hoja **PENDIENTES_REVISION_HUMANA** (214 filas). Hay una copia en CSV: `eval/revision_humana_model_comparison_v01_pendientes.csv`.

> No abra `eval/revision_humana_model_comparison_v01_map.json` ni los resultados o juicios de `eval/resultados/` ni de `eval/experimentos/` hasta terminar. La revisión es **ciega**: la planilla no indica qué sistema encontró cada fragmento, en qué posición, con qué similitud ni cómo se juzgó antes. Así su juicio no se contamina.

## Qué se evalúa

En cada fila hay una **consulta** de un cuidador y un **fragmento** de un folleto del NCI. Usted responde una sola pregunta:

**¿Este fragmento, por sí mismo, responde o ayuda a responder la necesidad expresada en esta consulta?**

- Evalúe el fragmento **frente a la consulta**. No evalúe la calidad del folleto ni la de ningún buscador o modelo.
- Use solo lo que está escrito en `texto`. **No infiera información ausente**: si el fragmento menciona un tema pero no dice qué hacer, no suponga que la respuesta está en otro lugar.
- `contexto_anterior` muestra el final del fragmento previo del mismo documento, para entender listas o frases que empiezan a mitad de sección. **Es solo de apoyo: no lo puntúe.** Si la información útil está solo en el contexto anterior y no en el texto, el fragmento no la contiene.
- Las páginas son páginas físicas del PDF.
- Las consultas se copian tal como fueron formuladas. No las corrija ni las reinterprete.

## Escala (columna `juicio_humano`)

| Valor | Significado |
|---|---|
| **2 — Pertinente** | Responde directamente o da información claramente útil para la necesidad expresada. |
| **1 — Parcialmente pertinente** | Tiene relación real con la consulta pero responde solo una parte, es demasiado general, describe el problema sin orientar o necesita otro fragmento para ser útil. |
| **0 — No pertinente** | No responde a la necesidad o puede llevar a una interpretación incorrecta. |

Escriba solo `0`, `1` o `2`; la celda tiene una lista desplegable. Si duda, elija el valor más bajo de los que considere razonables y explíquelo en `observacion_humana`.

## Casos frecuentes

**Coincidencia de palabras no es pertinencia.** Que el fragmento repita «peso», «quimioterapia» o «náuseas» no basta. Lo que importa es si responde a la intención de la consulta.

**Respuestas que dicen lo contrario de la consulta → 0.**
Ejemplo: la consulta dice «está bajando de peso, ¿cómo enriquecer sus comidas para mantener el peso?» y el fragmento explica cómo controlar un *aumento* de peso (comer frutas y verduras bajas en calorías para sentirse lleno). Aunque hable de peso y alimentación, va en la dirección opuesta: **0**. Lo mismo vale para diarrea frente a estreñimiento o, en general, para «evitar X» frente a «conseguir X».

**Introducciones, presentaciones del folleto, índices y títulos sueltos → normalmente 0.** Un fragmento que solo dice de qué trata la publicación, enumera problemas con remisiones a páginas o es solo un encabezado no orienta al cuidador. Use **1** solo si además aporta algún dato concreto y útil para la consulta.

**Definiciones y causas («¿Qué es?», «¿Por qué pasa?»).** Si la consulta pide qué hacer, una definición sola suele ser **0**. Use **1** si describe el problema de forma relevante para la necesidad, por ejemplo cuándo avisar al equipo, aunque no dé medidas. Si la consulta pregunta qué es, de qué depende o qué efectos puede haber, una buena explicación puede ser **2**.

**Preguntas sin respuesta** (cuestionarios con «Blank lines for answer») → **0**.

**Remisiones** («consulte la página…», «visite cancer.gov…») sin contenido propio → **0**.

**Información de otro tratamiento.** Por ejemplo, una consulta sobre radioterapia con un fragmento de *La quimioterapia y usted*. Si el consejo es general para el síntoma y aplicable (descanso, comidas pequeñas…), puede ser **1** o **2**: indique en la observación que viene de otro tratamiento. Si es específico del otro tratamiento y no aplica, es **0**.

**Parcialmente útil.** Si la consulta tiene dos partes (por ejemplo «cómo ayudarlo y cuándo avisar») y el fragmento cubre bien una sola, use **1**. Use **2** si cubre bien la parte principal de la necesidad.

**Seguridad.** No valide la exactitud clínica de las pautas ni las complete. Si un fragmento le parece clínicamente dudoso o peligroso para la consulta, anótelo en la observación.

## Columna `q04_especifico_infeccion` (solo filas Q04)

Q04 = «signos de infección durante la quimioterapia». En esas filas, además de `juicio_humano`, marque:

- **S** si el fragmento trata **específicamente de la infección**: sus signos, la fiebre como signo de infección, la sección Infección, etc.;
- **N** si trata de otro tema, aunque mencione fiebre de pasada (por ejemplo síntomas urinarios o tipo gripe).

Deje esta columna vacía en el resto de las consultas.

## Columna `observacion_humana`

Es opcional, pero recomendable cuando:

- puntúa 1;
- hay dirección opuesta;
- el contenido viene de otro tratamiento;
- el texto está cortado o ilegible;
- duda entre dos valores.

## Orden y prioridad

Las filas están ordenadas por `prioridad` (1 = más importante) y, dentro de cada prioridad, en orden aleatorio con semilla fija. Revise en ese orden: si no termina, lo revisado será lo más útil.

La prioridad **no** indica si el fragmento es bueno o malo; no la tenga en cuenta al puntuar.

| Prioridad | Filas | Contenido |
|---:|---:|---|
| 1 | 75 | Fragmentos que pueden cambiar el primer resultado útil; todo MD10 (pérdida de peso) y Q04 (infección) |
| 2 | 5 | Revisión adicional |
| 3 | 39 | MD04 (diarrea) e introducciones o definiciones |
| 4 | 95 | Resto |

## Hoja YA_REVISADOS_HUMANO

Contiene 75 pares que ya tienen un juicio humano anterior (Sí/No). Es solo de referencia: **no hay que revisarlos de nuevo** y no se modificarán.

## Qué no hacer

- No cambie `review_id`, `fragmento_id`, `consulta_id`, `consulta` ni `texto`; el script de aplicación valida que coincidan.
- No añada, borre ni reordene filas. Puede usar filtros de visualización.
- No busque el fragmento en otros archivos del repositorio para averiguar su posición o su juicio anterior.

Al terminar, guarde el archivo con el mismo nombre en formato `.xlsx` (o el CSV en UTF-8) y avise. Los juicios nuevos se registrarán como `humano_revision_4a1`, sin borrar los juicios anteriores.
