import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
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

function operationalAlerts(metrics: OperationalMetrics): Array<{ level: 'warning' | 'danger'; title: string; detail: string }> {
  const alerts: Array<{ level: 'warning' | 'danger'; title: string; detail: string }> = [];
  const serverErrors = metrics.http.by_status_family['5xx'] ?? 0;
  const rateLimited = countStatus(metrics, '429');
  const unauthorized = countStatus(metrics, '401');
  const forbidden = countStatus(metrics, '403');
  const failedJobs = Number(metrics.bulk_jobs.failed_jobs ?? 0);
  const failedStale = Number(metrics.bulk_jobs.failed_stale ?? 0);
  const retries = Number(metrics.bulk_jobs.retries_scheduled ?? 0);

  if (serverErrors > 0) alerts.push({ level: 'danger', title: 'Errores 5xx detectados', detail: `${serverErrors} respuesta(s) del servidor terminaron en error.` });
  if (rateLimited > 0) alerts.push({ level: 'warning', title: 'Rate limiting activo', detail: `${rateLimited} request(s) recibieron 429. Revisar integraciones o limites.` });
  if (unauthorized + forbidden > 0) alerts.push({ level: 'warning', title: 'Eventos de acceso denegado', detail: `${unauthorized} 401 y ${forbidden} 403 registrados.` });
  if (failedJobs > 0 || failedStale > 0) alerts.push({ level: 'danger', title: 'Jobs bulk fallidos', detail: `${failedJobs} fallido(s), ${failedStale} atascado(s) agotaron intentos.` });
  if (retries > 0) alerts.push({ level: 'warning', title: 'Reintentos bulk programados', detail: `${retries} job(s) fueron reprogramados con backoff.` });

  if (!alerts.length) alerts.push({ level: 'warning', title: 'Sin alertas operativas', detail: 'No se observan errores 5xx, 429 ni jobs bulk fallidos en este proceso.' });
  return alerts;
}

export function OperationalMetricsApp() {
  const [metrics, setMetrics] = useState<OperationalMetrics | null>(null);
  const [message, setMessage] = useState('Cargando métricas operativas...');

  async function loadMetrics() {
    try {
      setMetrics(await fetchOperationalMetrics());
      setMessage('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar métricas.');
    }
  }

  useEffect(() => {
    void loadMetrics();
  }, []);

  const busiestPaths = useMemo(() => topPaths(metrics?.http.by_path ?? {}, 'requests'), [metrics]);
  const slowestPaths = useMemo(() => topPaths(metrics?.http.by_path ?? {}, 'p95'), [metrics]);
  const alerts = useMemo(() => (metrics ? operationalAlerts(metrics) : []), [metrics]);

  return (
    <AppShell title="Métricas operativas">
      <main className="operational-metrics-shell">
        <section className="operational-metrics-hero">
          <div>
            <h2>Salud HTTP y latencia</h2>
            <p>Lectura en memoria del proceso actual. Útil para demo, preproducción y diagnóstico rápido.</p>
          </div>
          <button onClick={() => void loadMetrics()}>Actualizar</button>
        </section>
        {message ? <p role="status">{message}</p> : null}
        {metrics ? (
          <>
            <section className="operational-metric-cards">
              <article><strong>{metrics.http.total_requests}</strong><span>Requests</span></article>
              <article><strong>{formatDuration(metrics.http.avg_duration_ms)}</strong><span>Promedio</span></article>
              <article><strong>{formatDuration(metrics.http.latency_percentiles_ms.p95)}</strong><span>p95 global</span></article>
              <article><strong>{formatDuration(metrics.http.latency_percentiles_ms.p99)}</strong><span>p99 global</span></article>
              <article><strong>{formatDuration(metrics.http.max_duration_ms)}</strong><span>Máxima</span></article>
              <article><strong>{formatUptime(metrics.http.uptime_seconds)}</strong><span>Uptime</span></article>
              <article><strong>{metrics.metrics_enabled ? 'Activo' : 'Inactivo'}</strong><span>Métricas</span></article>
              <article><strong>{metrics.service}</strong><span>Servicio</span></article>
            </section>

            <section className="operational-alerts" aria-label="Alertas operativas">
              {alerts.map((alert) => (
                <article key={`${alert.title}-${alert.detail}`} className={alert.level}>
                  <strong>{alert.title}</strong>
                  <span>{alert.detail}</span>
                </article>
              ))}
            </section>

            <section className="operational-metrics-grid">
              <article className="operational-metrics-panel">
                <h3>Estados HTTP</h3>
                <div className="operational-status-grid">
                  {Object.entries(metrics.http.by_status_family).map(([family, count]) => (
                    <div key={family}><strong>{count}</strong><span>{family}</span></div>
                  ))}
                </div>
                <h4>Códigos exactos</h4>
                <div className="operational-code-list">
                  {Object.entries(metrics.http.by_status_code).map(([code, count]) => (
                    <span key={code}><strong>{code}</strong> {count}</span>
                  ))}
                </div>
              </article>

              <PathTable title="Rutas con más tráfico" rows={busiestPaths} />
              <PathTable title="Rutas más lentas por p95" rows={slowestPaths} />
            </section>
          </>
        ) : null}
      </main>
    </AppShell>
  );
}

function PathTable({ title, rows }: { title: string; rows: Array<[string, HttpPathMetrics]> }) {
  return (
    <article className="operational-metrics-panel">
      <h3>{title}</h3>
      {rows.length ? (
        <div className="operational-path-table">
          <div className="header"><span>Ruta</span><span>Req.</span><span>p95</span><span>Último</span></div>
          {rows.map(([path, values]) => (
            <div key={path}>
              <code>{path}</code>
              <span>{values.requests}</span>
              <span>{formatDuration(values.latency_percentiles_ms.p95)}</span>
              <span>{values.last_status_code}</span>
            </div>
          ))}
        </div>
      ) : <p>Todavía no hay tráfico registrado.</p>}
    </article>
  );
}
