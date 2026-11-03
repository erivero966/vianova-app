// Cliente de la API de Vianova
const TOKEN_KEY = 'vianova_token'

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(t) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch { /* sin almacenamiento */ }
}

export async function api(path, { method = 'GET', body, form, raw } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (form) payload = form
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(path, { method, headers, body: payload, keepalive: method === 'POST' && !form })
  if (raw) return res
  let data = null
  try { data = await res.json() } catch { /* sin cuerpo */ }
  if (!res.ok) {
    if (res.status === 401 && token) { setToken(null); window.dispatchEvent(new Event('vianova:logout')) }
    const detail = data?.detail
    const msg = Array.isArray(detail) ? detail.map(d => d.msg).join('; ') : (detail || 'Ocurrió un error')
    throw new Error(msg)
  }
  return data
}

export async function download(path, filename) {
  const res = await api(path, { raw: true })
  if (!res.ok) throw new Error('No se pudo descargar')
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

export const fmtDateTime = iso => iso ? new Date(iso).toLocaleString('es-PE', { dateStyle: 'medium', timeStyle: 'short' }) : '—'
export const fmtTime = iso => iso ? new Date(iso).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' }) : ''

// Fecha/hora local (Perú) en formato para el backend, sin zona
export function localIso(date) {
  const p = n => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}T${p(date.getHours())}:${p(date.getMinutes())}:00`
}

export const SYMPTOMS = [
  ['dolor', 'Dolor'], ['fiebre', 'Fiebre'], ['nauseas', 'Náuseas'], ['vomito', 'Vómitos'], ['fatiga', 'Cansancio'],
  ['diarrea', 'Diarrea'], ['estrenimiento', 'Estreñimiento'], ['disnea', 'Falta de aire'], ['mucositis', 'Llagas en la boca'],
  ['apetito', 'Sin apetito'], ['mareo', 'Mareo'], ['insomnio', 'No durmió'], ['ansiedad', 'Ansiedad'], ['tos', 'Tos'],
  ['sangrado', 'Sangrado'], ['confusion', 'Confusión'], ['hinchazon', 'Hinchazón'],
]
export const SYMPTOM_LABEL = Object.fromEntries(SYMPTOMS)

export const go = path => { window.location.hash = '/' + path }
