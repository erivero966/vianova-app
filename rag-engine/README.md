# Motor local de embeddings biomédicos

Capa de embeddings y base vectorial persistente (PostgreSQL + pgvector) del RAG de Vianova. Descarga modelos preentrenados de Hugging Face y los ejecuta localmente; no entrena modelos, no genera respuestas médicas y no utiliza servicios cloud.

El modelo predeterminado es `SINAI/ALIA-MrBERT-es-biomedical-embeddings`. La misma interfaz admite `Qwen/Qwen3-Embedding-0.6B` y `BAAI/bge-m3` para comparaciones posteriores.

Estado del corpus v01 (2026-11-03): tres NCI digitales activos, 428 chunks/embeddings, 419 chunks recuperables; documento sintético retirado e INEN fuera de retrieval. Véanse el [baseline multidocumento ALIA de 15 consultas](eval/corpus_v01_multidocumento_alia.md), el [banco independiente MD01–MD15](eval/consultas_multidocumento_v01.json) y el [manifest de curación](corpus/manifest_curacion.json). La evaluación documenta fallos de pertinencia. La comparación dense preliminar ALIA / Qwen3 / BGE-M3 sobre los mismos 419 chunks está en [eval/model_comparison_v01.md](eval/model_comparison_v01.md) (con Q04 en [eval/q04_model_comparison.md](eval/q04_model_comparison.md)); es preliminar y no selecciona modelo.

## 1. Crear el entorno virtual

El código es compatible con Python 3.11+. El entorno validado realmente usa **Python 3.13.13** (ver «Versiones validadas»); no es necesario recrearlo con 3.11.

Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
```

## 2. Instalar dependencias

Para CPU o si el paquete normal de PyTorch ya ofrece CUDA en su plataforma:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

La disponibilidad de una GPU NVIDIA no garantiza que el PyTorch instalado tenga soporte CUDA. Si `scripts/check_gpu.py` muestra `CUDA disponible: no`, instale la distribución de PyTorch indicada para su sistema operativo y versión de CUDA en el [selector oficial de PyTorch](https://pytorch.org/get-started/locally/), y vuelva a ejecutar la comprobación. No se fuerza un índice CUDA en `requirements.txt` porque cambiaría según la plataforma.

## 3. Configuración

`.env` contiene los valores de desarrollo:

```env
EMBEDDING_MODEL=alia
EMBEDDING_DEVICE=auto
EMBEDDING_BATCH_SIZE=16
```

- `EMBEDDING_MODEL`: `alia`, `qwen3` o `bge-m3`.
- `EMBEDDING_DEVICE`: `auto`, `cuda` o `cpu`. `auto` elige CUDA solo si `torch.cuda.is_available()` es verdadero. Incluso una selección explícita de CUDA cae a CPU con una advertencia si CUDA no funciona.
- `EMBEDDING_BATCH_SIZE`: entero positivo. Redúzcalo si se agota la VRAM.

Para cambiar de modelo posteriormente:

```env
EMBEDDING_MODEL=qwen3
```

o:

```env
EMBEDDING_MODEL=bge-m3
```

Los identificadores completos existen únicamente en `src/embeddings/registry.py`. ALIA y Qwen3 aplican a las consultas el prompt `query` recomendado por sus fichas oficiales; los documentos se codifican sin prompt. BGE-M3 no añade instrucciones a ninguno.

## 4. Comprobar CUDA

```bash
python scripts/check_gpu.py
```

El script muestra la versión de PyTorch, disponibilidad real de CUDA, nombre de GPU, VRAM y dispositivo finalmente seleccionado.

## 5. Ejecutar la recuperación de ejemplo

La primera ejecución descarga ALIA; las siguientes reutilizan la caché:

```bash
python scripts/test_retrieval.py
```

El script codifica tres documentos y una consulta, calcula el coseno mediante producto punto de vectores normalizados y presenta TOP 1–3 junto con la dimensión real del modelo. Para la consulta de náuseas, el documento sobre efectos adversos del tratamiento antineoplásico debe ocupar TOP 1.

Uso desde código:

```python
from src.embeddings import EmbeddingService

