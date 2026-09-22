import type { CatalogResult } from './catalogApi';

const fmt = (value: number) => value.toLocaleString('es-CO', { maximumFractionDigits: 1 });
const pct = (value: number) => `${fmt(value)}%`;
const agreementStatus: Record<string, string> = { new: 'Nuevo', pending: 'Pendiente', in_progress: 'En proceso', done: 'Cumplido' };

export function CommitteeReportView({ report, publicView = false }: { report: CatalogResult; publicView?: boolean }) {
  const details = report.committee;
  const activityAverage = details.activities.length ? details.activities.reduce((sum, row) => sum + row.progress, 0) / details.activities.length : null;
  const planned = details.budget.reduce((sum, row) => sum + row.planned, 0);
  const spent = details.budget.reduce((sum, row) => sum + row.spent, 0);
  const budgetPercent = planned ? spent / planned * 100 : null;
  const goalAverage = report.indicators.filter((item) => item.progress_percent !== null);
  const indicatorAverage = goalAverage.length ? goalAverage.reduce((sum, item) => sum + (item.progress_percent ?? 0), 0) / goalAverage.length : null;

  function downloadCsv() {
    const rows: string[][] = [['Sección', 'Elemento', 'Meta/Presupuesto', 'Actual/Ejecutado', 'Estado/Responsable']];
    details.activities.forEach((row) => rows.push(['Actividades', row.title, '100', String(row.progress), '']));
    report.indicators.forEach((row) => rows.push(['Indicadores', row.title, String(row.goal), String(row.actual), `${row.progress_percent ?? ''}%`]));
    details.alerts.forEach((row) => rows.push(['Alertas', row.title, row.priority, row.description, row.owner]));
    details.budget.forEach((row) => rows.push(['Presupuesto', row.component, String(row.planned), String(row.spent), '']));
    details.previous_agreements.forEach((row) => rows.push(['Acuerdos anteriores', row.title, row.due_date, agreementStatus[row.status], row.owner]));
    details.new_agreements.forEach((row) => rows.push(['Nuevos compromisos', row.title, row.due_date, agreementStatus[row.status], row.owner]));
    const csv = '\uFEFF' + rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `comite-${report.name.replace(/[^a-z0-9]+/gi, '-')}.csv`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <article className="committee-report">
    <header className="committee-report-header"><div><small>{publicView ? 'Informe compartido · solo lectura' : 'Informe de seguimiento · comité'}</small><h1>{report.name}</h1>{report.description && <p>{report.description}</p>}<div className="committee-meta">{details.meeting_at && <span>◷ {new Date(details.meeting_at).toLocaleString('es-CO')}</span>}{details.location && <span>⌖ {details.location}</span>}{details.audience && <span>♧ {details.audience}</span>}</div></div></header>
    <div className="committee-kpis"><div><strong>{activityAverage === null ? '—' : pct(activityAverage)}</strong><span>Avance de actividades</span></div><div><strong>{indicatorAverage === null ? '—' : pct(indicatorAverage)}</strong><span>Avance de indicadores</span></div><div><strong>{details.alerts.length}</strong><span>Alertas activas</span></div><div><strong>{budgetPercent === null ? '—' : pct(budgetPercent)}</strong><span>Presupuesto ejecutado</span></div></div>
    <section className="committee-panel"><h2><b>1</b> Avance de actividades vs. cronograma <small>{details.activities.length} actividades</small></h2>{details.activities.length ? <div className="committee-activities">{details.activities.map((row, index) => <div key={index}><strong>{index + 1}. {row.title}</strong><div className="committee-track"><i style={{ width: `${row.progress}%`, background: row.progress >= 100 ? '#16a67b' : row.progress >= 70 ? '#3689dc' : row.progress >= 40 ? '#e3a525' : '#e65d60' }} /></div><span>{pct(row.progress)}</span></div>)}</div> : <p className="committee-empty">Agrega actividades para mostrar el cronograma.</p>}</section>
    <section className="committee-panel"><h2><b>2</b> Indicadores y metas <small>{report.indicators.length} indicadores</small></h2><div className="committee-indicators">{report.indicators.map((row, index) => <div key={index}><strong>{row.title}</strong><div className="committee-track"><i style={{ width: `${Math.min(row.progress_percent ?? 0, 100)}%`, background: (row.progress_percent ?? 0) >= 100 ? '#16a67b' : (row.progress_percent ?? 0) >= 70 ? '#3689dc' : '#e3a525' }} /></div><span>{fmt(row.actual)} / {fmt(row.goal)} {row.unit} · {row.progress_percent === null ? 'Sin meta' : pct(row.progress_percent)}</span>{row.municipalities.length > 0 && <small>{row.municipalities.map((place) => `${place.municipality}: ${fmt(place.value)}`).join(' · ')}</small>}</div>)}</div></section>
    <section className="committee-panel"><h2><b>3</b> Alertas y riesgos <small>{details.alerts.length} activas</small></h2>{details.alerts.length ? <div className="committee-alerts">{details.alerts.map((row, index) => <div key={index}><span className={`committee-priority ${row.priority}`}>{row.priority === 'high' ? 'Alta' : row.priority === 'medium' ? 'Media' : 'Baja'}</span><div><strong>{row.title}</strong>{row.description && <p>{row.description}</p>}<small>{row.owner && `Responsable: ${row.owner}`}{row.next_action && ` · Acción: ${row.next_action}`}</small></div></div>)}</div> : <p className="committee-empty">No hay alertas registradas.</p>}</section>
    <section className="committee-panel"><h2><b>4</b> Presupuesto ejecutado <small>{budgetPercent === null ? 'Sin presupuesto' : pct(budgetPercent)}</small></h2>{details.budget.length ? <div className="committee-table-wrap"><table><thead><tr><th>Componente</th><th>Presupuesto</th><th>Ejecutado</th><th>%</th></tr></thead><tbody>{details.budget.map((row, index) => <tr key={index}><td>{row.component}</td><td>{fmt(row.planned)}</td><td>{fmt(row.spent)}</td><td>{row.planned ? pct(row.spent / row.planned * 100) : '—'}</td></tr>)}<tr><th>Total</th><th>{fmt(planned)}</th><th>{fmt(spent)}</th><th>{budgetPercent === null ? '—' : pct(budgetPercent)}</th></tr></tbody></table></div> : <p className="committee-empty">No hay componentes presupuestales.</p>}</section>
    <section className="committee-panel"><h2><b>5</b> Acuerdos anteriores <small>{details.previous_agreements.filter((row) => row.status !== 'done').length} pendientes</small></h2><AgreementTable rows={details.previous_agreements} /></section>
    <section className="committee-panel"><h2><b>6</b> Nuevos acuerdos y compromisos <small>{details.new_agreements.length} acuerdos</small></h2><AgreementTable rows={details.new_agreements} /></section>
    <footer className="committee-report-actions"><button type="button" onClick={downloadCsv}>Descargar CSV</button><button type="button" onClick={() => window.print()}>PDF / Imprimir</button></footer>
  </article>;
}

function AgreementTable({ rows }: { rows: CatalogResult['committee']['new_agreements'] }) {
  return rows.length ? <div className="committee-table-wrap"><table><thead><tr><th>Acuerdo</th><th>Responsable</th><th>Fecha límite</th><th>Estado</th></tr></thead><tbody>{rows.map((row, index) => <tr key={index}><td>{row.title}</td><td>{row.owner || '—'}</td><td>{row.due_date || '—'}</td><td>{agreementStatus[row.status]}</td></tr>)}</tbody></table></div> : <p className="committee-empty">No hay acuerdos registrados.</p>;
}
