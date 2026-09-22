import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { getCatalog, getIndividualFormReport, listCatalog } from './catalogApi';
import type { FormReport, IndicatorResult } from './catalogApi';

function num(value: number) { return value.toLocaleString('es-CO', { maximumFractionDigits: 2 }); }

export function FormReportApp() {
  const templateId = window.location.pathname.split('/')[3] ?? '';
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [report, setReport] = useState<FormReport | null>(null);
  const [linked, setLinked] = useState<Array<IndicatorResult & { reportName: string }>>([]);
  const [message, setMessage] = useState('Cargando informe del formulario…');

  useEffect(() => {
    if (!templateId) return;
    getIndividualFormReport(templateId).then((data) => { setReport(data); setMessage(''); }).catch((error: Error) => setMessage(error.message));
    listCatalog(projectId).then(async (catalog) => {
      const related = catalog.filter((item) => item.indicators.some((indicator) => indicator.source_mode === 'automatic' && indicator.template_id === templateId));
      const results = await Promise.all(related.map((item) => getCatalog(item.id)));
      setLinked(results.flatMap((item, index) => item.indicators.filter((_, position) => related[index].indicators[position]?.template_id === templateId).map((indicator) => ({ ...indicator, reportName: item.name }))));
    }).catch(() => setLinked([]));
  }, [projectId, templateId]);

  return <AppShell title="Informe del formulario"><main className="reports-shell reports-studio form-report-page"><a href={`/builder/form/${templateId}`}>← Volver al formulario</a>{message && <p role="status">{message}</p>}{report && <>
    <header className="form-report-head"><div><small>Informe individual · {report.status}</small><h1>{report.template_name}</h1><p>{report.description || 'Resultados agregados de este formulario.'}</p></div><a href={`/records/${templateId}`}>Ver tabla de respuestas</a></header>
    <section className="form-report-kpis"><article><strong>{num(report.records_total)}</strong><span>Respuestas recibidas</span></article><article><strong>{report.questions.length}</strong><span>Preguntas</span></article><article><strong>{report.last_record_at ? new Date(report.last_record_at).toLocaleDateString('es-CO') : '—'}</strong><span>Último envío</span></article></section>
    {linked.length > 0 && <section className="form-report-section"><h2>Indicadores vinculados a este formulario</h2><div className="form-report-linked">{linked.map((item, index) => <article key={`${item.reportName}-${index}`}><small>{item.reportName}</small><h3>{item.title}</h3><p>{num(item.actual)} / {num(item.goal)} {item.unit}</p><div className="catalog-track"><span style={{ width: `${Math.min(item.progress_percent ?? 0, 100)}%` }} /></div><strong>{item.progress_percent === null ? 'Sin meta' : `${num(item.progress_percent)}%`}</strong></article>)}</div></section>}
    <section className="form-report-section"><h2>Envíos por mes</h2>{report.months.length ? <div className="form-report-months">{report.months.map((month) => <div key={month.month}><span>{month.month}</span><div><i style={{ width: `${Math.max(2, month.count / Math.max(...report.months.map((item) => item.count), 1) * 100)}%` }} /></div><strong>{month.count}</strong></div>)}</div> : <p>Aún no hay envíos.</p>}</section>
    <section className="form-report-section"><h2>Preguntas y respuestas</h2><div className="form-report-questions">{report.questions.map((question) => <article key={question.name}><small>{question.name} · {question.field_type}</small><h3>{question.label}</h3><p>{num(question.answered)} respondidas · {num(question.missing)} sin dato</p>{question.choices.length > 0 && <div className="form-report-choices">{question.choices.map((choice) => <div key={choice.label}><span>{choice.label}</span><div><i style={{ width: `${Math.max(2, choice.count / Math.max(question.answered, 1) * 100)}%` }} /></div><strong>{choice.count}</strong></div>)}</div>}{question.numeric_average !== null && <p>Promedio: {num(question.numeric_average)} · Mínimo: {num(question.numeric_min ?? 0)} · Máximo: {num(question.numeric_max ?? 0)}</p>}</article>)}</div></section>
  </>}</main></AppShell>;
}
