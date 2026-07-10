export type BulkJob = {
  id: string;
  project_id: string;
  template_id: string;
  idempotency_key: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  worker_id?: string | null;
  locked_at?: string | null;
  attempt_count: number;
  max_attempts: number;
  next_attempt_at?: string | null;
  last_error?: string | null;
  received: number;
  created: number;
  failed: number;
  replayable: boolean;
};

export type BulkJobDetail = BulkJob & {
  response?: {
    project_id: string;
    template_id: string;
    job_id?: string | null;
    idempotency_key?: string | null;
    job_status: string;
    processing_mode: string;
    replayed: boolean;
    received: number;
    created: number;
    failed: number;
    results: Array<{ index: number; id?: string | null; status: string; error?: string | null }>;
  } | null;
};

export type BulkJobSummary = {
  project_id: string;
  total_jobs: number;
  queued_jobs: number;
  processing_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_received: number;
  total_created: number;
  total_failed: number;
  success_rate: number;
};

export type BulkWorkerMetrics = {
  worker_cycles: number;
  picked: number;
  processed: number;
  failed: number;
  recovered_stale: number;
  failed_stale: number;
  retries_scheduled: number;
  completed_jobs: number;
  failed_jobs: number;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function headers(): HeadersInit {
  return authorizationHeader();
}

export async function fetchBulkJobs(projectId: string, filters: { status?: string; templateId?: string } = {}): Promise<BulkJob[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.templateId) params.set('template_id', filters.templateId);
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/runtime/bulk/admin/${projectId}/jobs${query}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar los lotes de sincronización.');
  return response.json();
}

export async function fetchBulkSummary(projectId: string, filters: { templateId?: string } = {}): Promise<BulkJobSummary> {
  const params = new URLSearchParams();
  if (filters.templateId) params.set('template_id', filters.templateId);
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/runtime/bulk/admin/${projectId}/summary${query}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar el resumen de sincronización.');
  return response.json();
}

export async function fetchBulkJobDetail(projectId: string, jobId: string): Promise<BulkJobDetail> {
  const response = await fetch(`${API_BASE_URL}/runtime/bulk/admin/${projectId}/jobs/${jobId}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar el detalle del lote.');
  return response.json();
}

export async function processBulkJob(projectId: string, jobId: string): Promise<BulkJobDetail> {
  const response = await fetch(`${API_BASE_URL}/runtime/bulk/admin/${projectId}/jobs/${jobId}/process`, { method: 'POST', headers: headers() });
  if (!response.ok) throw new Error('No fue posible procesar el lote.');
  return response.json();
}

export async function downloadBulkJobErrorsCsv(projectId: string, jobId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/runtime/bulk/admin/${projectId}/jobs/${jobId}/errors.csv`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible exportar los errores del lote.');
  return response.blob();
}

export async function fetchBulkWorkerMetrics(): Promise<BulkWorkerMetrics> {
  const response = await fetch(`${API_BASE_URL}/health/metrics`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar las métricas del worker.');
  const data = await response.json();
  return data.bulk_jobs;
}
