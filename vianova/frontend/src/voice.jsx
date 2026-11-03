// Reconocimiento de voz bajo demanda (Web Speech API del navegador). El micrófono solo se activa al pulsar.
import { useRef, useState } from 'react'

export function useVoice(onText) {
  const SR = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)
  const [listening, setListening] = useState(false)
  const [error, setError] = useState('')
  const rec = useRef(null)

  function start() {
    setError('')
    if (!SR) { setError('Su navegador no permite el dictado por voz. Pruebe con Chrome o escriba el texto.'); return }
    const r = new SR()
    r.lang = 'es-PE'
    r.interimResults = false
    r.maxAlternatives = 1
    r.onresult = e => onText(e.results[0][0].transcript)
    r.onerror = e => setError(e.error === 'not-allowed' ? 'Debe permitir el uso del micrófono.' : 'No se entendió el audio, intente de nuevo.')
    r.onend = () => setListening(false)
    rec.current = r
    setListening(true)
    r.start()
  }
  function stop() { rec.current?.stop(); setListening(false) }
  return { supported: !!SR, listening, error, start, stop }
}

export function MicButton({ voice, label = 'Dictar' }) {
  return (
    <button type="button" className={`btn mic ${voice.listening ? 'on' : ''}`}
      onClick={voice.listening ? voice.stop : voice.start} aria-pressed={voice.listening}>
      <span aria-hidden="true">{voice.listening ? '■' : '🎤'}</span> {voice.listening ? 'Escuchando… (toque para parar)' : label}
    </button>
  )
}
