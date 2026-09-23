import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { fetchDashboard } from '../dashboard/api';
import type { DashboardSummary } from '../dashboard/api';
import { downloadReportSummary, fetchReportBoard, saveReportBoard } from './api';
import type { ReportTemplateMetric } from './api';
import { ReportBoardEditor } from './ReportBoardEditor';
import { ReportChart } from './ReportChart';
import type { ReportBoard, ReportWidget, ResolvedWidget } from './types';

export function ReportsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [board, setBoard] = useState<ReportBoard | null>(null);
  const [message, setMessage] = useState('Cargando reportes...');
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
    const rows = [['Formulario', 'Estado', 'Registros', 'Último registro'], ...board.summary.templates.map((item) => [item.template_name, item.template_status, String(item.records_total), item.last_record_at ?? ''])];
    const content = '\uFEFF' + rows.map((row) => row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(',')).join('\r\n');
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
      setMessage(error instanceof Error ? error.message : 'No fue posible exportar el reporte.');
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
      setMessage(error instanceof Error ? error.message : 'No fue posible guardar el tablero.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell title="Reportes">
      <main className="reports-shell reports-studio">
        <header className="reports-header">
          <div>
            <h2><span className="reports-logo-mark">▦</span> InfoMatt360 <small>· Módulo de reportes</small></h2>
            <p>Indicadores y resultados del proyecto</p>
          </div>
          <div className="reports-actions">
            <a href="/reports/indicators">Configuración de indicadores</a>
            <a href="/reports/catalog">Mis reportes e indicadores</a>
            {canEdit && !editing ? <button className="secondary" onClick={startEditing}>⚙ Personalizar y gestionar</button> : null}
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
            <nav className="reports-tabs" aria-label="Secciones de reportes">
              {([['operativo', '▤ Operativo'], ['indicadores', '▥ Indicadores'], ['analitico', '⌁ Analítico'], ['donantes', '▣ Donantes'], ['geografico', '⌖ Geográfico']] as const).map(([key, label]) => <button type="button" key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>)}
            </nav>
            {tab === 'operativo' && <>
              <section className="reports-overview" aria-label="Resumen operativo">
                <article><strong>{board.summary.records_total.toLocaleString()}</strong><span>Formularios enviados</span><small>Registros del proyecto</small></article>
                <article><strong>{(board.summary.records_by_status.pending ?? board.summary.records_by_status.submitted ?? 0).toLocaleString()}</strong><span>Pendientes de revisión</span><small>Según estado del registro</small></article>
                <article><strong>{board.summary.records_total ? `${Math.round(((board.summary.records_by_status.approved ?? 0) / board.summary.records_total) * 100)}%` : '0%'}</strong><span>Aprobados</span><small>Del total de registros</small></article>
                <article><strong>{board.summary.templates.length.toLocaleString()}</strong><span>Formularios</span><small>En este proyecto</small></article>
              </section>
              <div className="reports-operational-grid"><section className="reports-board">{board.widgets.map((widget, index) => <ReportWidgetView key={index} widget={widget} resolved={board.resolved[index]} summary={board.summary.templates} />)}</section><aside className="reports-recent"><h3>☷ Últimos envíos</h3>{activity?.recent_records.length ? <table><thead><tr><th>Formulario</th><th>Estado</th></tr></thead><tbody>{activity.recent_records.slice(0, 6).map((record) => <tr key={record.id}><td><a href={`/records/${record.template_id}`}>{record.template_name}</a><small>{new Date(record.created_at).toLocaleString()}</small></td><td><span>{record.status}</span></td></tr>)}</tbody></table> : <p>Aún no hay envíos recientes.</p>}</aside></div>
            </>}
            {(tab === 'indicadores' || tab === 'analitico') && <section className="reports-board">{board.widgets.map((widget, index) => ({ widget, resolved: board.resolved[index], index })).filter(({ widget }) => tab === 'indicadores' ? widget.type === 'kpi' : widget.type === 'chart' || widget.type === 'table').map(({ widget, resolved, index }) => <ReportWidgetView key={index} widget={widget} resolved={resolved} summary={board.summary.templates} />)}{!board.widgets.some((widget) => tab === 'indicadores' ? widget.type === 'kpi' : widget.type === 'chart' || widget.type === 'table') && <p>Agrega bloques desde “Personalizar y gestionar”.</p>}</section>}
            {tab === 'donantes' && <section className="reports-empty"><h3>Donantes</h3><p>Personaliza este tablero con los indicadores de tus formularios de donantes.</p>{canEdit && <button type="button" onClick={startEditing}>Agregar indicador</button>}</section>}
            {tab === 'geografico' && <section className="reports-empty"><h3>Vista geográfica</h3><p>Consulta los registros con ubicación en el mapa del proyecto.</p><a href="/maps">Abrir mapas</a></section>}
            <footer className="reports-export"><button type="button" onClick={() => void exportXlsx()}>▤ Excel</button><button type="button" onClick={exportCsv}>▤ CSV</button><button type="button" onClick={() => window.print()}>▤ PDF / Imprimir</button></footer>
          </>
        ) : null}
      </main>
    </AppShell>
  );
}

function ReportWidgetView({ widget, resolved, summary }: { widget: ReportWidget; resolved: ResolvedWidget; summary: ReportTemplateMetric[] }) {
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
                <th>Formulario</th>
                <th>Estado formulario</th>
                <th>Registros</th>
                <th>Distribución</th>
                <th>Último registro</th>
                <th>Acción</th>
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
  return (
    <tr>
      <td><strong>{template.template_name}</strong><small>{template.percent_of_total.toLocaleString()}% del total</small></td>
      <td>{template.template_status}</td>
      <td>{template.records_total.toLocaleString()}</td>
      <td>{statusSummary(template.records_by_status)}</td>
      <td>{template.last_record_at ? new Date(template.last_record_at).toLocaleString() : 'Sin registros'}</td>
      <td><a href={`/records/${template.template_id}`}>Abrir</a></td>
    </tr>
  );
}

function statusSummary(values: Record<string, number>): string {
  const entries = Object.entries(values);
  if (!entries.length) return 'Sin registros';
  return entries.map(([status, count]) => `${status}: ${count}`).join(' · ');
}
