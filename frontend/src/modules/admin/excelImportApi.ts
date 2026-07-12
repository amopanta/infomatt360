export type ExcelImportPreview = {
  headers: string[];
  sample_rows: Record<string, unknown>[];
};

export type ExcelImportJob = {
  id: string;
  project_id: string;
  entity_type: string;
  source_filename: string;
  status: string;
  column_mapping?: Record<string, string> | null;
  preview?: ExcelImportPreview | null;
  total_rows: number;
  imported_rows: number;
  failed_rows: number;
  error_report?: Record<string, unknown>[] | null;
  created_at: string;
  completed_at?: string | null;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function authHeaders(): HeadersInit {
  return authorizationHeader();
}

function jsonHeaders(): HeadersInit {
  return { ...authorizationHeader(), 'Content-Type': 'application/json' };
}

async function parseOrThrow<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  return response.json();
}

export async function uploadExcelImport(payload: { projectId: string; entityType: string; file: File }): Promise<ExcelImportJob> {
  const formData = new FormData();
  formData.append('project_id', payload.projectId);
  formData.append('entity_type', payload.entityType);
  formData.append('upload', payload.file);
  const response = await fetch(`${API_BASE_URL}/excel-import/upload`, { method: 'POST', headers: authHeaders(), body: formData });
  return parseOrThrow(response, 'No fue posible subir el archivo.');
}

export async function confirmExcelImportMapping(jobId: string, columnMapping: Record<string, string>): Promise<ExcelImportJob> {
  const response = await fetch(`${API_BASE_URL}/excel-import/${jobId}/mapping`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify({ column_mapping: columnMapping }),
  });
  return parseOrThrow(response, 'No fue posible confirmar el mapeo de columnas.');
}

export async function approveExcelImport(jobId: string): Promise<ExcelImportJob> {
  const response = await fetch(`${API_BASE_URL}/excel-import/${jobId}/approve`, { method: 'POST', headers: authHeaders() });
  return parseOrThrow(response, 'No fue posible aprobar el lote.');
}

export async function fetchExcelImportJobs(projectId: string): Promise<ExcelImportJob[]> {
  const response = await fetch(`${API_BASE_URL}/excel-import/project/${projectId}`, { headers: authHeaders() });
  return parseOrThrow(response, 'No fue posible consultar los lotes de carga.');
}