service = EmbeddingService(model="alia")
vector = service.encode_query(
    "Mi familiar tiene náuseas después de la quimioterapia"
)
print(vector.shape)
print(service.dimension)
```

La interfaz pública ofrece `encode_document`, `encode_documents`, `encode_query`, `dimension`, `model_name` y `device`. Los consumidores no acceden a `SentenceTransformer`.

## 6. Pruebas

Las pruebas rápidas usan un backend simulado, no descargan pesos y no necesitan Docker (`pytest.ini` excluye por defecto el marcador `integration`):

```bash
pytest -q
```

Las pruebas de integración usan PostgreSQL real (requieren `docker compose up -d`). Se ejecutan sobre una base aislada `vianova_rag_test` que se crea automáticamente en el mismo contenedor; nunca modifican `vianova_rag`. Si PostgreSQL no responde, se omiten con el motivo (`-rs` lo muestra):

```bash
pytest -q -m integration -rs
```

Para incluir además ALIA real (descarga/GPU), también contra pgvector:

Linux:

```bash
RUN_MODEL_TESTS=1 pytest -q -m integration
```

Windows (PowerShell):

```powershell
$env:RUN_MODEL_TESTS="1"; pytest -q -m integration
```

## 7. Base vectorial persistente (PostgreSQL 16 + pgvector)

Imagen fijada a `pgvector/pgvector:0.8.7-pg16@sha256:7b822b0a…` (ver «Imagen Docker reproducible»). Las credenciales salen de `.env` (copie `.env.example`; `.env` está en `.gitignore`):

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vianova_rag
POSTGRES_USER=vianova
POSTGRES_PASSWORD=vianova_dev
```

`vianova_dev` es solo un valor de desarrollo local. El puerto se publica únicamente en `127.0.0.1`.

### Levantar PostgreSQL

```bash
docker compose up -d
```

Al crear el volumen por primera vez, Docker ejecuta en orden los archivos de `sql/`: `001_extensions.sql` (`CREATE EXTENSION IF NOT EXISTS vector`), `002_schema.sql` (tablas y registro de ALIA) y `003_fragment_metadata.sql` (páginas/tokens por fragmento y tabla `ingesta`).

### Migraciones

Sobre una base ya existente (volumen creado en una fase anterior), aplique las migraciones pendientes:

```bash
python scripts/migrate_database.py
```

Cada archivo se registra en `schema_migracion` con su SHA-256 y no vuelve a ejecutarse. Si alguien edita una migración ya aplicada, el script se detiene con `SchemaDriftError`: los cambios de esquema siempre van en un archivo nuevo (`004_…sql`). `ingest_pdf.py` e `index_sample.py` también aplican las migraciones pendientes antes de escribir.

### Imagen Docker reproducible

El tag `pg16` es móvil (se republica con cada versión de pgvector o de PostgreSQL). Se comprobó en Docker Hub que el tag `0.8.7-pg16` apunta al mismo digest que la imagen validada (`sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a`, PostgreSQL 16.15 + pgvector 0.8.7, Debian bookworm). `docker-compose.yml` usa tag **y** digest: si el tag se republicara, Docker seguiría usando exactamente los bytes probados. Para actualizar, cambie ambos de forma deliberada y vuelva a ejecutar las pruebas de integración.

### Ver estado

```bash
docker compose ps
```

El servicio debe aparecer `(healthy)` (healthcheck con `pg_isready`).

### Comprobar la base

```bash
python scripts/check_database.py
```

Muestra conexión, versión de PostgreSQL, versión de pgvector, base y usuario, tablas requeridas, tipo real de la columna (`vector(768)`), configuraciones de modelo y número de registros. Devuelve código de salida 1 si falta algo.

### Indexar el ejemplo

```bash
python scripts/index_sample.py
```

Crea (o reutiliza) un documento sintético, su versión `1.0`, tres fragmentos y sus tres embeddings ALIA, en una única transacción. La versión se marca `activa` solo cuando todos sus embeddings están guardados. Reejecutarlo no crea duplicados: reutiliza documento, versión y fragmentos y reemplaza los embeddings existentes.

### Buscar

```bash
python scripts/search_database.py
python scripts/search_database.py "¿Cómo prevenir infecciones?" -k 2
python scripts/search_database.py --explain   # plan real de PostgreSQL
```

Solo la consulta se codifica en Python. La comparación y el ranking los ejecuta PostgreSQL:

