# Baseline después de limpieza estructural — ALIA · 450/75 · búsqueda exacta

Fecha: 2026-10-23 · Resultados crudos: `eval/resultados/alia_450_75_cleaned_20261023.json`  
Comparación: `eval/baseline_alia_450_75.md` · Banco fijo: `eval/consultas_baseline.json` (sin modificaciones).

Inspección técnica/manual. **No** es una evaluación clínica ni un ajuste de retrieval. Se corrigieron exclusivamente los problemas estructurales 1–4: maquetación repetitiva, continuidad de chunking, frontera entre secciones e índice fuera de la recuperación normal.

## Configuración preservada

| Parámetro | Valor |
|---|---|
| Documento | La quimioterapia y usted: Apoyo para las personas con cáncer — NCI, 2019 (80 págs.) |
| SHA-256 | `e131c803551271c5e38c6da1d8fe3f9cad18350c430be1bc75d798b265f7f97a` |
| Chunking | 450 tokens, solapamiento 75, tokenizer de ALIA |
| Embeddings | `SINAI/ALIA-MrBERT-es-biomedical-embeddings`, 768d, normalizados, CUDA |
| Búsqueda | PostgreSQL 16.15 + pgvector 0.8.7, `<=>` exacta, Top-5 |
| Consultas | Q01–Q10 exactamente como están en `eval/consultas_baseline.json` |

No se cambió modelo, dimensión, tokenizer, consultas, texto de consultas, parámetros de búsqueda ni búsqueda exacta.

## Métricas antes/después

| Métrica | Antes | Después |
|---|---:|---:|
| Chunks | 147 | 130 |
| Tokens mín. | 27 | 23 |
| Tokens promedio | 176.4 | 191.6 |
| Mediana | 149 | 153.5 |
| Tokens máx. | 445 | 450 |
| Chunks multipágina | 2 | 26 |
| Secciones falsas por footer | 74 | 0 |
| Títulos detectados | 280 | 156 |
| Chunks de índice recuperables | sí | no en búsqueda normal; sí en diagnóstico |
| Q01–Q10 Top-1 pertinente | 9/10 | 9/10 |
| Q01–Q10 Top-3 pertinente | 9/10 | 9/10 |

El mínimo de 23 tokens corresponde a contenido breve real; no se alteró 450/75 para perseguir una distribución más uniforme. Los 156 títulos restantes se dejan para el problema 8: esta iteración no intentó clasificarlos todos.

## Limpieza y clasificación obtenidas

Patrones de maquetación eliminados antes de detectar títulos:

| Patrón normalizado | Tipo | Apariciones | Páginas |
|---|---|---:|---|
| `#` (folio impreso) | header/footer · footer | 74 | 5–78 |
| `forma de controlar los efectos secundarios` | header/footer · header | 49 | 21–69 |
| `#-#-#-# (#-#-#-cancer)` | header/footer · footer alterno | 38 | pares 2–78 |
| `www.cancer.gov/espanol` | header/footer · footer alterno | 38 | impares 3–77 |

Las páginas físicas 3 y 4 se conservaron y sus 2 chunks quedaron marcados `tipo_contenido='indice'`. La búsqueda normal añade el filtro `tipo_contenido='contenido'`; `incluir_indice=True` o `--incluir-indice` permite inspeccionarlos. Verificación real: 0 chunks de índice entre candidatos normales y 2 en modo diagnóstico.

## Q01–Q10: Top-1 antes/después

“Pos. útil” indica el primer fragmento pertinente; en preguntas de acción se anota además el primer consejo práctico cuando difiere.

