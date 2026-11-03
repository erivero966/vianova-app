import { useEffect, useState } from 'react'
import { api, fmtDateTime } from '../api.js'
import { AlertCard } from './Home.jsx'

// RF-09 Avisos basados en reglas documentadas (historial)
export default function Alerts() {
  const [items, setItems] = useState(null)
  const [filter, setFilter] = useState('todos')
  const [err, setErr] = useState('')
  const load = () => api('/api/alerts?history=true').then(setItems).catch(e => setErr(e.message))
  useEffect(() => { load() }, [])
  async function ack(id) { await api(`/api/alerts/${id}/ack`, { method: 'POST' }); load() }
  const shown = (items || []).filter(a => filter === 'todos' || (filter === 'pendientes' ? !a.acknowledged : a.acknowledged))
  return (
    <section>
      <h1>Avisos</h1>
      <p className="muted">Un aviso aparece cuando un registro coincide con una regla tomada de una guía oficial (por ejemplo, fiebre de 38 °C o más
        durante la quimioterapia). No es un diagnóstico ni una clasificación de gravedad.</p>
      <div className="seg" role="group" aria-label="Filtrar avisos">
        {['todos', 'pendientes', 'revisados'].map(k => (
          <button key={k} className={filter === k ? 'active' : ''} aria-pressed={filter === k} onClick={() => setFilter(k)}>
            {k[0].toUpperCase() + k.slice(1)}</button>))}
      </div>
      {err && <p className="error">{err}</p>}
      {!items ? <p className="muted">Cargando…</p> : !shown.length ? <p className="muted">No hay avisos en esta vista.</p> : shown.map(a => (
        <div key={a.id}>
          <p className="muted tiny" style={{ marginBottom: -6 }}>{fmtDateTime(a.created_at)} · regla {a.rule_id}{a.acknowledged ? ' · revisado' : ''}</p>
          <AlertCard a={a} onAck={ack} />
        </div>
      ))}
    </section>
  )
}
