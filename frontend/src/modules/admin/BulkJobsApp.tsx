import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { downloadBulkJobErrorsCsv, fetchBulkJobDetail, fetchBulkJobs, fetchBulkSummary, fetchBulkWorkerMetrics, processBulkJob } from './bulkJobsApi';
import type { BulkJob, BulkJobDetail, BulkJobSummary, BulkWorkerMetrics } from './bulkJobsApi';

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '—';
}

function bulkOperations(jobs: BulkJob[], metrics: BulkWorkerMetrics | null) {
  const activeWorkers = new Set(jobs.map((job) => job.worker_id).filter(Boolean));
  const processing = jobs.filter((job) => job.status === 'processing');
  const retrying = jobs.filter((job) => job.next_attempt_at);
  const now = Date.now();
  const possiblyStale = processing.filter((job) => {
    if (!job.locked_at) return true;
    const lockedAt = new Date(job.locked_at).getTime();
    return Number.isNaN(lockedAt) || now - lockedAt > 15 * 60 * 1000;
  });
  return {
    activeWorkers: activeWorkers.size,
    processing: processing.length,
    retrying: retrying.length,
    possiblyStale: possiblyStale.length,
    recovered: metrics?.recovered_stale ?? 0,
  };
}

export function BulkJobsApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [jobs, setJobs] = useState<BulkJob[]>([]);
  const [selected, setSelected] = useState<BulkJobDetail | null>(null);
  const [summary, setSummary] = useState<BulkJobSummary | null>(null);
  const [workerMetrics, setWorkerMetrics] = useState<BulkWorkerMetrics | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [templateFilter, setTemplateFilter] = useState('');
  const operations = useMemo(() => bulkOperations(jobs, workerMetrics), [jobs, workerMetrics]);
  const [message, setMessage] = useState(t('admin.bulkJobs.loading'));

  function statusLabel(status: string) {
    const labels: Record<string, string> = {
      queued: t('admin.bulkJobs.statusQueued'),
      processing: t('admin.bulkJobs.statusProcessing'),
      completed: t('admin.bulkJobs.statusCompleted'),
      failed: t('admin.bulkJobs.statusFailed'),
    };
    return labels[status] ?? status;
  }

  function workerAlerts(metrics: BulkWorkerMetrics | null) {
    if (!metrics) return [];
    const alerts: Array<{ kind: 'warning' | 'danger'; title: string; detail: string }> = [];
    if (metrics.failed_jobs > 0) {
      alerts.push({
        kind: 'danger',
        title: t('admin.bulkJobs.alertFailedTitle'),
        detail: t('admin.bulkJobs.alertFailedDetail', { count: metrics.failed_jobs }),
      });
    }
    if (metrics.failed_stale > 0) {
      alerts.push({
        kind: 'danger',
        title: t('admin.bulkJobs.alertStaleFailedTitle'),
        detail: t('admin.bulkJobs.alertStaleFailedDetail', { count: metrics.failed_stale }),
      });
    }
    if (metrics.retries_scheduled > 0) {
      alerts.push({
        kind: 'warning',
        title: t('admin.bulkJobs.alertRetriesTitle'),
        detail: t('admin.bulkJobs.alertRetriesDetail', { count: metrics.retries_scheduled }),
      });
    }
    return alerts;
  }

  const alerts = workerAlerts(workerMetrics);

  async function loadJobs() {
    try {
      const templateId = templateFilter.trim();
      const [rows, currentSummary] = await Promise.all([
        fetchBulkJobs(projectId, { status: statusFilter, templateId }),
        fetchBulkSummary(projectId, { templateId }),
      ]);
      try {
        setWorkerMetrics(await fetchBulkWorkerMetrics());
      } catch {
        setWorkerMetrics(null);
      }
      setSummary(currentSummary);
      setJobs(rows);
      setMessage(rows.length ? '' : t('admin.bulkJobs.noJobsYet'));
      if (rows[0]) await selectJob(rows[0].id);
      else setSelected(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.bulkJobs.errorLoadJobs'));
    }
  }

  async function selectJob(jobId: string) {
    try {
      setSelected(await fetchBulkJobDetail(projectId, jobId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.bulkJobs.errorLoadDetail'));
    }
  }

  async function processSelected() {
    if (!selected) return;
    if (!window.confirm(t('admin.bulkJobs.confirmProcess', { id: selected.id }))) return;
    try {
      const updated = await processBulkJob(projectId, selected.id);
      const [currentSummary, currentMetrics] = await Promise.all([
        fetchBulkSummary(projectId, { templateId: templateFilter.trim() }),
        fetchBulkWorkerMetrics(),
      ]);
      setSelected(updated);
      setSummary(currentSummary);
      setWorkerMetrics(currentMetrics);
      setJobs((current) => current.map((item) => item.id === updated.id ? {
        ...item,
        status: updated.status,
        received: updated.received,
        created: updated.created,
        failed: updated.failed,
        completed_at: updated.completed_at,
        worker_id: updated.worker_id,
        locked_at: updated.locked_at,
        attempt_count: updated.attempt_count,
        max_attempts: updated.max_attempts,
        next_attempt_at: updated.next_attempt_at,
        last_error: updated.last_error,
      } : item));
      setMessage(t('admin.bulkJobs.batchProcessed'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.bulkJobs.errorProcessBatch'));
    }
  }

  async function exportErrors() {
    if (!selected) return;
    try {
      const blob = await downloadBulkJobErrorsCsv(projectId, selected.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `bulk_errors_${selected.id}.csv`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage(t('admin.bulkJobs.errorsExported'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.bulkJobs.errorExportErrors'));
    }
  }

  useEffect(() => {
    void loadJobs();
  }, [projectId, statusFilter]);

  return (
    <AppShell title={t('admin.bulkJobs.title')}>
      <main className="bulk-jobs-shell">
        <section className="bulk-summary">
          <article><strong>{summary?.total_jobs ?? 0}</strong><span>{t('admin.bulkJobs.batches')}</span></article>
          <article><strong>{summary?.queued_jobs ?? 0}</strong><span>{t('admin.bulkJobs.queued')}</span></article>
          <article><strong>{summary?.completed_jobs ?? 0}</strong><span>{t('admin.bulkJobs.completed')}</span></article>
          <article><strong>{summary?.failed_jobs ?? 0}</strong><span>{t('admin.bulkJobs.failedBatches')}</span></article>
          <article><strong>{summary?.total_received ?? 0}</strong><span>{t('admin.bulkJobs.recordsReceived')}</span></article>
          <article><strong>{summary?.total_created ?? 0}</strong><span>{t('admin.bulkJobs.recordsCreated')}</span></article>
          <article><strong>{summary?.total_failed ?? 0}</strong><span>{t('admin.bulkJobs.recordsFailed')}</span></article>
          <article><strong>{summary?.success_rate ?? 0}%</strong><span>{t('admin.bulkJobs.successRate')}</span></article>
        </section>
        <section className="bulk-worker-metrics" aria-label={t('admin.bulkJobs.workerMetricsAria')}>
          <header>
            <div>
              <h2>{t('admin.bulkJobs.workerOperationTitle')}</h2>
              <p>{t('admin.bulkJobs.workerOperationDescription')}</p>
            </div>
          </header>
          <div>
            <article><strong>{workerMetrics?.worker_cycles ?? 0}</strong><span>{t('admin.bulkJobs.cycles')}</span></article>
            <article><strong>{workerMetrics?.picked ?? 0}</strong><span>{t('admin.bulkJobs.picked')}</span></article>
            <article><strong>{workerMetrics?.processed ?? 0}</strong><span>{t('admin.bulkJobs.processed')}</span></article>
            <article><strong>{workerMetrics?.failed ?? 0}</strong><span>{t('admin.bulkJobs.cycleFaults')}</span></article>
            <article><strong>{workerMetrics?.recovered_stale ?? 0}</strong><span>{t('admin.bulkJobs.recovered')}</span></article>
            <article><strong>{workerMetrics?.failed_stale ?? 0}</strong><span>{t('admin.bulkJobs.staleFailed')}</span></article>
            <article><strong>{workerMetrics?.retries_scheduled ?? 0}</strong><span>{t('admin.bulkJobs.retries')}</span></article>
            <article><strong>{workerMetrics?.failed_jobs ?? 0}</strong><span>{t('admin.bulkJobs.failedJobs')}</span></article>
          </div>
          {alerts.length ? (
            <div className="bulk-worker-alerts" role="alert">
              {alerts.map((alert) => (
                <article className={alert.kind} key={alert.title}>
                  <strong>{alert.title}</strong>
                  <span>{alert.detail}</span>
                </article>
              ))}
            </div>
          ) : null}
        </section>
        <section className="bulk-operations" aria-label={t('admin.bulkJobs.operationalStatusAria')}>
          <article className={operations.activeWorkers ? 'ok' : 'neutral'}>
            <strong>{operations.activeWorkers}</strong>
            <span>{t('admin.bulkJobs.activeWorkers')}</span>
            <small>{t('admin.bulkJobs.activeWorkersNote')}</small>
          </article>
          <article className={operations.processing ? 'warning' : 'neutral'}>
            <strong>{operations.processing}</strong>
            <span>{t('admin.bulkJobs.processingNow')}</span>
            <small>{t('admin.bulkJobs.processingNote')}</small>
          </article>
          <article className={operations.retrying ? 'warning' : 'neutral'}>
            <strong>{operations.retrying}</strong>
            <span>{t('admin.bulkJobs.pendingRetries')}</span>
            <small>{t('admin.bulkJobs.pendingRetriesNote')}</small>
          </article>
          <article className={operations.possiblyStale ? 'danger' : 'ok'}>
            <strong>{operations.possiblyStale}</strong>
            <span>{t('admin.bulkJobs.possiblyStale')}</span>
            <small>{t('admin.bulkJobs.possiblyStaleNote')}</small>
          </article>
        </section>
        <section className="bulk-jobs-list">
          <header>
            <div>
              <h2>{t('admin.bulkJobs.receivedBatches')}</h2>
              <p>{t('admin.bulkJobs.receivedBatchesDescription')}</p>
            </div>
            <button onClick={() => void loadJobs()}>{t('admin.bulkJobs.refresh')}</button>
          </header>
          <div className="bulk-job-filters">
            <label>
              {t('admin.bulkJobs.statusFilterLabel')}
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="">{t('admin.bulkJobs.filterAll')}</option>
                <option value="queued">{t('admin.bulkJobs.filterQueued')}</option>
                <option value="processing">{t('admin.bulkJobs.filterProcessing')}</option>
                <option value="completed">{t('admin.bulkJobs.filterCompleted')}</option>
                <option value="failed">{t('admin.bulkJobs.filterFailed')}</option>
              </select>
            </label>
            <label>
              {t('admin.bulkJobs.templateFilterLabel')}
              <input value={templateFilter} onChange={(event) => setTemplateFilter(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void loadJobs(); }} placeholder="template_id" />
            </label>
          </div>
          {message ? <p role="status">{message}</p> : null}
          {jobs.map((job) => (
            <article className={`bulk-job-card ${job.status}`} key={job.id}>
              <button onClick={() => void selectJob(job.id)}>
                <strong>{statusLabel(job.status)}</strong>
                <span>{job.idempotency_key}</span>
                <small>{job.created} {t('admin.bulkJobs.created')} · {job.failed} {t('admin.bulkJobs.failed')} · {job.received} {t('admin.bulkJobs.received')}</small>
                {job.status === 'processing' ? <small>{t('admin.bulkJobs.workerLabel', { id: job.worker_id ?? t('admin.bulkJobs.unassigned') })} · {t('admin.bulkJobs.heartbeatLabel', { date: formatDate(job.locked_at) })}</small> : null}
                {job.next_attempt_at ? <small>{t('admin.bulkJobs.nextAttemptLabel', { date: formatDate(job.next_attempt_at) })}</small> : null}
              </button>
            </article>
          ))}
        </section>

        <section className="bulk-job-detail">
          {selected ? (
            <>
              <header>
                <div>
                  <h2>{t('admin.bulkJobs.batchDetail')}</h2>
                  <p><code>{selected.id}</code></p>
                </div>
                <div className="bulk-job-actions">
                  {selected.failed > 0 ? <button className="secondary" onClick={() => void exportErrors()}>{t('admin.bulkJobs.exportErrorsCsv')}</button> : null}
                  {selected.status === 'queued' ? <button className="primary" onClick={() => void processSelected()}>{t('admin.bulkJobs.processBatch')}</button> : null}
                </div>
              </header>
              <div className="bulk-job-metrics">
                <article><strong>{statusLabel(selected.status)}</strong><span>{t('admin.bulkJobs.statusLabel')}</span></article>
                <article><strong>{selected.received}</strong><span>{t('admin.bulkJobs.receivedLabel')}</span></article>
                <article><strong>{selected.created}</strong><span>{t('admin.bulkJobs.createdLabel')}</span></article>
                <article><strong>{selected.failed}</strong><span>{t('admin.bulkJobs.failedLabel')}</span></article>
              </div>
              <dl className="bulk-job-meta">
                <div><dt>{t('admin.bulkJobs.templateMeta')}</dt><dd>{selected.template_id}</dd></div>
                <div><dt>{t('admin.bulkJobs.idempotency')}</dt><dd>{selected.idempotency_key}</dd></div>
                <div><dt>{t('admin.bulkJobs.createdMeta')}</dt><dd>{formatDate(selected.created_at)}</dd></div>
                <div><dt>{t('admin.bulkJobs.completedMeta')}</dt><dd>{formatDate(selected.completed_at)}</dd></div>
                <div><dt>{t('admin.bulkJobs.workerMeta')}</dt><dd>{selected.worker_id ?? '—'}</dd></div>
                <div><dt>{t('admin.bulkJobs.heartbeatMeta')}</dt><dd>{formatDate(selected.locked_at)}</dd></div>
                <div><dt>{t('admin.bulkJobs.attempts')}</dt><dd>{selected.attempt_count} / {selected.max_attempts}</dd></div>
                <div><dt>{t('admin.bulkJobs.nextAttempt')}</dt><dd>{formatDate(selected.next_attempt_at)}</dd></div>
                {selected.last_error ? <div><dt>{t('admin.bulkJobs.lastError')}</dt><dd>{selected.last_error}</dd></div> : null}
              </dl>
              <h3>{t('admin.bulkJobs.results')}</h3>
              <div className="bulk-job-results">
                {selected.response?.results.length ? selected.response.results.slice(0, 50).map((item) => (
                  <article className={item.status} key={`${item.index}-${item.id ?? 'error'}`}>
                    <strong>#{item.index + 1} · {item.status}</strong>
                    <span>{item.id ?? item.error ?? t('admin.bulkJobs.noDetail')}</span>
                  </article>
                )) : <p>{t('admin.bulkJobs.noResultsYet')}</p>}
              </div>
            </>
          ) : <p>{t('admin.bulkJobs.selectBatchPrompt')}</p>}
        </section>
      </main>
    </AppShell>
  );
}
