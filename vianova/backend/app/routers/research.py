"""Módulo del investigador: indicadores, exportación seudonimizada de registros y auditoría."""
import csv
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..indicators import participant_indicators, weekly
from ..logs import audit
from ..models import User, EventLog, AuditLog
from ..security import require
from ..timeutil import now, parse, iso
from .. import config
import json

router = APIRouter(prefix="/api/research", tags=["investigador"])
investigador = require("investigador", "curador")


def _range(start: str | None, end: str | None) -> tuple[datetime, datetime]:
    e = parse(end) if end else now()
    s = parse(start) if start else e - timedelta(weeks=8)
    return s, e


@router.get("/indicators")
def indicators(start: str | None = None, end: str | None = None, user: User = Depends(investigador),
               db: Session = Depends(get_db)):
    s, e = _range(start, end)
    rows = [participant_indicators(db, u, s, e) for u in db.query(User).filter(User.role == "cuidador").order_by(User.code)]
    valid = [r for r in rows if r["dias_con_uso"]]
    def mean(key):
        vals = [r[key] for r in valid if r[key] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None
    return {"inicio": iso(s), "fin": iso(e), "participantes": rows,
            "resumen": {"n_con_uso": len(valid), "actividades_por_dia_media": mean("actividades_por_dia"),
                        "pct_tareas_a_tiempo_media": mean("pct_tareas_a_tiempo"), "ingresos_media": mean("ingresos")}}


@router.get("/weekly/{code}")
def weekly_ind(code: str, start: str | None = None, user: User = Depends(investigador), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.code == code).first()
    if not u:
        raise HTTPException(404, "Participante no encontrado")
    first = db.query(EventLog).filter(EventLog.id_participante == code).order_by(EventLog.fecha_hora).first()
    s = parse(start) if start else (datetime.combine(first.fecha_hora.date(), datetime.min.time()) if first else now())
    return weekly(db, u, s, 8)


@router.get("/logs.csv")
def logs_csv(start: str | None = None, end: str | None = None, user: User = Depends(investigador),
             db: Session = Depends(get_db)):
    s, e = _range(start, end)
    q = db.query(EventLog).filter(EventLog.fecha_hora >= s, EventLog.fecha_hora <= e).order_by(EventLog.fecha_hora)
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["id_evento", "id_participante", "fecha_hora", "tipo_evento", "modulo", "id_recurso", "hora_programada",
            "canal", "resultado", "fuente_id", "version_corpus", "duracion_ms"]
    w.writerow(cols)
    n = 0
    for l in q:
        w.writerow([l.id_evento, l.id_participante, iso(l.fecha_hora), l.tipo_evento, l.modulo, l.id_recurso,
                    iso(l.hora_programada), l.canal, l.resultado, l.fuente_id, l.version_corpus, l.duracion_ms])
        n += 1
    audit(db, user, "exportar_registros", f"{n} registros {iso(s)} a {iso(e)}")
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=registros_sistema.csv"})


@router.get("/audit")
def audit_log(user: User = Depends(require("curador", "investigador")), db: Session = Depends(get_db)):
    return [{"at": iso(a.at), "user": a.user_code, "action": a.action, "detail": a.detail}
            for a in db.query(AuditLog).order_by(AuditLog.at.desc()).limit(200)]


@router.get("/validation")
def validation(user: User = Depends(investigador)):
    """Resultados de la validación técnica del RAG (eval/run_eval.py) y de la suite de pruebas, si existen."""
    out = {"metricas": None, "casos": [], "pruebas": None}
    m = config.EVAL_RESULTS_DIR / "metricas.json"
    if m.exists():
        out["metricas"] = json.loads(m.read_text(encoding="utf-8"))
    f = config.EVAL_RESULTS_DIR / "ficha_casos_prueba.csv"
    if f.exists():
        with f.open(encoding="utf-8-sig") as fh:
            out["casos"] = list(csv.DictReader(fh))
    t = config.EVAL_RESULTS_DIR.parent.parent / "pruebas" / "resultados" / "resumen_pruebas.json"
    if t.exists():
        out["pruebas"] = json.loads(t.read_text(encoding="utf-8"))
    return out