```sql
SELECT f.id AS fragmento_id, f.orden, f.texto, f.ubicacion,
       d.id AS documento_id, d.titulo, d.entidad,
       v.id AS version_id, v.version,
       e.embedding <=> %(query)s AS distancia
FROM embedding_fragmento_alia AS e
JOIN fragmento AS f ON f.id = e.fragmento_id
JOIN version_documento AS v ON v.id = f.version_id
JOIN documento AS d ON d.id = v.documento_id
WHERE e.configuracion_id = %(config)s AND v.estado = 'activa'
  AND f.tipo_contenido = 'contenido'
ORDER BY e.embedding <=> %(query)s
LIMIT %(top_k)s;
```

### Detener

```bash
docker compose down
```

`docker compose down` detiene y elimina el contenedor y la red, pero **conserva el volumen `vianova_rag_pgdata`**: al volver a ejecutar `docker compose up -d` los datos siguen ahí.

Para **borrar los datos definitivamente** (operación destructiva e irreversible):

```bash
docker compose down -v
# o: docker volume rm vianova_rag_pgdata
```

Tras borrar el volumen, el siguiente `up` recrea la base vacía y vuelve a ejecutar los scripts de `sql/`.

### Modelo de datos

| Tabla | Contenido | Restricciones relevantes |
|---|---|---|
| `documento` | título, entidad, URL de origen | — |
| `version_documento` | versión, estado, vigencia, ruta y hash | `UNIQUE(documento_id, version)`; estado ∈ `borrador`, `revision`, `activa`, `retirada`; como máximo una `activa` por documento; FK `RESTRICT` |
| `fragmento` | texto, orden, ubicación, páginas, tokens y `tipo_contenido` | `UNIQUE(version_id, orden)`; tipo ∈ `contenido`, `indice`; FK `CASCADE` desde la versión |
| `configuracion_modelo` | modelo, dimensión, normalización, parámetros JSONB | `UNIQUE(nombre)`; ALIA registrado (768, normalizado) |
| `embedding_fragmento_alia` | `embedding VECTOR(768)` (tipo pgvector, no JSON/TEXT/array) | `UNIQUE(fragmento_id, configuracion_id)`; FK `CASCADE` desde el fragmento |

Todos los `id` son `UUID` (`gen_random_uuid()`) y todas las tablas tienen `creado_en TIMESTAMPTZ`.

La búsqueda devuelve únicamente fragmentos de versiones `activa`, de modo que una versión retirada deja de servirse sin borrar sus datos.

### Distancia y similitud

Se usa `<=>`, la **distancia coseno** de pgvector. ALIA produce vectores normalizados (norma 1), por lo que:

- `distancia = 1 − cos(q, d)`, en el rango [0, 2]; menor es mejor.
- `similitud = 1 − distancia = cos(q, d) = q · d`, en el rango [−1, 1].

El ranking es idéntico al del producto punto de la fase 1 (verificado: mismas similitudes hasta 6 decimales). `VectorRepository` rechaza vectores con dimensión incorrecta, NaN o no normalizados antes de llegar a SQL; PostgreSQL además rechaza cualquier vector que no tenga 768 dimensiones.

### Búsqueda exacta (sin HNSW/IVFFlat)

No se crean índices aproximados a propósito: sin ellos PostgreSQL calcula la distancia para cada candidato y ordena (`Sort Key: (e.embedding <=> ...)` en `--explain`), lo que da el resultado exacto. Esta es la línea base para comparar más adelante con HNSW cuando el tamaño del corpus lo justifique.

### Varios modelos y dimensiones (Qwen3, BGE-M3)

Una columna `VECTOR(768)` solo admite vectores de 768 dimensiones, y ALIA, Qwen3-Embedding-0.6B y BGE-M3 no comparten espacio vectorial (sus distancias no son comparables). Por eso **cada configuración de modelo tiene su propia tabla vectorial**, referenciada en `configuracion_modelo.parametros->>'tabla_embeddings'`. Para añadir un modelo en el futuro:

1. Crear su tabla en un nuevo `sql/00N_*.sql` (p. ej. `embedding_fragmento_bge_m3` con `VECTOR(1024)`), con la misma forma que la de ALIA.
2. Registrar la configuración en `configuracion_modelo`.
3. Añadir la tabla a la lista blanca `VECTOR_TABLES` de `src/database/vector_repository.py`.

