import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { fetchOperationalMetrics } from './operationalMetricsApi';
import type { HttpPathMetrics, OperationalMetrics } from './operationalMetricsApi';

function formatDuration(ms: number) {
  return `${ms.toFixed(ms >= 100 ? 0 : 2)} ms`;
}

function formatUptime(seconds: number) {
  if (seconds < 60) return `${seconds.toFixed(0)} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}

function topPaths(paths: Record<string, HttpPathMetrics>, sortBy: 'requests' | 'p95') {
  return Object.entries(paths)
    .sort(([, left], [, right]) => {
      if (sortBy === 'requests') return right.requests - left.requests;
      return right.latency_percentiles_ms.p95 - left.latency_percentiles_ms.p95;
    })
    .slice(0, 8);
}

function countStatus(metrics: OperationalMetrics, code: string): number {
  return metrics.http.by_status_code[code] ?? 0;
}

function operationalAlerts(metrics: OperationalMetrics, t: (key: string, params?: Record<string, string | number>) => string): Array<{ level: 'warning' | 'danger'; title: string; detail: string }> {
  const alerts: Array<{ level: 'warning' | 'danger'; title: string; detail: string }> = [];
  const serverErrors = metrics.http.by_status_family['5xx'] ?? 0;
  const rateLimited = countStatus(metrics, '429');
  const unauthorized = countStatus(metrics, '401');
  const forbidden = countStatus(metrics, '403');
  const failedJobs = Number(metrics.bulk_jobs.failed_jobs ?? 0);
  const failedStale = Number(metrics.bulk_jobs.failed_stale ?? 0);
  const retries = Number(metrics.bulk_jobs.retries_scheduled ?? 0);

  if (serverErrors > 0) alerts.push({ level: 'danger', title: t('admin.metrics.alert5xx'), detail: t('admin.metrics.alert5xxDetail', { count: serverErrors }) });
  if (rateLimited > 0) alerts.push({ level: 'warning', title: t('admin.metrics.alertRateLimit'), detail: t('admin.metrics.alertRateLimitDetail', { count: rateLimited }) });
  if (unauthorized + forbidden > 0) alerts.push({ level: 'warning', title: t('admin.metrics.alertAccessDenied'), detail: t('admin.metrics.alertAccessDeniedDetail', { unauthorized, forbidden }) });
  if (failedJobs > 0 || failedStale > 0) alerts.push({ level: 'danger', title: t('admin.metrics.alertBulkFailed'), detail: t('admin.metrics.alertBulkFailedDetail', { failed: failedJobs, stale: failedStale }) });
  if (retries > 0) alerts.push({ level: 'warning', title: t('admin.metrics.alertBulkRetries'), detail: t('admin.metrics.alertBulkRetriesDetail', { count: retries }) });

  if (!alerts.length) alerts.push({ level: 'warning', title: t('admin.metrics.alertNoAlerts'), detail: t('admin.metrics.alertNoAlertsDetail') });
  return alerts;
}

export function OperationalMetricsApp() {
  const { t } = useI18n();
  const [metrics, setMetrics] = useState<OperationalMetrics | null>(null);
  const [message, setMessage] = useState(t('admin.metrics.loadingMessage'));

  async function loadMetrics() {
    try {
      setMetrics(await fetchOperationalMetrics());
      setMessage('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.metrics.errorLoadMetrics'));
    }
  }

  useEffect(() => {
    void loadMetrics();
  }, []);

  const busiestPaths = useMemo(() => topPaths(metrics?.http.by_path ?? {}, 'requests'), [metrics]);
  const slowestPaths = useMemo(() => topPaths(metrics?.http.by_path ?? {}, 'p95'), [metrics]);
  const alerts = useMemo(() => (metrics ? operationalAlerts(metrics, t) : []), [metrics, t]);

  return (
    <AppShell title={t('admin.metrics.title')}>
      <main className="operational-metrics-shell">
        <section className="operational-metrics-hero">
          <div>
            <h2>{t('admin.metrics.httpHealthTitle')}</h2>
            <p>{t('admin.metrics.httpHealthDescription')}</p>
          </div>
          <button onClick={() => void loadMetrics()}>{t('admin.metrics.refresh')}</button>
        </section>
        {message ? <p role="status">{message}</p> : null}
        {metrics ? (
          <>
            <section className="operational-metric-cards">
              <article><strong>{metrics.http.total_requests}</strong><span>{t('admin.metrics.requests')}</span></article>
              <article><strong>{formatDuration(metrics.http.avg_duration_ms)}</strong><span>{t('admin.metrics.average')}</span></article>
              <article><strong>{formatDuration(metrics.http.latency_percentiles_ms.p95)}</strong><span>{t('admin.metrics.p95Global')}</span></article>
              <article><strong>{formatDuration(metrics.http.latency_percentiles_ms.p99)}</strong><span>{t('admin.metrics.p99Global')}</span></article>
              <article><strong>{formatDuration(metrics.http.max_duration_ms)}</strong><span>{t('admin.metrics.maximum')}</span></article>
              <article><strong>{formatUptime(metrics.http.uptime_seconds)}</strong><span>{t('admin.metrics.uptime')}</span></article>
              <article><strong>{metrics.metrics_enabled ? t('admin.metrics.metricsActive') : t('admin.metrics.metricsInactive')}</strong><span>{t('admin.metrics.metricsLabel')}</span></article>
              <article><strong>{metrics.service}</strong><span>{t('admin.metrics.serviceLabel')}</span></article>
            </section>

            <section className="operational-alerts" aria-label={t('admin.metrics.alertsAriaLabel')}>
              {alerts.map((alert) => (
                <article key={`${alert.title}-${alert.detail}`} className={alert.level}>
                  <strong>{alert.title}</strong>
                  <span>{alert.detail}</span>
                </article>
              ))}
            </section>

            <section className="operational-metrics-grid">
              <article className="operational-metrics-panel">
                <h3>{t('admin.metrics.httpStatusTitle')}</h3>
                <div className="operational-status-grid">
                  {Object.entries(metrics.http.by_status_family).map(([family, count]) => (
                    <div key={family}><strong>{count}</strong><span>{family}</span></div>
                  ))}
                </div>
                <h4>{t('admin.metrics.exactCodes')}</h4>
                <div className="operational-code-list">
                  {Object.entries(metrics.http.by_status_code).map(([code, count]) => (
                    <span key={code}><strong>{code}</strong> {count}</span>
                  ))}
                </div>
              </article>

              <PathTable title={t('admin.metrics.busiestPaths')} rows={busiestPaths} t={t} />
              <PathTable title={t('admin.metrics.slowestPaths')} rows={slowestPaths} t={t} />
            </section>
          </>
        ) : null}
      </main>
    </AppShell>
  );
}

function PathTable({ title, rows, t }: { title: string; rows: Array<[string, HttpPathMetrics]>; t: (key: string, params?: Record<string, string | number>) => string }) {
  return (
    <article className="operational-metrics-panel">
      <h3>{title}</h3>
      {rows.length ? (
        <div className="operational-path-table">
          <div className="header"><span>{t('admin.metrics.pathHeader')}</span><span>{t('admin.metrics.reqHeader')}</span><span>{t('admin.metrics.p95Header')}</span><span>{t('admin.metrics.lastHeader')}</span></div>
          {rows.map(([path, values]) => (
            <div key={path}>
              <code>{path}</code>
              <span>{values.requests}</span>
              <span>{formatDuration(values.latency_percentiles_ms.p95)}</span>
              <span>{values.last_status_code}</span>
            </div>
          ))}
        </div>
      ) : <p>{t('admin.metrics.noTrafficYet')}</p>}
    </article>
  );
}
