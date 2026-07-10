import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { downloadBulkJobErrorsCsv, fetchBulkJobDetail, fetchBulkJobs, fetchBulkSummary, fetchBulkWorkerMetrics, processBulkJob } from './bulkJobsApi';
import type { BulkJob, BulkJobDetail, BulkJobSummary, BulkWorkerMetrics } from './bulkJobsApi';

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '—';
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    queued: 'En cola',
    processing: 'Procesando',
    completed: 'Completado',
    failed: 'Fallido',
  };
  return labels[status] ?? status;
}

function workerAlerts(metrics: BulkWorkerMetrics | null) {
  if (!metrics) return [];
  const alerts: Array<{ kind: 'warning' | 'danger'; title: string; detail: string }> = [];
  if (metrics.failed_jobs > 0) {
    alerts.push({
      kind: 'danger',
      title: 'Jobs fallidos',
      detail: `${metrics.failed_jobs} job(s) llegaron a estado fallido. Revisa errores y reintentos.`,
    });
  }
  if (metrics.failed_stale > 0) {
    alerts.push({
      kind: 'danger',
      title: 'Jobs atascados fallidos',
      detail: `${metrics.failed_stale} job(s) estaban atascados y agotaron intentos.`,
    });
  }
  if (metrics.retries_scheduled > 0) {
    alerts.push({
      kind: 'warning',
      title: 'Reintentos programados',
      detail: `${metrics.retries_scheduled} job(s) fueron reprogramados con backoff.`,
    });
  }
  return alerts;
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
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [jobs, setJobs] = useState<BulkJob[]>([]);
  const [selected, setSelected] = useState<BulkJobDetail | null>(null);
  const [summary, setSummary] = useState<BulkJobSummary | null>(null);
  const [workerMetrics, setWorkerMetrics] = useState<BulkWorkerMetrics | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [templateFilter, setTemplateFilter] = useState('');
  const alerts = workerAlerts(workerMetrics);
  const operations = useMemo(() => bulkOperations(jobs, workerMetrics), [jobs, workerMetrics]);
  const [message, setMessage] = useState('Cargando lotes de sincronización...');

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
      setMessage(rows.length ? '' : 'Aún no hay lotes de sincronización registrados.');
      if (rows[0]) await selectJob(rows[0].id);
      else setSelected(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar los lotes.');
    }
  }

  async function selectJob(jobId: string) {
    try {
      setSelected(await fetchBulkJobDetail(projectId, jobId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar el detalle.');
    }
  }

  async function processSelected() {
    if (!selected) return;
    if (!window.confirm(`Vas a procesar manualmente el lote ${selected.id}. Confirma que revisaste su estado e idempotencia. ¿Continuar?`)) return;
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
      setMessage('Lote procesado correctamente.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible procesar el lote.');
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
      setMessage('Errores exportados.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible exportar errores.');
    }
  }

  useEffect(() => {
    void loadJobs();
  }, [projectId, statusFilter]);

  return (
    <AppShell title="Sincronización">
      <main className="bulk-jobs-shell">
        <section className="bulk-summary">
          <article><strong>{summary?.total_jobs ?? 0}</strong><span>Lotes</span></article>
          <article><strong>{summary?.queued_jobs ?? 0}</strong><span>En cola</span></article>
          <article><strong>{summary?.completed_jobs ?? 0}</strong><span>Completados</span></article>
          <article><strong>{summary?.failed_jobs ?? 0}</strong><span>Lotes fallidos</span></article>
          <article><strong>{summary?.total_received ?? 0}</strong><span>Registros recibidos</span></article>
          <article><strong>{summary?.total_created ?? 0}</strong><span>Registros creados</span></article>
          <article><strong>{summary?.total_failed ?? 0}</strong><span>Registros fallidos</span></article>
          <article><strong>{summary?.success_rate ?? 0}%</strong><span>Tasa de éxito</span></article>
        </section>
        <section className="bulk-worker-metrics" aria-label="Métricas operativas del worker bulk">
          <header>
            <div>
              <h2>Operación del worker</h2>
              <p>Visibilidad de procesamiento, recuperaciones, reintentos y fallos.</p>
            </div>
          </header>
          <div>
            <article><strong>{workerMetrics?.worker_cycles ?? 0}</strong><span>Ciclos</span></article>
            <article><strong>{workerMetrics?.picked ?? 0}</strong><span>Tomados</span></article>
            <article><strong>{workerMetrics?.processed ?? 0}</strong><span>Procesados</span></article>
            <article><strong>{workerMetrics?.failed ?? 0}</strong><span>Fallos de ciclo</span></article>
            <article><strong>{workerMetrics?.recovered_stale ?? 0}</strong><span>Recuperados</span></article>
            <article><strong>{workerMetrics?.failed_stale ?? 0}</strong><span>Atascados fallidos</span></article>
            <article><strong>{workerMetrics?.retries_scheduled ?? 0}</strong><span>Reintentos</span></article>
            <article><strong>{workerMetrics?.failed_jobs ?? 0}</strong><span>Jobs fallidos</span></article>
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
        <section className="bulk-operations" aria-label="Estado operativo de sincronización">
          <article className={operations.activeWorkers ? 'ok' : 'neutral'}>
            <strong>{operations.activeWorkers}</strong>
            <span>Workers activos</span>
            <small>Detectados por lotes en procesamiento.</small>
          </article>
          <article className={operations.processing ? 'warning' : 'neutral'}>
            <strong>{operations.processing}</strong>
            <span>Procesando ahora</span>
            <small>Lotes con bloqueo activo.</small>
          </article>
          <article className={operations.retrying ? 'warning' : 'neutral'}>
            <strong>{operations.retrying}</strong>
            <span>Reintentos pendientes</span>
            <small>Esperando próxima ventana de backoff.</small>
          </article>
          <article className={operations.possiblyStale ? 'danger' : 'ok'}>
            <strong>{operations.possiblyStale}</strong>
            <span>Posibles atascados</span>
            <small>Procesando sin heartbeat reciente.</small>
          </article>
        </section>
        <section className="bulk-jobs-list">
          <header>
            <div>
              <h2>Lotes recibidos</h2>
              <p>Seguimiento de cargas masivas enviadas por API.</p>
            </div>
            <button onClick={() => void loadJobs()}>Actualizar</button>
          </header>
          <div className="bulk-job-filters">
            <label>
              Estado
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="">Todos</option>
                <option value="queued">En cola</option>
                <option value="processing">Procesando</option>
                <option value="completed">Completado</option>
                <option value="failed">Fallido</option>
              </select>
            </label>
            <label>
              Plantilla
              <input value={templateFilter} onChange={(event) => setTemplateFilter(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void loadJobs(); }} placeholder="template_id" />
            </label>
          </div>
          {message ? <p role="status">{message}</p> : null}
          {jobs.map((job) => (
            <article className={`bulk-job-card ${job.status}`} key={job.id}>
              <button onClick={() => void selectJob(job.id)}>
                <strong>{statusLabel(job.status)}</strong>
                <span>{job.idempotency_key}</span>
                <small>{job.created} creados · {job.failed} fallidos · {job.received} recibidos</small>
                {job.status === 'processing' ? <small>Worker: {job.worker_id ?? 'sin asignar'} · heartbeat: {formatDate(job.locked_at)}</small> : null}
                {job.next_attempt_at ? <small>Próximo intento: {formatDate(job.next_attempt_at)}</small> : null}
              </button>
            </article>
          ))}
        </section>

        <section className="bulk-job-detail">
          {selected ? (
            <>
              <header>
                <div>
                  <h2>Detalle del lote</h2>
                  <p><code>{selected.id}</code></p>
                </div>
                <div className="bulk-job-actions">
                  {selected.failed > 0 ? <button className="secondary" onClick={() => void exportErrors()}>Exportar errores CSV</button> : null}
                  {selected.status === 'queued' ? <button className="primary" onClick={() => void processSelected()}>Procesar lote</button> : null}
                </div>
              </header>
              <div className="bulk-job-metrics">
                <article><strong>{statusLabel(selected.status)}</strong><span>Estado</span></article>
                <article><strong>{selected.received}</strong><span>Recibidos</span></article>
                <article><strong>{selected.created}</strong><span>Creados</span></article>
                <article><strong>{selected.failed}</strong><span>Fallidos</span></article>
              </div>
              <dl className="bulk-job-meta">
                <div><dt>Plantilla</dt><dd>{selected.template_id}</dd></div>
                <div><dt>Idempotencia</dt><dd>{selected.idempotency_key}</dd></div>
                <div><dt>Creado</dt><dd>{formatDate(selected.created_at)}</dd></div>
                <div><dt>Completado</dt><dd>{formatDate(selected.completed_at)}</dd></div>
                <div><dt>Worker</dt><dd>{selected.worker_id ?? '—'}</dd></div>
                <div><dt>Heartbeat</dt><dd>{formatDate(selected.locked_at)}</dd></div>
                <div><dt>Intentos</dt><dd>{selected.attempt_count} / {selected.max_attempts}</dd></div>
                <div><dt>Próximo intento</dt><dd>{formatDate(selected.next_attempt_at)}</dd></div>
                {selected.last_error ? <div><dt>Último error</dt><dd>{selected.last_error}</dd></div> : null}
              </dl>
              <h3>Resultados</h3>
              <div className="bulk-job-results">
                {selected.response?.results.length ? selected.response.results.slice(0, 50).map((item) => (
                  <article className={item.status} key={`${item.index}-${item.id ?? 'error'}`}>
                    <strong>#{item.index + 1} · {item.status}</strong>
                    <span>{item.id ?? item.error ?? 'Sin detalle'}</span>
                  </article>
                )) : <p>Este lote aún no tiene resultados item por item.</p>}
              </div>
            </>
          ) : <p>Selecciona un lote para ver el detalle.</p>}
        </section>
      </main>
    </AppShell>
  );
}
