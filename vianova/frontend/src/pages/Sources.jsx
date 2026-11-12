import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

// Consultar como chat. Cada mensaje se envía de forma INDEPENDIENTE a POST /api/rag/search (sin historial):
// el backend recupera Top-3 en rag-engine (BGE-M3 + pgvector) y qwen2.5:7b redacta la respuesta con sus fuentes.
// La evidencia llega en la misma respuesta; abrirla no hace otra petición.
// La conversación actual se guarda solo en localStorage del navegador (prototipo), una por usuario.
const EXAMPLES = ['Mi familiar tiene náuseas después de la quimioterapia', '¿Qué efectos secundarios puede causar la radioterapia?',
  'Tiene problemas para comer durante el tratamiento del cáncer', '¿Qué hacer si tiene diarrea durante la quimioterapia?']
const MSG_EMPTY = 'Escribe una consulta antes de continuar.'
const MSG_ERROR = 'No pude responder en este momento. Inténtalo nuevamente.'
const STORE_PREFIX = 'vianova_chat_v1_'
const MAX_TURNS = 40          // límite de mensajes guardados en el navegador

const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
const storeKey = user => STORE_PREFIX + (user?.code || 'anon')
function loadChat(key) {
  try { const v = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(v) ? v : [] } catch { return [] }
}
function saveChat(key, msgs) {
  try { msgs.length ? localStorage.setItem(key, JSON.stringify(msgs.slice(-MAX_TURNS))) : localStorage.removeItem(key) } catch { /* sin almacenamiento */ }
}

const pages = s => s.page_start == null ? '' : (s.page_end && s.page_end !== s.page_start ? `pp. ${s.page_start}–${s.page_end}` : `p. ${s.page_start}`)
// «National Cancer Institute (NCI)» → «NCI»; el nombre completo queda en la evidencia.
const shortEntity = e => (e || '').match(/\(([^)]+)\)\s*$/)?.[1] || e || ''
// «La quimioterapia y usted: Apoyo para…» → «La quimioterapia y usted»
const shortDoc = d => (d || '').split(':')[0]
// Las viñetas de los PDF del NCI se extraen como «Î»; solo se ajusta la presentación.
const display = text => (text || '').replace(/^Î\s*/gm, '• ')

function Evidence({ sources }) {
  return (
    <ol className="chat-evidence">
      {sources.map(s => (
        <li key={s.rank}>
          <p className="ev-text">{display(s.text)}</p>
          <p className="ev-meta">[{s.rank}] {s.entity} · {s.document}{s.version ? ` (${s.version})` : ''}
            {s.section ? <> · {s.section}</> : null}{pages(s) ? <> · {pages(s)}</> : null}</p>
        </li>
      ))}
    </ol>
  )
}

function AssistantMessage({ m }) {
  const [open, setOpen] = useState(false)
  const sources = m.sources || []
  // Fuera del corpus / fuera de alcance: solo el mensaje, sin fuentes ni evidencia irrelevantes.
  const answered = m.answer_status === 'respondida'
  const showEvidence = sources.length > 0 && (answered || m.answer_status === 'sin_generacion')
  const used = answered ? sources.filter(s => s.used) : []
  return (
    <div className={`msg bot ${m.error ? 'error' : ''}`}>
      <div className="msg-author"><span className="logo mini" aria-hidden="true">♥</span> Vianova</div>
      {m.urgent && <div className="chat-urgent" role="alert">⚠ {m.urgent_message}</div>}
      <p className="msg-text">{m.answer}</p>
      {used.length > 0 && (
        <ul className="chat-sources" aria-label="Fuentes">
          {used.map(s => (
            <li key={s.rank}><span className="src-n">[{s.rank}]</span> {shortEntity(s.entity)} · {shortDoc(s.document)}
              <br />{[s.section, pages(s)].filter(Boolean).join(' · ')}</li>
          ))}
        </ul>
      )}
      {showEvidence && (
        <>
          <button type="button" className="linklike ev-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? 'Ocultar evidencia' : 'Ver evidencia'}
          </button>
          {open && <Evidence sources={sources} />}
        </>
      )}
    </div>
  )
}

