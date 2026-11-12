from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def col_to_idx(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx_sheet(path: Path, sheet_name: str) -> list[list]:
    ns = {'m': MAIN_NS, 'r': REL_NS}
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap = {r.attrib['Id']: r.attrib['Target'] for r in rels}
        target = None
        for s in wb.find('m:sheets', ns):
            if s.attrib['name'] == sheet_name:
                rid = s.attrib[f'{{{REL_NS}}}id']
                target = relmap[rid]
                break
        if target is None:
            raise ValueError(f'No existe la hoja {sheet_name!r}')
        xml_path = target.lstrip('/') if target.startswith('/') else ('xl/' + target if not target.startswith('xl/') else target)
        root = ET.fromstring(z.read(xml_path))
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            sroot = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in sroot.findall(f'{{{MAIN_NS}}}si'):
                shared.append(''.join((t.text or '') for t in si.iter(f'{{{MAIN_NS}}}t')))
        rows = []
        for row in root.findall(f'.//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row'):
            values = {}
            for c in row.findall(f'{{{MAIN_NS}}}c'):
                ref = c.attrib['r']
                m = re.match(r'([A-Z]+)(\d+)$', ref)
                if not m:
                    continue
                ci = col_to_idx(m.group(1))
                typ = c.attrib.get('t')
                val = None
                if typ == 'inlineStr':
                    val = ''.join((t.text or '') for t in c.iter(f'{{{MAIN_NS}}}t'))
                else:
                    v = c.find(f'{{{MAIN_NS}}}v')
                    if v is not None:
                        raw = v.text or ''
                        if typ == 's':
                            val = shared[int(raw)]
                        elif typ == 'b':
                            val = raw == '1'
                        else:
                            try:
                                num = float(raw)
                                val = int(num) if num.is_integer() else num
                            except ValueError:
                                val = raw
                values[ci] = val
            max_col = max(values, default=-1)
            rows.append([values.get(i) for i in range(max_col + 1)])
        return rows


def rows_to_records(rows: list[list]) -> list[dict]:
    if not rows:
        return []
    headers = rows[0]
    out = []
    for row in rows[1:]:
        row = row + [None] * (len(headers) - len(row))
        out.append(dict(zip(headers, row)))
    return out


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def dump_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def validate_sources(repo: Path, map_data: dict):
    required = {
        'eval/resultados/model_comparison_v01/alia.json',
        'eval/resultados/model_comparison_v01/qwen3.json',
        'eval/resultados/model_comparison_v01/bge_m3.json',
        'eval/resultados/model_comparison_v01/judgments.json',
    }
    errors, checked, missing_optional = [], [], []
    for rel, expected in map_data.get('fuentes_sha256', {}).items():
        p = repo / rel
        if not p.exists():
            if rel in required:
                errors.append(f'Falta fuente obligatoria: {rel}')
            else:
                missing_optional.append(rel)
            continue
        actual = sha256_file(p)
        checked.append({'ruta': rel, 'sha256': actual})
        if actual != expected:
            errors.append(f'SHA-256 no coincide para {rel}: {actual} != {expected}')
    if errors:
        raise ValueError('\n'.join(errors))
    return checked, missing_optional


def build_review_maps(xlsx: Path, map_data: dict):
    pending = rows_to_records(read_xlsx_sheet(xlsx, 'PENDIENTES_REVISION_HUMANA'))
    old = rows_to_records(read_xlsx_sheet(xlsx, 'YA_REVISADOS_HUMANO'))
    if len(pending) != 214:
        raise ValueError(f'Se esperaban 214 pendientes; hay {len(pending)}')
    if len(old) != 75:
        raise ValueError(f'Se esperaban 75 humanos originales; hay {len(old)}')
    seen = set()
    for r in pending:
        rid = str(r.get('review_id') or '')
        if rid in seen:
            raise ValueError(f'review_id duplicado: {rid}')
        seen.add(rid)
        if rid not in map_data['entradas']:
            raise ValueError(f'review_id desconocido: {rid}')
        try:
            grade = int(r['juicio_humano'])
        except Exception:
            raise ValueError(f'{rid}: juicio_humano vacío o inválido')
        if grade not in (0, 1, 2):
            raise ValueError(f'{rid}: juicio_humano fuera de 0/1/2: {grade}')
        entry = map_data['entradas'][rid]
        if r['consulta_id'] != entry['consulta_id'] or r['fragmento_id'] != entry['fragmento_id']:
            raise ValueError(f'{rid}: IDs no coinciden con el mapa')
        if sha256_text(r['texto'] or '') != entry['texto_sha256']:
            raise ValueError(f'{rid}: hash del texto no coincide')
    for r in old:
        rid = str(r.get('review_id') or '')
        if rid not in map_data['entradas']:
            raise ValueError(f'{rid}: humano original no existe en mapa')
        entry = map_data['entradas'][rid]
        if r['consulta_id'] != entry['consulta_id'] or r['fragmento_id'] != entry['fragmento_id']:
            raise ValueError(f'{rid}: IDs humanos originales no coinciden')
        if sha256_text(r['texto'] or '') != entry['texto_sha256']:
            raise ValueError(f'{rid}: hash humano original no coincide')
    old_keys = {(r['consulta_id'], r['fragmento_id']) for r in old}
    new_keys = {(r['consulta_id'], r['fragmento_id']) for r in pending}
    if old_keys & new_keys:
        raise ValueError('Hay pares presentes como humano original y revisión nueva')
    return pending, old


def combined_judgments(pending: list[dict], old: list[dict], map_data: dict):
    pair_records = []
    pair_lookup = {}
    review_lookup = {}
    for r in old:
        yes = str(r['juicio_humano_original']).strip().lower() in {'sí', 'si', 'true', '1'}
        entry = map_data['entradas'][r['review_id']]
        rec = {
            'review_id': r['review_id'],
            'consulta_id': r['consulta_id'],
            'fragmento_id': r['fragmento_id'],
            'documento': r['documento'],
            'pagina_inicio': r['pagina_inicio'],
            'pagina_fin': r['pagina_fin'],
            'seccion': r['seccion'],
            'tipo_juicio': 'humano_original',
            'valor_original': r['juicio_humano_original'],
            'grado_humano': 2 if yes else 0,
            'pertinente_estricto': yes,
            'pertinente_laxo': yes,
            'observacion_humana': r['motivo_original'],
            'q04_especifico_infeccion': None,
            'texto_sha256': entry['texto_sha256'],
            'ocurrencias': entry.get('ocurrencias', []),
            'juicio_previo': entry.get('juicio_previo'),
        }
        key = (rec['consulta_id'], rec['fragmento_id'])
        pair_lookup[key] = rec
        review_lookup[rec['review_id']] = rec
        pair_records.append(rec)
    for r in pending:
        grade = int(r['juicio_humano'])
        entry = map_data['entradas'][r['review_id']]
        rec = {
            'review_id': r['review_id'],
            'consulta_id': r['consulta_id'],
            'fragmento_id': r['fragmento_id'],
            'documento': r['documento'],
            'pagina_inicio': r['pagina_inicio'],
            'pagina_fin': r['pagina_fin'],
            'seccion': r['seccion'],
            'tipo_juicio': 'humano_revision_4a1',
            'valor_original': grade,
            'grado_humano': grade,
            'pertinente_estricto': grade == 2,
            'pertinente_laxo': grade >= 1,
            'observacion_humana': r['observacion_humana'],
            'q04_especifico_infeccion': r.get('q04_especifico_infeccion'),
            'texto_sha256': entry['texto_sha256'],
            'ocurrencias': entry.get('ocurrencias', []),
            'juicio_previo': entry.get('juicio_previo'),
        }
        key = (rec['consulta_id'], rec['fragmento_id'])
        pair_lookup[key] = rec
        review_lookup[rec['review_id']] = rec
        pair_records.append(rec)
    return pair_records, pair_lookup, review_lookup


def build_slots(model_data: dict, pair_lookup: dict):
    slots = []
    for alias, data in model_data.items():
        for item in data['resultados']:
            key = (item['consulta_id'], item['fragmento_id'])
            rec = pair_lookup.get(key)
            if rec is None:
                raise ValueError(f'Sin juicio humano para slot {alias} {item["consulta_id"]} rank {item["rank"]}: {item["fragmento_id"]}')
            slots.append({
                'modelo': alias,
                'consulta_id': item['consulta_id'],
                'rank': item['rank'],
                'fragmento_id': item['fragmento_id'],
                'review_id': rec['review_id'],
                'grado_humano': rec['grado_humano'],
                'tipo_juicio': rec['tipo_juicio'],
                'pertinente_estricto': rec['pertinente_estricto'],
                'pertinente_laxo': rec['pertinente_laxo'],
            })
    return slots


def compute_metrics(model_data: dict, pair_lookup: dict, mode: str):
    keyname = 'pertinente_estricto' if mode == 'strict' else 'pertinente_laxo'
    out = {}
    for alias, data in model_data.items():
        byq = defaultdict(list)
        for item in data['resultados']:
            if item['consulta_id'].startswith('MD'):
                byq[item['consulta_id']].append(item)
        first = {}
        per_query = {}
        hit_counts = {1: 0, 3: 0, 5: 0, 10: 0}
        reciprocal = []
        for qid in sorted(byq):
            items = sorted(byq[qid], key=lambda x: x['rank'])
            relevant = []
            top = []
            for item in items:
                rec = pair_lookup[(qid, item['fragmento_id'])]
                rel = bool(rec[keyname])
                top.append({
                    'rank': item['rank'],
                    'fragmento_id': item['fragmento_id'],
                    'review_id': rec['review_id'],
                    'grado_humano': rec['grado_humano'],
                    'pertinente': rel,
                })
                if rel:
                    relevant.append(item['rank'])
            fr = min(relevant) if relevant else None
            first[qid] = fr
            for k in hit_counts:
                if fr is not None and fr <= k:
                    hit_counts[k] += 1
            reciprocal.append(1.0 / fr if fr else 0.0)
            per_query[qid] = {'primer_pertinente': fr, 'top10': top}
        n = len(byq)
        out[alias] = {
            'consultas': n,
            'Hit@1': hit_counts[1] / n,
            'Hit@3': hit_counts[3] / n,
            'Hit@5': hit_counts[5] / n,
            'Hit@10': hit_counts[10] / n,
            'Hit@1_count': hit_counts[1],
            'Hit@3_count': hit_counts[3],
            'Hit@5_count': hit_counts[5],
            'Hit@10_count': hit_counts[10],
            'MRR@10': sum(reciprocal) / n,
            'primer_pertinente_por_consulta': first,
            'por_consulta': per_query,
        }
    return out


def q04_analysis(pair_records: list[dict]):
    models = ['alia', 'qwen3', 'bge-m3']
    result = {}
    historical_id = None
    for rec in pair_records:
        if rec['consulta_id'] == 'Q04' and rec['pagina_inicio'] == 62 and (rec['seccion'] or '').startswith('Además de la fiebre'):
            historical_id = rec['fragmento_id']
            break
    for model in models:
        rows = []
        for rec in pair_records:
            if rec['consulta_id'] != 'Q04':
                continue
            for occ in rec.get('ocurrencias', []):
                if occ['modelo'] == model:
                    rows.append((occ['rank'], rec))
        rows.sort(key=lambda x: x[0])
        strict = [rank for rank, rec in rows if rec['pertinente_estricto']]
        lenient = [rank for rank, rec in rows if rec['pertinente_laxo']]
        specific = [rank for rank, rec in rows if rec.get('q04_especifico_infeccion') == 'S']
        specific_strict = [rank for rank, rec in rows if rec.get('q04_especifico_infeccion') == 'S' and rec['pertinente_estricto']]
        hist = [rank for rank, rec in rows if rec['fragmento_id'] == historical_id]
        result[model] = {
            'primer_pertinente_estricto': min(strict) if strict else None,
            'primer_pertinente_laxo': min(lenient) if lenient else None,
            'primer_fragmento_especifico_infeccion': min(specific) if specific else None,
            'primer_fragmento_especifico_y_pertinente_estricto': min(specific_strict) if specific_strict else None,
            'rank_fragmento_historico_p62': min(hist) if hist else None,
            'fragmento_historico_id': historical_id,
        }
    return result


def md10_top5(model_data: dict, pair_lookup: dict):
    out = {}
    for alias, data in model_data.items():
        items = sorted([x for x in data['resultados'] if x['consulta_id'] == 'MD10'], key=lambda x: x['rank'])[:5]
        out[alias] = []
        for x in items:
            rec = pair_lookup[('MD10', x['fragmento_id'])]
            out[alias].append({
                'rank': x['rank'],
                'fragmento_id': x['fragmento_id'],
                'documento': x['documento'],
                'pagina_inicio': x['pagina_inicio'],
                'pagina_fin': x['pagina_fin'],
                'seccion': x['seccion'],
                'grado_humano': rec['grado_humano'],
                'pertinente_estricto': rec['pertinente_estricto'],
                'pertinente_laxo': rec['pertinente_laxo'],
                'observacion_humana': rec['observacion_humana'],
                'texto_inicio': ' '.join((x['texto'] or '').split())[:280],
            })
    return out


def prelim_metrics(metrics_pre: dict):
    out = {}
    for alias, d in metrics_pre['modelos'].items():
        m = d['metricas_preliminares_humano_mas_asistido']
        out[alias] = m
    return out


def fmt_rate(v):
    return f'{v * 100:.1f}%'


def fmt_mrr(v):
    return f'{v:.3f}'


def write_report(path: Path, pending, old, strict, lenient, prelim, q04, md10, pair_records, map_data):
    dist = Counter(int(r['juicio_humano']) for r in pending)
    old_dist = Counter(str(r['juicio_humano_original']).strip() for r in old)
    prior_change = Counter()
    prior_assisted = {}
    for rec in pair_records:
        if rec['tipo_juicio'] != 'humano_revision_4a1':
            continue
        prev = rec.get('juicio_previo') or {}
        if prev.get('tipo_juicio') == 'asistido_preliminar':
            prior = bool(prev.get('pertinente'))
            prior_assisted[(rec['consulta_id'], rec['fragmento_id'])] = prior
            prior_change[(prior, rec['grado_humano'])] += 1
    lines = []
    lines.append('# Comparación de modelos v0.1 — revisión humana consolidada\n')
    lines.append('## Resumen\n')
    lines.append('La revisión ciega humana se aplicó a los 214 pares que no tenían juicio humano original. Los 75 pares humanos previos se conservaron sin cambios. Las métricas se recalcularon sin modificar embeddings, rankings, consultas ni PostgreSQL.\n')
    lines.append(f'- Pares únicos evaluados: **{len(pair_records)}**.')
    lines.append(f'- Humanos originales: **{len(old)}** (Sí={old_dist.get("Sí",0)}, No={old_dist.get("No",0)}).')
    lines.append(f'- Revisión humana 4A.1: **{len(pending)}** (0={dist[0]}, 1={dist[1]}, 2={dist[2]}).')
    lines.append('- Escenario estricto: solo `2` cuenta como pertinente; los humanos binarios originales mantienen Sí/No.')
    lines.append('- Escenario laxo: `1` y `2` cuentan como pertinentes; los humanos binarios originales mantienen Sí/No.\n')

    lines.append('## Métricas finales con revisión humana\n')
    lines.append('### Escenario estricto\n')
    lines.append('| Modelo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 |')
    lines.append('|---|---:|---:|---:|---:|---:|')
    for a in ['alia','qwen3','bge-m3']:
        m = strict[a]
        lines.append(f'| {a} | {m["Hit@1_count"]}/15 | {m["Hit@3_count"]}/15 | {m["Hit@5_count"]}/15 | {m["Hit@10_count"]}/15 | {fmt_mrr(m["MRR@10"])} |')
    lines.append('')
    lines.append('### Escenario laxo\n')
    lines.append('| Modelo | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR@10 |')
    lines.append('|---|---:|---:|---:|---:|---:|')
    for a in ['alia','qwen3','bge-m3']:
        m = lenient[a]
        lines.append(f'| {a} | {m["Hit@1_count"]}/15 | {m["Hit@3_count"]}/15 | {m["Hit@5_count"]}/15 | {m["Hit@10_count"]}/15 | {fmt_mrr(m["MRR@10"])} |')
    lines.append('')

    lines.append('## Comparación contra la evaluación preliminar\n')
    lines.append('| Modelo | Prelim. Hit@1 | Estricto Hit@1 | Laxo Hit@1 | Prelim. MRR | Estricto MRR | Laxo MRR |')
    lines.append('|---|---:|---:|---:|---:|---:|---:|')
    for a in ['alia','qwen3','bge-m3']:
        p = prelim[a]
        lines.append(f'| {a} | {round(p["Hit@1"]*15)}/15 | {strict[a]["Hit@1_count"]}/15 | {lenient[a]["Hit@1_count"]}/15 | {p["MRR@10"]:.3f} | {strict[a]["MRR@10"]:.3f} | {lenient[a]["MRR@10"]:.3f} |')
    lines.append('')
    lines.append('Con criterio estricto, la revisión humana reduce especialmente los primeros puestos de Qwen3 y BGE-M3. ALIA conserva exactamente su baseline porque su Top-5 ya estaba cubierto por los juicios humanos originales. BGE-M3 continúa con las mejores métricas en ambos escenarios.\n')

    lines.append('## Primer fragmento pertinente por consulta\n')
    lines.append('### Estricto\n')
    lines.append('| Consulta | ALIA | Qwen3 | BGE-M3 |')
    lines.append('|---|---:|---:|---:|')
    qids = sorted(strict['alia']['primer_pertinente_por_consulta'])
    for q in qids:
        def v(a):
            x = strict[a]['primer_pertinente_por_consulta'][q]
            return str(x) if x is not None else '—'
        lines.append(f'| {q} | {v("alia")} | {v("qwen3")} | {v("bge-m3")} |')
    lines.append('')
    lines.append('### Laxo\n')
    lines.append('| Consulta | ALIA | Qwen3 | BGE-M3 |')
    lines.append('|---|---:|---:|---:|')
    for q in qids:
        def v2(a):
            x = lenient[a]['primer_pertinente_por_consulta'][q]
            return str(x) if x is not None else '—'
        lines.append(f'| {q} | {v2("alia")} | {v2("qwen3")} | {v2("bge-m3")} |')
    lines.append('')

    lines.append('## Cambios frente a los juicios asistidos\n')
    lines.append('Entre los 210 pares que tenían un juicio `asistido_preliminar` y luego fueron revisados por una persona:')
    lines.append(f'- IA No → humano 0: **{prior_change[(False,0)]}**.')
    lines.append(f'- IA No → humano 1: **{prior_change[(False,1)]}**.')
    lines.append(f'- IA Sí → humano 0: **{prior_change[(True,0)]}**.')
    lines.append(f'- IA Sí → humano 1: **{prior_change[(True,1)]}**.')
    lines.append(f'- IA Sí → humano 2: **{prior_change[(True,2)]}**.')
    lines.append('Esto confirma que los juicios asistidos eran útiles como cribado preliminar, pero no sustituyen la revisión humana.\n')

    lines.append('## Q04 — signos de infección durante la quimioterapia\n')
    lines.append('| Modelo | Primer pertinente estricto | Primer pertinente laxo | Primer fragmento específico de infección | Fragmento histórico p. 62 |')
    lines.append('|---|---:|---:|---:|---:|')
    for a in ['alia','qwen3','bge-m3']:
        q = q04[a]
        lines.append(f'| {a} | {q["primer_pertinente_estricto"] or "—"} | {q["primer_pertinente_laxo"] or "—"} | {q["primer_fragmento_especifico_infeccion"] or "—"} | {q["rank_fragmento_historico_p62"] or "—"} |')
    lines.append('')
    lines.append('La revisión humana corrige la interpretación preliminar: los resultados de síntomas tipo influenza en rank 1 de ALIA/Qwen3 no cuentan como pertinentes. El primer fragmento claramente pertinente queda en rank 7 para ALIA, rank 9 para Qwen3 y rank 2 para BGE-M3. El fragmento histórico de la lista directa de signos (p. 62) queda en ranks 54, 22 y 5, respectivamente.\n')

    lines.append('## MD10 — pérdida de peso\n')
    lines.append('Los tres modelos siguen mostrando confusión con fragmentos sobre aumento de peso. La revisión humana marca esos fragmentos como no pertinentes. Primer pertinente estricto: ALIA rank 4, Qwen3 rank 2 y BGE-M3 rank 5. En el escenario laxo BGE-M3 obtiene un parcial en rank 3, pero su primer fragmento plenamente pertinente continúa en rank 5.\n')
    for a in ['alia','qwen3','bge-m3']:
        lines.append(f'### {a}\n')
        lines.append('| Rank | Grado | Página | Sección | Observación humana |')
        lines.append('|---:|---:|---:|---|---|')
        for x in md10[a]:
            obs = (x['observacion_humana'] or '').replace('|','\\|').replace('\n',' ')
            sec = (x['seccion'] or '—').replace('|','\\|')
            lines.append(f'| {x["rank"]} | {x["grado_humano"]} | {x["pagina_inicio"]} | {sec} | {obs} |')
        lines.append('')

    lines.append('## Conclusión de esta fase\n')
    lines.append('- **BGE-M3 dense** conserva el mejor desempeño en el corpus v0.1 tanto con criterio estricto como laxo.')
    lines.append('- Esto no constituye una selección definitiva para Vianova: el banco contiene solo 15 consultas y 3 documentos.')
    lines.append('- La diferencia entre estricto y laxo muestra que varios resultados altos son relacionados, pero incompletos. Por ello, una siguiente fase de reranking puede ser pertinente, especialmente para priorizar fragmentos plenamente accionables.')
    lines.append('- El caso pérdida/aumento de peso sigue demostrando que similitud semántica alta no equivale a responder correctamente la intención.')
    lines.append('')
    lines.append('## Integridad\n')
    lines.append(f'- Semilla de la revisión ciega: `{map_data.get("semilla_aleatoria")}`.')
    lines.append('- Los resultados de retrieval originales no fueron modificados; solo se generaron artefactos derivados de evaluación humana.')
    lines.append('- No se ejecutaron embeddings, búsquedas ni escrituras en PostgreSQL durante este recálculo.')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_q04_report(path: Path, q04: dict, pair_records: list[dict]):
    lines = ['# Q04 — comparación con revisión humana\n', 'Consulta: `signos de infección durante la quimioterapia`\n']
    lines += ['| Modelo | Primer pertinente estricto | Primer pertinente laxo | Primer específico infección | Fragmento histórico p. 62 |', '|---|---:|---:|---:|---:|']
    for a in ['alia','qwen3','bge-m3']:
        q=q04[a]
        lines.append(f'| {a} | {q["primer_pertinente_estricto"] or "—"} | {q["primer_pertinente_laxo"] or "—"} | {q["primer_fragmento_especifico_infeccion"] or "—"} | {q["rank_fragmento_historico_p62"] or "—"} |')
    lines.append('')
    lines.append('## Fragmentos específicos revisados\n')
    lines.append('| Página | Sección | Grado | Observación | Ranks por modelo |')
    lines.append('|---:|---|---:|---|---|')
    for r in sorted([x for x in pair_records if x['consulta_id']=='Q04' and x.get('q04_especifico_infeccion')=='S'], key=lambda x:(x['pagina_inicio'] or 0,x['review_id'])):
        ranks=', '.join(f'{o["modelo"]}:{o["rank"]}' for o in sorted(r['ocurrencias'],key=lambda x:(x['modelo'],x['rank'])))
        obs=(r['observacion_humana'] or '').replace('|','\\|').replace('\n',' ')
        sec=(r['seccion'] or '—').replace('|','\\|')
        lines.append(f'| {r["pagina_inicio"]} | {sec} | {r["grado_humano"]} | {obs} | {ranks} |')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def process(repo: Path, xlsx: Path, out_root: Path):
    map_path = repo / 'eval/revision_humana_model_comparison_v01_map.json'
    map_data = load_json(map_path)
    checked, missing_optional = validate_sources(repo, map_data)
    pending, old = build_review_maps(xlsx, map_data)
    pair_records, pair_lookup, review_lookup = combined_judgments(pending, old, map_data)
    model_files = {'alia':'alia.json','qwen3':'qwen3.json','bge-m3':'bge_m3.json'}
    model_data = {a: load_json(repo / 'eval/resultados/model_comparison_v01' / fn) for a,fn in model_files.items()}
    slots = build_slots(model_data, pair_lookup)
    if len(slots) != 480:
        raise ValueError(f'Se esperaban 480 slots (incluido Q04); hay {len(slots)}')
    strict = compute_metrics(model_data, pair_lookup, 'strict')
    lenient = compute_metrics(model_data, pair_lookup, 'lenient')
    q04 = q04_analysis(pair_records)
    md10 = md10_top5(model_data, pair_lookup)
    metrics_pre = load_json(repo / 'eval/resultados/model_comparison_v01/metrics.json')
    prelim = prelim_metrics(metrics_pre)

    dist = Counter(int(r['juicio_humano']) for r in pending)
    judgments_out = {
        'version': '4A.1-human-reviewed',
        'fecha_utc': datetime.now(timezone.utc).isoformat(),
        'fuentes': {
            'xlsx_revision_humana': str(xlsx),
            'xlsx_sha256': sha256_file(xlsx),
            'mapa': 'eval/revision_humana_model_comparison_v01_map.json',
            'mapa_sha256': sha256_file(map_path),
            'fuentes_validadas': checked,
            'fuentes_opcionales_no_disponibles_en_paquete': missing_optional,
        },
        'reglas': {
            'estricto': 'Humano original Sí=pertinente/No=no; revisión 4A.1 solo grado 2=pertinente.',
            'laxo': 'Humano original Sí=pertinente/No=no; revisión 4A.1 grados 1 o 2=pertinente.',
            'precedencia': 'humano_revision_4a1 > asistido_preliminar; humano_original se conserva inmutable.',
        },
        'recuentos': {
            'pares_unicos': len(pair_records),
            'humano_original': len(old),
            'humano_revision_4a1': len(pending),
            'revision_4a1_grado_0': dist[0],
            'revision_4a1_grado_1': dist[1],
            'revision_4a1_grado_2': dist[2],
            'slots_modelo_consulta_rank': len(slots),
        },
        'juicios_pares': sorted(pair_records, key=lambda x:x['review_id']),
        'slots': sorted(slots, key=lambda x:(x['modelo'],x['consulta_id'],x['rank'])),
    }
    metrics_out = {
        'version': '4A.1-human-reviewed',
        'fecha_utc': datetime.now(timezone.utc).isoformat(),
        'consultas_metricas_principales': 'MD01-MD15',
        'preliminar_humano_mas_asistido': prelim,
        'strict': strict,
        'lenient': lenient,
        'q04': q04,
        'md10_top5': md10,
        'nota': 'Q04 se analiza por separado y no entra en Hit@K/MRR de MD01-MD15.',
    }

    target_dir = out_root / 'eval/resultados/model_comparison_v01'
    dump_json(target_dir / 'judgments_human_reviewed.json', judgments_out)
    dump_json(target_dir / 'metrics_human_reviewed.json', metrics_out)
    write_report(out_root / 'eval/model_comparison_v01_human_reviewed.md', pending, old, strict, lenient, prelim, q04, md10, pair_records, map_data)
    write_q04_report(out_root / 'eval/q04_model_comparison_human_reviewed.md', q04, pair_records)
    return judgments_out, metrics_out


def main():
    ap=argparse.ArgumentParser(description='Aplica la revisión humana ciega de Fase 4A.1 y recalcula métricas sin tocar retrieval/DB.')
    ap.add_argument('--repo', type=Path, default=Path('.'))
    ap.add_argument('--xlsx', type=Path, default=Path('eval/revision_humana_model_comparison_v01.xlsx'))
    ap.add_argument('--out-root', type=Path, default=None, help='Por defecto escribe en el repo.')
    args=ap.parse_args()
    repo=args.repo.resolve(); xlsx=(repo/args.xlsx).resolve() if not args.xlsx.is_absolute() else args.xlsx.resolve()
    out=(args.out_root.resolve() if args.out_root else repo)
    _, metrics=process(repo,xlsx,out)
    for scenario in ('strict','lenient'):
        print(f'[{scenario}]')
        for a in ('alia','qwen3','bge-m3'):
            m=metrics[scenario][a]
            print(f'{a}: H@1 {m["Hit@1_count"]}/15, H@3 {m["Hit@3_count"]}/15, H@5 {m["Hit@5_count"]}/15, H@10 {m["Hit@10_count"]}/15, MRR {m["MRR@10"]:.3f}')

if __name__=='__main__':
    main()
