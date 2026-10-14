import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { fetchBackups, runBackup } from './backupsApi';
import type { BackupJob } from './backupsApi';
import { createScheduledBackupTask, fetchScheduledTasks } from './schedulerApi';
import type { ScheduledTask } from './schedulerApi';

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
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [backups, setBackups] = useState<BackupJob[]>([]);
  const [message, setMessage] = useState('');
  const [running, setRunning] = useState(false);
  const [scheduledTask, setScheduledTask] = useState<ScheduledTask | null>(null);
  const [frequency, setFrequency] = useState('daily');
  const [scheduling, setScheduling] = useState(false);

  function frequencyLabel(freq: string) {
    const labels: Record<string, string> = { hourly: t('admin.backups.frequencyHourly'), daily: t('admin.backups.frequencyDaily'), weekly: t('admin.backups.frequencyWeekly') };
    return labels[freq] ?? freq;
  }

  function statusLabel(status: string) {
    const labels: Record<string, string> = { success: t('admin.backups.statusSuccess'), failed: t('admin.backups.statusFailed'), running: t('admin.backups.statusRunning') };
    return labels[status] ?? status;
  }

  async function loadBackups() {
    try {
      setBackups(await fetchBackups(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.backups.errorLoadBackups'));
    }
  }

  async function loadScheduledTask() {
    if (!projectId) return;
    try {
      const tasks = await fetchScheduledTasks(projectId);
      setScheduledTask(tasks.find((task) => task.task_type === 'backup') ?? null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.backups.errorLoadSchedule'));
    }
  }

  useEffect(() => { void loadBackups(); void loadScheduledTask(); }, [projectId]);

  async function submitSchedule() {
    setScheduling(true);
    try {
      const task = await createScheduledBackupTask(projectId, frequency);
      setScheduledTask(task);
      setMessage(t('admin.backups.backupScheduled'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.backups.errorSchedule'));
    } finally {
      setScheduling(false);
    }
  }

  async function submitRunBackup() {
    setRunning(true);
    try {
      const job = await runBackup(projectId);
      setMessage(job.status === 'success' ? t('admin.backups.backupCompleted', { size: formatSize(job.size_bytes) }) : t('admin.backups.backupStatus', { status: statusLabel(job.status) }));
      await loadBackups();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.backups.errorRunBackup'));
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell title={t('admin.backups.title')}>
      <main className="audit-shell">
        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.backups.autoBackupTitle')}</h2>
              <p>{t('admin.backups.autoBackupDescription')}</p>
            </div>
          </header>
          {scheduledTask ? (
            <div className="ai-analyze-inline">
              <span>{t('admin.backups.frequencyPrefix', { frequency: frequencyLabel(scheduledTask.frequency) })}</span>
              <span>{t('admin.backups.nextRunPrefix', { date: scheduledTask.next_run_at ? new Date(scheduledTask.next_run_at).toLocaleString() : t('admin.backups.pendingWorker') })}</span>
              <span>{t('admin.backups.lastResultPrefix', { result: scheduledTask.last_result ?? t('admin.backups.notYetRun') })}</span>
            </div>
          ) : (
            <div className="ai-analyze-inline">
              <label>{t('admin.backups.frequencyLabel')}
                <select value={frequency} onChange={(event) => setFrequency(event.target.value)}>
                  <option value="hourly">{t('admin.backups.frequencyHourly')}</option>
                  <option value="daily">{t('admin.backups.frequencyDaily')}</option>
                  <option value="weekly">{t('admin.backups.frequencyWeekly')}</option>
                </select>
              </label>
              <button className="primary" disabled={scheduling} onClick={() => void submitSchedule()}>
                {scheduling ? t('admin.backups.scheduling') : t('admin.backups.scheduleAutoBackup')}
              </button>
            </div>
          )}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.backups.dbBackupsTitle')}</h2>
              <p>{t('admin.backups.dbBackupsDescription')}</p>
            </div>
            <button disabled={running} onClick={() => void submitRunBackup()}>{running ? t('admin.backups.running') : t('admin.backups.runBackupNow')}</button>
          </header>
          {message ? <p role="status" className="erp-message">{message}</p> : null}
          {!backups.length ? <p>{t('admin.backups.noBackupsYet')}</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>{t('admin.backups.colStart')}</th>
                  <th>{t('admin.backups.colStatus')}</th>
                  <th>{t('admin.backups.colSize')}</th>
                  <th>{t('admin.backups.colFile')}</th>
                  <th>{t('admin.backups.colError')}</th>
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