export default function Sources({ user }) {
  const key = storeKey(user)
  const [msgs, setMsgs] = useState(() => loadChat(key))
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [hint, setHint] = useState('')
  const input = useRef(null)
  const bottom = useRef(null)
  const log = useRef(null)

  useEffect(() => { saveChat(key, msgs) }, [key, msgs])
  useEffect(() => {
    // Al enviar: bajar hasta el indicador de carga. Al llegar la respuesta: llevar la última pregunta arriba,
    // para leer la pregunta y el comienzo de la respuesta (el cuadro de entrada fijo no la tapa).
    if (!msgs.length && !busy) return
    const last = msgs[msgs.length - 1]
    const asked = log.current?.querySelectorAll('.msg.user')
    if (!busy && last?.role === 'assistant' && asked?.length) asked[asked.length - 1].scrollIntoView({ behavior: 'smooth', block: 'start' })
    else bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [msgs.length, busy])
  useEffect(() => { autoGrow() }, [q])

  function autoGrow() {
    const el = input.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 132) + 'px'
  }

  async function send(text = q) {
    if (busy) return
    const query = text.trim()
    if (!query) { setHint(MSG_EMPTY); input.current?.focus(); return }
    setHint(''); setQ(''); setBusy(true)
    setMsgs(prev => [...prev, { id: newId(), role: 'user', content: query }])
    let reply
    try {
      // Consulta independiente: solo el texto actual, nunca el historial.
      const r = await api('/api/rag/search', { method: 'POST', body: { query } })
      reply = { id: newId(), role: 'assistant', query: r.query, answer: r.answer, answer_status: r.answer_status,
                sources: r.sources || [], urgent: !!r.urgent, urgent_message: r.urgent ? r.urgent_message : null }
    } catch {
      reply = { id: newId(), role: 'assistant', query, answer: MSG_ERROR, answer_status: 'error', sources: [], urgent: false,
                urgent_message: null, error: true }   // nunca se muestran detalles técnicos
    }
    setMsgs(prev => [...prev, reply])
    setBusy(false)
    input.current?.focus()
  }

  function newChat() {
    if (busy) return
    setMsgs([]); setQ(''); setHint('')
    try { localStorage.removeItem(key) } catch { /* sin almacenamiento */ }
    input.current?.focus()
  }

  function onKeyDown(e) {
    // Enter envía; Shift+Enter hace salto de línea (y no se interrumpe la composición de acentos/IME).
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send() }
  }

  const empty = msgs.length === 0 && !busy

  return (
    <section className="chat">
      {empty ? (
        <div className="chat-hello">
          <h1>¿En qué podemos ayudarte?</h1>
          <p className="muted">Información basada en fuentes verificadas.</p>
          <div className="chat-examples">
            {EXAMPLES.map(x => <button key={x} type="button" className="chip" onClick={() => void send(x)}>{x}</button>)}
          </div>
          <p className="tiny"><a href="#/asistente">Asistente con el corpus de demostración</a></p>
        </div>
      ) : (
        <div className="chat-bar">
          <h1 className="sr-only">Consultar</h1>
          <button type="button" className="linklike small" onClick={newChat} disabled={busy}>+ Nueva conversación</button>
        </div>
      )}

      <div className="chat-log" aria-live="polite" ref={log}>
        {msgs.map((m, i) => m.role === 'user'
          ? <div key={m.id || i} className="msg user"><p className="msg-text">{m.content}</p></div>
          : <AssistantMessage key={m.id || i} m={m} />)}
        {busy && (
          <div className="msg bot pending" role="status">
            <div className="msg-author"><span className="logo mini" aria-hidden="true">♥</span> Vianova</div>
            <p className="msg-text muted"><span className="dots" aria-hidden="true" /> Vianova está consultando las fuentes...</p>
          </div>
        )}
        <div ref={bottom} className="chat-end" />
      </div>

      <form className="chat-composer" onSubmit={e => { e.preventDefault(); void send() }}>
        <div className="composer-box">
          <label htmlFor="rag-q" className="sr-only">Escribe tu consulta</label>
          <textarea id="rag-q" ref={input} rows={1} value={q} maxLength={600} placeholder="Escribe tu consulta..."
            onChange={e => { setQ(e.target.value); if (hint) setHint('') }} onKeyDown={onKeyDown}
            aria-describedby="chat-note" />
          <button type="submit" className="send-btn" disabled={busy} aria-label={busy ? 'Consultando fuentes' : 'Consultar'}
            title="Consultar">➤</button>
        </div>
        {hint && <p className="error tiny" role="alert">{hint}</p>}
        <p id="chat-note" className="chat-note">Información educativa. No reemplaza la orientación de un profesional de salud.</p>
      </form>
    </section>
  )
}
