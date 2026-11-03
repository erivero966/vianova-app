# Corpus v01: primera revisión multidocumento con ALIA

**Corpus persistente operativo: tres documentos oficiales digitales activos, 428 chunks y 428 embeddings; 419 chunks elegibles para retrieval normal.** Las 15 consultas se ejecutaron con ALIA en CUDA y Top-5 exacto en pgvector. La revisión encontró fallos de pertinencia que impiden interpretar el funcionamiento técnico como validación de calidad de todas las recuperaciones.

Fecha de ejecución: 2026-11-03T18:04:51.003677+00:00. Páginas físicas del PDF, empezando en 1.

## Evidencia y alcance

- [Banco nuevo MD01–MD15](consultas_multidocumento_v01.json); Q01–Q10 permanece intacto.
- [75 resultados crudos completos](resultados/alia_multidocumento_v01.json).
- [Juicios manuales por resultado](evaluacion_manual_multidocumento_v01.json) y [resultados con Top-1/3/5 y evaluación](resultados/alia_multidocumento_v01_revisado.json).
- [Estado persistente, ingestas, hashes y EXPLAIN](corpus_v01_estado_persistente.json).
- [Verificación final contra PostgreSQL y archivos](corpus_v01_verificacion.json): 75 resultados contrastados, correspondientes a 58 fragmentos distintos.
- [Contraste de contenido disponible y no recuperado](multidocumento_v01_contraste_fuente.json).
- [Manifest de curación INEN](../corpus/manifest_curacion.json) y [hashes de evidencia previa](corpus_v01_evidencia_previa_sha256.json).

Se usaron los PDFs locales y el contenido persistido para comprobar fidelidad y pertinencia documental. No se generaron respuestas esperadas médicas. Los criterios y páginas de referencia del banco se fijaron antes de ejecutar las consultas. Los 75 textos devueltos se leyeron completos; los juicios no se deducen automáticamente de la similitud o del nombre de la fuente.

## Corpus real activo

| Documento | Versión | Chunks | Índice excluido | Recuperables | Embeddings | Estado |
|---|---|---:|---:|---:|---:|---|
| Consejos de alimentación: antes, durante y después del tratamiento del cáncer | 2024 | 167 | 5 | 162 | 167 | activa |
| La quimioterapia y usted: Apoyo para las personas con cáncer | 2019 | 130 | 2 | 128 | 130 | activa |
| La radioterapia y usted: Apoyo para las personas con cáncer | 2016 | 131 | 2 | 129 | 131 | activa |

Total activo: **428 chunks**, 9 de índice y **419 de contenido**. La base completa conserva además los 3 chunks y embeddings del documento sintético retirado: **431 registros físicos**, de los cuales solo los 419 de contenido activo se buscan. El sintético sigue `retirada`; no se borró. No hay documentos, versiones, fragmentos ni embeddings INEN en esta base ni resultados INEN en las 15 consultas.

## Metadatos e ingestas

Antes de indexar se validaron los dos JSON con `DocumentMetadata.from_json`, título y entidad contra las portadas y versión contra el colofón: Alimentación, p. 64, «Diciembre de 2024»; Radioterapia, p. 62, «Octubre de 2016». Sus URLs declaradas son de cancer.gov. Se conservaron los metadatos y `vigencia: por revisar`: la validación de identidad/edición no certifica actualidad clínica ni supone una comprobación web de esos enlaces.

| Documento | Versión | Chunks nuevos | Embeddings nuevos | Tiempo embeddings | Tiempo total pipeline | CUDA | Estado final |
|---|---|---:|---:|---:|---:|---|---|
| Consejos de alimentación: antes, durante y después del tratamiento del cáncer | 2024 | 167 | 167 | 2.617 s | 3.168 s | Sí | ACTIVA |
| La radioterapia y usted: Apoyo para las personas con cáncer | 2016 | 131 | 131 | 2.16 s | 2.61 s | Sí | ACTIVA |

Tiempos medidos por el pipeline; **no incluyen la carga inicial de pesos del modelo**. GPU comprobada: NVIDIA GeForce RTX 4060 Laptop GPU, PyTorch 2.14.1+cu130, CUDA 13.0. Los logs registran `Device: cuda`: [Alimentación](ingesta_nci_alimentacion_v01.log) y [Radioterapia](ingesta_nci_radioterapia_v01.log). Quimioterapia ya estaba activa y no se reindexó.

Configuración: `SINAI/ALIA-MrBERT-es-biomedical-embeddings`, **768 dimensiones**, vectores normalizados, **450/75**, tokenizer ALIA, distancia coseno `<=>`. PostgreSQL 16.15, pgvector 0.8.7. Sin HNSW/IVFFlat; se verificaron índices y el plan real, que recorre los 419 candidatos y los ordena por distancia. Filtros: versión activa y `tipo_contenido=contenido`. No se aplicaron filtros por fuente a las consultas.

