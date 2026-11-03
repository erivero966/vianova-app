"""Planilla ciega de revisión humana de pertinencia (Fase 4A.1).

Solo lee artefactos ya persistidos; no toca corpus, embeddings, rankings ni
PostgreSQL. La hoja visible no expone modelo, rank, similitud ni juicios
previos: esa información queda en un mapa interno separado.
"""

from collections import defaultdict
import random
from xml.sax.saxutils import escape
import re
import zipfile

SEED = 20261103
LIMIT_TAG = "[límite]"
NON_ACTIONABLE = {"introduccion_general", "definicion_causas", "preguntas_sin_respuesta", "lista_indice"}
SPECIAL_QUERIES = {"MD04", "MD10", "Q04"}
ALWAYS_P1 = {"MD10", "Q04"}

PENDING_COLUMNS = ["review_id", "prioridad", "consulta_id", "consulta", "fragmento_id", "documento",
                   "pagina_inicio", "pagina_fin", "seccion", "contexto_anterior", "texto",
                   "q04_especifico_infeccion", "juicio_humano", "observacion_humana"]
REVIEWED_COLUMNS = ["review_id", "consulta_id", "consulta", "fragmento_id", "documento", "pagina_inicio",
                    "pagina_fin", "seccion", "texto", "juicio_humano_original", "motivo_original"]
# Nada de esto puede aparecer como columna visible de la hoja de pendientes.
FORBIDDEN_COLUMNS = {"modelo", "alias", "rank", "posicion", "similitud", "distancia", "pertinente",
                     "tipo_juicio", "motivo", "categoria", "configuracion_id", "ocurrencias"}


def collect_pairs(judgments: list[dict]) -> dict[tuple[str, str], dict]:
    """Agrupa los juicios por (consulta_id, fragmento_id) conservando cada ocurrencia modelo/rank."""
    pairs = {}
    for j in judgments:
        key = (j["consulta_id"], j["fragmento_id"])
        pair = pairs.setdefault(key, {"judgment": {k: j[k] for k in ("pertinente", "tipo_juicio", "motivo",
                                                                     "fuente_juicio", "categoria")},
                                      "occurrences": []})
        if (pair["judgment"]["pertinente"], pair["judgment"]["tipo_juicio"]) != (j["pertinente"], j["tipo_juicio"]):
            raise ValueError(f"Juicios distintos para el mismo par {key}")
        pair["occurrences"].append({"modelo": j["modelo"], "rank": j["rank"], "en_top10": True})
    return pairs


def first_relevant_ranks(judgments: list[dict]) -> dict[tuple[str, str], int | None]:
    """(modelo, consulta) -> rank del primer pertinente actual (humano + asistido) en el Top-10."""
    ranks = defaultdict(list)
    for j in judgments:
        ranks[(j["modelo"], j["consulta_id"])].append(j)
    return {k: next((j["rank"] for j in sorted(v, key=lambda j: j["rank"]) if j["pertinente"]), None)
            for k, v in ranks.items()}


def priority(key: tuple[str, str], pair: dict, firsts: dict) -> tuple[int, list[str]]:
    query, _ = key
    reasons = []
    for occ in pair["occurrences"]:
        if not occ["en_top10"]:
            continue
        first = firsts[(occ["modelo"], query)]
        if first is None:
            reasons.append("sin_pertinente_en_top10")
        elif occ["rank"] <= first:
            reasons.append("antes_o_en_primer_pertinente")
    if query in ALWAYS_P1:
        reasons.append(f"{query}_obligatoria")
    if reasons:
        return 1, sorted(set(reasons))
    if LIMIT_TAG in (pair["judgment"].get("motivo") or ""):
        return 2, ["caso_limite"]
    if query in SPECIAL_QUERIES:
        return 3, [f"caso_especial_{query}"]
    if pair["judgment"].get("categoria") in NON_ACTIONABLE:
        return 3, ["introduccion_vs_consejo"]
    return 4, ["resto_top10"]


def ordered(items: list, seed: int = SEED) -> list:
    """Orden reproducible e independiente del modelo: por prioridad y aleatorio dentro de cada una."""
    result = []
    for prio in sorted({i["prioridad"] for i in items}):
        group = sorted((i for i in items if i["prioridad"] == prio),
                       key=lambda i: (i["consulta_id"], i["fragmento_id"]))
        random.Random(f"{seed}-{prio}").shuffle(group)
        result.extend(group)
    return result


