import { useEffect, useState } from 'react'
import { api, download, fmtDateTime } from '../api.js'

const TREAT = { quimioterapia: 'Quimioterapia', radioterapia: 'Radioterapia', cirugia: 'Cirugía', inmunoterapia: 'Inmunoterapia', paliativo: 'Cuidados paliativos' }
const METRIC = { frecuencia_cardiaca: 'Frecuencia cardiaca', pasos: 'Pasos', temperatura: 'Temperatura', spo2: 'Saturación (SpO₂)', sueno_horas: 'Horas de sueño' }

export default function Summary() {
  const [days, setDays] = useState(14)
  const [s, setS] = useState(null)
  useEffect(() => { setS(null); api(`/api/summary?days=${days}`).then(setS) }, [days])

  return (
    <section className="summary">
      <div className="row-between no-print">
        <h1>Resumen para el equipo de salud</h1>
      </div>
      <div className="row-gap no-print">
        <label className="inline">Periodo
          <select value={days} onChange={e => setDays(Number(e.target.value))}>
            <option value={7}>7 días</option><option value={14}>14 días</option><option value={30}>30 días</option></select>
        </label>
        <button className="btn primary" onClick={() => window.print()}>Imprimir / PDF</button>
        <button className="btn secondary" onClick={() => download(`/api/summary.csv?days=${days}`, 'resumen_registros.csv')}>Descargar CSV</button>
      </div>
      {!s ? <p className="muted">Cargando…</p> : (
        <div className="card print-area">
          <h2>Resumen de cuidado domiciliario — últimos {s.periodo_dias} días</h2>
          <p className="small">Generado: {fmtDateTime(s.generado)} · Cuidador(a): {s.cuidador}</p>
          <p className="small">Paciente: {s.paciente.patient_alias || '—'}{s.paciente.patient_age ? `, ${s.paciente.patient_age} años` : ''} ·
            Diagnóstico informado: {s.paciente.cancer_type || '—'} · Tratamiento: {(s.paciente.treatments || []).map(t => TREAT[t] || t).join(', ') || '—'}</p>
          <h3>Síntomas registrados</h3>
          {Object.keys(s.sintomas).length ? (
            <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable"><table><thead><tr><th>Síntoma</th><th>Registros</th><th>Intensidad máx.</th><th>Valor máx.</th></tr></thead>
              <tbody>{Object.entries(s.sintomas).map(([k, v]) => (
                <tr key={k}><td>{k}</td><td>{v.registros}</td><td>{v.intensidad_max ?? '—'}</td><td>{v.valor_max ?? '—'}</td></tr>))}</tbody></table></div>
          ) : <p className="muted">Sin síntomas registrados.</p>}
          <h3>Medicamentos (tomas registradas)</h3>
          {s.medicamentos.length ? (
            <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable"><table><thead><tr><th>Medicamento</th><th>Indicación</th><th>Programadas</th><th>Realizadas</th></tr></thead>
              <tbody>{s.medicamentos.map(m => (
                <tr key={m.medicamento}><td>{m.medicamento}</td><td>{m.indicacion || '—'}</td><td>{m.programadas}</td><td>{m.realizadas}</td></tr>))}</tbody></table></div>
          ) : <p className="muted">Sin medicamentos registrados.</p>}
          <h3>Avisos mostrados</h3>
          {s.avisos.length ? <ul>{s.avisos.map(a => <li key={a.id}>{fmtDateTime(a.created_at)} — {a.message.split('.')[0]}.</li>)}</ul> : <p className="muted">Ninguno.</p>}
          {Object.keys(s.dispositivos).length > 0 && (<>
            <h3>Datos de dispositivos (no clínicos)</h3>
            <ul>{Object.entries(s.dispositivos).map(([k, v]) => <li key={k}>{METRIC[k] || k}: {v.n} lecturas, rango {v.min}–{v.max} {v.unidad}</li>)}</ul>
          </>)}
          <h3>Detalle de registros</h3>
          {s.eventos.length ? (
            <div className="table-wrap" tabIndex={0} role="region" aria-label="Tabla desplazable"><table className="small"><thead><tr><th>Fecha</th><th>Registro</th><th>Nota</th></tr></thead>
              <tbody>{s.eventos.map(e => (
                <tr key={e.id}><td>{fmtDateTime(e.occurred_at)}</td>
                  <td>{e.symptom_label || e.kind}{e.intensity != null && ` ${e.intensity}/10`}{e.value != null && ` ${e.value} ${e.unit}`}{e.frequency != null && ` ×${e.frequency}`}</td>
                  <td>{e.text}</td></tr>))}</tbody></table></div>
          ) : <p className="muted">Sin registros.</p>}
          <p className="muted small">{s.nota}</p>
        </div>
      )}
    </section>
  )
}
