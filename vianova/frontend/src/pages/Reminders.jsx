import { useEffect, useState } from 'react'
import { api, fmtDateTime } from '../api.js'

// RF-03 Recordatorios y notificaciones
export default function Reminders() {
  const supported = 'Notification' in window
  const [perm, setPerm] = useState(supported ? Notification.permission : 'unsupported')
  const [items, setItems] = useState(null)
  const [msg, setMsg] = useState('')
  useEffect(() => {
    const t = new Date(); const p = n => String(n).padStart(2, '0')
    const day = d => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T00:00:00`
    const tomorrow = new Date(t.getTime() + 86400000)
    Promise.all([api(`/api/tasks/agenda?date=${day(t)}`), api(`/api/tasks/agenda?date=${day(tomorrow)}`)])
      .then(([a, b]) => setItems([...a.items, ...b.items].filter(i => i.status === 'pendiente' || i.status === 'vencida').slice(0, 12)))
      .catch(() => setItems([]))
  }, [])
  async function enable() { setPerm(await Notification.requestPermission()) }
  async function test() {
    const body = 'Así se verá un recordatorio de Vianova.'
    try {
      const reg = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : null
      if (reg) await reg.showNotification('Vianova', { body, icon: '/icons/icon-192.png', tag: 'prueba' })
      else new Notification('Vianova', { body })
      setMsg('Notificación de prueba enviada.')
    } catch { setMsg('No se pudo mostrar la notificación en este navegador.') }
  }
  const PERM = { granted: ['Activadas', 'ok'], denied: ['Bloqueadas en el navegador', 'warn'], default: ['Sin activar', ''], unsupported: ['No disponibles en este navegador', 'warn'] }
  return (
    <section>
      <h1>Recordatorios</h1>
      <p className="muted">Vianova le avisa a la hora programada de cada medicamento, cita o actividad de su agenda. Si no marca la tarea, queda como «vencida» para que pueda registrarla después.</p>
      <div className="card">
        <div className="row-between"><strong>Notificaciones del dispositivo</strong><span className={`badge ${PERM[perm][1]}`}>{PERM[perm][0]}</span></div>
        <p className="small muted">Con las notificaciones activadas recibe el recordatorio aunque esté usando otra aplicación.</p>
        <div className="row-gap">
          {perm === 'default' && <button className="btn primary" onClick={enable}>Activar notificaciones</button>}
          {perm === 'granted' && <button className="btn secondary" onClick={test}>Enviar notificación de prueba</button>}
          {perm === 'denied' && <p className="small">Para activarlas, habilite las notificaciones de este sitio en la configuración del navegador.</p>}
        </div>
        {msg && <p className="ok-msg small" role="status">{msg}</p>}
      </div>
      <h2>Próximos recordatorios</h2>
      {!items ? <p className="muted">Cargando…</p> : !items.length ? <p className="muted">No hay recordatorios pendientes para hoy ni mañana.</p> : (
        <ul className="plain">{items.map(it => (
          <li key={it.task.id + it.occurrence_at} className="event-row">
            <span><strong>{fmtDateTime(it.occurrence_at)}</strong> · <span className={`kind ${it.task.kind}`}>{it.task.kind}</span></span>
            <span>{it.task.title}{it.status === 'vencida' && <span className="badge warn">vencida</span>}</span>
          </li>))}</ul>
      )}
      <p className="muted small">La agenda completa y la creación de tareas están en <a href="#/agenda">Agenda</a>.</p>
    </section>
  )
}
