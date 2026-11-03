import { useEffect, useState } from 'react'
import { api, fmtDateTime } from '../api.js'

const EMPTY = { doc_id: '', institution: '', title: '', year: '', version: '1.0', url: '', doc_type: 'guía', topics: '', audience: 'cuidadores',
  crit_oficial: false, crit_vigente: false, crit_idioma: false, crit_pertinente: false }

export default function Corpus() {
  const [data, setData] = useState(null)
  const [show, setShow] = useState(false)
  const [f, setF] = useState(EMPTY)
  const [file, setFile] = useState(null)
  const [err, setErr] = useState('')
  const [msg, setMsg] = useState('')
  const load = () => api('/api/corpus').then(setData).catch(e => setErr(e.message))
  useEffect(() => { load() }, [])
  const set = k => e => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  async function upload(e) {
    e.preventDefault(); setErr(''); setMsg('')
    const form = new FormData()
    Object.entries(f).forEach(([k, v]) => { if (v !== '') form.append(k, v) })
    form.append('file', file)
    try {
      const d = await api('/api/corpus', { method: 'POST', form })
      setMsg(`Documento ${d.id} registrado como «${d.status}».`); setF(EMPTY); setFile(null); setShow(false); load()
    } catch (ex) { setErr(ex.message) }
  }
  async function status(d, st) {
    let reason = ''
    if (st !== 'incluido') { reason = prompt(`Motivo para marcar ${d.id} como ${st}:`) || ''; if (!reason.trim()) return }
    try { await api(`/api/corpus/${d.id}/status`, { method: 'PUT', body: { status: st, reason } }); load() } catch (ex) { setErr(ex.message) }
  }

  if (!data) return <section><p className="muted">{err || 'Cargando…'}</p></section>
  return (
    <section>
      <div className="row-between">
        <h1>Corpus documental</h1>
        <button className="btn primary" onClick={() => setShow(!show)}>{show ? 'Cerrar' : '+ Incorporar documento'}</button>
      </div>
      <p className="muted">Versión del corpus {data.version} · {data.indexed_chunks} fragmentos indexados. Solo los documentos «incluidos» se usan en las respuestas y recomendaciones.</p>
      {msg && <p className="ok-msg">{msg}</p>}
      {err && <p className="error">{err}</p>}
      {show && (
        <form className="card form" onSubmit={upload}>
          <h2>Ficha de curaduría documental</h2>
          <div className="grid3">
            <label>Identificador<input value={f.doc_id} onChange={set('doc_id')} required placeholder="MINSA-2022-01" /></label>
            <label>Institución<input value={f.institution} onChange={set('institution')} required /></label>
            <label>Año<input type="number" value={f.year} onChange={set('year')} /></label>
          </div>
          <label>Título<input value={f.title} onChange={set('title')} required /></label>
          <div className="grid3">
            <label>Versión<input value={f.version} onChange={set('version')} /></label>
            <label>Tipo<input value={f.doc_type} onChange={set('doc_type')} /></label>
            <label>Público<input value={f.audience} onChange={set('audience')} /></label>
          </div>
          <label>Enlace<input type="url" value={f.url} onChange={set('url')} /></label>
          <label>Temas (separados por comas)<input value={f.topics} onChange={set('topics')} placeholder="fiebre, quimioterapia, signos_alarma" /></label>
          <fieldset><legend>Criterios de inclusión</legend>
            <label className="check"><input type="checkbox" checked={f.crit_oficial} onChange={set('crit_oficial')} /><span>Fuente oficial o revisada por pares</span></label>
            <label className="check"><input type="checkbox" checked={f.crit_vigente} onChange={set('crit_vigente')} /><span>Vigente</span></label>
            <label className="check"><input type="checkbox" checked={f.crit_idioma} onChange={set('crit_idioma')} /><span>En español o inglés</span></label>
            <label className="check"><input type="checkbox" checked={f.crit_pertinente} onChange={set('crit_pertinente')} /><span>Pertinente para el cuidado domiciliario</span></label>
          </fieldset>
          <label>Archivo (PDF, TXT o MD)<input type="file" accept=".pdf,.txt,.md" onChange={e => setFile(e.target.files[0])} required /></label>
          <p className="hint">Si no cumple los cuatro criterios, el documento quedará registrado como «excluido».</p>
          <button className="btn primary">Registrar e indexar</button>
        </form>
      )}
      <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable">
        <table className="small">
          <thead><tr><th>ID</th><th>Título</th><th>Institución</th><th>Versión</th><th>Fragm.</th><th>Estado</th><th>Revisado</th><th></th></tr></thead>
          <tbody>{data.documents.map(d => (
            <tr key={d.id}>
              <td>{d.id}{d.is_demo && <span className="badge demo">demo</span>}</td>
              <td><a href={`#/documento/${d.id}`}>{d.title}</a></td><td>{d.institution}</td><td>{d.version}</td><td>{d.chunks}</td>
              <td><span className={`badge ${d.status === 'incluido' ? 'ok' : 'warn'}`}>{d.status}</span>{d.status_reason && <div className="tiny muted">{d.status_reason}</div>}</td>
              <td>{fmtDateTime(d.reviewed_at)}<div className="tiny muted">{d.curator}</div></td>
              <td className="nowrap">
                {d.status !== 'incluido' && <button className="btn tiny ghost" onClick={() => status(d, 'incluido')}>Incluir</button>}
                {d.status === 'incluido' && <button className="btn tiny ghost" onClick={() => status(d, 'excluido')}>Excluir</button>}
                {d.status !== 'retirado' && <button className="btn tiny ghost" onClick={() => status(d, 'retirado')}>Retirar</button>}
              </td>
            </tr>))}</tbody>
        </table>
      </div>
    </section>
  )
}
