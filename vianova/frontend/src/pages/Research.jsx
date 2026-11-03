import { useEffect, useState } from 'react'
import { api, download, fmtDateTime } from '../api.js'

export default function Research() {
  const [ind, setInd] = useState(null)
  const [weekly, setWeekly] = useState(null)
  const [audit, setAudit] = useState([])
  const [err, setErr] = useState('')
  useEffect(() => {
    api('/api/research/indicators').then(setInd).catch(e => setErr(e.message))
    api('/api/research/audit').then(setAudit).catch(() => {})
  }, [])
  const openWeekly = code => api(`/api/research/weekly/${code}`).then(w => setWeekly({ code, rows: w }))

  return (
    <section>
      <div className="row-between">
        <h1>Investigación</h1>
        <button className="btn secondary" onClick={() => download('/api/research/logs.csv', 'registros_sistema.csv')}>Exportar registros (CSV)</button>
      </div>
      <p className="muted">Indicadores calculados a partir de los registros del sistema (Tabla 8 del informe). Los participantes se identifican solo por código.</p>
      {err && <p className="error">{err}</p>}
      {ind && (
        <>
          <div className="stats">
            <div className="stat"><span>{ind.resumen.n_con_uso}</span>participantes con uso</div>
            <div className="stat"><span>{ind.resumen.actividades_por_dia_media ?? '—'}</span>actividades/día (media)</div>
            <div className="stat"><span>{ind.resumen.pct_tareas_a_tiempo_media ?? '—'}{ind.resumen.pct_tareas_a_tiempo_media != null && '%'}</span>tareas a tiempo (media)</div>
            <div className="stat"><span>{ind.resumen.ingresos_media ?? '—'}</span>ingresos (media)</div>
          </div>
          <p className="muted small">Periodo: {fmtDateTime(ind.inicio)} – {fmtDateTime(ind.fin)}</p>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable">
            <table className="small">
              <thead><tr><th>Código</th><th>Días con uso</th><th>Activ./día</th><th>Programadas</th><th>A tiempo</th><th>% a tiempo</th><th>Ingresos</th><th>Consultas</th><th>Avisos</th><th></th></tr></thead>
              <tbody>{ind.participantes.map(p => (
                <tr key={p.participante}><td>{p.participante}</td><td>{p.dias_con_uso}</td><td>{p.actividades_por_dia}</td><td>{p.tareas_programadas}</td>
                  <td>{p.tareas_completadas_a_tiempo}</td><td>{p.pct_tareas_a_tiempo ?? '—'}</td><td>{p.ingresos}</td><td>{p.consultas_rag}</td><td>{p.avisos_mostrados}</td>
                  <td><button className="btn tiny ghost" onClick={() => openWeekly(p.participante)}>Por semana</button></td></tr>))}</tbody>
            </table>
          </div>
        </>
      )}
      {weekly && (
        <div className="card">
          <h2>{weekly.code} — evolución semanal</h2>
          {!weekly.rows.length ? <p className="muted">Sin datos.</p> : (
            <table className="small"><thead><tr><th>Semana</th><th>Días con uso</th><th>Activ./día</th><th>% a tiempo</th><th>Ingresos</th></tr></thead>
              <tbody>{weekly.rows.map(r => <tr key={r.semana}><td>{r.semana}</td><td>{r.dias_con_uso}</td><td>{r.actividades_por_dia}</td><td>{r.pct_tareas_a_tiempo ?? '—'}</td><td>{r.ingresos}</td></tr>)}</tbody></table>
          )}
        </div>
      )}
      <h2>Auditoría de acciones sensibles</h2>
      {!audit.length ? <p className="muted">Sin registros.</p> : (
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable"><table className="small"><thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Detalle</th></tr></thead>
          <tbody>{audit.map((a, i) => <tr key={i}><td>{fmtDateTime(a.at)}</td><td>{a.user}</td><td>{a.action}</td><td>{a.detail}</td></tr>)}</tbody></table></div>
      )}
    </section>
  )
}
