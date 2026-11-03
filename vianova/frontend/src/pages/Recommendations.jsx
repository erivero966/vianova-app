import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { RecCard } from './Home.jsx'

// RF-05 Recomendaciones personalizadas explicadas · RF-08 Retroalimentación de utilidad
export default function Recommendations() {
  const [q, setQ] = useState('')
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [sent, setSent] = useState(0)
  async function load(query = '') {
    setErr('')
    try { setData(await api(`/api/recommendations?limit=8${query ? `&q=${encodeURIComponent(query)}` : ''}`)) } catch (e) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])
  const feedback = (doc_id, useful) => api('/api/recommendations/feedback', { method: 'POST', body: { doc_id, useful } })
    .then(() => setSent(n => n + 1)).catch(() => {})

  return (
    <section>
      <h1>Recomendaciones</h1>
      <p className="muted">Se ordenan según su consulta, el perfil del paciente, sus registros recientes y las reglas de seguridad.
        Cada tarjeta explica por qué se le muestra y de qué guía proviene.</p>
      <form className="card" role="search" onSubmit={e => { e.preventDefault(); load(q) }}>
        <label htmlFor="rq">¿Sobre qué necesita orientación?</label>
        <div className="row-gap" style={{ marginTop: 0 }}>
          <input id="rq" value={q} onChange={e => setQ(e.target.value)} placeholder="Ej.: alimentación, cansancio, cuidado de la piel" style={{ flex: 1 }} />
          <button className="btn primary">Buscar</button>
        </div>
      </form>
      {data && (
        <details className="card weights">
          <summary>¿Cómo se calcula el orden?</summary>
          <p className="small">Puntaje = 0,45 × similitud semántica + 0,25 × contexto del paciente + 0,20 × reglas (síntomas registrados) + 0,10 × sus valoraciones.
            Sus valoraciones solo cambian el orden; nunca desactivan las reglas de seguridad.</p>
        </details>
      )}
      {err && <p className="error">{err}</p>}
      {!data ? <p className="muted">Cargando…</p> : data.items.length === 0 ? <p className="muted">No hay recomendaciones para esta búsqueda.</p>
        : data.items.map(r => (
          <div key={r.doc_id}>
            <RecCard r={r} onFeedback={feedback} />
            {r.components && (
              <p className="muted tiny score-line">Puntaje {r.score.toFixed(2)} · semántica {r.components.sem} · contexto {r.components.ctx} · reglas {r.components.reg} · preferencia {r.components.pref}</p>
            )}
          </div>
        ))}
      {sent > 0 && <p className="ok-msg" role="status">Gracias: {sent} valoración{sent > 1 ? 'es' : ''} registrada{sent > 1 ? 's' : ''}.</p>}
      {data && <p className="muted tiny">Corpus {data.corpus_version}</p>}
    </section>
  )
}
