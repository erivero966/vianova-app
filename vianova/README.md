# Vianova: aplicación móvil de recomendaciones con RAG para cuidadores familiares de pacientes con cáncer

Este repositorio contiene la aplicación descrita en el Proyecto Fin de Carrera *Aplicación móvil de recomendaciones basada en conocimiento y generación aumentada por recuperación para cuidadores familiares de pacientes con cáncer, Arequipa 2026* (UCSM), y la usada en el informe de tesis.

- **App móvil:** PWA instalable (manifest + service worker) y proyecto Android con Capacitor (`mobile/`).
- **15 requerimientos funcionales, cada uno con su pantalla** (ver tabla de la sección 2).
- **Seguridad de la información:** ambientes separados (`APP_ENV`), datos ficticios fuera de producción (`seed_ficticio.py`) y respaldos cifrados solo en la nube (`backup.py`).
- **Pruebas:** 188 automatizadas (unitarias, integración, funcionales, E2E, seguridad, IA, configuración, accesibilidad) + carga/estrés/volumen + protocolo de pruebas de usuario (`pruebas/`).

- **Backend:** Python, FastAPI, SQLAlchemy y SQLite (o PostgreSQL).
- **Frontend:** React con Vite. La app web está pensada para el celular.
- **RAG:** funciona en modo local sin API key. Opcionalmente se conecta a Claude u OpenAI.

> ⚠️ **El corpus incluido (DEMO-01 a DEMO-15) y las reglas de avisos son de demostración.** Los redactó el equipo con recomendaciones generales para poder probar el sistema. Antes del piloto deben reemplazarse por documentos oficiales curados (INEN, MINSA, NCI y OMS) usando la ficha de curaduría (módulo *Corpus*), y cada regla de `backend/data/rules.json` debe validarse contra la guía que cita.

---

## 1. Puesta en marcha rápida (sin Docker)

Requisitos: Python 3.11 o superior. Node 18 o superior solo hace falta si va a modificar el frontend, porque `frontend/dist` ya viene compilado.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |   Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python seed_demo.py                  # opcional: crea un cuidador de demostración con datos
uvicorn app.main:app --port 8000
```

Abra **http://localhost:8000**. El backend sirve también la app web.

| Rol | Usuario | Contraseña |
|---|---|---|
| Cuidador demo (si ejecutó `seed_demo.py`) | demo@vianova.local | Demo2026! |
| Cuidadores ficticios (`seed_ficticio.py`) | ficticio0001@ficticio.pe … | Ficticio2026! |
| Curador del corpus | curador@vianova.local | Curador2026! |
| Investigador | investigador@vianova.local | Investigador2026! |
| Administrador (usuarios y roles) | admin@vianova.local | Admin2026! |

Los cuidadores nuevos se registran desde la pantalla de inicio, y para hacerlo deben aceptar el consentimiento. **Cambie las contraseñas iniciales** con las variables de entorno (ver `.env.example`).

También están los scripts `run.sh` (Linux/Mac) y `run.bat` (Windows), que hacen todo lo anterior.

### Con Docker

```bash
docker compose up --build            # app en http://localhost:8000 con PostgreSQL
```

### Desarrollo del frontend

```bash
cd frontend && npm install && npm run dev     # http://localhost:5173 (usa el backend en :8000 como proxy)
npm run build                                 # regenera frontend/dist
```

### Prototipo integrado (RAG: BGE-M3 + pgvector + qwen2.5:7b en Ollama)

La pantalla **Consultar** (`#/consultar`) responde con un RAG completo y local. Primero recupera los Top-3 fragmentos de las guías del NCI en `rag-engine` (`../rag-engine`). Luego `qwen2.5:7b`, servido por Ollama en local, redacta una respuesta breve basada solo en esos fragmentos. Debajo se muestran las **fuentes utilizadas**, con entidad, documento, sección y página, y el botón **Ver evidencia recuperada** despliega los fragmentos originales. El asistente anterior, que usa el corpus de demostración, sigue disponible en `#/asistente`.

Flujo: frontend → `POST /api/rag/search` (backend :8000) → `RAG_API_URL` (rag-engine :8001, `top_k=3`) → reglas de `safety.py` → Ollama `OLLAMA_URL` (`/api/chat`, `OLLAMA_MODEL`, sin streaming, temperatura 0) → verificación → respuesta, fuentes y evidencia.

