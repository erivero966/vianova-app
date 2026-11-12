# Q04 — comparación con revisión humana

Consulta: `signos de infección durante la quimioterapia`

| Modelo | Primer pertinente estricto | Primer pertinente laxo | Primer específico infección | Fragmento histórico p. 62 |
|---|---:|---:|---:|---:|
| alia | 7 | 7 | 7 | 54 |
| qwen3 | 9 | 9 | 9 | 22 |
| bge-m3 | 2 | 2 | 2 | 5 |

## Fragmentos específicos revisados

| Página | Sección | Grado | Observación | Ranks por modelo |
|---:|---|---:|---|---|
| 58 | Infección | 2 | Sección Infección, neutropenia, revisar la fiebre a diario, llamar con 38 °C o más | alia:7, bge-m3:2, qwen3:9 |
| 58 | Qué hacer para controlar la infección: | 0 | Medidas para prevenir la infección (lavado de manos, etc.), no describe los signos | alia:13, bge-m3:4, qwen3:11 |
| 59 | Qué hacer para controlar la infección: | 1 | Sobre todo prevención, incluye signos de infección alrededor del catéter (pus, enrojecimiento, hinchazón, dolor) | alia:85, bge-m3:73, qwen3:83 |
| 60 | Qué hacer para controlar la infección: | 0 | Prevención de infecciones (piel, cortaduras, animales, vacunas, alimentos), no describe los signos | alia:179, bge-m3:147, qwen3:195 |
| 61 | Qué hacer para controlar la infección: | 1 | Sobre todo prevención alimentaria, al final da algunos signos (fiebre de 38 °C o más, escalofríos, sudores) y pide llamar de inmediato | alia:94, bge-m3:55, qwen3:93 |
| 62 | Además de la fiebre, otras señales de infección son: | 2 | Lista directa de señales de infección además de la fiebre | alia:54, bge-m3:5, qwen3:22 |
