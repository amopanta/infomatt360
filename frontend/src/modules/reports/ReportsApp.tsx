import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { fetchDashboard } from '../dashboard/api';
import type { DashboardSummary } from '../dashboard/api';
import { downloadReportSummary, fetchReportBoard, saveReportBoard } from './api';
import type { ReportTemplateMetric } from './api';
import { ReportBoardEditor } from './ReportBoardEditor';
import { ReportChart } from './ReportChart';
import { SavedExportsPanel } from './SavedExportsPanel';
import type { ReportBoard, ReportWidget, ResolvedWidget } from './types';

export function ReportsApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [board, setBoard] = useState<ReportBoard | null>(null);
  const [message, setMessage] = useState(t('reports.loading'));
  const [editing, setEditing] = useState(false);
  const [draftWidgets, setDraftWidgets] = useState<ReportWidget[]>([]);
  const [saving, setSaving] = useState(false);
  const [activity, setActivity] = useState<DashboardSummary | null>(null);
  const [tab, setTab] = useState<'operativo' | 'indicadores' | 'analitico' | 'donantes' | 'geografico'>('operativo');
  const canEdit = hasAnyCurrentProjectPermission(['builder.write']);

  useEffect(() => {
    fetchReportBoard(projectId)
      .then((data) => {
        setBoard(data);
        setMessage('');
      })
      .catch((error: Error) => setMessage(error.message));
    fetchDashboard(projectId).then(setActivity).catch(() => setActivity(null));
  }, [projectId]);

  function exportCsv() {
    if (!board) return;
    const rows = [[t('reports.formHeader'), t('reports.formStatusHeader'), t('reports.recordsHeader'), t('reports.lastRecordHeader')], ...board.summary.templates.map((item) => [item.template_name, item.template_status, String(item.records_total), item.last_record_at ?? ''])];
    const content = '﻿' + rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `reporte-${projectId}.csv`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function exportXlsx() {
    try {
      await downloadReportSummary(projectId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('reports.exportError'));
    }
  }

  function startEditing() {
    if (!board) return;
    setDraftWidgets(board.widgets);
    setEditing(true);
  }

  async function saveBoard() {
    setSaving(true);
    setMessage('');
    try {
      const saved = await saveReportBoard(projectId, draftWidgets);
      setBoard(saved);
      setEditing(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('reports.saveBoardError'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell title={t('reports.title')}>
      <main className="reports-shell reports-studio">
        <header className="reports-header">
          <div>
            <h2><span className="reports-logo-mark">▦</span> InfoMatt360 <small>{t('reports.moduleSubtitle')}</small></h2>
            <p>{t('reports.description')}</p>
          </div>
          <div className="reports-actions">
            <a href="/reports/indicators">{t('reports.indicatorConfig')}</a>
            <a href="/reports/catalog">{t('reports.myReportsLink')}</a>
            {canEdit && !editing ? <button className="secondary" onClick={startEditing}>{t('reports.customize')}</button> : null}
          </div>
        </header>
        {message ? <p role="status">{message}</p> : null}

        {editing ? (
          <ReportBoardEditor
            projectId={projectId}
            widgets={draftWidgets}
            saving={saving}
            onChange={setDraftWidgets}
            onSave={() => void saveBoard()}
            onCancel={() => setEditing(false)}
          />
        ) : board ? (
          <>
            <nav className="reports-tabs" aria-label={t('reports.sectionsAria')}>
              {([['operativo', t('reports.tabOperational')], ['indicadores', t('reports.tabIndicators')], ['analitico', t('reports.tabAnalytic')], ['donantes', t('reports.tabDonors')], ['geografico', t('reports.tabGeographic')]] as const).map(([key, label]) => <button type="button" key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key as typeof tab)}>{label}</button>)}
            </nav>
            {tab === 'operativo' && <>
              <section className="reports-overview" aria-label={t('reports.operationalSummary')}>
                <article><strong>{board.summary.records_total.toLocaleString()}</strong><span>{t('reports.formsSent')}</span><small>{t('reports.projectRecords')}</small></article>
                <article><strong>{(board.summary.records_by_status.pending ?? board.summary.records_by_status.submitted ?? 0).toLocaleString()}</strong><span>{t('reports.pendingReview')}</span><small>{t('reports.byRecordStatus')}</small></article>
                <article><strong>{board.summary.records_total ? `${Math.round(((board.summary.records_by_status.approved ?? 0) / board.summary.records_total) * 100)}%` : '0%'}</strong><span>{t('reports.approved')}</span><small>{t('reports.ofTotalRecords')}</small></article>
                <article><strong>{board.summary.templates.length.toLocaleString()}</strong><span>{t('reports.forms')}</span><small>{t('reports.inThisProject')}</small></article>
              </section>
              <div className="reports-operational-grid"><section className="reports-board">{board.widgets.map((widget, index) => <ReportWidgetView key={index} widget={widget} resolved={board.resolved[index]} summary={board.summary.templates} />)}</section><aside className="reports-recent"><h3>{t('reports.latestSubmissions')}</h3>{activity?.recent_records.length ? <table><thead><tr><th>{t('reports.formHeader')}</th><th>{t('reports.formStatusHeader')}</th></tr></thead><tbody>{activity.recent_records.slice(0, 6).map((record) => <tr key={record.id}><td><a href={`/records/${record.template_id}`}>{record.template_name}</a><small>{new Date(record.created_at).toLocaleString()}</small></td><td><span>{record.status}</span></td></tr>)}</tbody></table> : <p>{t('reports.noRecentSubmissions')}</p>}</aside></div>
            </>}
            {(tab === 'indicadores' || tab === 'analitico') && <section className="reports-board">{board.widgets.map((widget, index) => ({ widget, resolved: board.resolved[index], index })).filter(({ widget }) => tab === 'indicadores' ? widget.type === 'kpi' : widget.type === 'chart' || widget.type === 'table').map(({ widget, resolved, index }) => <ReportWidgetView key={index} widget={widget} resolved={resolved} summary={board.summary.templates} />)}{!board.widgets.some((widget) => tab === 'indicadores' ? widget.type === 'kpi' : widget.type === 'chart' || widget.type === 'table') && <p>{t('reports.addBlocksHint')}</p>}</section>}
            {tab === 'donantes' && <section className="reports-empty"><h3>{t('reports.donors')}</h3><p>{t('reports.donorsDescription')}</p>{canEdit && <button type="button" onClick={startEditing}>{t('reports.addIndicator')}</button>}</section>}
            {tab === 'geografico' && <section className="reports-empty"><h3>{t('reports.geographicView')}</h3><p>{t('reports.geographicDescription')}</p><a href="/maps">{t('reports.openMaps')}</a></section>}
            <footer className="reports-export"><button type="button" onClick={() => void exportXlsx()}>{t('reports.exportExcel')}</button><button type="button" onClick={exportCsv}>{t('reports.exportCsv')}</button><button type="button" onClick={() => window.print()}>{t('reports.exportPdf')}</button></footer>
            <SavedExportsPanel projectId={projectId} templates={board.summary.templates} />
          </>
        ) : null}
      </main>
    </AppShell>
  );
}

function ReportWidgetView({ widget, resolved, summary }: { widget: ReportWidget; resolved: ResolvedWidget; summary: ReportTemplateMetric[] }) {
  const { t } = useI18n();

  if (widget.type === 'kpi' && resolved.kind === 'kpi') {
    return (
      <article className="reports-card">
        <span>{widget.title}</span>
        <strong>{resolved.display}</strong>
      </article>
    );
  }

  if (widget.type === 'chart' && resolved.kind === 'chart') {
    return (
      <article className="reports-panel reports-chart-panel">
        <header><h3>{widget.title}</h3></header>
        <ReportChart kind={widget.chart_kind} points={resolved.points} />
      </article>
    );
  }

  if (widget.type === 'table') {
    return (
      <section className="reports-panel">
        <header>
          <div><h2>{widget.title}</h2></div>
        </header>
        <div className="reports-table-wrap">
          <table className="reports-table">
            <thead>
              <tr>
                <th>{t('reports.formHeader')}</th>
                <th>{t('reports.formStatusHeader')}</th>
                <th>{t('reports.recordsHeader')}</th>
                <th>{t('reports.distributionHeader')}</th>
                <th>{t('reports.lastRecordHeader')}</th>
                <th>{t('reports.actionHeader')}</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((template) => <ReportRow key={template.template_id} template={template} />)}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  return null;
}

function ReportRow({ template }: { template: ReportTemplateMetric }) {
  const { t } = useI18n();
  return (
    <tr>
      <td><strong>{template.template_name}</strong><small>{t('reports.percentOfTotal', { percent: template.percent_of_total.toLocaleString() })}</small></td>
      <td>{template.template_status}</td>
      <td>{template.records_total.toLocaleString()}</td>
      <td>{statusSummary(template.records_by_status, t)}</td>
      <td>{template.last_record_at ? new Date(template.last_record_at).toLocaleString() : t('reports.noRecords')}</td>
      <td><a href={`/records/${template.template_id}`}>{t('reports.open')}</a></td>
    </tr>
  );
}

function statusSummary(values: Record<string, number>, t: (key: string) => string): string {
  const entries = Object.entries(values);
  if (!entries.length) return t('reports.noRecords');
  return entries.map(([status, count]) => `${status}: ${count}`).join(' · ');
}
