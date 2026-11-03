import { useEffect, useState } from 'react'
import { api, fmtDateTime } from '../api.js'

// RF-13 Gestión de usuarios, roles y auditoría (administrador)
const ROLE = { cuidador: 'Cuidador', curador: 'Curador del corpus', investigador: 'Investigador', admin: 'Administrador' }

export default function Users({ me }) {
  const [users, setUsers] = useState(null)
  const [audit, setAudit] = useState([])
  const [tab, setTab] = useState('usuarios')
  const [f, setF] = useState({ full_name: '', email: '', password: '', role: 'curador' })
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const load = () => { api('/api/admin/users').then(setUsers).catch(e => setErr(e.message)); api('/api/admin/audit').then(setAudit).catch(() => {}) }
  useEffect(() => { load() }, [])
  const set = k => e => setF({ ...f, [k]: e.target.value })
  async function create(e) {
    e.preventDefault(); setErr(''); setMsg('')
    try { const u = await api('/api/admin/users', { method: 'POST', body: f }); setMsg(`Cuenta ${u.code} creada.`); setF({ full_name: '', email: '', password: '', role: 'curador' }); load() }
    catch (ex) { setErr(ex.message) }
  }
  async function upd(u, body) {
    setErr('')
    try { await api(`/api/admin/users/${u.id}`, { method: 'PUT', body }); load() } catch (ex) { setErr(ex.message) }
  }
  return (
    <section>
      <h1>Usuarios y roles</h1>
      <div className="tabs" role="tablist">
        {['usuarios', 'auditoría'].map(t => <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t[0].toUpperCase() + t.slice(1)}</button>)}
      </div>
      {err && <p className="error">{err}</p>}
      {tab === 'usuarios' && (
        <>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable"><table className="small">
            <thead><tr><th>Código</th><th>Nombre</th><th>Correo</th><th>Rol</th><th>Estado</th><th>Alta</th><th></th></tr></thead>
            <tbody>{(users || []).map(u => (
              <tr key={u.id}><td>{u.code}</td><td>{u.full_name}</td><td>{u.email}</td>
                <td>{u.role === 'cuidador' ? ROLE[u.role] : (
                  <select aria-label={`Rol de ${u.code}`} value={u.role} disabled={u.id === me.id} onChange={e => upd(u, { role: e.target.value })}>
                    {['curador', 'investigador', 'admin'].map(r => <option key={r} value={r}>{ROLE[r]}</option>)}</select>)}</td>
                <td>{u.active ? <span className="badge ok">Activa</span> : <span className="badge">Inactiva</span>}</td>
                <td>{fmtDateTime(u.created_at)}</td>
                <td>{u.id !== me.id && <button className="btn tiny ghost" onClick={() => upd(u, { active: !u.active })}>{u.active ? 'Desactivar' : 'Activar'}</button>}</td></tr>
            ))}</tbody></table></div>
          <h2>Nueva cuenta interna</h2>
          <form className="card form" onSubmit={create}>
            <div className="grid2">
              <label>Nombre completo<input value={f.full_name} onChange={set('full_name')} required /></label>
              <label>Correo<input type="email" value={f.email} onChange={set('email')} required /></label>
            </div>
            <div className="grid2">
              <label>Contraseña inicial (mín. 10)<input type="password" minLength={10} value={f.password} onChange={set('password')} required autoComplete="new-password" /></label>
              <label>Rol<select value={f.role} onChange={set('role')}>{['curador', 'investigador', 'admin'].map(r => <option key={r} value={r}>{ROLE[r]}</option>)}</select></label>
            </div>
            <p className="hint">Los cuidadores crean su propia cuenta desde la app aceptando el consentimiento informado.</p>
            {msg && <p className="ok-msg">{msg}</p>}
            <button className="btn primary">Crear cuenta</button>
          </form>
        </>
      )}
      {tab === 'auditoría' && (
        !audit.length ? <p className="muted">Sin registros.</p> : (
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable"><table className="small"><thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Detalle</th></tr></thead>
            <tbody>{audit.map((a, i) => <tr key={i}><td>{fmtDateTime(a.at)}</td><td>{a.user}</td><td>{a.action}</td><td>{a.detail}</td></tr>)}</tbody></table></div>)
      )}
    </section>
  )
}
