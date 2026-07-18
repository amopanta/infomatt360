import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
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
  const canEdit = hasAnyCurrentProjectPermission(['builder.write']);

  useEffect(() => {
    fetchReportBoard(projectId)
      .then((data) => {
        setBoard(data);
        setMessage('');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

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
      <main className="reports-shell">
        <header className="reports-header">
          <div>
            <h2>Tablero de reportes</h2>
            <p>Personaliza qué se muestra: KPIs, gráficos y tablas sobre tus formularios.</p>
          </div>
          <div className="reports-actions">
            <button onClick={() => void exportXlsx()}>Exportar XLSX</button>
            <a href="/records">Ver registros</a>
            {canEdit && !editing ? <button className="secondary" onClick={startEditing}>Personalizar tablero</button> : null}
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
          <section className="reports-board">
            {board.widgets.map((widget, index) => (
              <ReportWidgetView key={index} widget={widget} resolved={board.resolved[index]} summary={board.summary.templates} />
            ))}
          </section>
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