`VectorRepository` no cambia: resuelve la tabla desde la configuración y rechaza combinaciones incoherentes (p. ej. un modelo de 1024d apuntando a la tabla de 768). Las tablas de documento, versión y fragmento son comunes a todos los modelos.

### Uso desde código

El resto del RAG no escribe SQL; usa los repositorios de `src/database`:

```python
from src.database import ModelConfigRepository, VectorRepository, connect
from src.embeddings import EmbeddingService

service = EmbeddingService("alia")
with connect() as conn:  # commit al salir; rollback ante excepción
    config = ModelConfigRepository(conn).get_active("alia")
    vectors = VectorRepository(conn, config)
    results = vectors.search_similar(service.encode_query("..."), top_k=3)
```

`VectorRepository` ofrece `save_embedding`, `get_embedding`, `search_similar`, `explain_search`, `delete_embeddings_for_fragment` y `count_embeddings`. `index_document` (en `src/database/indexing.py`) orquesta documento → versión → fragmentos → embeddings en una transacción.

## 8. Ingestión documental (PDF)

```text
PDF aprobado (corpus/aprobados/)
  ↓ validación (cabecera %PDF, contraseña) + SHA-256 de los bytes originales
  ↓ ¿mismo hash ya registrado? → no se duplica
  ↓ si es escaneado: derivado OCR separado + validación automática + revisión manual
  ↓ extracción página a página (PyMuPDF)
  ↓ validación de la extracción (páginas sin texto, caracteres ilegibles)
  ↓ limpieza conservadora + encabezados/pies repetidos + títulos
  ↓ chunking por tokens del tokenizer de ALIA (página inicio/fin, sección)
  ↓ ALIA (GPU) → embeddings 768d normalizados
  ↓ transacción única: documento, versión, fragmentos, embeddings, ingesta, activar versión
PostgreSQL + pgvector → búsqueda exacta por distancia coseno
```

### Corpus

| Carpeta | Uso | ¿Se indexa? |
|---|---|---|
| `corpus/candidatos/` | documentos recibidos, pendientes de revisión | **No** |
| `corpus/aprobados/` | documentos revisados y aprobados | **Sí** |
| `corpus/ocr/` | derivados técnicos con capa OCR y trazabilidad | **No, hasta revisión manual** |
| `corpus/rechazados/` | documentos descartados | **No** |

El pipeline rechaza (`NotApprovedError`) cualquier PDF fuera de `corpus/aprobados/`. El contenido de las tres carpetas está en `.gitignore`: los PDFs no se versionan. No coloque documentos con datos de pacientes.

Cada PDF aprobado lleva un JSON con el **mismo nombre** (`guia.pdf` → `guia.json`):

```json
{
  "titulo": "Guía ...",
  "entidad": "INEN",
  "version": "2025",
  "url_origen": "https://...",
  "vigencia": "vigente",
  "paginas_indice": [3, 4]
}
```

`titulo`, `entidad` y `version` son obligatorios; campos desconocidos se rechazan. `paginas_indice` es una corrección manual opcional (páginas físicas, 1-based) para tablas de contenidos que no puedan detectarse con suficiente confianza. No se infiere ningún metadato con IA.

### 1. Inspeccionar antes de indexar

```bash
python scripts/inspect_pdf.py corpus/candidatos/guia.pdf
python scripts/inspect_pdf.py corpus/candidatos/guia.pdf --paginas --chunks --mostrar 5
```

No escribe en la base ni usa la GPU. Muestra SHA-256, páginas, páginas con/sin texto, caracteres, promedio por página, fracción de caracteres ilegibles, encabezados/pies que se eliminarían, títulos detectados y, con `--chunks`, la segmentación que se obtendría (con el tokenizer real de ALIA). Devuelve código 2 si el PDF no es apto.

### 2. Indexar

```bash
python scripts/ingest_pdf.py corpus/aprobados/guia.pdf
python scripts/ingest_pdf.py corpus/aprobados/guia.pdf --metadata corpus/aprobados/guia.json
python scripts/ingest_pdf.py --todos            # todos los PDF de corpus/aprobados/
```

Muestra el progreso (extracción, chunks, embeddings `32 / 134`…, guardado) y un resumen: documento, entidad, versión, SHA-256, páginas, chunks, distribución de tokens, modelo, dimensión, device, tiempos y estado (`ACTIVA`).

