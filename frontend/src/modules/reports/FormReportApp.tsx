import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { getCatalog, getIndividualFormReport, listCatalog } from './catalogApi';
import type { FormReport, IndicatorResult } from './catalogApi';

function num(value: number) { return value.toLocaleString('es-CO', { maximumFractionDigits: 2 }); }

export function FormReportApp() {
  const { t } = useI18n();
  const templateId = window.location.pathname.split('/')[3] ?? '';
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [report, setReport] = useState<FormReport | null>(null);
  const [linked, setLinked] = useState<Array<IndicatorResult & { reportName: string }>>([]);
  const [message, setMessage] = useState(t('reports.form.loading'));

  useEffect(() => {
    if (!templateId) return;
    getIndividualFormReport(templateId).then((data) => { setReport(data); setMessage(''); }).catch((error: Error) => setMessage(error.message));
    listCatalog(projectId).then(async (catalog) => {
      const related = catalog.filter((item) => item.indicators.some((indicator) => indicator.source_mode === 'automatic' && indicator.template_id === templateId));
      const results = await Promise.all(related.map((item) => getCatalog(item.id)));
      setLinked(results.flatMap((item, index) => item.indicators.filter((_, position) => related[index].indicators[position]?.template_id === templateId).map((indicator) => ({ ...indicator, reportName: item.name }))));
    }).catch(() => setLinked([]));
  }, [projectId, templateId]);

  return <AppShell title={t('reports.form.loading').replace('…', '')}><main className="reports-shell reports-studio form-report-page"><a href={`/builder/form/${templateId}`}>{t('reports.form.backToForm')}</a>{message && <p role="status">{message}</p>}{report && <>
    <header className="form-report-head"><div><small>{t('reports.form.individualReport', { status: report.status })}</small><h1>{report.template_name}</h1><p>{report.description || t('reports.form.defaultDescription')}</p></div><a href={`/records/${templateId}`}>{t('reports.form.viewResponseTable')}</a></header>
    <section className="form-report-kpis"><article><strong>{num(report.records_total)}</strong><span>{t('reports.form.responsesReceived')}</span></article><article><strong>{report.questions.length}</strong><span>{t('reports.form.questions')}</span></article><article><strong>{report.last_record_at ? new Date(report.last_record_at).toLocaleDateString('es-CO') : '—'}</strong><span>{t('reports.form.lastSubmission')}</span></article></section>
    {linked.length > 0 && <section className="form-report-section"><h2>{t('reports.form.linkedIndicators')}</h2><div className="form-report-linked">{linked.map((item, index) => <article key={`${item.reportName}-${index}`}><small>{item.reportName}</small><h3>{item.title}</h3><p>{num(item.actual)} / {num(item.goal)} {item.unit}</p><div className="catalog-track"><span style={{ width: `${Math.min(item.progress_percent ?? 0, 100)}%` }} /></div><strong>{item.progress_percent === null ? t('reports.form.noGoal') : `${num(item.progress_percent)}%`}</strong></article>)}</div></section>}
    <section className="form-report-section"><h2>{t('reports.form.submissionsByMonth')}</h2>{report.months.length ? <div className="form-report-months">{report.months.map((month) => <div key={month.month}><span>{month.month}</span><div><i style={{ width: `${Math.max(2, month.count / Math.max(...report.months.map((item) => item.count), 1) * 100)}%` }} /></div><strong>{month.count}</strong></div>)}</div> : <p>{t('reports.form.noSubmissionsYet')}</p>}</section>
    <section className="form-report-section"><h2>{t('reports.form.questionsAndAnswers')}</h2><div className="form-report-questions">{report.questions.map((question) => <article key={question.name}><small>{question.name} · {question.field_type}</small><h3>{question.label}</h3><p>{t('reports.form.answeredMissing', { answered: num(question.answered), missing: num(question.missing) })}</p>{question.choices.length > 0 && <div className="form-report-choices">{question.choices.map((choice) => <div key={choice.label}><span>{choice.label}</span><div><i style={{ width: `${Math.max(2, choice.count / Math.max(question.answered, 1) * 100)}%` }} /></div><strong>{choice.count}</strong></div>)}</div>}{question.numeric_average !== null && <p>{t('reports.form.averageMinMax', { avg: num(question.numeric_average), min: num(question.numeric_min ?? 0), max: num(question.numeric_max ?? 0) })}</p>}</article>)}</div></section>
  </>}</main></AppShell>;
}
