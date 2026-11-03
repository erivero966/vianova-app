import { useEffect, useState } from 'react'
import { api, fmtDateTime } from '../api.js'

const METRIC = { frecuencia_cardiaca: 'Frecuencia cardiaca', pasos: 'Pasos', temperatura: 'Temperatura', spo2: 'Saturación (SpO₂)', sueno_horas: 'Horas de sueño' }

export default function Devices() {
  const [profile, setProfile] = useState(null)
  const [rows, setRows] = useState([])
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const load = () => { api('/api/profile').then(setProfile); api('/api/devices/readings?days=14').then(setRows) }
  useEffect(load, [])

  async function toggle(granted) {
    setProfile(await api('/api/profile/devices-consent', { method: 'POST', body: { granted } }))
  }
  async function upload(e) {
    const file = e.target.files[0]
    if (!file) return
    setErr(''); setMsg('')
    const form = new FormData(); form.append('file', file)
    try {
      const r = await api('/api/devices/import', { method: 'POST', form })
      setMsg(`Se importaron ${r.importadas} lecturas${r.rechazadas ? ` (${r.rechazadas} rechazadas por formato)` : ''}.`)
      load()
    } catch (ex) { setErr(ex.message) }
    e.target.value = ''
  }

  if (!profile) return <section><p className="muted">Cargando…</p></section>
  return (
    <section>
      <h1>Dispositivos (opcional)</h1>
      <p className="muted">Si el paciente usa un reloj o pulsera inteligente, puede importar sus datos para tenerlos en el resumen.
        Estos datos <strong>no equivalen a mediciones clínicas</strong> y el sistema funciona igual sin ellos.</p>
      <div className="card">
        <label className="check">
          <input type="checkbox" checked={profile.devices_authorized} onChange={e => toggle(e.target.checked)} />
          <span>Autorizo la importación de datos de dispositivos del paciente. Puedo revocar esta autorización en cualquier momento.</span>
        </label>
      </div>
      {profile.devices_authorized && (
        <div className="card">
          <h2>Importar archivo</h2>
          <p className="small">Formato JSON o CSV con los campos <code>metrica</code>, <code>valor</code>, <code>fecha</code> y <code>dispositivo</code>.
            Métricas: {Object.keys(METRIC).join(', ')}.</p>
          <label>Archivo de la pulsera o reloj (.json o .csv)<input type="file" accept=".json,.csv" onChange={upload} /></label>
          {msg && <p className="ok-msg" role="status">{msg}</p>}
          {err && <p className="error">{err}</p>}
        </div>
      )}
      <h2>Lecturas recientes</h2>
      {!rows.length ? <p className="muted">Sin lecturas importadas.</p> : (
        <table className="small"><thead><tr><th>Fecha</th><th>Métrica</th><th>Valor</th><th>Dispositivo</th></tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i}><td>{fmtDateTime(r.measured_at)}</td><td>{METRIC[r.metric] || r.metric}</td><td>{r.value} {r.unit}</td><td>{r.device}</td></tr>)}</tbody></table>
      )}
    </section>
  )
}