Controles contra alucinaciones (`backend/app/rag/grounded.py`):

1. Las reglas deterministas tienen prioridad. La alerta de urgencia siempre se muestra, diga lo que diga el modelo. Las consultas fuera de alcance (dosis, diagnóstico, pronóstico, cambios de tratamiento) se responden sin llamar al LLM.
2. **Abstención previa:** si no hay resultados o la similitud del mejor fragmento es menor que `RAG_MIN_SCORE` (0.50), no se llama al LLM. El umbral se calibró a mano con unas 16 consultas: las de fuera del corpus quedaron en ≤ 0.49 y las cubiertas en ≥ 0.52. Es una regla mínima de demo, no un resultado de evaluación.
3. **Prompt restrictivo:** solo fuentes, una cita `[n]` por oración, y la frase "Las fuentes recuperadas no indican…" cuando falta información. Si no hay información suficiente, el modelo devuelve la frase de abstención exacta.
4. **Verificación posterior:** se eliminan las oraciones con menos del 60 % de palabras de contenido presentes en las fuentes (`text.coverage`). En las frases "Las fuentes no indican…, pero…" se recorta lo que va después del "pero". Una cantidad con unidad de medicamento (por ejemplo "8 mg") que no esté en las fuentes descarta la respuesta. Si no queda nada respaldado, el sistema se abstiene.
5. Si Ollama está caído, es lento o responde algo inválido, se muestra "No fue posible generar una explicación…" y la evidencia recuperada queda a la vista.

```bash
# 1. Levantar PostgreSQL + pgvector
cd ../rag-engine && docker compose up -d
# 2. Levantar RAG :8001 (sin conexión a Hugging Face; el modelo debe estar en caché)
source .venv/bin/activate && HF_HUB_OFFLINE=1 uvicorn src.api.app:app --host 0.0.0.0 --port 8001
curl http://localhost:8001/health          # "status":"ok", "embeddings":419
# 3. Levantar backend :8000 (otra terminal)
cd vianova/backend && source .venv/bin/activate && RAG_API_URL=http://127.0.0.1:8001 uvicorn app.main:app --port 8000
# 4. Frontend: el backend ya sirve frontend/dist. Para desarrollo: cd vianova/frontend && npm run dev   (:5173)
# 5. Abrir http://localhost:8000/#/consultar  (o :5173) con demo@vianova.local / Demo2026!
```

**Arranque en un solo paso:** `./run_demo.sh` (o `./run_demo.sh --vite`) deja lista toda la demo y reutiliza los servicios que ya estén levantados:

1. PostgreSQL + pgvector.
2. RAG Engine en :8001 (`HF_HUB_OFFLINE=1`).
3. Ollama en :11434. Si su API (`/api/tags`) no responde, el script lo inicia: con `systemctl start ollama` si existe el servicio systemd (instalación oficial en Linux; puede pedir contraseña) o, si no, con `ollama serve` en segundo plano (log en `/tmp/vianova-ollama.log`). Después reintenta cada 0,5 s hasta 30 s.
4. Backend en :8000.
5. Vite en :5173 (solo con `--vite`).

Sobre Ollama:

- El script nunca ejecuta `ollama run` ni descarga modelos.
- `qwen2.5:7b` debe estar instalado de antemano (`ollama pull qwen2.5:7b`). Si falta, el script se detiene y lo indica.
- No se precarga el modelo: Qwen se carga en memoria con la primera consulta, que tarda unos segundos más, y queda cargado 30 min (`keep_alive`).
- Un Ollama que ya estaba en marcha se reutiliza y nunca se detiene. Ctrl+C solo detiene lo que el script inició, salvo PostgreSQL y Ollama.

---

## 2. Requerimientos y pantallas