Las nuevas ingestas registran origen `digital` y estrategia `tipografia_digital`. Quimioterapia conserva `cleaner_version=2`; las nuevas registran `3`, que incorpora la rama OCR ya existente. Se documenta la diferencia de versión, sin reindexar ni cambiar la segmentación de esta tarea. Esto no es una comparación controlada de modelos.

| Documento | Páginas / con texto | Caracteres | Títulos | Tokens mín./prom./máx. |
|---|---|---:|---:|---|
| Consejos de alimentación: antes, durante y después del tratamiento del cáncer | 64 / 63 | 74516 | 202 | 4 / 129.8 / 446 |
| La quimioterapia y usted: Apoyo para las personas con cáncer | 80 / 79 | 87395 | 156 | 23 / 191.6 / 450 |
| La radioterapia y usted: Apoyo para las personas con cáncer | 62 / 56 | 71103 | 144 | 17 / 172.6 / 450 |

El mínimo de 4 tokens de Alimentación y las secciones genéricas detectadas son limitaciones observadas de la segmentación actual; no se corrigieron reglas en esta fase.

## Decisión OCR conservada

El primer INEN queda formalmente `estado_curacion=rechazado`, `indexable=false`, motivo `errores_ocr_clinicamente_relevantes`. Se conservan original, derivado, `.provenance.json`, revisión e inventario. Su procedencia mantiene el estado histórico pendiente; el manifest registra la decisión posterior sin sobrescribirla. El manifest es administrativo, no un nuevo autorizador de ingesta. Las rutas OCR siguen bloqueadas y los originales escaneados carecen de texto indexable.

Métricas para memoria: 50 páginas, 49 con texto OCR, 89 448 caracteres, 68 títulos, 130 chunks potenciales, promedio 329.6 tokens; 36 chunks revisados (2 correctos, 13 aceptables, 21 problemáticos); 36 verificaciones sensibles (21 coincidencias, 15 discrepancias); 39 chunks contaminados por p. 28–39. Errores confirmados: `7 días → Y días`, `500 ml → 500 mil`, fila de plaquetopenia omitida.

