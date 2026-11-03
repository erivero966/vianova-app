# Revisión manual: INEN, paciente oncológico inmunodeprimido

**Dictamen: NO APTO para la ingesta de los 130 chunks actuales.**

Revisión documental del 3 de noviembre de 2026. Se revisaron completos **36 chunks: 2 CORRECTOS, 13 ACEPTABLES y 21 PROBLEMÁTICOS**. La selección cubre las secciones solicitadas y casos de riesgo; no es una muestra aleatoria y sus proporciones no estiman la tasa de error de todo el documento. Los 94 chunks restantes no reciben una clasificación manual individual.

La reducción de títulos mejoró la segmentación, pero persisten números/unidades alterados, pérdida de filas y fragmentación del contexto. Excluir únicamente las páginas 28–39 dejaría errores relevantes en las páginas 9, 15, 22, 24, 25, 44 y 46, entre otras. Esta revisión no aprueba un subconjunto alternativo ni aplica exclusiones.

[Inventario de los 130 chunks y los 68 títulos](ocr_inen_inmunodeprimido_chunks_review.md) · [Texto completo y metadatos JSON](ocr_inen_inmunodeprimido_chunks_review.json).

## Alcance y reproducibilidad

Se utilizó el pipeline existente de extracción, limpieza y segmentación, con origen `ocr`, estrategia `estructura_textual_ocr`, tamaño 450 y solapamiento 75 tokens. Solo se cargó el tokenizer de ALIA para contar tokens; no se ejecutaron modelos de embeddings, LLM, Qwen3, BGE-M3, retrieval, Q04, ingesta ni conexiones a PostgreSQL.

Se crearon el script solicitado `scripts/review_chunks.py`, el inventario Markdown/JSON, este informe y representaciones PNG del original. No se modificaron los algoritmos existentes, los PDFs, la ficha de procedencia ni la base de datos. Las recomendaciones de clasificación/exclusión que siguen son documentales.

Las páginas citadas son **páginas físicas del PDF, empezando en 1**, no la numeración impresa. Por ejemplo, la página física 24 dice «Pag. N° 20». Las imágenes proceden del PDF INEN original; los PNG `rot90` giran la vista para leer las tablas, sin modificar ningún PDF ni ejecutar OCR.

| Propiedad | Valor reproducido |
|---|---|
| Páginas / páginas con texto | 50 / 49; página 42 sin texto extraído |
| Caracteres / ilegibles Unicode | 89 448 / 0,00 % |
| Títulos | 68 apariciones, 64 textos distintos |
| Chunks / con sección / multipágina | 130 / 129 / 48 |
| Tokens mínimo / promedio / máximo | 19 / 329,6 / 450 |
| Tipo actual de los chunks | Los 130 son `contenido` |
| Candidatos tipográficos descartados / rótulos neutralizados | 2528 / 54 |
| Páginas con orientación no fiable según diagnóstico existente | 28–39 |

El 0,00 % de caracteres ilegibles mide caracteres Unicode anómalos, no la exactitud de palabras, cifras, unidades o estructura. Las tablas destruidas siguen usando caracteres válidos.

Hashes SHA-256 de la revisión:

```text
Original:   b51a7c637b6a09268583e5c02a6ad8281a2f7a6417b9ec16da832253d777de25
Derivado:   9e8fcd1471c07c9c759713b9e12d6a9d71840e8318a1138cfb4df7b3293e7263
Provenance: 792c574b54493450624dfdf3245c1706b46d4905e08898f61e5f71e6b7f710ff
```

El original sigue siendo `corpus/aprobados/inen_paciente_oncologico_inmunodeprimido_2020.pdf`; el PDF de `corpus/ocr/` es su derivado técnico. Los IDs Cxxx son temporales, asociados a estos hashes y configuración.

## Muestra manual de 36 chunks

Se leyó el texto completo, incluyendo sus finales, y se contrastó con las páginas originales. «ACEPTABLE» significa comprensible como extracción documental; no equivale a aprobar su utilización clínica. Una alteración del símbolo de grados se distingue de la pérdida de una cantidad, una unidad dimensional o una fila. La columna de sección describe la sección asignada; cuando difiere del contenido real se señala explícitamente.

