import { useI18n } from '../../i18n';
import type { CatalogResult } from './catalogApi';

const fmt = (value: number) => value.toLocaleString('es-CO', { maximumFractionDigits: 1 });
const pct = (value: number) => `${fmt(value)}%`;

export function CommitteeReportView({ report, publicView = false }: { report: CatalogResult; publicView?: boolean }) {
  const { t } = useI18n();
  const agreementStatus: Record<string, string> = { new: t('reports.committee.statusNew'), pending: t('reports.committee.statusPending'), in_progress: t('reports.committee.statusInProgress'), done: t('reports.committee.statusDone') };
  const details = report.committee;
  const activityAverage = details.activities.length ? details.activities.reduce((sum, row) => sum + row.progress, 0) / details.activities.length : null;
  const planned = details.budget.reduce((sum, row) => sum + row.planned, 0);
  const spent = details.budget.reduce((sum, row) => sum + row.spent, 0);
  const budgetPercent = planned ? spent / planned * 100 : null;
  const goalAverage = report.indicators.filter((item) => item.progress_percent !== null);
  const indicatorAverage = goalAverage.length ? goalAverage.reduce((sum, item) => sum + (item.progress_percent ?? 0), 0) / goalAverage.length : null;

  function downloadCsv() {
    const rows: string[][] = [[t('reports.committee.csvSection'), t('reports.committee.csvElement'), t('reports.committee.csvGoalBudget'), t('reports.committee.csvActualSpent'), t('reports.committee.csvStatusOwner')]];
    details.activities.forEach((row) => rows.push([t('reports.committee.csvActivities'), row.title, '100', String(row.progress), '']));
    report.indicators.forEach((row) => rows.push([t('reports.committee.csvIndicators'), row.title, String(row.goal), String(row.actual), `${row.progress_percent ?? ''}%`]));
    details.alerts.forEach((row) => rows.push([t('reports.committee.csvAlerts'), row.title, row.priority, row.description, row.owner]));
    details.budget.forEach((row) => rows.push([t('reports.committee.csvBudget'), row.component, String(row.planned), String(row.spent), '']));
    details.previous_agreements.forEach((row) => rows.push([t('reports.committee.csvPrevAgreements'), row.title, row.due_date, agreementStatus[row.status], row.owner]));
    details.new_agreements.forEach((row) => rows.push([t('reports.committee.csvNewAgreements'), row.title, row.due_date, agreementStatus[row.status], row.owner]));
    const csv = '﻿' + rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `comite-${report.name.replace(/[^a-z0-9]+/gi, '-')}.csv`; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <article className="committee-report">
    <header className="committee-report-header"><div><small>{publicView ? t('reports.committee.sharedReadOnly') : t('reports.committee.committeeReport')}</small><h1>{report.name}</h1>{report.description && <p>{report.description}</p>}<div className="committee-meta">{details.meeting_at && <span>◷ {new Date(details.meeting_at).toLocaleString('es-CO')}</span>}{details.location && <span>⌖ {details.location}</span>}{details.audience && <span>♧ {details.audience}</span>}</div></div></header>
    <div className="committee-kpis"><div><strong>{activityAverage === null ? '—' : pct(activityAverage)}</strong><span>{t('reports.committee.activityProgress')}</span></div><div><strong>{indicatorAverage === null ? '—' : pct(indicatorAverage)}</strong><span>{t('reports.committee.indicatorProgress')}</span></div><div><strong>{details.alerts.length}</strong><span>{t('reports.committee.activeAlerts')}</span></div><div><strong>{budgetPercent === null ? '—' : pct(budgetPercent)}</strong><span>{t('reports.committee.budgetSpent')}</span></div></div>
    <section className="committee-panel"><h2><b>1</b> {t('reports.committee.activitiesVsSchedule')} <small>{t('reports.committee.activitiesCount', { count: details.activities.length })}</small></h2>{details.activities.length ? <div className="committee-activities">{details.activities.map((row, index) => <div key={index}><strong>{index + 1}. {row.title}</strong><div className="committee-track"><i style={{ width: `${row.progress}%`, background: row.progress >= 100 ? '#16a67b' : row.progress >= 70 ? '#3689dc' : row.progress >= 40 ? '#e3a525' : '#e65d60' }} /></div><span>{pct(row.progress)}</span></div>)}</div> : <p className="committee-empty">{t('reports.committee.addActivitiesHint')}</p>}</section>
    <section className="committee-panel"><h2><b>2</b> {t('reports.committee.indicatorsAndGoals')} <small>{t('reports.committee.indicatorsCount', { count: report.indicators.length })}</small></h2><div className="committee-indicators">{report.indicators.map((row, index) => <div key={index}><strong>{row.title}</strong><div className="committee-track"><i style={{ width: `${Math.min(row.progress_percent ?? 0, 100)}%`, background: (row.progress_percent ?? 0) >= 100 ? '#16a67b' : (row.progress_percent ?? 0) >= 70 ? '#3689dc' : '#e3a525' }} /></div><span>{fmt(row.actual)} / {fmt(row.goal)} {row.unit} · {row.progress_percent === null ? t('reports.committee.noGoal') : pct(row.progress_percent)}</span>{row.municipalities.length > 0 && <small>{row.municipalities.map((place) => `${place.municipality}: ${fmt(place.value)}`).join(' · ')}</small>}</div>)}</div></section>
    <section className="committee-panel"><h2><b>3</b> {t('reports.committee.alertsAndRisks')} <small>{t('reports.committee.activeCount', { count: details.alerts.length })}</small></h2>{details.alerts.length ? <div className="committee-alerts">{details.alerts.map((row, index) => <div key={index}><span className={`committee-priority ${row.priority}`}>{row.priority === 'high' ? t('reports.committee.priorityHigh') : row.priority === 'medium' ? t('reports.committee.priorityMedium') : t('reports.committee.priorityLow')}</span><div><strong>{row.title}</strong>{row.description && <p>{row.description}</p>}<small>{row.owner && t('reports.committee.responsiblePrefix', { owner: row.owner })}{row.next_action && ` · ${t('reports.committee.actionPrefix', { action: row.next_action })}`}</small></div></div>)}</div> : <p className="committee-empty">{t('reports.committee.noAlertsRegistered')}</p>}</section>
    <section className="committee-panel"><h2><b>4</b> {t('reports.committee.budgetExecuted')} <small>{budgetPercent === null ? t('reports.committee.noBudget') : pct(budgetPercent)}</small></h2>{details.budget.length ? <div className="committee-table-wrap"><table><thead><tr><th>{t('reports.committee.componentLabel')}</th><th>{t('reports.committee.budgetLabel')}</th><th>{t('reports.committee.spentLabel')}</th><th>{t('reports.committee.budgetPercentHeader')}</th></tr></thead><tbody>{details.budget.map((row, index) => <tr key={index}><td>{row.component}</td><td>{fmt(row.planned)}</td><td>{fmt(row.spent)}</td><td>{row.planned ? pct(row.spent / row.planned * 100) : '—'}</td></tr>)}<tr><th>{t('reports.committee.totalLabel')}</th><th>{fmt(planned)}</th><th>{fmt(spent)}</th><th>{budgetPercent === null ? '—' : pct(budgetPercent)}</th></tr></tbody></table></div> : <p className="committee-empty">{t('reports.committee.noBudgetComponents')}</p>}</section>
    <section className="committee-panel"><h2><b>5</b> {t('reports.committee.previousAgreementsTitle')} <small>{t('reports.committee.pendingCount', { count: details.previous_agreements.filter((row) => row.status !== 'done').length })}</small></h2><AgreementTable rows={details.previous_agreements} agreementStatus={agreementStatus} t={t} /></section>
    <section className="committee-panel"><h2><b>6</b> {t('reports.committee.newAgreementsTitle')} <small>{t('reports.committee.agreementsCount', { count: details.new_agreements.length })}</small></h2><AgreementTable rows={details.new_agreements} agreementStatus={agreementStatus} t={t} /></section>
    <footer className="committee-report-actions"><button type="button" onClick={downloadCsv}>{t('reports.committee.downloadCsv')}</button><button type="button" onClick={() => window.print()}>{t('reports.committee.printPdf')}</button></footer>
  </article>;
}

function AgreementTable({ rows, agreementStatus, t }: { rows: CatalogResult['committee']['new_agreements']; agreementStatus: Record<string, string>; t: (key: string) => string }) {
  return rows.length ? <div className="committee-table-wrap"><table><thead><tr><th>{t('reports.committee.agreementHeader')}</th><th>{t('reports.committee.responsibleLabel')}</th><th>{t('reports.committee.dueDateLabel')}</th><th>{t('reports.committee.statusLabel')}</th></tr></thead><tbody>{rows.map((row, index) => <tr key={index}><td>{row.title}</td><td>{row.owner || '—'}</td><td>{row.due_date || '—'}</td><td>{agreementStatus[row.status]}</td></tr>)}</tbody></table></div> : <p className="committee-empty">{t('reports.committee.noAgreements')}</p>;
}
