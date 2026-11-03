import { useEffect, useState } from 'react'
import { api } from '../api.js'

// RF-12 Configuración vigente del modelo (lectura): parámetros RAG, pesos del recomendador, versión del corpus y reglas
export default function Config() {
  const [c, setC] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => { api('/api/admin/config').then(setC).catch(e => setErr(e.message)) }, [])
  if (!c) return <section><p className="muted">{err || 'Cargando…'}</p></section>
  const Row = ({ k, v }) => <tr><th scope="row">{k}</th><td>{String(v)}</td></tr>
  return (
    <section>
      <h1>Configuración del modelo</h1>
      <p className="muted">Parámetros vigentes. Se cambian por variables de entorno en un despliegue versionado; cada cambio requiere reindexar y repetir la validación técnica.</p>
      <div className="stats">
        <div className="stat"><span>{c.version_corpus}</span>versión del corpus</div>
        <div className="stat"><span>{c.documentos.incluidos}/{c.documentos.total}</span>documentos incluidos</div>
        <div className="stat"><span>{c.indice.fragmentos}</span>fragmentos indexados</div>
        <div className="stat"><span>{c.ambiente}</span>ambiente</div>
      </div>
      <div className="grid2">
        <div className="card"><h2>Recuperación y generación (RAG)</h2><table className="small"><tbody>
          <Row k="Umbral de abstención τ" v={c.rag.tau} /><Row k="Cobertura mínima" v={c.rag.cobertura_minima} />
          <Row k="Top-k" v={c.indice.top_k} /><Row k="Dimensión de embeddings" v={c.indice.dimension_embeddings} />
          <Row k="Peso del componente denso" v={c.indice.peso_denso} /><Row k="Proveedor" v={c.rag.proveedor} /><Row k="Modelo" v={c.rag.modelo} />
        </tbody></table></div>
        <div className="card"><h2>Recomendador</h2><table className="small"><tbody>
          <Row k="w₁ semántica" v={c.recomendador.w_sem} /><Row k="w₂ contexto" v={c.recomendador.w_ctx} />
          <Row k="w₃ reglas" v={c.recomendador.w_reg} /><Row k="w₄ preferencia" v={c.recomendador.w_pref} />
        </tbody></table>
          <h2>Reglas de avisos</h2><table className="small"><tbody>
            <Row k="Archivo" v={c.reglas.archivo} /><Row k="N.º de reglas" v={c.reglas.n} /><Row k="Huella SHA-256" v={c.reglas.sha256} />
          </tbody></table></div>
      </div>
      <p className="muted small">Consentimiento vigente: {c.consentimiento_vigente} · tolerancia «a tiempo»: {c.tolerancia_a_tiempo_min} min{c.documentos.demo ? ` · ${c.documentos.demo} documentos de demostración` : ''}</p>
    </section>
  )
}