El segundo INEN queda `candidato`, `requiere_ocr`, `no_indexado`, `indexable=false`. No se ejecutó OCR sobre él ni se reintentó el primero. El [gate de fidelidad](../corpus/README.md#control-de-fidelidad-y-decisiones-de-curación) deja explícito: **la finalización técnica del OCR no implica que un documento pueda incorporarse al corpus**.

## Criterio y recuentos de la revisión manual

Sí exige al menos un aporte práctico/sustantivo a lo preguntado. Una definición sola no basta cuando se piden cuidados; para alimentación se requiere contenido alimentario. Un sí puede ser parcial, y se indica la limitación. Fuente esperada se comprueba aparte por documento en Top-5, sin implicar pertinencia. No se validan ni combinan pautas clínicas.

En particular, una definición del síntoma no se cuenta como respuesta pertinente cuando el cuidador pide qué hacer. Tampoco bastan un prólogo, una remisión a otra guía o una pregunta con líneas en blanco. Un fragmento puede ser temáticamente relacionado y recibir «No» para la necesidad concreta. «Sí» puede cubrir solo parte de una pregunta; no significa respuesta completa ni validación de aplicación clínica.

| Observación en este banco | Consultas |
|---|---:|
| Top-1 pertinente | 6 de 15 |
| Top-3 contiene al menos un pertinente | 9 de 15 |
| Top-5 contiene al menos un pertinente | 13 de 15 |
| Fuente esperada presente en Top-5 | 15 de 15 |
| Fuente esperada aporta un fragmento pertinente en Top-5 | 11 de 15 |

Son recuentos descriptivos de juicios manuales en un banco pequeño e intencional. No se calcularon métricas formales, porcentajes de rendimiento, Precision/Recall, MRR, nDCG ni comparaciones de modelos. No hay segundo revisor independiente. «Fuente presente» se cuenta por documento, no por corrección de su fragmento.

## Resumen de las 15 consultas

Q = NCI Quimioterapia; A = NCI Alimentación; R = NCI Radioterapia. Cada referencia indica documento, página física y similitud coseno. Top-3 incluye Top-1.

| ID / tema | Top-1 | Top-3, en orden | Top-1 pertinente | Pertinente en Top-3 | Fuente esperada en Top-5 |
|---|---|---|---|---|---|
| [MD01](#md01) / náuseas | Q p.66–67 (0.7018) | Q p.66–67 (0.7018); Q p.65 (0.6557); Q p.65 (0.6289) | Sí | Sí | Q: Sí |
| [MD02](#md02) / vómitos | Q p.65 (0.6286) | Q p.65 (0.6286); Q p.66–67 (0.6052); Q p.19 (0.5738) | No | Sí | Q: Sí |
| [MD03](#md03) / cansancio | Q p.46–47 (0.6512) | Q p.46–47 (0.6512); A p.15 (0.5900); R p.31–32 (0.5792) | Sí | Sí | Q: Sí |
| [MD04](#md04) / diarrea | Q p.48 (0.6941) | Q p.48 (0.6941); Q p.65–66 (0.6016); A p.22 (0.5981) | No | No | Q: Sí |
| [MD05](#md05) / estreñimiento | A p.20 (0.6342) | A p.20 (0.6342); Q p.53 (0.5813); Q p.65 (0.5597) | No | No | Q: Sí |
| [MD06](#md06) / poco apetito | A p.3 (0.7307) | A p.3 (0.7307); A p.17 (0.7071); A p.18–19 (0.7021) | No | Sí | A: Sí |
| [MD07](#md07) / dificultad para comer | A p.3 (0.6594) | A p.3 (0.6594); A p.3 (0.6422); A p.8 (0.6032) | No | No | A: Sí |
| [MD08](#md08) / alimentación con náuseas | Q p.67 (0.6986) | Q p.67 (0.6986); A p.29–30 (0.6347); A p.28 (0.6322) | No | Sí | A: Sí |
| [MD09](#md09) / llagas en la boca | A p.32–33 (0.5964) | A p.32–33 (0.5964); R p.36 (0.5959); A p.30 (0.5561) | No | No | A: Sí |
| [MD10](#md10) / pérdida de peso | A p.3 (0.6359) | A p.3 (0.6359); A p.43 (0.6202); A p.42 (0.6144) | No | No | A: Sí |
| [MD11](#md11) / efectos secundarios | R p.56 (0.8052) | R p.56 (0.8052); R p.56 (0.7524); R p.56 (0.7099) | No | No | R: Sí |
| [MD12](#md12) / cansancio | R p.31–32 (0.6297) | R p.31–32 (0.6297); R p.30 (0.5861); R p.31 (0.5776) | Sí | Sí | R: Sí |
| [MD13](#md13) / piel | R p.47 (0.7430) | R p.47 (0.7430); R p.48 (0.6735); Q p.37 (0.6665) | Sí | Sí | R: Sí |
| [MD14](#md14) / alimentación | R p.10 (0.7221) | R p.10 (0.7221); R p.12 (0.5919); R p.31–32 (0.5825) | Sí | Sí | R: Sí |
| [MD15](#md15) / cuidados durante radioterapia | R p.12 (0.6592) | R p.12 (0.6592); R p.31 (0.6173); R p.10 (0.5680) | Sí | Sí | R: Sí |

## Recuperación cruzada, errores y observaciones

- **Cruce útil, MD02:** Quimioterapia rank 2 y Alimentación rank 4 aportan manejo de vómitos/comunicación con el equipo. Las diferencias de plazos expresadas por las fuentes se conservan; no se fusionan en una nueva indicación.
- **Cruce útil, MD03:** Quimioterapia rank 1 y Alimentación rank 2 ofrecen apoyo para descanso y actividad; Radioterapia aporta complementos generales en ranks 3 y 5, con contexto distinto explícito.
- **Cruce mixto, MD08:** una referencia de Quimioterapia ocupa Top-1 (0.698625), por delante del contenido de Alimentación en rank 2 (0.634681). El verdadero cruce útil es Alimentación rank 2 + Quimioterapia rank 5; citar otra guía no equivale a aportar sus consejos.
- **Cruce útil tardío, MD09:** Quimioterapia rank 4 aporta preparaciones para boca dolorida; los primeros tres resultados de Alimentación/Radioterapia no responden qué preparar.
- **Cruce de contexto incorrecto, MD13:** Quimioterapia rank 3 mezcla uñas y radiation recall tras irradiación previa. No equivale al cuidado de piel durante radioterapia actual. El Top-1 de Radioterapia sí es pertinente.
- **Oposición de intención, MD10:** rank 3 trata aumento de peso/dieta para bajarlo; la consulta pide enriquecer comidas por pérdida de peso. El fragmento útil aparece en rank 4. Pertenecer a la fuente correcta no evita este fallo.
- **Preguntas sin respuesta, MD11:** ranks 1–3 son preguntas del formulario de p. 56 con `Blank lines for answer`. Top-1 alcanza 0.805217, pero la explicación está en rank 4. Similitud alta no garantiza contenido útil.
- **Introducciones dominantes:** Alimentación p. 3 ocupa Top-1 en MD06, MD07 y MD10. Es contenido general clasificado como `contenido`, aunque no responde esas necesidades concretas.
- **Contenido presente pero no recuperado:** MD05 no recupera cuidados del estreñimiento (Quimioterapia p. 53–54); MD07 no recupera comidas para dificultad al tragar (Alimentación p. 34–35). Se localizaron directamente en PostgreSQL por página, sin otra búsqueda semántica. La evidencia conserva UUID, orden y texto. También existen los apartados alimentarios de mucositis p. 30–31 y enriquecimiento para pérdida de peso p. 43, fuera de sus respectivos Top-5.
- **Secciones poco informativas:** `¿Por qué pasa?`, `¿Qué más puedo hacer?` y `Formas de controlarlos` se repiten sin el título temático padre. Es una posible contribución a la ambigüedad; no se demuestra causalidad ni se retocó el algoritmo.

No todos los cruces son errores y no todos son beneficiosos. En MD01 no hubo cruce con Alimentación; en MD14 no hubo cruce con Alimentación pese al tema nutricional. Se reportan los rankings obtenidos, sin inventar el patrón esperado.

## Detalle de consultas y Top-5

Cada tabla incluye los cinco resultados, con sección, similitud y juicio manual. Los textos completos y UUID están en los JSON vinculados; no se reemplazaron por resúmenes para realizar la revisión.

### MD01

Mi mamá tiene náuseas después de la quimioterapia. ¿Qué podemos hacer en casa para ayudarla?

Fuente esperada: **La quimioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: Náuseas y vómitos, p. 65, 66, 67.

Top-1 pertinente: **Sí**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | Q | 66–67 | Qué hacer para controlar las náuseas y los vómitos: | 0.701778 | Sí | Medidas concretas para náuseas, relajación y comunicación con el equipo; responde la necesidad. |
| 2 | Q | 65 | Náuseas y vómitos | 0.655657 | No | Define náuseas y vómitos; no explica qué hacer en casa. |
| 3 | Q | 65 | Las náuseas y los vómitos pueden suceder: | 0.628925 | Sí | Explica prevención y conversación con el equipo sobre el control del síntoma. |
| 4 | Q | 65–66 | Qué hacer para controlar las náuseas y los vómitos: | 0.618214 | Sí | Medidas alimentarias concretas y precauciones durante quimioterapia. |
| 5 | Q | 15 | Su estado de ánimo durante la quimioterapia | 0.584403 | No | Estado de ánimo general; no aborda manejo de náuseas. |

Top-1 útil y fuente esperada. Los cinco resultados pertenecen a Quimioterapia; no se observó cruce con Alimentación en esta consulta.

### MD02

Mi papá ha vomitado después de la quimioterapia. ¿Cómo puedo ayudarlo y cuándo debo avisar al equipo médico?

Fuente esperada: **La quimioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: Náuseas y vómitos, p. 65, 66, 67.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | Q | 65 | Náuseas y vómitos | 0.628597 | No | Definición y mecanismo, sin cuidados ni criterios para avisar. |
| 2 | Q | 66–67 | Qué hacer para controlar las náuseas y los vómitos: | 0.605216 | Sí | Contiene ayuda práctica y situaciones para informar al equipo; cubre ambas partes. |
| 3 | Q | 19 | ¿Qué se puede hacer acerca de los efectos secundarios? | 0.573835 | No | Consejo general sobre efectos secundarios; no aporta manejo específico del vómito. |
| 4 | A | 40 | ¿Qué más puedo hacer? | 0.564823 | Sí | Alimentación aporta control del vómito y comunicación con el médico; cruce útil. |
| 5 | Q | 14 | Sobre los efectos secundarios | 0.563471 | No | Lista de preguntas con espacios en blanco; no aporta respuestas. |

Quimioterapia rank 2 y Alimentación rank 4 aportan contenido pertinente. Las fuentes expresan plazos de aviso distintos; se conservan separados, sin sintetizar una pauta nueva.

### MD03

Desde que recibe quimioterapia, mi familiar está muy cansado. ¿Cómo organizamos el descanso y las actividades del día?

Fuente esperada: **La quimioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: Cansancio, p. 44, 45, 46, 47.

Top-1 pertinente: **Sí**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | Q | 46–47 | Qué hacer para controlar el cansancio: | 0.651161 | Sí | Descanso, ayuda familiar, actividades y registro de energía. |
| 2 | A | 15 | Hacer frente a sus sentimientos durante el tratamiento del cáncer | 0.589978 | Sí | Consejos generales de descanso y tareas durante tratamiento; complemento parcial desde Alimentación. |
| 3 | R | 31–32 | Formas de controlarla | 0.579194 | Sí | Planificación de actividades y ayuda en fatiga; complemento general desde Radioterapia, conservando ese contexto. |
| 4 | Q | 45–46 | Qué hacer para controlar el cansancio: | 0.563849 | Sí | Descansos y planificación de actividad en quimioterapia. |
| 5 | R | 31 | Formas de controlarla | 0.548501 | Sí | Descanso y actividades para fatiga en radioterapia; complemento parcial, sin asumir equivalencia de tratamientos. |

Cruce de las tres fuentes; Quimioterapia encabeza y Alimentación añade apoyo cotidiano. Los fragmentos de Radioterapia se consideran complementos generales, no instrucciones transferibles en bloque.

### MD04

Mi mamá tiene diarrea durante la quimioterapia. ¿Qué cuidados y cambios en la comida pueden ayudarla?

Fuente esperada: **La quimioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: Diarrea, p. 48, 49, 50.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **No**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | Q | 48 | Diarrea | 0.694111 | No | Define diarrea y sus causas; no aporta los cuidados solicitados. |
| 2 | Q | 65–66 | Qué hacer para controlar las náuseas y los vómitos: | 0.601627 | No | Cuidados para náuseas y vómitos, no para diarrea. |
| 3 | A | 22 | ¿Por qué pasa? | 0.598134 | No | Explica causas de diarrea, sin cambios de comida ni cuidados. |
| 4 | R | 29–30 | Formas de controlarla | 0.586011 | Sí | Cuidados y alimentos a evitar para diarrea; complemento parcial desde Radioterapia, manteniendo su procedencia. |
| 5 | Q | 50 | Cómo obtener más información: | 0.581594 | No | Remisión a otro libro; no contiene recomendaciones. |

El Top-3 no aporta cuidados concretos. Top-4 contiene apoyo para diarrea desde otra fuente; no recuperó en Top-5 la sección de manejo de diarrea de Quimioterapia.

### MD05

Mi papá está estreñido desde que empezó la quimioterapia. ¿Qué podemos hacer para ayudarlo a ir al baño?

Fuente esperada: **La quimioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: Estreñimiento, p. 53, 54.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **No**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | A | 20 | ¿Por qué pasa? | 0.634195 | No | Alimentación explica causas de estreñimiento, no medidas de ayuda. |
| 2 | Q | 53 | Estreñimiento | 0.581295 | No | Quimioterapia describe estreñimiento y causas, sin el apartado de cuidados. |
| 3 | Q | 65 | Náuseas y vómitos | 0.559732 | No | Náuseas y vómitos: otro síntoma. |
| 4 | Q | 66–67 | Qué hacer para controlar las náuseas y los vómitos: | 0.537701 | No | Control de náuseas y vómitos: otro síntoma. |
| 5 | Q | 42 | Cambios urinarios, en los riñones o en la vejiga | 0.535128 | No | Problemas urinarios; la expresión ir al baño recupera un contexto distinto. |

La fuente esperada aparece en rank 2, pero ningún Top-5 responde cómo ayudar. La sección Forma de controlar el estreñimiento está persistida en p. 53–54 y no fue recuperada.

### MD06

Mi familiar está en tratamiento contra el cáncer y casi no tiene apetito. ¿Cómo puedo ayudarlo a comer un poco más?

Fuente esperada: **Consejos de alimentación: antes, durante y después del tratamiento del cáncer**. Referencia documental previa: Falta de apetito, p. 17, 18.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | A | 3 | problemas de alimentación | 0.730719 | No | Introducción con temas del folleto y remisión general; no ofrece formas de comer más. |
| 2 | A | 17 | Falta de apetito | 0.707102 | No | Definición de falta de apetito; no da medidas. |
| 3 | A | 18–19 | ¿Qué más puedo hacer? | 0.702057 | Sí | Medidas concretas para apetito y comidas agradables, con apoyo profesional. |
| 4 | A | 17 | ¿Por qué pasa? | 0.694772 | No | Lista de causas; no contiene medidas. |
| 5 | A | 14 | Los sentimientos afectan el apetito | 0.684281 | No | Describe sentimientos y su relación con apetito; no propone acciones. |

La fuente esperada domina, pero su introducción desplaza los cuidados al rank 3.

### MD07

A mi mamá le cuesta tragar durante el tratamiento del cáncer. ¿Qué comidas podrían resultarle más fáciles de pasar?

Fuente esperada: **Consejos de alimentación: antes, durante y después del tratamiento del cáncer**. Referencia documental previa: Esofagitis (inflamación de la garganta y dificultad para tragar), p. 34, 35, 36.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **No**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | A | 3 | problemas de alimentación | 0.659432 | No | Introducción; sin comidas ni preparación para dificultad al tragar. |
| 2 | A | 3 | Acerca de esta publicación | 0.642203 | No | Presentación del libro; sin contenido específico. |
| 3 | A | 8 | Los efectos secundarios del tratamiento del cáncer podrían causar problemas para comer | 0.603165 | No | Enumeración de problemas para comer; no da soluciones para tragar. |
| 4 | Q | 67 | Cómo obtener más información: | 0.594278 | No | Referencia desde Quimioterapia a otra publicación sobre náuseas; no responde. |
| 5 | A | 7 | — | 0.577542 | No | Solo un título general. |

No hay un fragmento pertinente en Top-5. La sección alimentaria para esofagitis está en la base (p. 34–35); se confirma un fallo de selección, no ausencia del contenido.

### MD08

Mi familiar tiene náuseas con el tratamiento del cáncer. ¿Qué alimentos le puedo ofrecer y cuáles conviene evitar?

Fuente esperada: **Consejos de alimentación: antes, durante y después del tratamiento del cáncer**. Referencia documental previa: Náuseas / Alimentos y bebidas fáciles de digerir, p. 28, 29, 52, 53.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | Q | 67 | Cómo obtener más información: | 0.698625 | No | Quimioterapia remite al libro de Alimentación; no aporta alimentos. |
| 2 | A | 29–30 | ¿Qué más puedo hacer? | 0.634681 | Sí | Alimentación incluye alimentos con olores fuertes que evitar y ayuda para preparación; cubre parte de la pregunta. |
| 3 | A | 28 | ¿Por qué pasa? | 0.632202 | No | Causas de náuseas; no ofrece opciones alimentarias. |
| 4 | R | 41–42 | Formas de controlarlos | 0.617804 | No | Radioterapia remite a otras fuentes; sin recomendaciones en este fragmento. |
| 5 | Q | 65–66 | Qué hacer para controlar las náuseas y los vómitos: | 0.608583 | Sí | Quimioterapia aporta opciones suaves y alimentos/olores a evitar; cruce pertinente. |

El Top-1 es una referencia de otra guía que desplaza al contenido pertinente de Alimentación (rank 2). El cruce útil aparece entre ranks 2 y 5, no por la mera coincidencia del título citado.

### MD09

Mi papá tiene llagas en la boca por el tratamiento y le duele comer. ¿Qué le puedo preparar para que le moleste menos?

Fuente esperada: **Consejos de alimentación: antes, durante y después del tratamiento del cáncer**. Referencia documental previa: Mucositis (dolor en la boca), p. 30, 31, 32, 33.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **No**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | A | 32–33 | Consejos para controlar los problemas de alimentación | 0.596366 | No | Cuidados bucales y consulta sobre dolor, pero no qué comida preparar; el rótulo RECETA no incluye la receta. |
| 2 | R | 36 | ¿Cuánto tiempo duran? | 0.595869 | No | Duración de llagas en radioterapia; no responde qué preparar. |
| 3 | A | 30 | ¿Por qué pasa? | 0.556103 | No | Causas de lesión de mucosa; no ofrece comidas. |
| 4 | Q | 33–34 | Qué hacer para controlar los problemas de la boca: | 0.540800 | Sí | Quimioterapia sí incluye alimentos y formas de preparación para boca dolorida. |
| 5 | Q | 76 | Alimentos para no lastimar una boca irritada | 0.538203 | No | Solo título/remisión de una lista, sin alimentos en el chunk. |

Alimentación aparece primero, pero no responde la preparación solicitada. El cruce útil con Quimioterapia está en rank 4. Su propia sección de alimentación para mucositis también está persistida.

### MD10

Mi mamá está bajando de peso durante el tratamiento del cáncer. ¿Cómo puedo enriquecer sus comidas para ayudarla a mantener el peso?

Fuente esperada: **Consejos de alimentación: antes, durante y después del tratamiento del cáncer**. Referencia documental previa: Pérdida de peso / Formas de agregar proteína y calorías, p. 43, 44, 57, 58, 59, 60, 61.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **No**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | A | 3 | Acerca de esta publicación | 0.635934 | No | Introducción del folleto; no enseña a enriquecer comidas. |
| 2 | A | 43 | ¿Por qué pasa? | 0.620158 | No | Causas de pérdida de peso; no da medidas. |
| 3 | A | 42 | ¿Qué más puedo hacer? | 0.614383 | No | Habla de AUMENTO de peso y dieta para bajarlo: dirección opuesta a la consulta. |
| 4 | A | 44 | Consejos para controlar los problemas de alimentación | 0.593311 | Sí | Contenido sobre mantener/recuperar peso mediante alimentos ricos en calorías/proteínas; pertinente, aunque sin lista detallada de ingredientes. |
| 5 | A | 3 | problemas de alimentación | 0.589955 | No | Descripción de temas de la publicación; no contenido específico. |

Fallo de contexto relevante: aumento de peso en rank 3 desplaza pérdida de peso en rank 4. La sección con ejemplos concretos para enriquecer comidas de p. 43 existe en la base y tampoco está en Top-5.

### MD11

Mi familiar va a empezar radioterapia. ¿Qué efectos secundarios puede tener y de qué depende que aparezcan?

Fuente esperada: **La radioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: Efectos secundarios de la radioterapia, p. 25, 26, 27.

Top-1 pertinente: **No**. Top-3 contiene pertinente: **No**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | R | 56 | Sobre efectos secundarios | 0.805217 | No | Pregunta para hacer al equipo con Blank lines for answer; no es respuesta. |
| 2 | R | 56 | ¿Qué clase de efectos secundarios tardíos deberé esperar después de que termine la radioterapia? | 0.752422 | No | Otra pregunta con líneas en blanco. |
| 3 | R | 56 | ¿Desaparecerán estos efectos secundarios después de que termine   la radioterapia? | 0.709944 | No | Otra pregunta con líneas en blanco. |
| 4 | R | 25–26 | Efectos secundarios comunes | 0.706381 | Sí | Enumera efectos secundarios y relación con área tratada; responde ambas partes. |
| 5 | R | 3 | Este libro cubre: | 0.675214 | No | Presentación del contenido del libro, no explicación sustantiva de los efectos. |

Los tres primeros resultados son formularios de preguntas. La respuesta documental está en rank 4 pese a que Top-1 tiene similitud 0.805217.

### MD12

Mi papá está agotado desde que empezó la radioterapia. ¿Cómo puedo ayudarlo a manejar el cansancio en casa?

Fuente esperada: **La radioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: Fatiga, p. 30, 31, 32.

Top-1 pertinente: **Sí**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | R | 31–32 | Formas de controlarla | 0.629729 | Sí | Planificación, ayuda familiar y manejo de energía durante radioterapia. |
| 2 | R | 30 | ¿Cuánto tiempo dura? | 0.586107 | No | Duración de la fatiga; no manejo doméstico. |
| 3 | R | 31 | Formas de controlarla | 0.577575 | Sí | Descanso y actividades para manejar fatiga. |
| 4 | R | 13 | Después de haber terminado la radioterapia, ¿en qué síntomas me deberé fijar? | 0.555848 | No | Vigilancia de síntomas DESPUÉS del tratamiento; no manejo de fatiga durante radioterapia. |
| 5 | R | 30 | Fatiga | 0.555441 | No | Define fatiga y causas; no ofrece acciones. |

La fuente y el contenido de manejo de fatiga están en Top-1 y Top-3. Algunos resultados posteriores no contestan la necesidad.

### MD13

A mi mamá se le está irritando la piel donde recibe radioterapia. ¿Cómo debemos cuidarla y qué debemos evitar?

Fuente esperada: **La radioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: Cambios en la piel, p. 46, 47, 48.

Top-1 pertinente: **Sí**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | R | 47 | Formas de controlarlos | 0.742970 | Sí | Cuidados específicos de la piel irradiada y productos/acciones que evitar. |
| 2 | R | 48 | Formas de controlarlos | 0.673469 | Sí | Precauciones para piel irradiada y comunicación de cambios al equipo. |
| 3 | Q | 37 | Qué hacer para controlar los cambios en la piel y en las uñas: | 0.666481 | No | Quimioterapia trata uñas y radiation recall tras radioterapia previa; no equivale a cuidado habitual durante irradiación actual. |
| 4 | R | 46 | Cambios en la piel | 0.659519 | Sí | Describe cambios y una precaución explícita para evitar rascarse; aporte parcial. |
| 5 | R | 47–48 | Formas de controlarlos | 0.603406 | Sí | Ropa, protección solar y precauciones durante radioterapia. |

Cruce de contexto no pertinente en rank 3: radiation recall y uñas desde Quimioterapia. No desplazó al Top-1 correcto, pero entra en Top-3 y debe mantenerse distinguido.

### MD14

Mi familiar está recibiendo radioterapia. ¿Necesita comer de alguna forma especial para mantener sus fuerzas y su peso?

Fuente esperada: **La radioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: ¿Deberé seguir una dieta especial mientras reciba radioterapia?, p. 10, 59.

Top-1 pertinente: **Sí**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | R | 10 | ¿Deberé seguir una dieta especial mientras reciba radioterapia? | 0.722090 | Sí | Necesidades de calorías/proteínas y mantenimiento de peso en radioterapia. |
| 2 | R | 12 | ¿Cómo aprovecho al máximo la radioterapia? | 0.591867 | Sí | Autocuidado y comunicación sobre alimentación/peso; complemento parcial. |
| 3 | R | 31–32 | Formas de controlarla | 0.582509 | Sí | Medidas de alimentación dentro del manejo de fatiga; complemento parcial. |
| 4 | R | 49–50 | Formas de controlarlos | 0.563811 | Sí | Alimentación calórica/proteica cuando hay garganta irritada; pertinente solo bajo esa condición explícita. |
| 5 | R | 10 | ¿Puedo seguir trabajando durante la radioterapia? | 0.550943 | No | El grueso trata trabajo y bajas laborales; la remisión final a consultar dieta no aporta contenido suficiente sobre alimentación. |

Los cinco resultados son de Radioterapia. Top-1 responde claramente; no se produjo cruce con Alimentación en esta consulta.

### MD15

Voy a acompañar a mi papá durante la radioterapia. ¿Qué cuidados diarios y hábitos le ayudan a llevar mejor el tratamiento?

Fuente esperada: **La radioterapia y usted: Apoyo para las personas con cáncer**. Referencia documental previa: ¿Cómo aprovecho al máximo la radioterapia?, p. 12.

Top-1 pertinente: **Sí**. Top-3 contiene pertinente: **Sí**. Fuente esperada recuperada en Top-5: **Sí**.

| Rango | Documento | Página | Sección | Similitud | Pertinente | Motivo manual |
|---:|---|---|---|---:|---|---|
| 1 | R | 12 | ¿Cómo aprovecho al máximo la radioterapia? | 0.659160 | Sí | Autocuidado general, asistencia y comunicación con el equipo durante radioterapia. |
| 2 | R | 31 | Formas de controlarla | 0.617280 | Sí | Hábitos de descanso y actividad para fatiga. |
| 3 | R | 10 | ¿Deberé seguir una dieta especial mientras reciba radioterapia? | 0.568020 | Sí | Alimentación y mantenimiento del peso durante radioterapia. |
| 4 | R | 19 | ¿Cómo podré relajarme durante las sesiones de tratamiento? | 0.565969 | Sí | Actividades para relajarse en sesiones; apoyo práctico. |
| 5 | R | 47 | Formas de controlarlos | 0.555195 | Sí | Cuidados de piel irradiada como parte del autocuidado diario. |

Top-1 y Top-3 pertinentes; todos los resultados conservan el contexto de Radioterapia.

## Verificación y límites de esta entrega

Se comprobaron correspondencia chunk/embedding por versión, hashes PDF/base, configuración 768d/450/75, estado retirado del sintético, ausencia de INEN y de índices ANN, y el plan SQL de búsqueda. Se verificó que cada resultado pertenece a una versión activa de los tres NCI y conserva página, sección y texto; que hay 15 consultas y 75 resultados; y que la evidencia anterior y Q01–Q10 conservan sus hashes.

El corpus multidocumento funciona técnicamente y este baseline deja sus fallos visibles. No se cambiaron limpieza, chunking ni ranking para mejorar el resultado; no se ejecutaron Qwen3, BGE-M3, reranking, búsqueda híbrida ni generación con LLM. La ingesta autorizada de los NCI y la evaluación documental no constituyen una certificación de vigencia clínica. Las decisiones de futuros cambios quedan fuera de esta fase.

## Reproducción

Ingestas realizadas (sin `--reindex`, sin ignorar advertencias OCR):

```bash
HF_HUB_OFFLINE=1 EMBEDDING_DEVICE=cuda CHUNK_SIZE_TOKENS=450 CHUNK_OVERLAP_TOKENS=75 .venv/bin/python scripts/ingest_pdf.py corpus/aprobados/nci_consejos_alimentacion_2024.pdf
HF_HUB_OFFLINE=1 EMBEDDING_DEVICE=cuda CHUNK_SIZE_TOKENS=450 CHUNK_OVERLAP_TOKENS=75 .venv/bin/python scripts/ingest_pdf.py corpus/aprobados/nci_radioterapia_y_usted.pdf
```

Para repetir las consultas conservando estos resultados, use **otro nombre de salida** (el runner existente puede sobrescribir un archivo si se reutiliza su nombre):

```bash
HF_HUB_OFFLINE=1 EMBEDDING_DEVICE=cuda CHUNK_SIZE_TOKENS=450 CHUNK_OVERLAP_TOKENS=75 .venv/bin/python scripts/run_queries.py --consultas eval/consultas_multidocumento_v01.json --top-k 5 --salida eval/resultados/alia_multidocumento_v01_repeticion.json
```
