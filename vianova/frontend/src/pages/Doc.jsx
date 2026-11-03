import { useEffect, useState } from 'react'
import { api, fmtDateTime } from '../api.js'

export default function Doc({ id }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api(`/api/documents/${id}`).then(setD).catch(e => setErr(e.message)) }, [id])
  if (err) return <section><p className="error">{err}</p></section>
  if (!d) return <section><p className="muted">Cargando…</p></section>
  return (
    <section className="doc">
      <button className="btn ghost small" onClick={() => history.back()}>← Volver</button>
      <h1>{d.title}</h1>
      <p className="muted small">{d.institution}{d.year ? ` · ${d.year}` : ''} · versión {d.version} · revisado {fmtDateTime(d.reviewed_at)}
        {d.url && <> · <a href={d.url} target="_blank" rel="noreferrer">documento original</a></>}</p>
      {d.is_demo && <p className="demo-note">Contenido de demostración: será reemplazado por el documento oficial curado antes del piloto.</p>}
      {d.sections.map((s, i) => (
        <div key={i}>{s.section && <h2>{s.section}</h2>}<p>{s.text}</p></div>
      ))}
      <p className="disclaimer">Información de apoyo. No reemplaza las indicaciones del equipo de salud.</p>
    </section>
  )
}
