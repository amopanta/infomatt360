import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { downloadReportSummary, fetchReportSummary } from './api';
import type { ReportProjectSummary, ReportTemplateMetric } from './api';

export function ReportsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [summary, setSummary] = useState<ReportProjectSummary | null>(null);
  const [message, setMessage] = useState('Cargando reportes...');

  useEffect(() => {
    fetchReportSummary(projectId)
      .then((data) => {
        setSummary(data);
        setMessage('');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  const activeTemplates = useMemo(() => summary?.templates.filter((template) => template.records_total > 0).length ?? 0, [summary]);

  async function exportXlsx() {
    try {
      await downloadReportSummary(projectId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible exportar el reporte.');
    }
  }

  return (
    <AppShell title="Reportes">
      <main className="reports-shell">
        {message ? <p role="status">{message}</p> : null}
        {summary ? (
          <>
            <section className="reports-cards">
              <ReportCard label="Registros" value={summary.records_total} detail={statusSummary(summary.records_by_status)} />
              <ReportCard label="Formularios con datos" value={activeTemplates} detail={`${summary.templates.length} formularios del proyecto`} />
              <ReportCard label="Generado" value={new Date(summary.generated_at).toLocaleDateString()} detail={new Date(summary.generated_at).toLocaleTimeString()} />
            </section>
            <section className="reports-panel">
              <header>
                <div>
                  <h2>Resumen por formulario</h2>
                  <p>Conteo operativo de registros capturados por estado.</p>
                </div>
                <div className="reports-actions">
                  <button onClick={() => void exportXlsx()}>Exportar XLSX</button>
                  <a href="/records">Ver registros</a>
                </div>
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
                    {summary.templates.map((template) => <ReportRow key={template.template_id} template={template} />)}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : null}
      </main>
    </AppShell>
  );
}

function ReportCard({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <article className="reports-card"><span>{label}</span><strong>{typeof value === 'number' ? value.toLocaleString() : value}</strong><small>{detail}</small></article>;
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
