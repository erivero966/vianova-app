import { useEffect, useRef, useState } from 'react'
import { api, getToken, setToken, fmtTime, go } from './api.js'
import Auth from './pages/Auth.jsx'
import Home from './pages/Home.jsx'
import Tasks from './pages/Tasks.jsx'
import Register from './pages/Register.jsx'
import Ask from './pages/Ask.jsx'
import Sources from './pages/Sources.jsx'
import Doc from './pages/Doc.jsx'
import Summary from './pages/Summary.jsx'
import Devices from './pages/Devices.jsx'
import Profile from './pages/Profile.jsx'
import Corpus from './pages/Corpus.jsx'
import Research from './pages/Research.jsx'
import Recommendations from './pages/Recommendations.jsx'
import Alerts from './pages/Alerts.jsx'
import Reminders from './pages/Reminders.jsx'
import Privacy from './pages/Privacy.jsx'
import Users from './pages/Users.jsx'
import Config from './pages/Config.jsx'
import Validation from './pages/Validation.jsx'

const MORE_PAGES = ['mas', 'recomendaciones', 'avisos', 'recordatorios', 'resumen', 'dispositivos', 'perfil', 'privacidad']
const STAFF_NAV = {
  curador: [['corpus', 'Corpus'], ['configuracion', 'Configuración']],
  investigador: [['investigacion', 'Investigación'], ['validacion', 'Validación'], ['configuracion', 'Configuración']],
  admin: [['usuarios', 'Usuarios y roles'], ['configuracion', 'Configuración']],
}
const STAFF_HOME = { curador: 'corpus', investigador: 'investigacion', admin: 'usuarios' }

function EnvBanner({ compact = false }) {
  const [env, setEnv] = useState(null)
  useEffect(() => { fetch('/api/health').then(r => r.json()).then(d => setEnv(d.ambiente)).catch(() => {}) }, [])
  if (!env || env === 'produccion') return null
  if (compact) return <span className="env-tag" title={`Ambiente de ${env}: solo datos ficticios`}>Demo</span>
  return <div className={`env-banner ${env}`} role="note">Ambiente de {env === 'pruebas' ? 'PRUEBAS / CALIDAD' : 'DESARROLLO'} · solo datos ficticios</div>
}

const CAREGIVER_NAV = [
  ['inicio', 'Inicio', '⌂'], ['agenda', 'Agenda', '✓'], ['registrar', 'Registrar', '+'],
  ['consultar', 'Consultar', '?'], ['mas', 'Más', '≡'],
]

