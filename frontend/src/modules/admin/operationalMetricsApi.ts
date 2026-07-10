export type LatencyPercentiles = {
  p50: number;
  p95: number;
  p99: number;
};

export type HttpPathMetrics = {
  requests: number;
  avg_duration_ms: number;
  max_duration_ms: number;
  latency_percentiles_ms: LatencyPercentiles;
  last_status_code: number;
};

export type OperationalMetrics = {
  status: string;
  service: string;
  metrics_enabled: boolean;
  http: {
    uptime_seconds: number;
    total_requests: number;
    avg_duration_ms: number;
    max_duration_ms: number;
    latency_percentiles_ms: LatencyPercentiles;
    by_status_family: Record<string, number>;
    by_status_code: Record<string, number>;
    by_path: Record<string, HttpPathMetrics>;
  };
  bulk_jobs: Record<string, number>;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function fetchOperationalMetrics(): Promise<OperationalMetrics> {
  const response = await fetch(`${API_BASE_URL}/health/metrics`, {
    headers: authorizationHeader(),
  });
  if (!response.ok) throw new Error('No fue posible consultar las métricas operativas.');
  return response.json();
}
