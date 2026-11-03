# Corpus documental

| Carpeta | Uso | ¿Se indexa? |
|---|---|---|
| `candidatos/` | PDFs recibidos, pendientes de revisión profesional | No |
| `aprobados/` | PDFs revisados y aprobados, cada uno con su `.json` de metadatos | Sí (`scripts/ingest_pdf.py`) |
| `ocr/` | derivados técnicos OCR + ficha `.provenance.json` | No, mientras la revisión manual esté pendiente |
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