| ID | Top-1 antes (sim.) | Top-1 después (sim.) | Pos. útil después | Página / sección después | Cambio observado |
|---|---|---|---:|---|---|
| Q01 | Náuseas, pero sección `www.cancer.gov/espanol` (0.7565) | Náuseas y vómitos (0.7355) | 1; acciones 3 | p65; acciones p66–67 | Footer/cinta fuera; consejo práctico entra en Top-3. |
| Q02 | Náuseas, sección `www.cancer.gov/espanol` (0.7577) | Náuseas y vómitos (0.7518) | 1; acciones 3 | p65; acciones p66–67 | Top-1 sigue siendo definición; dos chunks de acciones quedan en Top-5. |
| Q03 | Cansancio, sección teléfono (0.7084) | Cansancio (0.6982) | 1; acciones 2 | p44; acciones p46–47 | Metadata correcta y consejo práctico en Top-2. |
| Q04 | Síntomas como influenza (0.6253) | Síntomas como influenza (0.6253) | 7 | p58 · Infección | Sigue fallando Top-5. Infección mejora de posición 8 a 7; la lista de señales pasa de 42 a 47. No se ajustó la query. |
| Q05 | Estreñimiento, sección `www.cancer.gov/espanol` (0.7038) | Estreñimiento (0.6908) | 1 | p53 · Estreñimiento | Índice deja de ocupar Top-3; sección correcta. |
| Q06 | Diarrea, sección teléfono (0.7840) | Diarrea (0.7903) | 1 | p48 · Diarrea | Índice deja de ocupar Top-2; sección correcta. |
| Q07 | Dolor, sección `www.cancer.gov/espanol` (0.6899) | Dolor (0.6825) | 1 | p51 · Dolor | Top-3 completo pertenece a Dolor; metadata limpia. |
| Q08 | Cambios de apetito, sección `www.cancer.gov/espanol` (0.7287) | Cambios de apetito (0.7209) | 1 | p27 · Cambios de apetito | Índice sale del Top-5; sección correcta. |
| Q09 | Boca/garganta, sección `www.cancer.gov/espanol` (0.7616) | Cambios en la boca y garganta (0.7612) | 1; acciones 2 | p31; acciones p31–32 | Consejo práctico multipágina en Top-2; índice sale del Top-5. |
| Q10 | Seguridad en casa (0.6983) | Seguridad en casa (0.6983) | 1 | p6 · Seguridad en casa… | Top-1 se conserva idéntico; footer ya no contamina resultados secundarios. |

Las variaciones de similitud son consecuencia de volver a generar embeddings sobre chunks limpios; no hubo cambio del espacio vectorial ni reranking.

## Inspección manual de secciones

| Sección | Resultado inspeccionado |
|---|---|
| Náuseas y vómitos | p65–67; títulos razonables; chunks de acciones p65–66 y p66–67; continuidad y solapamiento visibles; sin footer. |
| Cansancio | p44–47; definición y acciones separadas; acciones cruzan p45–46 y p46–47; sin cinta/footer. |
| Infección | p58–62; definición correcta y cuatro chunks multipágina de acciones; lista de señales en p62; no contiene el inicio de Infecundidad. |
| Estreñimiento | p53–54; definición p53 y acciones p53–54; sección y páginas correctas. |
| Diarrea | p48–49; definición p48 y acciones p48–49; continuidad entre chunks conservada. |
| Seguridad en casa | p6; sección y página correctas; no se fusionó con secciones vecinas. |

El caso anterior p62–63 se corrigió: el rótulo final de emergencia queda con Infección y el chunk siguiente comienza `Infecundidad` en p63. No existe un chunk de contenido que mezcle ambas secciones. Las coincidencias de ambos términos que permanecen son únicamente el índice conservado y una tabla general de efectos secundarios, no el corte defectuoso.

## Operación sobre el corpus sintético

La versión `1.0` de `Documento de prueba - fase 2 (pgvector)` se cambió de `activa` a `retirada`. Se conservaron el documento, la versión, sus 3 fragmentos y sus embeddings históricos. La única versión activa para recuperación normal es ahora el PDF NCI 2019 con 130 fragmentos.

## Alcance pendiente deliberadamente

- Q04 continúa fuera del Top-5: esto apunta a embeddings/formulación de consulta/reranking y corresponde a una iteración posterior.
- El carácter `Î` permanece (problema 6); no se aplicó una transformación Unicode amplia.
- No se reconstruyeron tablas complejas (problema 7).
- No se intentó depurar individualmente los 156 títulos restantes (problema 8).