| RF | Pantalla (ruta) | Implementación |
|---|---|---|
| RF-01 Cuenta, perfil y consentimiento | Ingreso / Crear cuenta; Perfil (`#/perfil`) | `routers/auth.py`, `/api/profile` |
| RF-02 Agenda de cuidado | Agenda (`#/agenda`) | `/api/tasks`, `schedule.py` |
| RF-03 Recordatorios y notificaciones | Recordatorios (`#/recordatorios`) + aviso emergente | `App.jsx` (useReminders), `public/sw.js` |
| RF-04 Registro por voz/texto con confirmación | Registrar (`#/registrar`) | `nlp.py`, `/api/events/parse`, `/api/events` |
| RF-05 Recomendaciones explicadas | Recomendaciones (`#/recomendaciones`) | `recommender.py` |
| RF-06 Asistente RAG con abstención | Consultar (`#/consultar`) | `rag/assistant.py`, `rag/index.py`, `rag/safety.py` |
| RF-07 Trazabilidad (fuente, documento, traza RAG) | «Ver cómo se obtuvo esta respuesta»; Documento | `trace` en la respuesta, `pages/Doc.jsx` |
| RF-08 Retroalimentación | «¿Le sirvió?» | `/api/recommendations/feedback` |
| RF-09 Avisos e historial | Avisos (`#/avisos`) | `alerts.py`, `data/rules.json` |
| RF-10 Resumen exportable | Resumen (`#/resumen`) | `/api/summary`, `/api/summary.csv` |
| RF-11 Wearables (opcional) | Dispositivos (`#/dispositivos`) | `/api/devices/import` |
| RF-12 Corpus y configuración | Corpus; Configuración (`#/configuracion`) | `/api/corpus`, `/api/admin/config` |
| RF-13 Usuarios, roles y auditoría | Usuarios y roles (`#/usuarios`) | `routers/admin.py` |
| RF-14 Indicadores, validación y exportación | Investigación; Validación (`#/validacion`) | `routers/research.py` |
| RF-15 Privacidad y derechos ARCO | Privacidad (`#/privacidad`) | `routers/privacy.py` |

### Seguridad de la información

```bash
APP_ENV=desarrollo python seed_ficticio.py --n 20    # datos ficticios (bloqueado en producción)
VIANOVA_BACKUP_DEST=s3://bucket/vianova python backup.py crear   # respaldo cifrado; rechaza discos externos
```
Cada ambiente guarda su base y sus claves en `backend/data/entornos/<ambiente>/`. En producción la app no arranca sin `JWT_SECRET`, `VIANOVA_FERNET_KEY`, PostgreSQL y contraseñas iniciales cambiadas.

## 3. Validación técnica (Técnica 4, Instrumento 6)

```bash
python eval/run_eval.py --calibrar     # barre τ y sugiere el umbral
python eval/run_eval.py                # calcula los indicadores con el τ configurado
```

Este comando genera `eval/resultados/metricas.json` y `eval/resultados/ficha_casos_prueba.csv`, que es la ficha de casos de prueba ya llena.

Resultado con el corpus y los casos **demo** (94 casos: 64 de pertinencia, 20 sin evidencia y 10 fuera de alcance; τ = 0,12):

| Indicador | Valor |
|---|---|
| Precision@5 | 0,275 (máximo posible con estas listas de pertinentes: 0,284) |
| Recall@5 / acierto en 1.ª posición / MRR | 0,98 / 0,97 / 0,98 |
| Trazabilidad | 100 % |
| Abstención correcta | 95 % |
| Fuera de alcance detectado | 100 % |
| Falsas abstenciones | 1,6 % |

> Estos números provienen de datos de demostración, y τ y algunos parámetros se ajustaron con este mismo conjunto. **Para la tesis**, construyan el conjunto de referencia con el corpus oficial y usen **dos conjuntos distintos**: uno para calibrar τ y otro para la validación final que se reporte.
>
> Sobre Precision@5: si una consulta tiene un solo documento pertinente, su Precision@5 máxima es 0,2. Por eso se reporta también el máximo posible y el Recall@5.

## 4. Análisis estadístico (sección 4.2 del informe)

```bash
python analysis/analisis_estadistico.py datos_piloto.csv
python analysis/analisis_estadistico.py --demo    # SOLO para probar el script con datos simulados
```

El script hace lo siguiente:
1. Depura los datos: rango de 1 a 5; si faltan más del 10 % de los ítems, se excluye la medición; si faltan menos, se imputa la media personal.
2. Calcula el puntaje y la categoría del ZBI-22 (cortes de Martín et al., 1996).
3. Obtiene los descriptivos.
4. Aplica Shapiro-Wilk sobre D = pre − post.
5. Aplica la t de Student para muestras relacionadas (con dz) o la prueba de Wilcoxon (con r = Z/√N).
6. Calcula el alfa de Cronbach.
7. Hace el gráfico pre-post.

