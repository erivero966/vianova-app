import { useEffect, useState } from 'react'
import { api, localIso, fmtDateTime } from '../api.js'
import { Agenda } from './Home.jsx'

const REC_LABEL = { unica: 'Una vez', diaria: 'Todos los días', cada_n_horas: 'Cada N horas' }

function defaultStart() {
  const d = new Date(); d.setMinutes(0, 0, 0); d.setHours(d.getHours() + 1)
  return localIso(d).slice(0, 16)
}

export default function Tasks() {
  const [tasks, setTasks] = useState([])
  const [agenda, setAgenda] = useState([])
  const [day, setDay] = useState(localIso(new Date()).slice(0, 10))
  const [show, setShow] = useState(false)
  const empty = { kind: 'medicamento', title: '', instructions: '', start_at: defaultStart(), recurrence: 'diaria', every_hours: 8, end_date: '' }
  const [f, setF] = useState(empty)
  const [err, setErr] = useState('')
  const set = k => e => setF({ ...f, [k]: e.target.value })

  async function load() {
    const [t, a] = await Promise.all([api('/api/tasks'), api(`/api/tasks/agenda?date=${day}T00:00:00`)])
    setTasks(t); setAgenda(a.items)
  }
  useEffect(() => { load().catch(e => setErr(e.message)) }, [day])

  async function save(e) {
    e.preventDefault(); setErr('')
    try {
      await api('/api/tasks', { method: 'POST', body: {
        ...f, start_at: f.start_at + ':00', every_hours: f.recurrence === 'cada_n_horas' ? Number(f.every_hours) : null,
        end_date: f.end_date ? f.end_date + 'T23:59:00' : null } })
      setF(empty); setShow(false); load()
    } catch (ex) { setErr(ex.message) }
  }
  async function remove(id) {
    if (!confirm('¿Desactivar esta tarea? Ya no se mostrarán recordatorios.')) return
    await api(`/api/tasks/${id}`, { method: 'DELETE' }); load()
  }
  async function done(it, status) {
    await api(`/api/tasks/${it.task.id}/complete`, { method: 'POST', body: { occurrence_at: it.occurrence_at.slice(0, 19), status } })
    load()
  }

  return (
    <section>
      <div className="row-between">
        <h1>Agenda de cuidado</h1>
        <button className="btn primary" onClick={() => setShow(!show)}>{show ? 'Cerrar' : '+ Nueva'}</button>
      </div>
      {show && (
        <form className="card form" onSubmit={save}>
          <div className="seg">
            {[['medicamento', 'Medicamento'], ['cita', 'Cita'], ['actividad', 'Actividad']].map(([k, l]) => (
              <button type="button" key={k} className={f.kind === k ? 'active' : ''} onClick={() => setF({ ...f, kind: k })}>{l}</button>
            ))}
          </div>
          <label>Nombre<input value={f.title} onChange={set('title')} required placeholder={f.kind === 'medicamento' ? 'Ej.: nombre del medicamento' : f.kind === 'cita' ? 'Ej.: control en oncología' : 'Ej.: cambio de posición'} /></label>
          <label>Indicación del equipo de salud (opcional)<input value={f.instructions} onChange={set('instructions')} placeholder="Copie la indicación tal como figura en la receta" />
            {f.kind === 'medicamento' && <span className="hint">Vianova no indica dosis: registre la que le dio el equipo de salud.</span>}
          </label>
          <div className="grid2">
            <label>Primera vez<input type="datetime-local" value={f.start_at} onChange={set('start_at')} required /></label>
            <label>Repetición<select value={f.recurrence} onChange={set('recurrence')}>
              {Object.entries(REC_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          </div>
          <div className="grid2">
            {f.recurrence === 'cada_n_horas' && <label>Cada cuántas horas<input type="number" min="1" max="48" value={f.every_hours} onChange={set('every_hours')} /></label>}
            {f.recurrence !== 'unica' && <label>Hasta (opcional)<input type="date" value={f.end_date} onChange={set('end_date')} /></label>}
          </div>
          {err && <p className="error">{err}</p>}
          <button className="btn primary block">Guardar</button>
        </form>
      )}
      <div className="row-between">
        <h2>Agenda</h2>
        <input type="date" value={day} onChange={e => setDay(e.target.value)} aria-label="Día" />
      </div>
      <Agenda items={agenda} onDone={done} compact />
      <h2>Tareas activas</h2>
      {!tasks.length && <p className="muted">Aún no registra tareas. Agregue los medicamentos y citas del paciente.</p>}
      <ul className="plain">
        {tasks.map(t => (
          <li key={t.id} className="card task-row">
            <div>
              <span className={`kind ${t.kind}`}>{t.kind}</span> <strong>{t.title}</strong>
              <div className="muted small">{REC_LABEL[t.recurrence]}{t.recurrence === 'cada_n_horas' ? ` (${t.every_hours} h)` : ''} · desde {fmtDateTime(t.start_at)}</div>
              {t.instructions && <div className="small">{t.instructions}</div>}
            </div>
            <button className="btn small ghost" onClick={() => remove(t.id)}>Desactivar</button>
          </li>
        ))}
      </ul>
    </section>
  )
}
