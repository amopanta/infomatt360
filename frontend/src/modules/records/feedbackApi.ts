/** Devoluciones con destinatario, observaciones y exportaciones separadas (docs/141). */
import { authorizationHeader, currentAccessToken, jsonAuthHeaders } from '../auth/session';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type ObservationStatus = 'pending' | 'in_correction' | 'corrected' | 'verified' | 'rejected';
export type Observation = {
  id: string; record_id: string; field_name: string | null; repeat_path: string | null; evidence_file_id: string | null;
  reason: string; requested_action: string | null; status: ObservationStatus; response_note: string | null;
  created_by: string; resolved_by: string | null; created_at: string; updated_at: string;
};
export type ObservationInput = { field_name?: string; repeat_path?: string; reason: string; requested_action?: string };
export type ProjectUser = { id: string; full_name: string };
export type BulkReturnRow = { fila: number; id_registro: string; estado: 'ok' | 'error' | 'duplicada' | 'ya_aplicada' | 'aplicada'; detalle: string };
export type BulkReturnResult = {
  filas: number; registros_a_devolver: number; aplicadas: number; errores: number; duplicadas: number; ya_aplicadas: number;
  resultados: BulkReturnRow[]; errores_csv: string; vista_previa: boolean;
};

async function json<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : fallback);
  }
  return response.json();
}

/** Usuario de la sesión (sub del token), para saber si me toca corregir. */
export function currentUserId(): string | null {
  try {
    const payload = currentAccessToken().split('.')[1] ?? '';
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/'))).sub ?? null;
  } catch {
    return null;
  }
}

export const fetchObservations = async (recordId: string) =>
  json<Observation[]>(await fetch(`${API}/review/records/${recordId}/observations`, { headers: authorizationHeader() }), 'No fue posible consultar las observaciones.');

export const returnWithObservations = async (recordId: string, body: { notes: string; assignee_user_id?: string | null; observations: ObservationInput[] }) =>
  json<{ correction_user_id: string | null; observations: Observation[] }>(await fetch(`${API}/review/records/${recordId}/return`, {
    method: 'POST', headers: jsonAuthHeaders(), body: JSON.stringify(body),
  }), 'No fue posible devolver el registro.');

export const updateObservation = async (id: string, status: ObservationStatus, note?: string) =>
  json<Observation>(await fetch(`${API}/review/observations/${id}`, {
    method: 'PATCH', headers: jsonAuthHeaders(), body: JSON.stringify({ status, note }),
  }), 'No fue posible actualizar la observación.');

export const fetchProjectUsers = async (projectId: string) =>
  json<ProjectUser[]>(await fetch(`${API}/cases/project/${projectId}/assignees`, { headers: authorizationHeader() }), 'No fue posible consultar los gestores.');

export async function bulkReturns(projectId: string, file: File, previewOnly: boolean): Promise<BulkReturnResult> {
  const body = new FormData();
  body.set('upload', file);
  body.set('preview_only', String(previewOnly));
  return json<BulkReturnResult>(await fetch(`${API}/review/bulk-returns/${projectId}`, { method: 'POST', headers: authorizationHeader(), body }), 'No fue posible procesar el archivo.');
}

function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = name;
  document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function saveText(text: string, name: string) {
  saveBlob(new Blob(['﻿' + text], { type: 'text/csv;charset=utf-8' }), name);
}

async function download(path: string, name: string, fallback: string) {
  const response = await fetch(`${API}${path}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error(fallback);
  saveBlob(await response.blob(), name);
}

export const downloadBulkReturnTemplate = () => download('/review/bulk-returns/template.csv', 'plantilla_devoluciones.csv', 'No fue posible descargar la plantilla.');

export function downloadCleanAnswers(templateId: string, filters: { status?: string; dateFrom?: string; dateTo?: string }) {
  const query = new URLSearchParams();
  query.set('status', filters.status || 'approved');
  if (filters.dateFrom) query.set('date_from', new Date(`${filters.dateFrom}T00:00:00`).toISOString());
  if (filters.dateTo) { const end = new Date(`${filters.dateTo}T00:00:00`); end.setDate(end.getDate() + 1); query.set('date_to', end.toISOString()); }
  return download(`/runtime/template/${templateId}/records/clean-export.csv?${query}`, `respuestas_limpias-${templateId}.csv`, 'No fue posible exportar las respuestas.');
}

export const downloadObservations = (templateId: string) =>
  download(`/runtime/template/${templateId}/records/observations.csv`, `observaciones-${templateId}.csv`, 'No fue posible exportar las observaciones.');

/** Preguntas del registro, con cada campo de cada integrante de un REPEAT ("integrantes[1].edad"). */
export function observationTargets(values: { field_name: string; field_value_json: string }[]): { value: string; label: string; field: string; path?: string }[] {
  const out: { value: string; label: string; field: string; path?: string }[] = [];
  for (const value of values) {
    out.push({ value: value.field_name, label: value.field_name, field: value.field_name });
    try {
      const parsed = JSON.parse(value.field_value_json);
      if (Array.isArray(parsed) && parsed.every((row) => row && typeof row === 'object' && 'values' in row)) {
        parsed.forEach((row: { values: Record<string, unknown> }, index: number) => {
          for (const key of Object.keys(row.values ?? {})) {
            const path = `${value.field_name}[${index}].${key}`;
            out.push({ value: path, label: `${value.field_name} ${index + 1} · ${key}`, field: key, path });
          }
        });
      }
    } catch { /* valor simple */ }
  }
  return out;
}
