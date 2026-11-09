import { useState } from 'react'
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { Download } from 'lucide-react'
import { useApi } from '../services/hooks'
import { API } from '../services/api'
import type { WeatherEvaluation } from '../services/types'
import { Card, H, Loading, Pill, KindBadge, fmt } from './ui'

const f3 = (x: number | null | undefined) => (x == null ? '—' : x.toFixed(3))
const Stat = ({ label, value, note }: { label: string; value: string | number; note?: string }) =>
  <Card className="p-4"><div className="text-xs text-muted">{label}</div><div className="text-xl font-semibold mt-1">{value}</div>{note && <div className="text-[11px] text-muted mt-1">{note}</div>}</Card>

/** Prompt B "Weather Evaluation" dashboard (dataset, split, MAE, six demonstrations, tests, validation, limitations). */
export default function Evaluation({ pid = 'prompt-b' }: { pid?: string }) {
  const r = useApi<WeatherEvaluation>(`/api/projects/${pid}/evaluation`)
  const [city, setCity] = useState(''); const [hz, setHz] = useState(1)
  if (!r.data) return <Loading error={r.error} />
  const e = r.data; const cities = e.evaluation.cities; const c = cities.find(x => x.city === city) ?? cities[0]
  const rows = c.evaluation_rows.find(x => x.horizon === hz)!.rows; const sum = rows.reduce((a, x) => a + x.abs_error, 0)
  const maeData = cities.map(x => ({ city: x.city, ...Object.fromEntries(x.metrics.by_horizon.map(h => [`${h.horizon}-day`, h.mae])) }))
  const splitData = cities.map(x => ({ city: x.city, Training: x.split.train_count, Evaluation: x.split.evaluation_count }))
  const methodData = c.comparison.map(m => ({ name: m.label.replace(' (last 3 days)', ''), mae: m.heldout_mae, selected: m.selected }))
  const lineData = rows.map(x => ({ date: x.date.slice(5), Actual: x.actual, Predicted: x.predicted }))
  const dq = e.data_quality
  return <div className="space-y-6">
    <div className="text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-3 py-2"><strong>{e.disclaimer}</strong> The supplied dataset is <strong>synthetic</strong>; a very low MAE reflects the regular pattern built into it, not real forecasting skill.</div>
    <div className="flex flex-wrap items-center gap-2 justify-between"><H title="Weather evaluation" sub={`Computed by the implementation on ${fmt(e.generated_at)} — ${e.evaluation.split_config.description}`} right={<KindBadge kind="real" />} />
      <div className="flex gap-2 flex-wrap -mt-4"><a className="btn btn-primary" href={`${API}/api/projects/${pid}/evaluation/download`}><Download size={14} />JSON</a>
        <a className="btn" href={`${API}/api/projects/${pid}/report/download`}><Download size={14} />Report (.md)</a><a className="btn" href={`${API}/api/projects/${pid}/report/download.pdf`}><Download size={14} />Report (.pdf)</a></div></div>

    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
      <Stat label="Observations" value={e.overview.dataset.valid_rows} note={`${e.overview.dataset.first_date} → ${e.overview.dataset.last_date}`} />
      <Stat label="Cities" value={e.overview.cities.join(', ')} />
      <Stat label="Training obs. / city" value={c.split.train_count} note={`${c.split.train_start} → ${c.split.train_end}`} />
      <Stat label="Evaluation obs. / city" value={c.split.evaluation_count} note={`${c.split.evaluation_start} → ${c.split.evaluation_end}`} />
      <Stat label="Overall held-out MAE" value={`${f3(e.evaluation.overall.mae)} °C`} note={`${e.evaluation.overall.n} forecasts`} />
      <Stat label="Tests passed" value={`${e.tests.passed} / ${e.tests.passed + e.tests.failed}`} note={`${e.tests.suites.length} suites`} /></div>

    <Card className="p-4"><div className="text-sm"><strong>Forecasting method:</strong> {c.selection.label}{c.selection.period ? ` with a ${c.selection.period}-day cycle` : ''} — chosen per city by backtest on the training period only. Time-ordered split ({c.split.strategy}), shuffled: <strong>{c.split.shuffled ? 'yes' : 'no'}</strong>, leakage check: <strong className={c.split.no_leakage ? 'text-ok' : 'text-err'}>{c.split.no_leakage ? 'verified' : 'violated'}</strong>.</div></Card>

    <div className="grid lg:grid-cols-3 gap-4">
      <Card className="p-4"><H title="MAE by city" sub="Held-out, by forecast horizon (°C)" /><div className="h-56"><ResponsiveContainer><BarChart data={maeData}><CartesianGrid stroke="#E5EAF1" vertical={false} /><XAxis dataKey="city" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} /><Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="1-day" fill="#4F6BED" radius={[4, 4, 0, 0]} /><Bar dataKey="2-day" fill="#7C93F2" radius={[4, 4, 0, 0]} /><Bar dataKey="3-day" fill="#B3C0F7" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
      <Card className="p-4"><H title="Training vs evaluation" sub="Observations per city (time-ordered)" /><div className="h-56"><ResponsiveContainer><BarChart data={splitData}><CartesianGrid stroke="#E5EAF1" vertical={false} /><XAxis dataKey="city" tick={{ fontSize: 12 }} /><YAxis allowDecimals={false} tick={{ fontSize: 12 }} /><Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Training" stackId="a" fill="#94A3B8" /><Bar dataKey="Evaluation" stackId="a" fill="#16A36A" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
      <Card className="p-4"><H title={`Held-out MAE by method — ${c.city}`} sub="Selected method highlighted" /><div className="h-56"><ResponsiveContainer><BarChart data={methodData} layout="vertical" margin={{ left: 10 }}><CartesianGrid stroke="#E5EAF1" horizontal={false} /><XAxis type="number" tick={{ fontSize: 11 }} /><YAxis type="category" dataKey="name" width={118} tick={{ fontSize: 10 }} /><Tooltip />
        <Bar dataKey="mae" radius={[0, 4, 4, 0]}>{methodData.map(m => <Cell key={m.name} fill={m.selected ? '#16A36A' : '#CBD5E1'} />)}</Bar></BarChart></ResponsiveContainer></div></Card></div>

    <div><H title="Data validation results" sub={`${dq.valid_rows} of ${dq.total_rows} supplied rows are valid; ${dq.excluded_total} excluded (missing ${dq.missing_values_total}, malformed ${dq.malformed_total}, duplicates ${dq.duplicates_total}). Executed robustness checks:`} />
      <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted"><tr><th className="p-3">Group</th><th className="p-3">Check</th><th className="p-3">Input</th><th className="p-3">Actual outcome</th><th className="p-3">Result</th></tr></thead>
        <tbody>{e.robustness_checks.map((k, i) => <tr key={i} className="border-t border-line align-top"><td className="p-3 text-muted whitespace-nowrap">{k.group}</td><td className="p-3 font-medium">{k.name}</td><td className="p-3 font-mono text-xs break-words">{k.input}</td><td className="p-3 text-xs break-words">{k.outcome}</td><td className="p-3"><Pill s={k.passed ? 'passed' : 'failed'} /></td></tr>)}</tbody></table></Card></div>

    <div><H title="Forecast results — six demonstration cases" sub={e.demonstrations.note} />
      <Card className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted"><tr><th className="p-3">City</th><th className="p-3">Horizon</th><th className="p-3">Method</th><th className="p-3">Day 1</th><th className="p-3">Day 2</th><th className="p-3">Day 3</th><th className="p-3">Held-out MAE</th></tr></thead>
        <tbody>{e.demonstrations.cases.map(k => <tr key={k.case} className="border-t border-line align-top"><td className="p-3 font-medium">{k.city}</td><td className="p-3">{k.horizon_days} day{k.horizon_days > 1 ? 's' : ''}</td><td className="p-3 text-xs">{k.method}{k.period_days ? ` (${k.period_days}-day cycle)` : ''}</td>
          {[0, 1, 2].map(i => <td key={i} className="p-3 whitespace-nowrap">{k.predictions[i] ? <>{k.predictions[i].predicted_temp_c.toFixed(1)} °C<div className="text-[11px] text-muted">{k.predictions[i].date}</div></> : <span className="text-muted">—</span>}</td>)}
          <td className="p-3 text-xs">{k.heldout_mae_by_forecast_day.map(m => f3(m.mae)).join(' / ')}</td></tr>)}</tbody></table></Card>
      <p className="text-xs text-muted mt-2">{e.disclaimer} Generated {e.demonstrations.cases[0].generated_on}; forecasts start after the last observation ({e.demonstrations.cases[0].last_observation_date}).</p></div>

    <div><H title="MAE calculation on the reserved evaluation data" sub={e.evaluation.formula} right={<div className="flex gap-2 flex-wrap">
      <select aria-label="City" className="btn" value={c.city} onChange={x => setCity(x.target.value)}>{cities.map(x => <option key={x.city}>{x.city}</option>)}</select>
      <select aria-label="Horizon" className="btn" value={hz} onChange={x => setHz(Number(x.target.value))}>{[1, 2, 3].map(h => <option key={h} value={h}>{h}-day ahead</option>)}</select></div>} />
      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="p-4"><div className="h-64"><ResponsiveContainer><LineChart data={lineData}><CartesianGrid stroke="#E5EAF1" vertical={false} /><XAxis dataKey="date" tick={{ fontSize: 11 }} /><YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} unit="°" /><Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="Actual" stroke="#64748B" strokeWidth={2} dot={{ r: 3 }} /><Line type="monotone" dataKey="Predicted" stroke="#4F6BED" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div></Card>
        <Card className="overflow-auto max-h-[22rem]"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-muted sticky top-0"><tr><th className="p-2.5">Evaluation date</th><th className="p-2.5 text-right">Actual °C</th><th className="p-2.5 text-right">Predicted °C</th><th className="p-2.5 text-right">|Error| °C</th></tr></thead>
          <tbody>{rows.map(x => <tr key={x.date} className="border-t border-line"><td className="p-2.5">{x.date}</td><td className="p-2.5 text-right">{x.actual.toFixed(1)}</td><td className="p-2.5 text-right">{x.predicted.toFixed(1)}</td><td className="p-2.5 text-right">{x.abs_error.toFixed(1)}</td></tr>)}</tbody></table></Card></div>
      <Card className="p-4 mt-3 text-sm"><strong>{c.city}, {hz}-day ahead: MAE = Σ|error| / n = {sum.toFixed(1)} / {rows.length} = {(sum / rows.length).toFixed(3)} °C.</strong> <span className="text-muted">{c.explanation}</span>
        <div className="mt-2 text-xs text-muted">Stricter check (model sees only the training set): MAE {f3(c.metrics.train_only_fixed_origin.mae)} °C over {c.metrics.train_only_fixed_origin.n} days. Independent recomputation from the CSV: {e.independent_check.cities.map(k => `${k.city} ${k.mae_independent.toFixed(6)} vs ${k.mae_reported.toFixed(6)} ${k.match ? '✓' : '✗'}`).join('; ')}.</div></Card></div>

    <div className="grid lg:grid-cols-2 gap-4">
      <div><H title="Test results" /><Card className="overflow-hidden"><table className="w-full text-sm"><tbody>{e.tests.suites.map(s => <tr key={s.id} className="border-b border-line last:border-0"><td className="p-3">{s.title}</td><td className="p-3 text-right whitespace-nowrap"><span className="text-ok font-medium">{s.passed} passed</span>{s.failed > 0 && <span className="text-err font-medium ml-2">{s.failed} failed</span>}</td></tr>)}</tbody></table></Card></div>
      <div><H title="Known limitations" /><Card className="p-4"><ul className="list-disc ml-4 space-y-1.5 text-sm">{e.known_limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></Card></div></div>
  </div>
}