function useRoute() {
  const get = () => (window.location.hash.replace(/^#\/?/, '') || '').split('/')
  const [route, setRoute] = useState(get)
  useEffect(() => {
    const f = () => { setRoute(get()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', f)
    return () => window.removeEventListener('hashchange', f)
  }, [])
  return route
}


// Recordatorios: revisa la agenda cada minuto y avisa cuando una tarea llega a su hora (RF-02)
function useReminders(enabled, onToast) {
  // Las claves ya notificadas se guardan en la sesión para no repetir el recordatorio al recargar la app
  const notified = useRef(new Set((() => { try { return JSON.parse(sessionStorage.getItem('vianova_notified') || '[]') } catch { return [] } })()))
  useEffect(() => {
    if (!enabled) return
    let stop = false
    async function tick() {
      try {
        const ag = await api('/api/tasks/agenda')
        const now = Date.now()
        for (const it of ag.items) {
          const t = new Date(it.occurrence_at).getTime()
          const key = `${it.task.id}|${it.occurrence_at}`
          if (it.status === 'pendiente' || it.status === 'vencida') {
            if (t <= now && now - t < 10 * 60000 && !notified.current.has(key)) {
              notified.current.add(key)
              try { sessionStorage.setItem('vianova_notified', JSON.stringify([...notified.current].slice(-200))) } catch { /* sin almacenamiento */ }
              const msg = `${it.task.kind === 'cita' ? 'Cita' : 'Recordatorio'}: ${it.task.title} (${fmtTime(it.occurrence_at)})`
              onToast(msg)
              if ('Notification' in window && Notification.permission === 'granted') {
                const reg = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : null
                if (reg) reg.showNotification('Vianova', { body: msg, icon: '/icons/icon-192.png', tag: key })
                else new Notification('Vianova', { body: msg })
              }
              api('/api/logs/client', { method: 'POST', body: { tipo_evento: 'recordatorio_emitido', modulo: 'recordatorios',
                id_recurso: `TAR-${String(it.task.id).padStart(4, '0')}`, hora_programada: it.occurrence_at.slice(0, 19) } }).catch(() => {})
            }
          }
        }
      } catch { /* sin conexión */ }
      if (!stop) setTimeout(tick, 60000)
    }
    tick()
    return () => { stop = true }
  }, [enabled])
}

export default function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!getToken())
  const [toast, setToast] = useState('')
  const sessionStart = useRef(Date.now())
  const route = useRoute()

  useEffect(() => {
    if (getToken()) api('/api/auth/me').then(setUser).catch(() => setToken(null)).finally(() => setLoading(false))
    const out = () => setUser(null)
    window.addEventListener('vianova:logout', out)
    return () => window.removeEventListener('vianova:logout', out)
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(''), 6000)
    return () => clearTimeout(t)
  }, [toast])

  useReminders(user?.role === 'cuidador', setToast)

  function onLogin(data) {
    setToken(data.token)
    setUser(data.user)
    sessionStart.current = Date.now()
    if (data.user.role === 'cuidador') go(data.user.has_profile ? 'inicio' : 'perfil')
    else go(STAFF_HOME[data.user.role] || 'investigacion')
  }
  async function logout() {
    try {
      await api('/api/logs/client', { method: 'POST', body: { tipo_evento: 'fin_sesion', modulo: 'autenticacion',
        duracion_ms: Date.now() - sessionStart.current } })
    } catch { /* ignorar */ }
    setToken(null)
    setUser(null)
    go('')
  }

  if (loading) return <div className="center-screen">Cargando…</div>
  if (!user) return <><EnvBanner /><Auth onLogin={onLogin} /></>

  const [page, arg] = route
  let content
  if (user.role === 'cuidador') {
    content = {
      '': <Home user={user} />, inicio: <Home user={user} />, agenda: <Tasks />, tareas: <Tasks />, registrar: <Register />,
      recomendaciones: <Recommendations />, avisos: <Alerts />, recordatorios: <Reminders />, privacidad: <Privacy />,
      consultar: <Sources user={user} />, asistente: <Ask />, documento: <Doc id={arg} />, resumen: <Summary />, dispositivos: <Devices />,
      perfil: <Profile onSaved={() => api('/api/auth/me').then(setUser)} />,
      mas: <More user={user} logout={logout} />,
    }[page] ?? <Home user={user} />
  } else {
    const allowed = Object.fromEntries((STAFF_NAV[user.role] || []).map(([k]) => [k, true]))
    const pages = {
      corpus: <Corpus />, investigacion: <Research />, validacion: <Validation />, usuarios: <Users me={user} />,
      configuracion: <Config />, documento: <Doc id={arg} />,
    }
    const home = STAFF_HOME[user.role] || 'investigacion'
    content = (allowed[page] || (page === 'documento' && user.role !== 'admin')) ? pages[page] : pages[home]
  }

  return (
    <div className="app">
      <a className="skip-link" href="#contenido">Saltar al contenido</a>
      {page !== 'consultar' && <EnvBanner />}
      <header className="topbar">
        <a href="#/" className="brand"><span className="logo" aria-hidden="true">♥</span> Vianova{page === 'consultar' && <EnvBanner compact />}</a>
        <div className="topbar-right">
          {user.role !== 'cuidador' && (
            <nav className="staff-nav" aria-label="Módulos">
              {(STAFF_NAV[user.role] || []).map(([k, label]) => {
                const on = page === k || (!page && STAFF_HOME[user.role] === k)
                return <a key={k} href={`#/${k}`} className={on ? 'active' : ''} aria-current={on ? 'page' : undefined}>{label}</a>
              })}
            </nav>
          )}
          <span className="who">{user.full_name}</span>
          {user.role !== 'cuidador' && <button className="btn ghost small" onClick={logout}>Salir</button>}
        </div>
      </header>
      <main id="contenido" tabIndex={-1} className={user.role === 'cuidador' ? 'main caregiver' : 'main staff'}>{content}</main>
      {user.role === 'cuidador' && (
        <nav className="bottomnav" aria-label="Navegación principal">
          {CAREGIVER_NAV.map(([k, label, icon]) => {
            const active = (page || 'inicio') === k || (k === 'agenda' && page === 'tareas') || (k === 'consultar' && page === 'asistente') || (k === 'mas' && MORE_PAGES.includes(page))
            return (
              <a key={k} href={`#/${k}`} className={active ? 'active' : ''} aria-current={active ? 'page' : undefined}>
                <span className="ico" aria-hidden="true">{icon}</span><span>{label}</span>
              </a>
            )
          })}
        </nav>
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  )
}

function More({ user, logout }) {
  const perm = 'Notification' in window ? Notification.permission : 'unsupported'

  return (
    <section>
      <h1>Más opciones</h1>
      <div className="list-menu">
        <a href="#/recomendaciones" className="card link-card"><strong>Recomendaciones</strong><span>Orientación personalizada con su fuente y el motivo</span></a>
        <a href="#/avisos" className="card link-card"><strong>Avisos</strong><span>Historial de avisos generados por sus registros</span></a>
        <a href="#/recordatorios" className="card link-card"><strong>Recordatorios y notificaciones</strong><span>{perm === 'granted' ? 'Notificaciones activadas' : 'Active las notificaciones del dispositivo'}</span></a>
        <a href="#/resumen" className="card link-card"><strong>Resumen para el equipo de salud</strong><span>Imprima o descargue los registros recientes</span></a>
        <a href="#/dispositivos" className="card link-card"><strong>Dispositivos (opcional)</strong><span>Importe datos de un reloj o pulsera</span></a>
        <a href="#/perfil" className="card link-card"><strong>Perfil y paciente</strong><span>Datos del paciente y preferencias</span></a>
        <a href="#/privacidad" className="card link-card"><strong>Privacidad y mis datos</strong><span>Autorizaciones, descarga de datos y eliminación de cuenta</span></a>
      </div>
      <p className="muted small">Sesión de {user.full_name} · código {user.code}</p>
      <button className="btn secondary" onClick={logout}>Cerrar sesión</button>
      <p className="disclaimer">Vianova brinda información de apoyo basada en fuentes verificadas. No reemplaza la atención
        de un profesional de salud. Ante una emergencia, llame a los servicios de emergencia.</p>
    </section>
  )
}
