import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { approveExcelImport, confirmExcelImportMapping, fetchExcelImportJobs, uploadExcelImport } from './excelImportApi';
import type { ExcelImportJob } from './excelImportApi';

const TARGET_FIELDS: Record<string, string[]> = {
  participants: ['document_id', 'full_name', 'external_code', 'participant_type'],
  users: ['document_id', 'full_name', 'email', 'phone'],
};

function statusLabel(status: string) {
  const labels: Record<string, string> = { uploaded: 'Subido (pendiente de mapeo)', mapped: 'Mapeado (listo para aprobar)', completed: 'Completado', failed: 'Fallido' };
  return labels[status] ?? status;
}

function statusClass(status: string) {
  if (status === 'completed') return 'sent';
  if (status === 'failed') return 'failed';
  return 'skipped';
}

export function ExcelImportApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [entityType, setEntityType] = useState('participants');
  const [file, setFile] = useState<File | null>(null);
  const [currentJob, setCurrentJob] = useState<ExcelImportJob | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [jobs, setJobs] = useState<ExcelImportJob[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function loadJobs() {
    try {
      setJobs(await fetchExcelImportJobs(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar el historial de lotes.');
    }
  }

  useEffect(() => { void loadJobs(); }, [projectId]);

  async function submitUpload() {
    if (!file) return;
    setBusy(true);
    try {
      const job = await uploadExcelImport({ projectId, entityType, file });
      setCurrentJob(job);
      setColumnMapping(job.column_mapping ?? {});
      setMessage(`Archivo subido: ${job.total_rows} fila(s) detectada(s).`);
      await loadJobs();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible subir el archivo.');
    } finally {
      setBusy(false);
    }
  }

  async function submitMapping() {
    if (!currentJob) return;
    setBusy(true);
    try {
      const mapping = Object.fromEntries(Object.entries(columnMapping).filter(([, target]) => target));
      const job = await confirmExcelImportMapping(currentJob.id, mapping);
      setCurrentJob(job);
      setMessage('Mapeo confirmado. El lote esta listo para aprobar e importar.');
      await loadJobs();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible confirmar el mapeo.');
    } finally {
      setBusy(false);
    }
  }

  async function submitApprove() {
    if (!currentJob) return;
    setBusy(true);
    try {
      const job = await approveExcelImport(currentJob.id);
      setCurrentJob(job);
      setMessage(`Importacion completada: ${job.imported_rows} importada(s), ${job.failed_rows} fallida(s).`);
      await loadJobs();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible aprobar el lote.');
    } finally {
      setBusy(false);
    }
  }

  const targetFields = TARGET_FIELDS[entityType] ?? [];

  return (
    <AppShell title="Carga masiva desde Excel">
      <main className="audit-shell">
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>1. Subir archivo</h2>
              <p>Excel con columnas a mapear hacia participantes o usuarios (ver docs/76).</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <label>
              Tipo de entidad
              <select value={entityType} onChange={(event) => setEntityType(event.target.value)}>
                <option value="participants">Participantes</option>
                <option value="users">Usuarios</option>
              </select>
            </label>
            <label>
              Archivo (.xlsx)
              <input type="file" accept=".xlsx" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            </label>
            <button disabled={!file || busy} onClick={() => void submitUpload()}>Subir y previsualizar</button>
          </div>
        </section>

        {currentJob?.preview ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>2. Mapear columnas</h2>
                <p>{currentJob.source_filename} · {currentJob.total_rows} fila(s) · estado: <span className={`wa-status ${statusClass(currentJob.status)}`}>{statusLabel(currentJob.status)}</span></p>
              </div>
            </header>
            <div className="audit-table-wrap">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>Columna del Excel</th>
                    <th>Campo destino</th>
                    {currentJob.preview.sample_rows.slice(0, 2).map((_, index) => <th key={index}>Ejemplo {index + 1}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {currentJob.preview.headers.map((header) => (
                    <tr key={header}>
                      <td>{header}</td>
                      <td>
                        <select
                          value={columnMapping[header] ?? ''}
                          onChange={(event) => setColumnMapping((previous) => ({ ...previous, [header]: event.target.value }))}
                        >
                          <option value="">(ignorar)</option>
                          {targetFields.map((field) => <option key={field} value={field}>{field}</option>)}
                        </select>
                      </td>
                      {currentJob.preview!.sample_rows.slice(0, 2).map((row, index) => (
                        <td key={index}>{String(row[header] ?? '—')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {currentJob.status === 'uploaded' ? (
              <button className="primary" disabled={busy} onClick={() => void submitMapping()}>Confirmar mapeo</button>
            ) : null}
            {currentJob.status === 'mapped' ? (
              <button className="primary" disabled={busy} onClick={() => void submitApprove()}>Aprobar e importar</button>
            ) : null}
            {currentJob.status === 'completed' || currentJob.status === 'failed' ? (
              <article className="ds-map-card">
                <strong>Importadas: {currentJob.imported_rows} · Fallidas: {currentJob.failed_rows}</strong>
                {currentJob.error_report?.length ? (
                  <ul>
                    {currentJob.error_report.map((error, index) => <li key={index}>{JSON.stringify(error)}</li>)}
                  </ul>
                ) : null}
              </article>
            ) : null}
          </section>
        ) : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>Historial de lotes</h2>
            </div>
            <button onClick={() => void loadJobs()}>Actualizar</button>
          </header>
          {!jobs.length ? <p>Aun no hay lotes de carga masiva en este proyecto.</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Archivo</th>
                  <th>Tipo</th>
                  <th>Estado</th>
                  <th>Importadas / Fallidas</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>{new Date(job.created_at).toLocaleString()}</td>
                    <td>{job.source_filename}</td>
                    <td>{job.entity_type}</td>
                    <td><span className={`wa-status ${statusClass(job.status)}`}>{statusLabel(job.status)}</span></td>
                    <td>{job.imported_rows} / {job.failed_rows}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
