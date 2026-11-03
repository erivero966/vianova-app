# Corpus documental

| Carpeta | Uso | ¿Se indexa? |
|---|---|---|
| `candidatos/` | PDFs recibidos, pendientes de revisión profesional | No |
| `aprobados/` | PDFs revisados y aprobados, cada uno con su `.json` de metadatos | Sí (`scripts/ingest_pdf.py`) |
| `ocr/` | derivados técnicos OCR + ficha `.provenance.json` | No; ruta bloqueada por el pipeline actual |
| `rechazados/` | PDFs descartados en la revisión | No |

El contenido de las carpetas está excluido de Git (`.gitignore`). No coloque
documentos con datos de pacientes.

Metadatos (`aprobados/<nombre>.json`, mismo nombre que el PDF):

```json
{
  "titulo": "Guía ...",
  "entidad": "INEN",
  "version": "2025",
  "url_origen": "https://...",
  "vigencia": "vigente"
}
```

`titulo`, `entidad` y `version` son obligatorios; `url_origen` y `vigencia`, opcionales.

Los PDFs escaneados de `aprobados/` se conservan intactos. Genere una copia con capa de texto mediante:

```bash
python scripts/ocr_pdf.py corpus/aprobados/<documento>.pdf
```

El resultado aparece en `ocr/<documento>_ocr.pdf`, acompañado por su trazabilidad. Es un derivado técnico: la fuente documental continúa siendo el original de `aprobados/`. No se indexa hasta completar la inspección automática y el muestreo visual descritos en el README principal.

## Control de fidelidad y decisiones de curación

> La finalización técnica del OCR no implica que un documento pueda incorporarse al corpus.

La aprobación depende de la fidelidad documental, especialmente en números, unidades, medicamentos y relaciones entre celdas de tablas.

```text
Documento candidato
    ↓
inspección
    ↓
¿texto digital?
    ├── sí → limpieza/chunking → revisión de metadata y contenido → elegible
    └── no → OCR (solo si está autorizado)
                ↓
           revisión manual
                ↓
           ¿OCR confiable?
                ├── sí → elegible para aprobación de ingesta
                └── no → rechazado; indexable=false
```

El [manifest de curación](manifest_curacion.json) registra el rechazo del primer INEN y la suspensión del segundo. El original, derivado, procedencia e informes se conservan en sus rutas como evidencia experimental. Estar físicamente en `aprobados/` no revoca una decisión de rechazo: los INEN se mantienen allí para no mover ni alterar la evidencia.

La procedencia del primer OCR conserva el estado histórico `pendiente`; la decisión posterior **rechazado** está en el manifest. Este registro es administrativo, no un nuevo mecanismo automático de autorización. Las barreras técnicas existentes rechazan la ruta `ocr/` y los originales sin texto. No usar `--todos` para este corpus mixto ni intentar eludir esas barreras; ejecutar únicamente ingestas explícitas de los NCI digitales autorizados. No se habilita ingesta OCR en esta fase.

Las métricas completas del experimento fallido están en el manifest y en [la revisión manual](../eval/ocr_inen_inmunodeprimido_revision_manual.md), para futuras secciones de validación y limitaciones. No se realizará otro OCR del primer INEN ni del documento de agentes antineoplásicos en esta fase.
