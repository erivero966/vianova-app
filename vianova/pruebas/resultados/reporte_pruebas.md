# Reporte consolidado de pruebas · ronda 2

Fecha: 2026-10-16 19:09 · Ambiente: pruebas (datos ficticios)

| Tipo de prueba | Total | Aprobadas | Fallidas |
|---|---:|---:|---:|
| Unitarias | 40 | 40 | 0 |
| Integración (API + BD + índice) | 10 | 10 | 0 |
| Funcionales por RF | 15 | 15 | 0 |
| Seguridad | 29 | 29 | 0 |
| Componente de IA (RAG) | 23 | 23 | 0 |
| Extremo a extremo (E2E) | 16 | 16 | 0 |
| Configuración (tamaños de pantalla) | 30 | 30 | 0 |
| Accesibilidad automática (axe-core) | 25 | 25 | 0 |
| **Total** | **188** | **188** | **0** |

## Carga, estrés y volumen

Entorno: uvicorn, 1 proceso, SQLite (ambiente de pruebas), 2 CPU.

| Usuarios | Solicitudes/s | Errores | Mediana CRUD máx. (ms) | Mediana RAG (ms) | p95 RAG (ms) |
|---:|---:|---:|---:|---:|---:|
| 1 | 100.8 | 0 | 7.2 | 10.8 | 14.4 |
| 10 | 116.3 | 0 | 65.4 | 83.8 | 140.6 |
| 25 | 110.9 | 0 | 153.2 | 181.5 | 373.4 |
| 50 | 100.2 | 0 | 312.4 | 389.1 | 1247.5 |

| Estrés (solicitudes RAG simultáneas) | p50 (ms) | p95 (ms) | Error (%) |
|---:|---:|---:|---:|
| 100 usuarios × 3 | 1924.9 | 3124.0 | 0.0 |
| 150 usuarios × 3 | 3635.3 | 5411.9 | 0.0 |
| 200 usuarios × 3 | 7062.2 | 11677.8 | 0.5 |

RNF-R01 (mediana CRUD ≤ 2 s y RAG ≤ 10 s): **cumple**.

## Validación técnica del RAG

Precision@5 0.275 (máx. 0.2844), Recall@5 0.9792, MRR 0.9688, trazabilidad 100.0 %, abstención correcta 95.0 %, fuera de alcance 100.0 %.
