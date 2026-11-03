import { useEffect, useState } from 'react'
import { api, fmtTime, fmtDateTime } from '../api.js'

export function SourceTag({ s }) {
  return (
    <span className="source">
      Fuente: <a href={`#/documento/${s.doc_id}`}>{s.title}</a> · {s.institution}{s.year ? `, ${s.year}` : ''} · v{s.version}
      {s.is_demo && <span className="badge demo">demo</span>}
    </span>
  )
}

export function AlertCard({ a, onAck }) {
  return (
    <div className="alert-card" role="alert">
      <div className="alert-title">⚠ Aviso</div>
      <p>{a.message}</p>
      {a.source && <SourceTag s={a.source} />}
      {onAck && !a.acknowledged && <button className="btn small light" onClick={() => onAck(a.id)}>Entendido</button>}
    </div>
  )
}

export function Agenda({ items, onDone, compact }) {
  if (!items.length) return <p className="muted">No hay tareas programadas para hoy.</p>
  return (
    <ul className="agenda">
      {items.map(it => (
        <li key={it.task.id + it.occurrence_at} className={`agenda-item ${it.status}`}>
          <div className="time">{fmtTime(it.occurrence_at)}</div>
          <div className="what">
            <span className={`kind ${it.task.kind}`}>{it.task.kind}</span>
            <strong>{it.task.title}</strong>
            {!compact && it.task.instructions && <span className="muted small">{it.task.instructions}</span>}
          </div>
          <div className="act">
            {it.status === 'hecha' && <span className="badge ok">Hecha</span>}
            {it.status === 'omitida' && <span className="badge">Omitida</span>}
            {(it.status === 'pendiente' || it.status === 'vencida') && (
              <>
                <button className="btn small primary" onClick={() => onDone(it, 'hecha')}>Hecho</button>
                {it.status === 'vencida' && <button className="btn small ghost" onClick={() => onDone(it, 'omitida')}>No se hizo</button>}
              </>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

export function RecCard({ r, onFeedback }) {
  const [voted, setVoted] = useState(null)
  return (
    <article className={`rec ${r.priority ? 'priority' : ''}`}>
      <h3><a href={`#/documento/${r.doc_id}`}>{r.title}</a></h3>
      <p className="snippet">{r.snippet}</p>
      <ul className="reasons">{r.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>
      <div className="rec-foot">
        <span className="source">{r.institution} · v{r.version} {r.is_demo && <span className="badge demo">demo</span>}</span>
        <span className="vote">
          {voted === null ? (
            <>¿Le sirvió?
              <button className="btn tiny ghost" onClick={() => { setVoted(true); onFeedback(r.doc_id, true) }}>Sí</button>
              <button className="btn tiny ghost" onClick={() => { setVoted(false); onFeedback(r.doc_id, false) }}>No</button>
            </>
          ) : <span className="muted small">¡Gracias!</span>}
        </span>
      </div>
    </article>
  )
}

export default function Home({ user }) {
  const [agenda, setAgenda] = useState(null)
  const [recs, setRecs] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [err, setErr] = useState('')

  async function load() {
    try {
      const [ag, rc, al] = await Promise.all([api('/api/tasks/agenda'), api('/api/recommendations'), api('/api/alerts')])
      setAgenda(ag.items); setRecs(rc.items); setAlerts(al.filter(a => !a.acknowledged))
    } catch (e) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])

  async function done(it, status) {
    await api(`/api/tasks/${it.task.id}/complete`, { method: 'POST', body: { occurrence_at: it.occurrence_at.slice(0, 19), status } })
    load()
  }
  async function ack(id) { await api(`/api/alerts/${id}/ack`, { method: 'POST' }); setAlerts(alerts.filter(a => a.id !== id)) }
  const feedback = (doc_id, useful) => api('/api/recommendations/feedback', { method: 'POST', body: { doc_id, useful } }).catch(() => {})

  const hour = new Date().getHours()
  const greet = hour < 12 ? 'Buenos días' : hour < 19 ? 'Buenas tardes' : 'Buenas noches'
  const pending = agenda?.filter(i => i.status === 'pendiente' || i.status === 'vencida').length ?? 0

  return (
    <section>
      <h1>{greet}, {user.full_name.split(' ')[0]}</h1>
      <p className="muted">{agenda ? (pending ? `Tiene ${pending} tarea${pending > 1 ? 's' : ''} pendiente${pending > 1 ? 's' : ''} hoy.` : 'Todo al día por ahora.') : ' '}</p>
      {err && <p className="error">{err}</p>}
      {alerts.map(a => <AlertCard key={a.id} a={a} onAck={ack} />)}
      {alerts.length > 0 && <p className="small"><a href="#/avisos">Ver historial de avisos</a></p>}
      <div className="quick">
        <a className="quick-btn" href="#/registrar"><span>+</span>Registrar síntoma</a>
        <a className="quick-btn" href="#/consultar"><span>?</span>Hacer una consulta</a>
      </div>
      <h2>Hoy</h2>
      {agenda ? <Agenda items={agenda} onDone={done} compact /> : <p className="muted">Cargando…</p>}
      <div className="row-between"><h2>Recomendado para usted</h2><a href="#/recomendaciones" className="small">Ver todas</a></div>
      <p className="muted small">Según su perfil y sus registros recientes. Siempre se indica la fuente.</p>
      {recs ? recs.map(r => <RecCard key={r.doc_id} r={r} onFeedback={feedback} />) : <p className="muted">Cargando…</p>}
    </section>
  )
}