| Chunk | Páginas | Sección asignada / cobertura | Clasificación | Hallazgo y efecto |
|---|---:|---|---|---|
| [C001](ocr_inen_inmunodeprimido_chunks_review.md#c001) | 1 | Sin sección; inicio administrativo | ACEPTABLE | `AEPUBLICA DEL PERy` y número de resolución ruidoso. No contiene instrucciones clínicas; identificación documental debe apoyarse en el original. |
| [C004](ocr_inen_inmunodeprimido_chunks_review.md#c004) | 1 | `DE ENFERMERÍA EN LA ATENCION DEL PACIENTE ONCOLÓGICO` | PROBLEMÁTICO | Solo 19 tokens de una oración de la resolución, promovidos a título y separados de su continuación. |
| [C005](ocr_inen_inmunodeprimido_chunks_review.md#c005) | 1–2 | `TRESe` | PROBLEMÁTICO | Título espurio; comienza con `INMUNODEPRIMIDO, ha sido elaborado...`, separado del nombre del documento de C004. Hay una referencia al título truncada en p. 2. |
| [C015](ocr_inen_inmunodeprimido_chunks_review.md#c015) | 5 | `FINALIDAD` | ACEPTABLE | Párrafo continuo y comprensible; coma final en lugar del punto del original. |
| [C016](ocr_inen_inmunodeprimido_chunks_review.md#c016) | 5 | `OBJETIVOS`, incluye objetivo general | CORRECTO | Conserva finalidad operativa, riesgos de infección y estancia hospitalaria. |
| [C017](ocr_inen_inmunodeprimido_chunks_review.md#c017) | 5 | `2.2. OBJETIVOS ESPECIFICOS` | CORRECTO | Dos objetivos completos: estandarización y educación al paciente/familia; sin contaminación importante. |
| [C018](ocr_inen_inmunodeprimido_chunks_review.md#c018) | 5 | `. ÁMBITO DE APLICACIÓN:` | ACEPTABLE | Numeración romana del título perdida; alcance institucional y uso por otros establecimientos comprensibles. |
| [C023](ocr_inen_inmunodeprimido_chunks_review.md#c023) | 7 | `V. TÉRMINOS Y DIFINICIONES` | ACEPTABLE | Definiciones continuas, viñetas alteradas. `DIFINICIONES` ya está escrito así en el original. |
| [C025](ocr_inen_inmunodeprimido_chunks_review.md#c025) | 8 | Términos y definiciones | ACEPTABLE | Definiciones legibles, incluida fiebre; `38 °C` pasa a `38 *C`. Encabezado administrativo residual. |
| [C026](ocr_inen_inmunodeprimido_chunks_review.md#c026) | 8 | Términos y definiciones | ACEPTABLE | Fungemia, inmunosupresión y hemocultivos comprensibles; rango 24–48 horas conservado. Pie de página mezclado. |
| [C028](ocr_inen_inmunodeprimido_chunks_review.md#c028) | 9 | `EMISOR: DEPARTAMENTO DE ENFERMERÍA ON MS` | ACEPTABLE | Metadato de sección incorrecto; las definiciones individuales se identifican por su propio texto, incluida infección. No hay una oración clínica cortada en este chunk. |
| [C031](ocr_inen_inmunodeprimido_chunks_review.md#c031) | 10 | `EMISOR... ON MS`; definiciones | PROBLEMÁTICO | Inmunodepresión legible, pero definición de sepsis acaba en `...trata de forma`; sellos intercalados y sección administrativa ajena. |
| [C032](ocr_inen_inmunodeprimido_chunks_review.md#c032) | 10–11 | `EMISOR... ON MS`; sepsis | PROBLEMÁTICO | Repite la definición incompleta; incorpora pie y encabezado, pero no une `temprana...` de p. 11. |
| [C033](ocr_inen_inmunodeprimido_chunks_review.md#c033) | 11 | `EMISOR... O on` | PROBLEMÁTICO | Abre con `temprana, puede ocasionar daño irreversible...`, sin el antecedente «sepsis». El falso encabezado rompe el contexto. |
| [C039](ocr_inen_inmunodeprimido_chunks_review.md#c039) | 14 | `+ ANTIBIÓTICOS:` | PROBLEMÁTICO | Nombre `Sulfametoxazo!` alterado, numerosos `SN` de viñetas. La entrada `Piperaciclina 4.5 mg` coincide con el original: anomalía de fuente, no error atribuible al OCR. |
| [C041](ocr_inen_inmunodeprimido_chunks_review.md#c041) | 14 | `e ANTIVIRALES:` | ACEPTABLE | Aciclovir 250 mg y 200 mg conservados; `Y` sustituye las marcas de lista. |
| [C043](ocr_inen_inmunodeprimido_chunks_review.md#c043) | 14–15 | `. CITOSTÁTICOS:` | PROBLEMÁTICO | `Ifosfamida` pasa a `lfostamida`; pies/encabezados interrumpen el listado. Algunas concentraciones sí se conservan, como `0,5 mg`. |
| [C045](ocr_inen_inmunodeprimido_chunks_review.md#c045) | 15 | `+ SOLUCIONES:` | PROBLEMÁTICO | `1000 ml` y `100 ml` pasan a `1000 mi` y `100 mi`; pérdida de unidad en volúmenes. |
| [C054](ocr_inen_inmunodeprimido_chunks_review.md#c054) | 19–20 | Hospitalización | ACEPTABLE | Medidas de aislamiento y lista de síntomas completas. Comienza con continuación y acaba cortando el punto siguiente, recuperado en C055; hay ruido administrativo. |
| [C055](ocr_inen_inmunodeprimido_chunks_review.md#c055) | 20 | Hospitalización | ACEPTABLE | Síntomas y comunicación al oncólogo legibles; conserva 38.3, 38.0 y 1 hora. Cambia ° por * y arrastra pie de página. |
| [C056](ocr_inen_inmunodeprimido_chunks_review.md#c056) | 21 | `EPEZP` | PROBLEMÁTICO | Sección ficticia para actuaciones ante fiebre; encabezado ruidoso. La frase `60 minutos mínimo` procede del original y discrepa de otras páginas de la propia guía. |
| [C059](ocr_inen_inmunodeprimido_chunks_review.md#c059) | 22–23 | `EPEZP` | PROBLEMÁTICO | `500 ml` → `500 mil`, `60 ml` → `60 mil`; fórmula fragmentada respecto de C058. Texto de limpieza y encabezados intercalados. |
| [C063](ocr_inen_inmunodeprimido_chunks_review.md#c063) | 24 | Catéteres venosos centrales | PROBLEMÁTICO | Frecuencia de curación `cada 7 días` → `cada Y días`. El resto del párrafo legible no compensa esa pérdida. |
| [C065](ocr_inen_inmunodeprimido_chunks_review.md#c065) | 25 | Cuidados durante plaquetopenia | PROBLEMÁTICO | `cel./mm³` se convierte en `cel, Im?` y `cel./mm*`; grado II pasa a `11`. Números 20 000 y 50 000 sobreviven con unidades/grado dañados. |
| [C067](ocr_inen_inmunodeprimido_chunks_review.md#c067) | 26 | Plaquetopenia; incluye cuidados emocionales | PROBLEMÁTICO | Mezcla secciones 7.2.3 y 7.2.4. Empieza `minutos a 1 hora` sin el inicio «30» de la oración. Apoyo a familia legible pero con sección incorrecta. |
| [C068](ocr_inen_inmunodeprimido_chunks_review.md#c068) | 26 | `7.3. ALTA DEL PACIENTE:` | ACEPTABLE | Alta y documentos comprensibles; marcas de verificación convertidas en `Y`. |
| [C070](ocr_inen_inmunodeprimido_chunks_review.md#c070) | 27–28 | Pie institucional de p. 26 | PROBLEMÁTICO | Consejería domiciliaria legible contaminada por texto invertido de la tabla siguiente. |
| [C081](ocr_inen_inmunodeprimido_chunks_review.md#c081) | 30 | Pie institucional de p. 26 | PROBLEMÁTICO | Tabla de riesgo de infección destruida: `UOIO9aJul`, `soubis`, caracteres y columnas sin orden; no conserva relaciones clínicas. |
| [C101](ocr_inen_inmunodeprimido_chunks_review.md#c101) | 37 | Pie institucional de p. 26 | PROBLEMÁTICO | Tabla de salud oral ilegible; palabras invertidas, celdas y escalas mezcladas. |
| [C108](ocr_inen_inmunodeprimido_chunks_review.md#c108) | 39–40 | Pie institucional de p. 26 | PROBLEMÁTICO | Texto invertido y encabezado de p. 40; absorbe `7.5. INDICADORES` sin cambiar la sección asignada. |
| [C114](ocr_inen_inmunodeprimido_chunks_review.md#c114) | 44–45 | `GRADOS DE NEUTROPENIA` | PROBLEMÁTICO | Grados 2 y 3 quedan después de sus parámetros; `células/mm3` se altera a `célulasimm3` / `células/imm3`. Asociación fila–grado ambigua en texto lineal. |
| [C115](ocr_inen_inmunodeprimido_chunks_review.md#c115) | 45–46 | `ANEXO N* 03` | ACEPTABLE | Escala de mucositis reproducida, con pie/encabezado residual. La secuencia 0,1,2,4 también existe en el original; no se atribuye al OCR ni se corrige. |
| [C117](ocr_inen_inmunodeprimido_chunks_review.md#c117) | 46–47 | `GRADOS DE PLAQUETOPENIA` | PROBLEMÁTICO | Falta la fila completa de grado 2 (50 000–75 000), además de etiquetas de otros grados; fuente y encabezados mezclados. |
| [C121](ocr_inen_inmunodeprimido_chunks_review.md#c121) | 47 | `N? ITEMS` | PROBLEMÁTICO | Checklist linealizado con números 1→4, 2→9 y 11→41; unidades de recuento dañadas y números de fila incrustados en recomendaciones. |
| [C124](ocr_inen_inmunodeprimido_chunks_review.md#c124) | 48 | `EMISOR... Implementación` | PROBLEMÁTICO | Invierte el orden de líneas dentro de varias filas: `16 tiempo posible... Administra...`; mezcla continuaciones y adopta un encabezado administrativo. |
| [C129](ocr_inen_inmunodeprimido_chunks_review.md#c129) | 50 | `IX. BIBLIOGRAFÍA` | ACEPTABLE | Referencias reconocibles, pero 17→47 y se pierde el número 21. No es evidencia de recomendaciones clínicas por sí misma. |

**Recuento de esta tabla:** CORRECTO 2; ACEPTABLE 13; PROBLEMÁTICO 21; total 36. Los 130 textos completos están en el inventario, no solo sus primeros 500 caracteres.

## Falsos títulos: contexto e impacto

Se distingue una detección de título de su uso posterior como metadato `section`: no todas las detecciones terminan asignadas a un chunk. El JSON registra ambos vínculos.

| Título / IDs | Página | Chunks y texto alrededor | Impacto observado |
|---|---:|---|---|
| `AEPUBLICA DEL PERy` / H001 | 1 | C001: después del nombre del instituto y número de resolución. [Original](ocr_inen_inmunodeprimido_evidencia/original_p001.png). | El arco del escudo dice «REPUBLICA DEL PERU». Ruido administrativo y candidato de título falso; C001 mantiene sección nula. Impacto local, principalmente cosmético, sin propagación de sección. |
| `DE ENFERMERÍA EN LA ATENCION DEL PACIENTE ONCOLÓGICO` / H003 | 1 | C004, seguido de C005 `INMUNODEPRIMIDO, ha sido elaborado...`. | Fragmento de una oración de resolución convertido en chunk de 19 tokens. No es un título independiente. |
| `TRESe` / H004 | 1 | Texto en C005; sección de C005–C006 (p. 1–2). [Original p. 1](ocr_inen_inmunodeprimido_evidencia/original_p001.png), [p. 2](ocr_inen_inmunodeprimido_evidencia/original_p002.png). | No corresponde a un título visible. Rompe el enlace del nombre del documento entre páginas y rotula dos chunks administrativos. Efecto estructural, aunque no clínico directo. |
| `1d PEZ` / H027 | 9 | C027: seguido de `GUÍA TÉCNICA... Código...`; solo 61 tokens. [Original](ocr_inen_inmunodeprimido_evidencia/original_p009.png). | Artefacto de la cabecera, crea un chunk administrativo sin definiciones. |
| `EMISOR... ON MS` / H028 y `EMISOR... O on` / H029 | 9, 11 | C028–C032 y C033. Final de C032 `...trata de forma`; inicio de C033 `temprana, puede ocasionar daño irreversible...`. | Sustituyen «Términos y definiciones» y cortan la definición de sepsis. Efecto contextual real; no es solo mala ortografía del título. |
| `EPEZP` / H042 | 21 | C056 contiene el artefacto; sección heredada por C056–C060, p. 21–23: fiebre, cultivos, salud oral y limpieza. [Original](ocr_inen_inmunodeprimido_evidencia/original_p021.png). | No hay tal título visual. Cinco chunks clínicos reciben una sección sin significado. |
| `INSTITUTO NACIONAL DE ENFERMEDADES NEOPLÁSICAS Pag. N” 22` / H047 | 26 | Pie al terminar el alta; C069–C108, desde p. 26–40. [Original](ocr_inen_inmunodeprimido_evidencia/original_p026.png). | **40 chunks** con el pie como sección: continuidad del alta, tablas y principio de indicadores. Es la propagación falsa más extensa detectada. |
| `FUENT` / H057 | 46 | C116: `EMISOR... FUENT GUÍA TÉCNICA ANEXO N' 04`. [Original](ocr_inen_inmunodeprimido_evidencia/original_p046.png). | Fragmento de «FUENTE», leído fuera de lugar. No se usa como sección, pero deja un chunk de 29 tokens sin contenido del anexo. |
| `INMUNODEPRIMIDO` / H012 y H062 | 3, 47 | Se asigna a C120, con `Cumplimiento` y dirección institucional. | Palabra real dentro del título largo; en p. 47 su aislamiento no representa una sección clínica. C120 queda administrativo. |
| `N? ITEMS` y `SI NO` / H063–H064 | 47 | C121–C122: encabezados de columnas del checklist, seguidos de actuaciones ante neutropenia y fiebre. [Original](ocr_inen_inmunodeprimido_evidencia/original_p047.png). | Columnas convertidas en títulos; C122 hereda `SI NO`. Pérdida del contexto del anexo y estructura tabular. |
| `EMISOR: DEPARTAMENTO DE ENFERMERÍA Implementación` / H019, H060, H066 | 5, 47, 48 | C014, C118, C124; este último `15 oncólogo: Radiografía... Verifica...`. | Tres detecciones del mismo texto. El encabezado pasa a sección; en C124 oculta la continuidad del checklist. |

Las consecuencias sobre recuperación se infieren del texto y metadatos producidos: secciones falsas, fragmentos sin antecedente y ruido indexable. **No se midieron rankings, recall ni resultados de retrieval.**

## Páginas 28–39: tablas clínicas con OCR inutilizable

Se compararon visualmente **las 12 páginas** con sus textos OCR. Son tablas de plan de cuidados, con diagnóstico de enfermería, resultados NOC, intervenciones NIC, complicaciones y escalas. No son meros adornos ni, en esta ubicación, anexos: forman parte de la sección 7.4. El original es legible al girar la vista; la capa OCR contiene palabras invertidas/deformadas y celdas entremezcladas.

| Página física / evidencia visual | Chars OCR | Chunks que intersectan la página | Contenido visible en el original |
|---|---:|---|---|
| [28](ocr_inen_inmunodeprimido_evidencia/original_p028_rot90.png) | 1874 | C070–C074 (5) | Inicio de tabla 01; afrontamiento, ansiedad y apoyo emocional. |
| [29](ocr_inen_inmunodeprimido_evidencia/original_p029_rot90.png) | 1704 | C074–C078 (5) | Hipertermia y proceso infeccioso; fiebre, vigilancia y antibióticos. |
| [30](ocr_inen_inmunodeprimido_evidencia/original_p030_rot90.png) | 1970 | C078–C082 (5) | Riesgo de infección, inmunosupresión y educación a paciente/familia sobre signos. |
| [31](ocr_inen_inmunodeprimido_evidencia/original_p031_rot90.png) | 1190 | C082–C085 (4) | Control de infecciones, manos y dispositivos intravasculares. |
| [32](ocr_inen_inmunodeprimido_evidencia/original_p032_rot90.png) | 1337 | C085–C088 (4) | Mantenimiento de catéteres periféricos, apósitos e intervalos. |
| [33](ocr_inen_inmunodeprimido_evidencia/original_p033_rot90.png) | 1235 | C088–C091 (4) | Continuación periféricos y cuidados de catéter venoso central. |
| [34](ocr_inen_inmunodeprimido_evidencia/original_p034_rot90.png) | 1260 | C090–C093 (4) | CVC: volúmenes de lavado, limpieza y signos de infección. |
| [35](ocr_inen_inmunodeprimido_evidencia/original_p035_rot90.png) | 1724 | C093–C097 (5) | Riesgo de sangrado y trombocitopenia; restricciones y prevención. |
| [36](ocr_inen_inmunodeprimido_evidencia/original_p036_rot90.png) | 1127 | C097–C100 (4) | Continuación de cuidados ante sangrado; hidratación y transfusión. |
| [37](ocr_inen_inmunodeprimido_evidencia/original_p037_rot90.png) | 1749 | C099–C103 (5) | Mucosa oral, mucositis, higiene y enjuagues. |
| [38](ocr_inen_inmunodeprimido_evidencia/original_p038_rot90.png) | 938 | C103–C105 (3) | Hemoderivados, tiempos y reacciones transfusionales. |
| [39](ocr_inen_inmunodeprimido_evidencia/original_p039_rot90.png) | 1152 | C105–C108 (4) | Salud bucal, preparación de colutorios y manejo del dolor. |

Son **39 chunks únicos, C070–C108**, no la suma de las incidencias por página. **37** quedan enteramente dentro de p. 28–39 (C071–C107); C070 cruza 27–28 y C108 cruza 39–40. La contaminación alcanza, por tanto, chunks con texto vecino útil.

Ejemplo de p. 30/C081: `UOIO9aJul “uOlD0ayul ... soubis ... oBsaly`; no permite reconstruir de forma fiable «riesgo de infección», signos y sus relaciones. En p. 37/C101 aparecen `ejsaes eluedojenbejdua` y columnas de escalas intercaladas con cuidados orales. Reconocer alguna palabra aislada no hace utilizable el chunk.

**Recomendación documental:** excluir estos 39 chunks del retrieval normal mientras mantengan este texto; conservar originales y trazabilidad. Si en una etapa posterior se recupera la estructura, su clasificación apropiada sería `tabla`, con descripción de plan de cuidados NIC/NOC. No conviene etiquetarlos todos como `anexo` o `diagrama`. **No se aplicó ninguna exclusión ni reclasificación.** Tampoco basta esa exclusión para aprobar los demás chunks.

## Contraste visual de 36 ejemplos sensibles

Se buscaron números, unidades, medicamentos, dosis y frecuencias en **las 50 páginas de texto OCR**, y se seleccionaron los siguientes casos para cotejo visual. «Sí» significa coincidencia con lo que se ve en el original, no validación de la indicación médica. Se normaliza únicamente el espaciado de la transcripción visual; la columna OCR conserva el texto relevante extraído.

No apareció `mL` literal en la capa OCR ni `°C` contiguo; sí `ml`, `mi`, `mil` y `*C`. Esa ausencia no prueba ausencia de volúmenes/temperaturas en el original. «Dosis» aparece en instrucciones de comprobación de p. 18–19; los mg del listado de recursos son presentaciones, no una pauta individual que se deba inferir. No se encontró un caso demostrado de 10→100 mg o 0.5→05 mL: no se afirma que ocurrieran.

| Nº | Página / chunk / original visual | Texto original visible | Texto OCR | Correcto | Observación |
|---|---|---|---|---|---|
| 01 | [14](ocr_inen_inmunodeprimido_evidencia/original_p014.png), C039 | `Colistina 150 mg amp.` | `Colistina 150 mg amp.` | Sí | Nombre y cantidad preservados. |
| 02 | [14](ocr_inen_inmunodeprimido_evidencia/original_p014.png), C039 | `Linezolid 600 mg fco. amp.` | `Linezolid 600 mg fco. amp.` | Sí | Unidad y presentación preservadas. |
| 03 | [14](ocr_inen_inmunodeprimido_evidencia/original_p014.png), C040 | `Caspofungina 50 mg y 70 mg. amp.` | `Caspofungina 50 mg y 70 mg. amp.` | Sí | Dos cantidades, sin fusión. |
| 04 | [14](ocr_inen_inmunodeprimido_evidencia/original_p014.png), C043 | `Actinomicina 0,5 mg amp.` | `Actinomicina 0,5 mg amp.` | Sí | Coma decimal conservada. |
| 05 | [14](ocr_inen_inmunodeprimido_evidencia/original_p014.png), C042 | `Morfina 10 mg, 20 mg amp. y tabletas 30 mg` | `Morfina 10 mg, 20 mg amp. y tabletas 30 mg` | Sí | No se observa 10→100 en este caso. |
| 06 | [14](ocr_inen_inmunodeprimido_evidencia/original_p014.png), C041 | `Aciclovir 250 mg amp.` | `Aciclovir 250 mg amp.` | Sí | Viñeta alterada fuera del fragmento. |
| 07 | [15](ocr_inen_inmunodeprimido_evidencia/original_p015.png), C043 | `Ifosfamida 1gr amp.` | `lfostamida 1gr amp.` | No | Nombre del medicamento alterado: I/l y f/t. |
| 08 | [14](ocr_inen_inmunodeprimido_evidencia/original_p014.png), C039 | `Sulfametoxazol + Trimetropin` | `Sulfametoxazo! + Trimetropin` | No | l→! en el nombre; no se corrige «Trimetropin» de la fuente. |
| 09 | [15](ocr_inen_inmunodeprimido_evidencia/original_p015.png), C045 | `Agua destilada o estéril de 1000 ml` | `Agua destilada o estéril de 1000 mi` | No | Unidad ml→mi. |
| 10 | [15](ocr_inen_inmunodeprimido_evidencia/original_p015.png), C045 | `Cloruro de sodio al 0.9% de 100 ml` | `Cloruro de sodio al 0.9% de 100 mi` | No | Porcentaje conservado, unidad alterada. |
| 11 | [15](ocr_inen_inmunodeprimido_evidencia/original_p015.png), C045 | `Dextrosa al 5% de 100 ml, 250 ml, 500 ml y 1000 ml` | `Dextrosa al 5% de 100 ml, 250 ml, 500 ml y 1000 ml` | Sí | Contraste con los errores de la misma página. |
| 12 | [9](ocr_inen_inmunodeprimido_evidencia/original_p009.png), C029 | `7 a 10 días post- quimioterapia` | `7 a 10 días post- quimioterapia` | Sí | Rango temporal del nadir conservado. |
| 13 | [9](ocr_inen_inmunodeprimido_evidencia/original_p009.png), C029 | `menos 1 000/mm³` | `menos 1 000/mm?` | No | Exponente dimensional perdido; ruido de sello contiguo. |
| 14 | [20](ocr_inen_inmunodeprimido_evidencia/original_p020.png), C055 | `pico febril de 38.3 °C` | `pico febril de 38.3 *C` | No | Solo símbolo °→*; cifra preservada. No había ≥ en este original. |
| 15 | [20](ocr_inen_inmunodeprimido_evidencia/original_p020.png), C055 | `temperatura de 38.0 °C durante 1 hora` | `temperatura de 38.0 *C durante 1 hora` | No | Cifra y duración preservadas; símbolo alterado. |
| 16 | [20](ocr_inen_inmunodeprimido_evidencia/original_p020.png), C054 | `cada 8 horas` | `cada 8 horas` | Sí | Frecuencia de signos vitales conservada. |
| 17 | [21](ocr_inen_inmunodeprimido_evidencia/original_p021.png), C056 | `mayor a 39 °C` | `mayor a 39 *C` | No | «mayor a» conservado; cambia el símbolo. |
| 18 | [21](ocr_inen_inmunodeprimido_evidencia/original_p021.png), C056 | `cada 4 - 6 horas` | `cada 4 - 6 horas` | Sí | Rango/frecuencia conservados. |
| 19 | [22](ocr_inen_inmunodeprimido_evidencia/original_p022.png), C058 | `Clorhexidina 0.12%` | `Clorhexidina 0.12%` | Sí | Decimal y porcentaje conservados. |
| 20 | [22](ocr_inen_inmunodeprimido_evidencia/original_p022.png), C059 | `Agua estéril 500 ml.` | `Agua estéril 500 mil.` | No | ml→mil; la salida puede leerse como otra cantidad, pierde unidad. |
| 21 | [22](ocr_inen_inmunodeprimido_evidencia/original_p022.png), C059 | `Sulfametoxazol jarabe 30 ml.` | `Sulfametoxazol jarabe 30 ml.` | Sí | Nombre, volumen y unidad preservados aquí. |
| 22 | [22](ocr_inen_inmunodeprimido_evidencia/original_p022.png), C059 | `Hidróxido de aluminio solución 60 ml.` | `Hidróxido de aluminio solución 60 mil.` | No | Unidad y lectura de cantidad ambiguas. |
| 23 | [22](ocr_inen_inmunodeprimido_evidencia/original_p022.png), C059 | `Tiempo de duración de 24 horas.` | `Tiempo de duración de 24 horas.` | Sí | Duración conservada. |
| 24 | [22](ocr_inen_inmunodeprimido_evidencia/original_p022.png), C059 | `2 °C - 8 °C` | `2 *C -—8*C` | No | Valores conservados; símbolos y separador dañados. |
| 25 | [22](ocr_inen_inmunodeprimido_evidencia/original_p022.png), C059 | `de 4 - 6 veces al día` | `de 4 - 6 veces al día` | Sí | Frecuencia conservada. |
| 26 | [24](ocr_inen_inmunodeprimido_evidencia/original_p024.png), C063 | `catéter venoso central cada 7 días` | `catéter venoso central cada Y días` | No | Pérdida de la frecuencia numérica. |
| 27 | [24](ocr_inen_inmunodeprimido_evidencia/original_p024.png), C063 | `Clorhexidina al 2%` | `Clorhexidina al 2%` | Sí | Concentración conservada. |
| 28 | [24](ocr_inen_inmunodeprimido_evidencia/original_p024.png), C063 | `jeringa de 10 ml` | `jeringa de 10 ml` | Sí | Volumen conservado. |
| 29 | [24](ocr_inen_inmunodeprimido_evidencia/original_p024.png), C063 | `pulsos 1 ml cada vez` | `pulsos 1 ml cada vez` | Sí | Volumen por pulso conservado. |
| 30 | [25](ocr_inen_inmunodeprimido_evidencia/original_p025.png), C065 | `20 000 cel./mm³ (grado IV)` | `20 000 cel, Im? (grado IV)` | No | Cantidad conservada; unidad dimensional destruida. |
| 31 | [25](ocr_inen_inmunodeprimido_evidencia/original_p025.png), C065 | `1.5 litros - 2 litros al día` | `1.5 litros - 2 litros al día` | Sí | Decimal y rango conservados. |
| 32 | [44](ocr_inen_inmunodeprimido_evidencia/original_p044.png), C114 | `< 500 células/mm3` | `< 500 células/imm3` | No | Signo < y valor conservados, unidad alterada. |
| 33 | [44](ocr_inen_inmunodeprimido_evidencia/original_p044.png), C114 | `<100 células/mm3` | `<100 células/mm3` | Sí | Signo < y umbral de neutropenia profunda preservados. |
| 34 | [46](ocr_inen_inmunodeprimido_evidencia/original_p046.png), C117 | `Grado 2` / `Plaquetas de 50 000 a 75 000 células/mm3` | No aparece la fila en el texto OCR de p. 46 ni en C117 | No | Omisión completa, comprobada antes del chunking. |
| 35 | [45](ocr_inen_inmunodeprimido_evidencia/original_p045.png), C115 | `4 Eritema y ulceración: No puede tragar sólidos.` | `4 Eritema y ulceración: No puede tragar sólidos.` | Sí | La secuencia de la tabla original es 0,1,2,4; no se atribuye a OCR la ausencia de 3. |
| 36 | [21](ocr_inen_inmunodeprimido_evidencia/original_p021.png), C056 | `en 60 minutos mínimo` | `en 60 minutos mínimo` | Sí | Coincide con la fuente, aunque contradice otros pasajes; ver abajo. |

Son **21 coincidencias y 15 discrepancias**, contando la omisión de fila como discrepancia. Varias discrepancias son solo el símbolo de temperatura; no se equiparan en gravedad a perder una frecuencia, una fila o una unidad dimensional. El muestreo de casos sospechosos no permite estimar una tasa general de exactitud.

### Separación entre defectos de fuente, OCR y segmentación

- **Fuente:** `DIFINICIONES` en p. 7; `Piperaciclina 4.5 mg amp.` en p. 14; tabla de mucositis con grados 0,1,2,4 en p. 45. Se transcriben sin corregir ni atribuirlos al OCR.
- **Fuente:** p. 21 dice «60 minutos mínimo» para antibióticos, mientras p. 29 indica un máximo de 60 minutos y p. 48 dice «dentro de la primera hora». La discrepancia es visible en los originales y requiere revisión documental clínica; aquí no se decide cuál aplicar.
- **OCR/extracción previa al chunking:** `7`→`Y`, `ml`→`mil`, nombre `lfostamida`, unidad `mm?` y fila de plaquetopenia ausente ya en el texto completo de página.
- **Estructura/segmentación:** falsa sección `EPEZP`, pie institucional propagado, definición de sepsis separada, tabla sin relaciones entre celdas. No se cambió ninguna regla para corregirlos en esta tarea.

## Fragmentos útiles para la futura evaluación de infección

Esta es una localización manual, no una ejecución de Q04 ni una respuesta médica. Los extractos siguientes son del texto producido; se señala cuándo no permiten utilizar el chunk completo sin revisión.

| Página | Sección real / sección asignada | Chunk | Texto relevante y estado |
|---|---|---|---|
| 5 | Objetivo general / `OBJETIVOS` | C016 | `Disminuir la aparición de complicaciones y riesgos de infección durante y después de la estancia hospitalaria...`. Conservado; declara el objetivo, no enumera síntomas. |
| 8 | Definiciones / Términos y definiciones | C025 | `Fiebre: Respuesta del organismo a las infecciones, elevando la temperatura corporal por encima de los 38 *C.` Comprensible, símbolo alterado. |
| 8 | Definiciones / Términos y definiciones | C025–C026 | `Fungemia: Presencia de hongos en la sangre. Es más frecuente en pacientes con inmunosupresión.` Conservado. |
| 9 | Definiciones / `EMISOR... ON MS` | C028 | `Infección: Invasión del organismo por gérmenes patógenos que se reproducen y multiplican produciendo una enfermedad.` Conservado, sección equivocada. |
| 9 | Definiciones / `EMISOR... ON MS` | C029 | `Neutropenia: Reducción del recuento de neutrófilos sanguíneos...` y `Neutropenia febril... menos 1 000/mm? ... 38.3 *C ... 38.0 *C, durante 1 hora.` Existe contenido, pero sellos y unidad dañada impiden considerar fiable el fragmento completo. |
| 10 | Definiciones / `EMISOR... ON MS` | C031 | `...por su tratamiento (Ejemplo: Quimioterapia) presenta alteraciones en su sistema inmunológico y es susceptible de adquirir infecciones.` Pasaje legible; el mismo chunk incluye sepsis cortada. |
| 10–11 | Definición de sepsis / dos variantes `EMISOR...` | C031–C033 | `La sepsis es una urgencia médica y si no se diagnostica y trata de forma` / `temprana, puede ocasionar daño irreversible...`. Solo se comprende uniendo chunks separados; contexto actualmente defectuoso. |
| 20 | 7.2.1 Cuidados durante neutropenia / Hospitalización | C054–C055 | `Malestar general, deposiciones líquidas, dolor abdominal, lesiones de la piel, dificultad para respirar.` Lista legible y cotejada visualmente. |
| 20 | 7.2.1 Cuidados durante neutropenia / Hospitalización | C055 | `pico febril de 38.3 *C o temperatura de 38.0 *C durante 1 hora` y `comunica al médico oncólogo de guardia`. Valores/duración conservados; °→*. |
| 21 | Cuidados durante neutropenia / `EPEZP` | C057 | `expectoración asociada a fiebre` y `distensión, dolor abdominal o diarreas... enteritis neutropénica`. Fragmentos legibles, pero sección ficticia y contaminación administrativa. |
| 24 | CVC / Catéteres venosos centrales | C063 | `dolor en la piel del sitio de inserción, eritema local, irritación, supuración...`. Signos legibles; el mismo chunk contiene la frecuencia dañada `cada Y días`. |
| 25 | CVC / Catéteres venosos centrales | C064 | `escalofríos, fiebre, dolor en el sitio de inserción...` y `infección local o bacteriemia relacionada con el catéter`. El original también divide mal «manifestaciones» entre viñetas; hay encabezados mezclados. |
| 27 | Alta / Pie institucional | C070 | `Brinda consejería sobre cuidado domiciliario... indicación al paciente y familiares...`. No enumera signos de alarma; su final está contaminado por la tabla invertida. |
| 30 | Tabla de plan de cuidados / Pie institucional | C078–C082 | El original contiene educación a paciente/familia sobre signos de infección. La extracción invertida no conserva una formulación utilizable; C081 es evidencia del fallo. |
| 44 | Anexo 02 / Grados de neutropenia | C114 | Rangos numéricos presentes, pero orden grado–parámetro y algunas unidades están dañados. No usar la tabla linealizada como clasificación fiable. |

La frase exacta «signos de alarma» no aparece en el texto OCR buscado; sí existen síntomas y actuaciones relacionadas. La ausencia literal no demuestra ausencia del concepto en el original, especialmente en las tablas ilegibles. Hay información útil para una futura evaluación, pero existencia textual y aptitud de todo el chunk son criterios distintos.

## Evaluación inicial de los 68 títulos

El [inventario completo](ocr_inen_inmunodeprimido_chunks_review.md#inventario-de-títulos) lista **cada una de las 68 apariciones**, su página, número total de apariciones del mismo texto, chunk que lo contiene y motivo heurístico. Son 64 textos distintos: `EMISOR: DEPARTAMENTO DE ENFERMERÍA Implementación` aparece 3 veces; `INMUNODEPRIMIDO` e `INSTITUTO NACIONAL DE ENFERMEDADES NEOPLÁSICAS` aparecen 2 veces cada uno. Los demás, una vez.

| Grupo inicial | Apariciones | Lectura manual de la clasificación |
|---|---:|---|
| Probablemente válido | 27 | Incluye títulos reales de objetivos, cuidados, anexos y bibliografía, pero también los encabezados de columna `N? ITEMS` y `SI NO` y el fragmento H003. No son 27 títulos validados. |
| Probablemente ruido OCR | 6 | H005 `\| \| SE RESUELVE:`, H017 `> Departamento de Oncología Médica`, H032 `+ ANTIBIÓTICOS:`, H035 `Y” ANALGESICOS:`, H037 `+ SOLUCIONES:`, H038 `+. OTROS MEDICAMENTOS:`. El texto semántico puede ser legítimo y el ruido limitarse al prefijo; no excluirlos automáticamente. |
| Dudoso | 35 | Incluye artefactos como `TRESe`, `1d PEZ`, `EPEZP`, rótulos administrativos y también títulos reales de una palabra (`FINALIDAD`, `OBJETIVOS`). Necesita contexto. |

La clasificación es una ayuda de revisión contenida exclusivamente en el script de informe. No se entrega al cleaner ni al chunker y **no debe usarse como lista de exclusión**. El análisis manual anterior identifica los errores estructurales más importantes y las limitaciones de la heurística.

## Decisión y condiciones pendientes

**NO APTO.** El conjunto actual contiene errores OCR que pueden alterar información clínica, incluso fuera de las tablas giradas. La evidencia más directa es `cada 7 días`→`cada Y días`, `500 ml`→`500 mil`, unidades de recuento destruidas y desaparición de una fila de clasificación de plaquetopenia. Además, la sección falsa que arrastran 40 chunks y la definición de sepsis cortada perjudican el contexto.

Para poder reconsiderar posteriormente una ingesta limitada haría falta delimitar un subconjunto explícito, verificar todos sus datos sensibles y revisar sus límites con chunks excluidos; las tablas requerirían preservar las relaciones entre filas y columnas. Eso queda pendiente y no se implementó en esta revisión. La decisión no implica que los 130 chunks sean todos ilegibles ni que el original carezca de valor.

La ficha de procedencia conserva su estado pendiente de revisión y `indexable: false`. No se aprobaron documentos ni se modificaron archivos existentes del corpus, algoritmos o base de datos.

## Uso del script de revisión

```bash
.venv/bin/python scripts/review_chunks.py \
  corpus/ocr/inen_paciente_oncologico_inmunodeprimido_2020_ocr.pdf
```

Ese comando genera el inventario solicitado cuando no existe. El script rechaza sobrescribir informes existentes; para reproducirlo conservando esta revisión:

```bash
HF_HUB_OFFLINE=1 .venv/bin/python scripts/review_chunks.py \
  corpus/ocr/inen_paciente_oncologico_inmunodeprimido_2020_ocr.pdf \
  --salida eval/ocr_inen_inmunodeprimido_segunda_chunks_review.md
```

`--paginas-visuales 1,5,14,20,24,44,46,50` permite generar imágenes del original para inspección, sin ejecutar OCR. El modo offline presupone el tokenizer ya disponible localmente, como en esta revisión. Los informes reproducidos no constituyen una nueva revisión manual ni una autorización de ingesta.

Comprobaciones completadas: sintaxis y ayuda del script; ejecución real que generó 130 chunks y 68 títulos; rechazo de sobrescritura conservando los hashes de Markdown/JSON; enlaces de evidencia existentes; recuentos de la muestra y de las tablas; contraste de los extractos OCR citados con el JSON. Los hashes de original, derivado y procedencia permanecen iguales. También se verificó que extractor, cleaner, chunker, pipeline e `inspect_pdf.py` conservan los hashes registrados al inicio. No se ejecutaron pruebas de integración que requirieran modelos o base de datos.
