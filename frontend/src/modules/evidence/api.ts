import { authorizationHeader, jsonAuthHeaders } from '../auth/session';
import type { EvidenceAsset, EvidenceFilters, EvidenceUploader } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function buildQuery(filters: EvidenceFilters): string {
  const params = new URLSearchParams();
  if (filters.participantId) params.set('participant_id', filters.participantId);
  if (filters.templateId) params.set('template_id', filters.templateId);
  if (filters.status) params.set('status_filter', filters.status);
  if (filters.createdBy) params.set('created_by', filters.createdBy);
  if (filters.dateFrom) params.set('date_from', `${filters.dateFrom}T00:00:00`);
  if (filters.dateTo) params.set('date_to', `${filters.dateTo}T23:59:59`);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export async function fetchProjectEvidence(projectId: string, filters: EvidenceFilters = {}): Promise<EvidenceAsset[]> {
  const response = await fetch(`${API_BASE_URL}/files/project/${projectId}${buildQuery(filters)}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar las evidencias del proyecto.');
  return response.json();
}

export async function fetchProjectUploaders(projectId: string): Promise<EvidenceUploader[]> {
  const response = await fetch(`${API_BASE_URL}/files/project/${projectId}/uploaders`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar los gestores del proyecto.');
  return response.json();
}

export type EvidenceBatchSelection = { assetIds?: string[] } & EvidenceFilters;
export type EvidenceBatchPayload = {
  asset_ids: string[] | null;
  participant_id: string | null;
  template_id: string | null;
  status: string | null;
  created_by: string | null;
  date_from: string | null;
  date_to: string | null;
};

/** `asset_ids` tiene prioridad sobre los filtros -- nunca se combinan ambos
 * caminos, mismo criterio que `buildBatchPayload` en `acta/api.ts`
 * (docs/110). Extraida como funcion pura para poder probarla sin mockear
 * `fetch`. */
export function buildEvidenceBatchPayload(selection: EvidenceBatchSelection): EvidenceBatchPayload {
  return {
    asset_ids: selection.assetIds?.length ? selection.assetIds : null,
    participant_id: selection.participantId || null,
    template_id: selection.templateId || null,
    status: selection.status || null,
    created_by: selection.createdBy || null,
    date_from: selection.dateFrom ? `${selection.dateFrom}T00:00:00` : null,
    date_to: selection.dateTo ? `${selection.dateTo}T23:59:59` : null,
  };
}

/** Descarga un ZIP con las evidencias seleccionadas, renombradas
 * automaticamente (docs/96 item #7). Mismo patron de blob que
 * `renderActaBatch` (ver `acta/api.ts`, docs/110). */
export async function downloadEvidenceBatch(projectId: string, selection: EvidenceBatchSelection): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/files/project/${projectId}/download-batch`, {
    method: 'POST',
    headers: jsonAuthHeaders(),
    body: JSON.stringify(buildEvidenceBatchPayload(selection)),
  });
  if (!response.ok) throw new Error((await safeErrorDetail(response)) ?? 'No fue posible generar el lote de evidencias.');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = 'evidencias-lote.zip';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadEvidenceAsset(assetId: string, fileNameHint: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/files/${assetId}/download`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error((await safeErrorDetail(response)) ?? 'No fue posible descargar la evidencia.');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileNameHint;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function safeErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json();
    return typeof body?.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}
