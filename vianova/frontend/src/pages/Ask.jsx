import { useState } from 'react'
import { api } from '../api.js'
import { useVoice, MicButton } from '../voice.jsx'
import { SourceTag } from './Home.jsx'

const EXAMPLES = ['Tiene llagas en la boca, ¿qué puede comer?', '¿Qué hago si tiene fiebre durante la quimioterapia?',
  'Se me olvidó darle una pastilla', 'Me siento agotada de cuidarlo']
const STATUS = { respondida: ['Respuesta basada en fuentes', 'ok'], abstencion: ['Sin evidencia suficiente', 'warn'],
  fuera_de_alcance: ['Fuera del alcance del sistema', 'warn'] }

export default function Ask() {
  const [q, setQ] = useState('')
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const voice = useVoice(t => { setQ(t); send(t, 'voz') })

  async function send(text = q, channel = 'texto') {
    if (!text.trim()) return
    setBusy(true); setErr('')
    try {
      const r = await api('/api/assistant/ask', { method: 'POST', body: { query: text, channel } })
      setHistory([r, ...history]); setQ('')
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  return (
    <section>
      <h1>Consultar</h1>
      <p className="muted">Las respuestas se basan solo en las guías del sistema y siempre muestran la fuente. Si no hay información suficiente, se lo diremos.</p>
      <form className="card" onSubmit={e => { e.preventDefault(); send() }}>
        <textarea rows={2} value={q} onChange={e => setQ(e.target.value)} placeholder="Escriba su pregunta…" maxLength={600} />
        <div className="row-gap">
          <MicButton voice={voice} label="Preguntar por voz" />
          <button className="btn primary" disabled={busy || !q.trim()}>{busy ? 'Buscando…' : 'Preguntar'}</button>
        </div>
        {voice.error && <p className="error small">{voice.error}</p>}
        {err && <p className="error">{err}</p>}
      </form>
      {!history.length && (
        <div className="chips">{EXAMPLES.map(x => <button key={x} className="chip" onClick={() => send(x)}>{x}</button>)}</div>
      )}
      {history.map((r, i) => (
        <article key={i} className={`answer ${r.status}`}>
          <p className="q">“{r.query}”</p>
          {r.urgent && <div className="urgent" role="alert">🚨 {r.urgent_message}</div>}
          <span className={`badge ${STATUS[r.status][1]}`}>{STATUS[r.status][0]}</span>
          <p>{r.answer}</p>
          {r.sources.map(s => <div key={s.doc_id}><SourceTag s={s} />{s.section && <span className="muted small"> — {s.section}</span>}</div>)}
          <p className="muted tiny">Corpus {r.corpus_version} · modo {r.mode || '—'}</p>
          {r.trace && <RagTrace t={r.trace} />}
        </article>
      ))}
      <p className="disclaimer">Vianova no indica dosis, diagnósticos ni cambios de tratamiento. Consulte esas decisiones con el equipo de salud.</p>
    </section>
  )
}

// RF-07 Trazabilidad: muestra cómo se obtuvo la respuesta (recuperación → umbral → generación → fuentes)
export function RagTrace({ t }) {
  return (
    <details className="trace">
      <summary>Ver cómo se obtuvo esta respuesta</summary>
      <ol className="trace-steps">{t.pasos.map((p, i) => <li key={i}><strong>{p.paso.replace(/^\d+\.\s*/, '')}:</strong> {p.resultado}</li>)}</ol>
      {!!t.candidatos.length && (
        <ul className="trace-cands" aria-label="Fragmentos recuperados">
          {t.candidatos.map((c, i) => (
            <li key={i} className={c.usado ? 'used' : c.seleccionado ? 'ctx' : 'discarded'}>
              <div className="tc-head"><strong>{c.doc_id}</strong> · {c.seccion}
                <span className={`badge ${c.usado ? 'ok' : ''}`}>{c.usado ? 'citado' : c.seleccionado ? 'en contexto' : c.supera_tau ? 'baja cobertura' : 'bajo τ'}</span></div>
              <div className="tc-scores">Puntaje híbrido <b>{c.puntaje}</b> (TF-IDF {c.disperso} · embedding {c.denso}) · cobertura {c.cobertura}</div>
              <div className="tc-text">{c.fragmento.length > 120 ? c.fragmento.slice(0, 120) + '…' : c.fragmento}</div>
            </li>))}
        </ul>
      )}
      <p className="muted tiny">τ = {t.tau} · cobertura mínima {t.cobertura_minima} · embeddings de {t.dimension_embeddings} dimensiones · peso denso {t.peso_denso}</p>
    </details>
  )
}
