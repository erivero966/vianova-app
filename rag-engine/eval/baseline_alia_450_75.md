# Baseline de recuperación — ALIA · 450/75 · búsqueda exacta

Fecha: 2026-10-23 · Resultados crudos: `eval/resultados/alia_450_75_20261023T212232Z.json`
Banco de consultas: `eval/consultas_baseline.json` (no modificar).

Inspección técnica/manual. **No** es una evaluación clínica: no hay gold standard validado, por lo que no se calculan Recall@K ni nDCG.

## Configuración

| Parámetro | Valor |
|---|---|
| Documento | La quimioterapia y usted: Apoyo para las personas con cáncer — NCI, 2019 (80 págs.) |
| SHA-256 | `e131c803551271c5e38c6da1d8fe3f9cad18350c430be1bc75d798b265f7f97a` |
| Extractor | PyMuPDF 2.0 (MuPDF 1.28.5), sin OCR |
| Chunking | 450 tokens, solapamiento 75, tokenizer de ALIA |
| Embeddings | `SINAI/ALIA-MrBERT-es-biomedical-embeddings`, 768d, normalizados, CUDA |
| Búsqueda | PostgreSQL 16.15 + pgvector 0.8.7, `<=>` exacta, Top-5 |
| Corpus indexado | 147 fragmentos NCI + 3 fragmentos sintéticos de la fase 2 |

## Resultados (páginas = página física del PDF; impresa = física − 4)

| Consulta | Top-1 (pág. física · sección real según el TOC) | Sim. Top-1 | Top-1 pertinente | Pertinente en Top-3 | Observación |
|---|---|---|---|---|---|
| Q01 náuseas después de la quimioterapia | p65 · Náuseas y vómitos | 0.7565 | Sí | Sí | Top-2 también p65 (antieméticos). Índice (p3) en Top-4. |
| Q02 qué hacer si tiene vómitos… | p65 · Náuseas y vómitos (definición) | 0.7577 | Sí | Sí | El consejo práctico aparece en Top-3 (p67). El chunk «Qué hacer para controlar las náuseas…» (p65) no entra en el Top-5. |
| Q03 paciente muy cansado… | p44 · Cansancio | 0.7084 | Sí | Sí | Top-2 p46 con consejos prácticos. |
| Q04 signos de infección… | p69 · Otros efectos (síntomas como de influenza) | 0.6253 | **No** | **No** | La sección Infección (p58–62) no aparece en el Top-5: su mejor chunk queda en el puesto 8 y la lista «señales de infección» (p62), en el 42. |
| Q05 estreñimiento… | p53 · Estreñimiento | 0.7038 | Sí | Sí | Solo el Top-1 es pertinente; Top-2 y Top-3 son náuseas e índice. |
| Q06 diarrea causada por la quimioterapia | p48 · Diarrea | 0.7840 | Sí | Sí | Índice en Top-2. |
| Q07 dolor durante el tratamiento… | p51 · Dolor | 0.6899 | Sí | Sí | Top-2 y Top-3 también son de la sección Dolor (p52). |
| Q08 problemas para comer… | p27 · Cambios de apetito | 0.7287 | Sí | Sí | Top-2 p66 (plan para comer y beber). |
| Q09 llagas o molestias en la boca… | p31 · Cambios en la boca y garganta | 0.7616 | Sí | Sí | Top-2 p32 menciona las llagas. |
| Q10 seguridad en casa… | p6 · Seguridad en casa después de recibir quimioterapia | 0.6983 | Sí | Sí | Solo el Top-1 es pertinente. |

Resumen: Top-1 pertinente en 9 de 10 consultas; información pertinente en el Top-3 en 9 de 10. El único fallo es Q04.

## Observaciones del baseline

1. **Secciones almacenadas incorrectas**: 74 de 147 chunks (50 %) tienen como `ubicacion` el pie de página alterno (`1-800-422-6237 (1-800-4-CANCER)` en las páginas pares, `www.cancer.gov/espanol` en las impares). Cada uno aparece en 38 de 79 páginas (48 %), por debajo del umbral de repetición del 50 %, así que no se eliminan; como van en negrita, se clasifican como títulos.
2. **Cinta superior** «Forma de controlar los efectos secundarios» (18 pt, negrita) en 49 páginas, justo bajo la zona de margen del 10 %: se toma como título y ensucia el inicio de los chunks.
3. **Cortes por página**: esos falsos títulos fuerzan un corte en cada página. Resultado: solo 2 chunks multipágina, promedio de 176 tokens (lejos de 450), oraciones partidas entre chunks sin solapamiento (p. ej. p66→p67) y un chunk que mezcla el final de Infección con el inicio de Infecundidad (p62–63).
4. **Página del índice (p3)** indexada como contenido: aparece en el Top-5 de 7 de las 10 consultas.
5. **Top-1 tiende a ser el chunk de definición** («¿Qué es y por qué sucede?») en lugar del de acciones («Qué hacer para controlar…»), que es el más útil para cuidadores.
6. **Viñetas «Î»**: la viñeta triangular de FontAwesome se extrae como `Î` (U+00CE) en 416 líneas. El texto sigue siendo legible.
7. **Tablas** (p34, p70–77): se aplanan por columnas; el español y el inglés quedan en líneas separadas y se pierde la correspondencia por fila. No se inventa estructura.
8. **Títulos**: las 31 secciones del índice del PDF se detectan en su página física exacta, pero se detectan 280 títulos en total (falsos positivos: pies de página, cinta superior, líneas del índice, encabezados de tabla).
9. **Errata del original**: p65 dice «Consuma y bebidas suaves» (falta «alimentos»). Verificado visualmente en la página impresa: no es una pérdida del pipeline.
10. **Corpus mezclado**: el documento sintético de la fase 2 sigue con versión `activa` en `vianova_rag`. No apareció en ningún Top-5, pero conviene retirarlo del corpus de evaluación.
