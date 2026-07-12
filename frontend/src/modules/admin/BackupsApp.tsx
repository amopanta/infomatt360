import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchBackups, runBackup } from './backupsApi';
import type { BackupJob } from './backupsApi';

function statusLabel(status: string) {
  const labels: Record<string, string> = { success: 'Exitoso', failed: 'Fallido', running: 'En progreso' };
  return labels[status] ?? status;
}

function statusClass(status: string) {
  if (status === 'success') return 'sent';
  if (status === 'failed') return 'failed';
  return 'skipped';
}

function formatSize(bytes?: number | null) {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function BackupsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [backups, setBackups] = useState<BackupJob[]>([]);
  const [message, setMessage] = useState('');
  const [running, setRunning] = useState(false);

  async function loadBackups() {
    try {
      setBackups(await fetchBackups(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar el historial de respaldos.');
    }
  }

  useEffect(() => { void loadBackups(); }, [projectId]);

  async function submitRunBackup() {
    setRunning(true);
    try {
      const job = await runBackup(projectId);
      setMessage(job.status === 'success' ? `Respaldo completado (${formatSize(job.size_bytes)}).` : `Respaldo con estado: ${statusLabel(job.status)}.`);
      await loadBackups();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible ejecutar el respaldo.');
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell title="Backups programables">
      <main className="audit-shell">
        <section className="audit-panel">
          <header>
            <div>
              <h2>Respaldos de base de datos</h2>
              <p>Ejecuta un volcado (pg_dump) del proyecto actual y consulta el historial (ver docs/78).</p>
            </div>
            <button disabled={running} onClick={() => void submitRunBackup()}>{running ? 'Ejecutando…' : 'Ejecutar respaldo ahora'}</button>
          </header>
          {message ? <p role="status" className="erp-message">{message}</p> : null}
          {!backups.length ? <p>Aun no hay respaldos ejecutados para este proyecto.</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Inicio</th>
                  <th>Estado</th>
                  <th>Tamaño</th>
                  <th>Archivo</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((job) => (
                  <tr key={job.id}>
                    <td>{new Date(job.started_at).toLocaleString()}</td>
                    <td><span className={`wa-status ${statusClass(job.status)}`}>{statusLabel(job.status)}</span></td>
                    <td>{formatSize(job.size_bytes)}</td>
                    <td>{job.file_path ?? '—'}</td>
                    <td>{job.error ?? '—'}</td>
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
