import { useEffect, useState } from 'react'
import { api } from '../api.js'

// RF-14 Resultados de validación técnica del RAG y de la suite de pruebas
const pct = v => (v == null ? '—' : `${Number(v).toFixed(1)} %`)
export default function Validation() {
  const [d, setD] = useState(null)
  const [f, setF] = useState('todos')
  const [err, setErr] = useState('')
  useEffect(() => { api('/api/research/validation').then(setD).catch(e => setErr(e.message)) }, [])
  if (!d) return <section><p className="muted">{err || 'Cargando…'}</p></section>
  const m = d.metricas
  const COLS = ['id', 'tipo', 'consulta', 'esperado', 'estado', 'fuente_mostrada', 'similitud_max', 'veredicto']
  const casos = d.casos.filter(c => f === 'todos' || (f === 'fallidos' ? c.veredicto !== 'superado' : c.tipo === f))
  return (
    <section>
      <h1>Validación técnica</h1>
      {!m ? <p className="muted">Aún no se ejecutó <code>python eval/run_eval.py</code>.</p> : (
        <>
          <p className="muted">Conjunto de {m.n_casos ?? d.casos.length} casos · τ = {m.tau} · k = {m.k} · modo {m.modo_generacion}</p>
          <div className="stats">
            <div className="stat"><span>{m.precision_at_5}</span>Precision@5 (máx. {m.precision_at_5_maxima_posible})</div>
            <div className="stat"><span>{m.recall_at_5}</span>Recall@5</div>
            <div className="stat"><span>{m.mrr}</span>MRR</div>
            <div className="stat"><span>{pct(m.trazabilidad_pct)}</span>trazabilidad</div>
            <div className="stat"><span>{pct(m.abstencion_correcta_pct)}</span>abstención correcta</div>
            <div className="stat"><span>{pct(m.fuera_de_alcance_correcto_pct)}</span>fuera de alcance</div>
          </div>
        </>
      )}
      {d.pruebas && (
        <>
          <h2>Suite de pruebas automatizadas</h2>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable"><table className="small"><thead><tr><th>Tipo</th><th>Total</th><th>Aprobadas</th><th>Fallidas</th></tr></thead>
            <tbody>{Object.entries(d.pruebas.por_tipo || {}).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.total}</td><td>{v.aprobadas}</td><td>{v.fallidas}</td></tr>)}</tbody></table></div>
        </>
      )}
      {!!d.casos.length && (
        <>
          <h2>Ficha de casos de prueba</h2>
          <select aria-label="Filtrar casos" value={f} onChange={e => setF(e.target.value)} style={{ maxWidth: 260 }}>
            <option value="todos">Todos</option><option value="pertinencia">Pertinencia</option><option value="abstencion">Sin evidencia</option>
            <option value="fuera_de_alcance">Fuera de alcance</option><option value="fallidos">No superados</option></select>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable" style={{ marginTop: '.6rem' }}><table className="small">
            <thead><tr>{COLS.map(k => <th key={k}>{k.replace('_', ' ')}</th>)}</tr></thead>
            <tbody>{casos.slice(0, 120).map((c, i) => <tr key={i}>{COLS.map(k => <td key={k} className={k === 'veredicto' && c[k] !== 'superado' ? 'error' : ''}>{c[k]}</td>)}</tr>)}</tbody></table></div>
        </>
      )}
    </section>
  )
}
