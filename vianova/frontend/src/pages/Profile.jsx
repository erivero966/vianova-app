import { useEffect, useState } from 'react'
import { api, go } from '../api.js'

const TREATMENTS = [['quimioterapia', 'Quimioterapia'], ['radioterapia', 'Radioterapia'], ['cirugia', 'Cirugía'],
  ['inmunoterapia', 'Inmunoterapia'], ['paliativo', 'Cuidados paliativos']]

export default function Profile({ onSaved }) {
  const [f, setF] = useState(null)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState('')
  useEffect(() => { api('/api/profile').then(setF) }, [])
  if (!f) return <section><p className="muted">Cargando…</p></section>
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const toggleT = t => setF({ ...f, treatments: f.treatments.includes(t) ? f.treatments.filter(x => x !== t) : [...f.treatments, t] })

  async function save(e) {
    e.preventDefault(); setErr('')
    try {
      await api('/api/profile', { method: 'PUT', body: { ...f, patient_age: f.patient_age ? Number(f.patient_age) : null } })
      setSaved(true); onSaved?.()
      setTimeout(() => go('inicio'), 700)
    } catch (ex) { setErr(ex.message) }
  }

  return (
    <section>
      <h1>Perfil y paciente</h1>
      <p className="muted">Estos datos permiten priorizar la información más útil para su situación. No se usan para diagnosticar.</p>
      <form className="card form" onSubmit={save}>
        <div className="grid2">
          <label>¿Cómo llama al paciente?<input value={f.patient_alias} onChange={set('patient_alias')} placeholder="Ej.: mamá, Juan" /></label>
          <label>Parentesco<input value={f.relationship_to_patient} onChange={set('relationship_to_patient')} placeholder="Ej.: hija" /></label>
        </div>
        <div className="grid2">
          <label>Edad del paciente<input type="number" min="18" max="120" value={f.patient_age ?? ''} onChange={set('patient_age')} /></label>
          <label>Tipo de cáncer (según el diagnóstico médico)<input value={f.cancer_type} onChange={set('cancer_type')} required placeholder="Ej.: mama, colon, pulmón" /></label>
        </div>
        <fieldset><legend>Tratamiento actual</legend>
          <div className="chips">{TREATMENTS.map(([k, l]) => (
            <button type="button" key={k} className={`chip ${f.treatments.includes(k) ? 'on' : ''}`} aria-pressed={f.treatments.includes(k)} onClick={() => toggleT(k)}>{l}</button>
          ))}</div>
        </fieldset>
        <div className="grid2">
          <label>Movilidad del paciente<select value={f.mobility} onChange={set('mobility')}>
            <option value="">—</option><option value="independiente">Se moviliza solo</option>
            <option value="ayuda_parcial">Necesita ayuda</option><option value="encamado">Pasa la mayor parte del tiempo en cama</option></select></label>
          <label>Prefiero registrar por<select value={f.interaction_pref} onChange={set('interaction_pref')}>
            <option value="texto">Texto o selección</option><option value="voz">Voz</option></select></label>
        </div>
        {err && <p className="error">{err}</p>}
        <button className="btn primary block">{saved ? '✓ Guardado' : 'Guardar'}</button>
      </form>
    </section>
  )
}