Reglas de duplicados y versiones:

| Situación | Resultado |
|---|---|
| Mismo archivo (hash), mismos metadatos y misma configuración | `ya estaba indexado`: no se toca nada |
| Mismo archivo con otra configuración de chunking/modelo | error; `--reindex` reemplaza sus fragmentos y embeddings |
| Mismo archivo con otros metadatos | error: un archivo solo puede pertenecer a una versión |
| Otro archivo con una etiqueta de versión ya usada | error: use una versión nueva |
| Otro archivo con versión nueva del mismo documento | se indexa, se activa y la versión anterior pasa a `retirada` |

Todo se publica en **una transacción**: los embeddings se calculan antes de escribir, y si falla cualquier escritura (p. ej. el embedding 17 de 30) se revierte todo; nunca queda una versión `activa` incompleta.

### 3. Buscar

```bash
python scripts/search_corpus.py "náuseas después de la quimioterapia" --top-k 5
python scripts/search_corpus.py "higiene de manos" --entidad INEN --max-caracteres 300
python scripts/search_corpus.py "fiebre" --documento-id <uuid> --explain
python scripts/search_corpus.py "infección" --incluir-indice  # solo diagnóstico
```

Cada resultado muestra similitud, documento, entidad, versión, página (o rango `14–15`), sección, tipo de contenido y texto. La consulta se codifica con ALIA y el ranking lo hace PostgreSQL (`ORDER BY embedding <=> consulta`); `--explain` muestra el plan real. `VectorRepository.search_similar` acepta los filtros `entidad` y `documento_id`; solo se buscan versiones `activa` y, por defecto, fragmentos `tipo_contenido='contenido'`. `--incluir-indice`/`incluir_indice=True` habilita la inspección administrativa del índice.

### PDFs escaneados y OCR

Una página se considera **sin texto** si tiene menos de 30 caracteres visibles, y **posiblemente escaneada** si además contiene imágenes. El PDF se rechaza en la ingesta si:

- no tiene ninguna página con texto, o más del 5 % de sus caracteres son ilegibles (fuentes sin mapa Unicode), o
- al menos el 20 % de sus páginas no tienen texto (`ADVERTENCIA: El PDF puede contener páginas escaneadas…`).

En el segundo caso, tras revisar el documento (p. ej. páginas en blanco intencionadas), se puede aceptar la advertencia con `--ignorar-advertencia-ocr`; este argumento **no** permite indexar un PDF completamente escaneado y no ejecuta OCR. Los umbrales están en `src/ingestion/pdf_extractor.py`.

#### Dependencias OCR en Fedora

Compruebe primero:

```bash
ocrmypdf --version
tesseract --version
tesseract --list-langs
```

La lista debe contener `spa` y, para corregir orientación con `--rotate-pages`, `osd`. Si falta cualquier componente, instálelo manualmente; los scripts nunca ejecutan `sudo`:

```bash
sudo dnf install ocrmypdf tesseract-osd tesseract-langpack-spa
```

#### Crear un derivado OCR

Los originales de `corpus/aprobados/` son la fuente documental y permanecen intactos. `ocr_pdf.py` solo acepta originales dentro de esa carpeta y publica el resultado en `corpus/ocr/`:

```bash
python scripts/ocr_pdf.py \
  corpus/aprobados/inen_paciente_oncologico_inmunodeprimido_2020.pdf

```