El formato de entrada está en `analysis/datos_demo/zbi_usabilidad_SIMULADO.csv`. **Esos datos son simulados y no deben reportarse.**

## 5. Pruebas

```bash
cd backend && pytest -q                 # 117 pruebas: unitarias, integración, funcionales (CF-01..15), seguridad, IA
python pruebas/e2e/run_e2e.py           # E2E por RF + capturas (390×844), configuración (5 pantallas) y axe-core
python pruebas/carga/run_carga.py       # carga, estrés y volumen (200 cuidadores ficticios)
python pruebas/consolidar.py            # reporte consolidado → pruebas/resultados/reporte_pruebas.md
```
Las pruebas de usuario (usabilidad y accesibilidad) están en `pruebas/usuarios/` (protocolo, instrumentos y `analizar_usuarios.py`); el registro de observaciones está en `pruebas/registro_observaciones.csv`.

## 6. Configuración (variables de entorno)

Ver `.env.example`. Las principales son:

- `LLM_PROVIDER`: `local` por defecto, `anthropic` u `openai`.
- `ANTHROPIC_API_KEY` u `OPENAI_API_KEY`.
- `RAG_TAU` y `RAG_MIN_COVERAGE`.
- `OLLAMA_URL` (`http://127.0.0.1:11434`), `OLLAMA_MODEL` (`qwen2.5:7b`), `OLLAMA_TIMEOUT` (60 s) y `RAG_MIN_SCORE` (0.50): generación local de la pantalla Consultar.
- `RAG_API_URL` (por defecto `http://127.0.0.1:8001`): URL del motor `rag-engine` que usa la pantalla Consultar. También `RAG_API_TIMEOUT` (15 s) y `RAG_API_TOP_K` (3). El backend no lee el archivo `.env` por sí solo, así que esta variable debe exportarse antes de arrancarlo.
- `W_SEM`, `W_CTX`, `W_REG` y `W_PREF`, los pesos del recomendador, que deben sumar 1.
- `ON_TIME_TOLERANCE_MIN`.
- `DATABASE_URL`, por ejemplo PostgreSQL.
- `JWT_SECRET` y `VIANOVA_FERNET_KEY`: si no se definen, se generan por ambiente en `backend/data/entornos/<ambiente>/` (en producción son obligatorios). Respalden la clave Fernet en el gestor de secretos: sin ella no se puede leer el texto cifrado.

En modo `local`, la respuesta es **extractiva**: son oraciones literales del documento con su fuente. Con `anthropic` u `openai`, el modelo redacta usando solo los fragmentos recuperados; si responde `NO_EVIDENCIA`, el sistema se abstiene.

## 7. Estructura

```
backend/app/        API (routers/), modelo de datos, RAG (rag/), recomendador, avisos, indicadores
backend/data/       corpus/ (documentos .md con metadatos), rules.json, base SQLite y claves (se crean al iniciar)
backend/tests/      pruebas automatizadas
frontend/           app web React (src/) y compilado (dist/)
eval/               casos de prueba y script de validación técnica
analysis/           script de procesamiento estadístico
samples/            archivos de ejemplo de wearables
```

## 8. Limitaciones conocidas del MVP

- **Corpus y reglas:** son de demostración (ver la advertencia al inicio).
- **Recuperación:** híbrida (TF-IDF de palabras y caracteres + embeddings LSA) con corrección ortográfica fonética. Funciona sin servicios externos; puede migrarse a embeddings neuronales y pgvector sin cambiar la interfaz.
- **Reconocimiento de voz:** depende del navegador (funciona en Chrome y Edge; en Firefox no). La transcripción siempre se revisa antes de guardar.
- **Recordatorios:** aviso en la app y notificación vía service worker; con la app cerrada se usa el plugin de notificaciones locales del APK (Capacitor).
- **Arquitectura:** es una sola aplicación FastAPI organizada en módulos (routers). Separarla en microservicios es un paso de despliegue posterior.
