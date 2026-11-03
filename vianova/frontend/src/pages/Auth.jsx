import { useState } from 'react'
import { api } from '../api.js'

export default function Auth({ onLogin }) {
  const [mode, setMode] = useState('login')
  const [f, setF] = useState({ full_name: '', email: '', password: '', consent_study: false })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [showConsent, setShowConsent] = useState(false)
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  async function submit(e) {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      const data = mode === 'login'
        ? await api('/api/auth/login', { method: 'POST', body: { email: f.email, password: f.password } })
        : await api('/api/auth/register', { method: 'POST', body: f })
      onLogin(data)
    } catch (ex) { setErr(ex.message) } finally { setBusy(false) }
  }

  return (
    <div className="auth">
      <div className="auth-hero">
        <div className="logo big" aria-hidden="true">♥</div>
        <h1>Vianova</h1>
        <p>Orientación verificada y organización del cuidado para quienes cuidan a un familiar con cáncer.</p>
      </div>
      <form className="card auth-card" onSubmit={submit}>
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={mode === 'login'} className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Ingresar</button>
          <button type="button" role="tab" aria-selected={mode === 'register'} className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Crear cuenta</button>
        </div>
        {mode === 'register' && (
          <label>Nombre completo<input value={f.full_name} onChange={set('full_name')} required autoComplete="name" /></label>
        )}
        <label>Correo<input type="email" value={f.email} onChange={set('email')} required autoComplete="email" /></label>
        <label>Contraseña<input type="password" value={f.password} onChange={set('password')} required minLength={mode === 'register' ? 8 : 1}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'} />
          {mode === 'register' && <span className="hint">Mínimo 8 caracteres</span>}
        </label>
        {mode === 'register' && (
          <>
            <label className="check">
              <input type="checkbox" checked={f.consent_study} onChange={set('consent_study')} />
              <span>He leído y acepto el <button type="button" className="linklike" onClick={() => setShowConsent(!showConsent)}>consentimiento informado</button> para participar en el estudio.</span>
            </label>
            {showConsent && (
              <div className="consent-box">
                <p><strong>Consentimiento informado (resumen, v1.0-2026).</strong> Usted participa voluntariamente en una investigación de la
                  Universidad Católica de Santa María que evalúa un sistema de apoyo para cuidadores informales de pacientes con cáncer.</p>
                <p>El sistema brinda información basada en fuentes verificadas, recordatorios y registros. <strong>No emite diagnósticos ni
                  indicaciones de tratamiento y no reemplaza la atención médica.</strong></p>
                <p>Sus datos se identifican con un código, se almacenan cifrados y se analizan solo de forma agregada, conforme a la
                  Ley N.° 29733. Puede retirarse en cualquier momento sin consecuencias.</p>
                <p className="muted small">El texto completo y aprobado por el comité de ética reemplazará este resumen antes del piloto.</p>
              </div>
            )}
          </>
        )}
        {err && <p className="error" role="alert">{err}</p>}
        <button className="btn primary block" disabled={busy || (mode === 'register' && !f.consent_study)}>
          {busy ? 'Un momento…' : mode === 'login' ? 'Ingresar' : 'Crear cuenta'}
        </button>
      </form>
      <p className="disclaimer">No reemplaza la atención de un profesional de salud. Ante una emergencia, llame a los servicios de emergencia.</p>
    </div>
  )
}