El comando anterior documenta el experimento ya realizado; **no repetirlo en esta fase**. El primer INEN fue rechazado por errores clínicamente relevantes. El segundo INEN, `inen_agentes_antineoplasicos_2023.pdf`, permanece candidato, requiere OCR y no está autorizado para procesamiento. Véanse el [gate de fidelidad documental](corpus/README.md#control-de-fidelidad-y-decisiones-de-curación) y el [manifest persistente](corpus/manifest_curacion.json). Se conserva toda la evidencia original.

El script:

1. confirma con PyMuPDF que el archivo requiere OCR;
2. comprueba OCRmyPDF, Tesseract, `spa`, `osd` y la compatibilidad real de `--rotate-pages`, `--deskew` y la opción de idioma;
3. ejecuta el equivalente a `ocrmypdf -l spa --rotate-pages --deskew entrada salida`, sin `--force-ocr`;
4. valida que se conserve el número de páginas y que el derivado tenga texto extraíble;
5. vuelve a comprobar el SHA-256 del original;
6. publica atómicamente `<nombre>_ocr.pdf` y `<nombre>_ocr.provenance.json`.

Nunca sobrescribe una salida existente. Ante un error, el archivo temporal se elimina y no queda un derivado parcial. La ficha JSON registra ambos hashes, versiones de OCRmyPDF/Tesseract, idioma, fecha, comando, métricas y la relación inequívoca entre fuente y derivado.

#### Validación y revisión obligatorias

La validación automática no autoriza la indexación. Cada ficha se crea con:

```json
{
  "revision_manual": {
    "estado": "pendiente",
    "indexable": false
  }
}
```

Ejecute para cada derivado:

```bash
python scripts/inspect_pdf.py \
  corpus/ocr/inen_paciente_oncologico_inmunodeprimido_2020_ocr.pdf \
  --paginas --chunks

python scripts/inspect_pdf.py \
  corpus/ocr/inen_agentes_antineoplasicos_2023_ocr.pdf \
  --paginas --chunks
```

Compare páginas totales/con texto, caracteres, caracteres ilegibles, títulos, chunks y tokens. Después inspeccione visualmente al menos diez páginas por documento: portada, índice, primera página de contenido, páginas intermedias, tablas, signos/síntomas y páginas finales. Verifique especialmente `mg`, `ml`, `mL`, `%`, `°`, números, rangos, siglas, medicamentos, títulos, viñetas y tablas. La lista de páginas distribuida que imprime el script es un punto de partida; debe sustituir o complementar páginas para cubrir todas esas categorías.

Un error OCR en una dosis, unidad, rango, porcentaje o medicamento es clínicamente relevante. Regístrelo y no indexe el documento hasta corregirlo o descartarlo. El pipeline actual mantiene `corpus/ocr/` fuera de la lista de rutas indexables, de modo que crear el derivado o ejecutar `inspect_pdf.py` nunca escribe chunks, embeddings ni filas en PostgreSQL.

#### Estrategias estructurales: PDF digital frente a OCR

`extract_pdf()` clasifica el origen como `digital` u `ocr`. No usa el sufijo `_ocr.pdf`: para reconocer OCR exige una ficha hermana `.provenance.json`, comprueba que `archivo_ocr` apunta al PDF inspeccionado y valida los SHA-256 tanto del derivado como de la fuente original. Una ficha presente pero incompleta, alterada o asociada a otro archivo detiene la extracción; no se degrada silenciosamente a `digital`.

La limpieza selecciona dos estrategias independientes:

| Origen | Estrategia de títulos |
|---|---|
| `digital` | `tipografia_digital`: conserva el detector validado basado en tamaño/negrita y estructura básica. |
| `ocr` | `estructura_textual_ocr`: una diferencia tipográfica nunca basta; exige brevedad, límites de palabras/líneas, capitalización o numeración estructural y ausencia de terminación propia de una oración. |

Para OCR también se neutralizan como estructura los rótulos repetidos en muchas páginas, se rechazan tamaños tipográficos desproporcionados y se impide que texto vertical/invertido de tablas o diagramas abra secciones. El texto no se elimina por estas reglas: permanece como contenido; únicamente deja de tratarse como título.

`inspect_pdf.py` registra explícitamente:

- origen de extracción y ficha de trazabilidad;
- estrategia de títulos;
- candidatos descartados por depender solo de tipografía OCR;
- rótulos repetidos neutralizados;
- páginas donde la orientación OCR no permite inferir títulos;
- títulos, chunks y distribución de tokens resultantes.

La misma información queda preparada en `ingesta.parametros` y `ingesta.metricas` para una futura ingesta revisada. La ruta `corpus/ocr/` sigue bloqueada para indexación y este diagnóstico no modifica PostgreSQL.

### Limpieza

Solo corrige forma (`src/ingestion/cleaner.py`): Unicode NFC (no NFKC, para no alterar `m²` o `µg`), ligaduras (`ﬁ` → `fi`), espacios especiales, guiones blandos, espacios repetidos, saltos de línea dentro de un párrafo y palabras partidas por guion al final de línea (solo minúscula + `-` / minúscula: `trata-`/`miento` → `tratamiento`; `A-`/`B` se conserva). Une un párrafo cortado por un salto de página cuando la página termina sin cierre de oración y la siguiente empieza en minúscula. No resume, no parafrasea, no traduce y no reconstruye tablas.

**Encabezados y pies**: las líneas candidatas deben estar en una banda exterior estrecha. La detección combina texto normalizado (incluidos números variables), posición vertical estable, recurrencia global y recurrencia dentro de páginas pares o impares. Así reconoce pies alternos y cintas repetitivas que no alcanzan por sí solas el 50 % global, sin eliminar una frase solo por repetirse en el cuerpo. El diagnóstico registra patrón, tipo `header/footer`, área, apariciones y páginas afectadas en `inspect_pdf.py` e `ingesta.metricas`.

**Índices**: una heurística conservadora combina rótulos como `Índice`/`Tabla de contenidos` con densidad de entradas `título … número`; sin rótulo exige una señal estructural más fuerte. Las páginas no se borran: sus chunks se guardan con `tipo_contenido='indice'` y quedan fuera de la recuperación normal. La metadata `paginas_indice` permite una corrección explícita y reproducible.

**Secciones**: un bloque es título si es corto (≤ 16 palabras, ≤ 150 caracteres), no termina como oración y su tipografía lo distingue (≥ 1,15 × el tamaño del cuerpo o íntegramente en negrita). Ese título se guarda como `fragmento.ubicacion`. Si no hay evidencia tipográfica, `ubicacion` queda `NULL`: no se inventan secciones.

### Chunking y tokenizer

```env
CHUNK_SIZE_TOKENS=450
CHUNK_OVERLAP_TOKENS=75
```

Valores iniciales, no definitivos; se registran en cada ingesta para comparar configuraciones. Los tokens se cuentan con el **tokenizer del propio ALIA** (`SINAI/ALIA-MrBERT-es-biomedical-embeddings`, SentencePiece, versión *fast*), sin tokens especiales; se toma del modelo ya cargado. ALIA (ModernBERT) acepta hasta 8192 tokens, así que 450 nunca se trunca.

Estrategia (`src/ingestion/chunker.py`):

1. Un título siempre abre un fragmento nuevo, sin solapamiento con la sección anterior.
2. Párrafos y elementos de lista se agregan enteros mientras quepan.
3. Un párrafo que no cabe solo se divide por oraciones (respetando abreviaturas como `Dr.`, `aprox.`).
4. Solo una oración más larga que el límite se corta por tokens, en inicio de palabra.
5. El solapamiento repite oraciones completas del final del fragmento anterior, hasta 75 tokens.

### Trazabilidad por página

Cada página conserva su número físico 1-based. Cada fragmento guarda `pagina_inicio`, `pagina_fin` (puede cruzar páginas), `token_count` y `ubicacion` (sección). `version_documento` guarda `hash_archivo` (SHA-256) y `ruta_archivo`. Cada ingesta completada deja una fila en `ingesta` con:

- `parametros`: versiones del pipeline, extractor (PyMuPDF/MuPDF) y limpieza, `chunk_size_tokens`, `chunk_overlap_tokens`, tokenizer, modelo, dimensión, normalización.
- `metricas`: páginas, caracteres, chunks, tokens min/max/promedio/mediana, embeddings, patrones eliminados, y tiempos de extracción, limpieza+chunking, embeddings, guardado y total.

## 9. API del prototipo

API HTTP (FastAPI) que expone **solo el retrieval ya implementado**: BGE-M3 dense (1024d) → pgvector, búsqueda exacta por distancia coseno, con los filtros normales del corpus (versión `activa`, `tipo_contenido = 'contenido'`). No incluye reranker, BM25, búsqueda híbrida ni LLM, y no genera respuestas: devuelve fragmentos con su fuente.

```bash
docker compose up -d
source .venv/bin/activate
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
# equivalente: python scripts/run_api.py --port 8000
```

- Swagger: <http://localhost:8000/docs>
- El modelo se carga **una vez** al iniciar (CUDA si está disponible) y se reutiliza. Use un único worker: cada worker cargaría otra copia en la GPU.
- Al arrancar se registran modelo, device, dimensión, base y nº de embeddings BGE-M3.
- El backend del prototipo (`vianova/backend`) también usa el puerto 8000; si se ejecutan a la vez, levante esta API con `--port 8001`.
- CORS: por defecto `http://localhost:5173` y `http://127.0.0.1:5173` (Vite). Otros orígenes: `API_CORS_ORIGINS="http://a:1,http://b:2"`.

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado; comprueba conexión real a PostgreSQL. 503 si la base o el modelo no están disponibles. |
| POST | `/api/rag/search` | Top-K fragmentos. `query` obligatoria y no vacía; `top_k` entre 1 y 10 (por defecto 3). |

Códigos: `422` request inválido, `503` base o modelo no disponibles, `500` error inesperado (sin stack trace; el detalle queda en el log del servidor).

### Ejemplo

```bash
curl -X POST http://localhost:8000/api/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "náuseas después de la quimioterapia", "top_k": 3}'
```

Respuesta real (texto recortado):

```json
{
  "query": "náuseas después de la quimioterapia",
  "model": "BAAI/bge-m3",
  "top_k": 3,
  "results": [
    {
      "rank": 1,
      "fragment_id": "da86be80-4b90-4385-a531-e982ae6c3b7a",
      "score": 0.69522,
      "distance": 0.30478,
      "text": "Náuseas y vómitos\n\n¿Qué son y por qué suceden?\n\nAlgunos tipos de quimioterapia pueden causar náuseas, vómitos o ambos. …",
      "document": "La quimioterapia y usted: Apoyo para las personas con cáncer",
      "entity": "National Cancer Institute (NCI)",
      "version": "2019",
      "section": "Náuseas y vómitos",
      "page_start": 65,
      "page_end": 65
    }
  ]
}
```

`score` = similitud coseno = `1 - distance`. `page_start`/`page_end` son páginas físicas del PDF.

```bash
curl http://localhost:8000/health
# {"status":"ok","database":"connected","model":"BAAI/bge-m3","retrieval":"pgvector_exact","device":"cuda","dimension":1024,"embeddings":419}
```

### Pruebas

```bash
pytest -q tests/test_api.py                          # rápidas: sin modelo ni base
pytest -q -m integration tests/test_api_integration.py  # BGE-M3 real + vianova_rag (solo lectura)
```

## Versiones validadas

Ejecutado en Linux (Fedora 42) con NVIDIA GeForce RTX 4060 Laptop GPU:

| Componente | Versión |
|---|---|
| Python | 3.13.13 |
| PyTorch | 2.14.1+cu130 (CUDA 13.0) |
| sentence-transformers | 6.2.0 |
| transformers | 5.20.2 |
| NumPy | 2.5.4 |
| psycopg | 3.3.6 (binary) |
| pgvector (Python) | 0.5.1 |
| PyMuPDF | 2.0 (MuPDF 1.28.5) |
| PostgreSQL | 16.15 (imagen `pgvector/pgvector:0.8.7-pg16@sha256:7b822b0a…`) |
| pgvector (extensión) | 0.8.7 |
| FastAPI / Uvicorn | 0.162.5 / 0.54.0 |
| Docker / Compose | 29.5.3 / v5.1.4 |

## Caché de Hugging Face

`sentence-transformers` reutiliza la caché estándar de Hugging Face. Normalmente se encuentra en `~/.cache/huggingface/hub` (Linux) o `%USERPROFILE%\.cache\huggingface\hub` (Windows), salvo que se configure `HF_HOME` o `HF_HUB_CACHE`.

Para liberar espacio puede borrar solo la carpeta del modelo dentro de `hub` cuando ningún proceso la esté usando. Hugging Face volverá a descargarla en la siguiente ejecución. También puede usar `hf cache ls` y `hf cache rm <model-id>` si tiene instalada una versión reciente de `huggingface_hub`.

## Alcance y seguridad clínica

Esta etapa demuestra ingestión documental y recuperación semántica persistente. La similitud no acredita corrección clínica: cualquier corpus y resultado destinado a cuidadores debe ser curado y validado por profesionales. Existe un experimento OCR rechazado y conservado como evidencia; el corpus activo de esta fase usa documentos digitales. La fase termina en la recuperación de fragmentos, expuesta mediante una API HTTP de solo retrieval para el prototipo, sin generación de respuestas ni LLM.

No deben guardarse en el repositorio contraseñas reales (`.env` está ignorado por Git), PDFs médicos personales ni información identificable de pacientes. El corpus de ejemplo (`src/sample_corpus.py`) es sintético.