def previous_context(chunk: dict, by_order: dict, chars: int = 400) -> str:
    prev = by_order.get((chunk["version_id"], chunk["orden"] - 1))
    if prev is None:
        return ""
    tail = prev["texto"][-chars:]
    return f"[{prev['ubicacion'] or 'sin sección'} · p. {prev['pagina_inicio']}] …{tail}"


# --- Escritura XLSX mínima con la biblioteca estándar --------------------------------------

_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _col(n: int) -> str:
    name = ""
    while n:
        n, r = divmod(n - 1, 26)
        name = chr(65 + r) + name
    return name


def _cell(ref: str, value, style: int) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    text = escape(_ILLEGAL.sub("", "" if value is None else str(value)))[:32767]
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet(columns: list[str], rows: list[dict], widths: dict, validations: dict) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
           'state="frozen"/></sheetView></sheetViews><cols>']
    for i, c in enumerate(columns, 1):
        out.append(f'<col min="{i}" max="{i}" width="{widths.get(c, 14)}" customWidth="1"/>')
    out.append("</cols><sheetData>")
    for r, row in enumerate([dict(zip(columns, columns))] + rows, 1):
        style = 1 if r == 1 else 2
        out.append(f'<row r="{r}">' + "".join(_cell(f"{_col(i)}{r}", row.get(c), style)
                                              for i, c in enumerate(columns, 1)) + "</row>")
    last = f"{_col(len(columns))}{len(rows) + 1}"
    out.append(f'</sheetData><autoFilter ref="A1:{last}"/>')
    if validations and rows:
        out.append(f'<dataValidations count="{len(validations)}">')
        for c, values in validations.items():
            ref = f"{_col(columns.index(c) + 1)}2:{_col(columns.index(c) + 1)}{len(rows) + 1}"
            out.append(f'<dataValidation type="list" allowBlank="1" showErrorMessage="1" sqref="{ref}">'
                       f'<formula1>"{",".join(values)}"</formula1></dataValidation>')
        out.append("</dataValidations>")
    out.append("</worksheet>")
    return "".join(out)


def write_xlsx(path, sheets: list[dict]) -> None:
    """sheets: [{name, columns, rows, widths, validations}] → .xlsx válido sin dependencias."""
    names = [s["name"] for s in sheets]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(1, len(sheets) + 1)) + "</Types>")
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   "</Relationships>")
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1))
                   + "</sheets>"
                   + "".join(f'<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
                             f"'{n}'!$A$1:${_col(len(s['columns']))}${len(s['rows']) + 1}</definedName></definedNames>"
                             for i, (n, s) in enumerate(zip(names, sheets)) if i == 0)
                   + "</workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                             for i in range(1, len(sheets) + 1))
                   + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                   "</Relationships>")
        z.writestr("xl/styles.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
                   '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
                   '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
                   '<fill><patternFill patternType="solid"><fgColor rgb="FFDDEBF7"/></patternFill></fill></fills>'
                   '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
                   '<cellXfs count="3"><xf/>'
                   '<xf fontId="1" fillId="2" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>'
                   '<xf applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs>'
                   "</styleSheet>")
        for i, s in enumerate(sheets, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml",
                       _sheet(s["columns"], s["rows"], s.get("widths", {}), s.get("validations", {})))


def read_xlsx_rows(path, sheet_index: int = 1) -> list[dict]:
    """Lee filas (inlineStr o sharedStrings) de una hoja; para validar y para aplicar la revisión."""
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        root = ET.fromstring(z.read(f"xl/worksheets/sheet{sheet_index}.xml"))
    table = []
    for row in root.find("m:sheetData", ns).findall("m:row", ns):
        cells = {}
        for c in row.findall("m:c", ns):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            if c.get("t") == "inlineStr":
                value = "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
            elif c.get("t") == "s":
                value = shared[int(c.find("m:v", ns).text)]
            else:
                v = c.find("m:v", ns)
                value = None if v is None else v.text
            cells[col] = value
        table.append(cells)
    if not table:
        return []
    header = table[0]
    return [{header[k]: v for k, v in r.items() if k in header} for r in table[1:]]
