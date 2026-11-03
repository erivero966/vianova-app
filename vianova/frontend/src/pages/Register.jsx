import { useEffect, useState } from 'react'
import { api, SYMPTOMS, SYMPTOM_LABEL, fmtDateTime } from '../api.js'
import { useVoice, MicButton } from '../voice.jsx'
import { AlertCard } from './Home.jsx'

const BLANK = { kind: 'sintoma', symptom: '', intensity: null, value: null, unit: '', moment: '', frequency: null, text: '', channel: 'seleccion' }

export default function Register() {
  const [text, setText] = useState('')
  const [prop, setProp] = useState(null)        // propuesta pendiente de confirmación
  const [result, setResult] = useState(null)
  const [events, setEvents] = useState([])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const voice = useVoice(t => { setText(t); interpret(t, 'voz') })

  const loadEvents = () => api('/api/events?days=7').then(setEvents).catch(() => {})
  useEffect(() => { loadEvents() }, [])

  async function interpret(t = text, channel = 'texto') {
    if (!t.trim()) return
    setErr(''); setResult(null)
    try {
      const p = await api('/api/events/parse', { method: 'POST', body: { text: t } })
      setProp({ ...p, channel })
    } catch (e) { setErr(e.message) }
  }
  function quick(sym) { setResult(null); setProp({ ...BLANK, symptom: sym, channel: 'seleccion' }) }

  async function confirm() {
    setBusy(true); setErr('')
    try {
      const body = { ...prop, confirmed: true, unit: prop.unit || '', value: prop.value === '' ? null : prop.value }
      delete body.other_symptoms
      const r = await api('/api/events', { method: 'POST', body })
      setResult(r); setProp(null); setText(''); loadEvents()
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  const upd = (k, conv = v => v) => e => setProp({ ...prop, [k]: e.target.value === '' ? null : conv(e.target.value) })

  return (
    <section>
      <h1>Registrar</h1>
      <p className="muted">Anote cómo está el paciente. Puede tocar un síntoma, escribir o dictar por voz; antes de guardar siempre podrá revisar y corregir.</p>

      {!prop && (
        <>
          <h2>Selección rápida</h2>
          <div className="chips">
            {SYMPTOMS.map(([k, l]) => <button key={k} className="chip" onClick={() => quick(k)}>{l}</button>)}
          </div>
          <h2>Describirlo con sus palabras</h2>
          <div className="card">
            <textarea rows={3} value={text} onChange={e => setText(e.target.value)}
              placeholder="Ej.: Esta mañana tuvo fiebre de 38,2 grados y dolor 6 de 10" />
            <div className="row-gap">
              <MicButton voice={voice} />
              <button className="btn primary" onClick={() => interpret(text, 'texto')} disabled={!text.trim()}>Revisar</button>
            </div>
            {voice.error && <p className="error small">{voice.error}</p>}
          </div>
        </>
      )}

      {prop && (
        <div className="card form confirm-card">
          <h2>Revise antes de guardar</h2>
          {prop.text && <p className="quote">“{prop.text}”</p>}
          {prop.other_symptoms?.length > 0 && <p className="hint">También mencionó: {prop.other_symptoms.map(s => SYMPTOM_LABEL[s] || s).join(', ')}. Puede registrarlos por separado.</p>}
          <div className="grid2">
            <label>Tipo<select value={prop.kind} onChange={upd('kind')}>
              <option value="sintoma">Síntoma</option><option value="observacion">Observación</option><option value="actividad">Actividad</option></select></label>
            <label>Síntoma<select value={prop.symptom || ''} onChange={e => setProp({ ...prop, symptom: e.target.value })}>
              <option value="">— ninguno —</option>{SYMPTOMS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          </div>
          <label>Intensidad (0 = nada, 10 = máxima): <strong>{prop.intensity ?? 'sin indicar'}</strong>
            <input type="range" min="0" max="10" value={prop.intensity ?? 0} onChange={upd('intensity', Number)} />
          </label>
          <div className="grid2">
            {(prop.symptom === 'fiebre' || prop.value != null) && (
              <label>Temperatura (°C)<input type="number" step="0.1" min="34" max="43" value={prop.value ?? ''}
                onChange={e => setProp({ ...prop, value: e.target.value === '' ? null : Number(e.target.value), unit: '°C' })} /></label>
            )}
            {['vomito', 'diarrea'].includes(prop.symptom) && (
              <label>¿Cuántas veces?<input type="number" min="0" max="50" value={prop.frequency ?? ''} onChange={upd('frequency', Number)} /></label>
            )}
            <label>¿Cuándo?<input value={prop.moment || ''} onChange={e => setProp({ ...prop, moment: e.target.value })} placeholder="Ej.: esta mañana" /></label>
          </div>
          <label>Nota (opcional)<textarea rows={2} value={prop.text || ''} onChange={e => setProp({ ...prop, text: e.target.value })} /></label>
          {err && <p className="error">{err}</p>}
          <div className="row-gap">
            <button className="btn primary" onClick={confirm} disabled={busy}>Confirmar y guardar</button>
            <button className="btn ghost" onClick={() => setProp(null)}>Cancelar</button>
          </div>
          <p className="muted small">Canal: {prop.channel === 'voz' ? 'voz (transcripción revisada por usted)' : prop.channel}</p>
        </div>
      )}

      {result && (
        <div className="saved">
          <p className="ok-msg">✓ Registro guardado.</p>
          {result.alerts.map(a => <AlertCard key={a.id} a={a} />)}
        </div>
      )}

      <h2>Últimos 7 días</h2>
      {!events.length && <p className="muted">Sin registros recientes.</p>}
      <ul className="plain">
        {events.map(e => (
          <li key={e.id} className="event-row">
            <span className="muted small">{fmtDateTime(e.occurred_at)}</span>
            <span><strong>{e.symptom ? (SYMPTOM_LABEL[e.symptom] || e.symptom_label) : e.kind}</strong>
              {e.intensity != null && ` · ${e.intensity}/10`}{e.value != null && ` · ${e.value} ${e.unit}`}
              {e.frequency != null && ` · ${e.frequency} veces`}{e.moment && ` · ${e.moment}`}</span>
            {e.text && <span className="small">{e.text}</span>}
          </li>
        ))}
      </ul>
    </section>
  )
}
