import { useEffect, useState } from 'react'
import { api, download, fmtDateTime, setToken } from '../api.js'

// RF-15 Privacidad y derechos ARCO (Ley 29733)
const KIND = { estudio: 'Consentimiento informado del estudio', dispositivos: 'Importación de datos de dispositivos' }

export default function Privacy() {
  const [c, setC] = useState(null)
  const [pw, setPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const load = () => api('/api/privacy/consents').then(setC).catch(e => setErr(e.message))
  useEffect(() => { load() }, [])
  async function revoke() {
    if (!window.confirm('Se revocará la autorización y se eliminarán los datos importados de dispositivos. ¿Continuar?')) return
    const r = await api('/api/privacy/consents/revoke', { method: 'POST', body: { kind: 'dispositivos' } })
    setMsg(`Autorización revocada. Se eliminaron ${r.lecturas_eliminadas} lecturas.`); load()
  }
  async function del(e) {
    e.preventDefault(); setErr('')
    try {
      await api('/api/privacy/delete-account', { method: 'POST', body: { password: pw, confirm } })
      setToken(null); window.location.hash = '/'; window.location.reload()
    } catch (ex) { setErr(ex.message) }
  }
  if (!c) return <section><p className="muted">{err || 'Cargando…'}</p></section>
  return (
    <section>
      <h1>Privacidad y mis datos</h1>
      <p className="muted">Usted es titular de sus datos personales (Ley 29733). Aquí puede ver sus autorizaciones, descargar sus datos y eliminar su cuenta.</p>
      <h2>Autorizaciones</h2>
      {Object.entries(KIND).map(([k, label]) => {
        const v = c.vigente[k]
        return (
          <div key={k} className="card row-between">
            <div><strong>{label}</strong><br /><span className="muted small">{v ? `${v.granted ? 'Otorgada' : 'Revocada'} el ${fmtDateTime(v.at)} · versión ${v.version}` : 'No otorgada'}</span></div>
            {k === 'dispositivos' && v?.granted && <button className="btn ghost small" onClick={revoke}>Revocar</button>}
            {k === 'dispositivos' && !v?.granted && <a className="btn ghost small" href="#/dispositivos">Autorizar</a>}
          </div>
        )
      })}
      {msg && <p className="ok-msg" role="status">{msg}</p>}
      <h2>Acceso y rectificación</h2>
      <div className="card">
        <p className="small">Descargue una copia de todos sus datos (perfil, agenda, registros, avisos y valoraciones) en formato JSON. Para corregir datos del paciente use <a href="#/perfil">Perfil</a>.</p>
        <button className="btn secondary" onClick={() => download('/api/privacy/export', 'mis_datos_vianova.json')}>Descargar mis datos</button>
      </div>
      <h2>Eliminar mi cuenta</h2>
      <form className="card danger-zone" onSubmit={del}>
        <p className="small">Se borrarán su perfil, agenda, registros, avisos, datos de dispositivos y valoraciones. Los registros de uso del estudio se conservan solo con su código anónimo. Esta acción no se puede deshacer.</p>
        <label>Contraseña<input type="password" autoComplete="current-password" value={pw} onChange={e => setPw(e.target.value)} required /></label>
        <label>Escriba ELIMINAR para confirmar<input value={confirm} onChange={e => setConfirm(e.target.value)} required /></label>
        {err && <p className="error">{err}</p>}
        <button className="btn danger" disabled={confirm !== 'ELIMINAR' || !pw}>Eliminar mi cuenta</button>
      </form>
      <details className="muted small"><summary>Historial de autorizaciones</summary>
        <ul>{c.historial.map((h, i) => <li key={i}>{fmtDateTime(h.at)} · {KIND[h.kind] || h.kind} · {h.granted ? 'otorgada' : 'revocada'} ({h.version})</li>)}</ul>
      </details>
    </section>
  )
}
