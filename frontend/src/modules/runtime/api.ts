/**
 * Proyecto: InfoMatt360
 * Modulo: Runtime API Client
 * Responsabilidad: Centralizar llamadas HTTP del Runtime Renderer.
 * Notas: El access token se conserva en memoria y el refresh token via cookie httpOnly.
 */

import { authorizationHeader, jsonAuthHeaders } from '../auth/session';
import type { RuntimeFileValue, RuntimeFormValues, RuntimeTemplate } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function authHeaders(): HeadersInit {
  return jsonAuthHeaders();
}

export type RuntimeRecordSummary = {
  id: string;
  values: { field_name: string; field_value_json: string }[];
};

/** Candidatos para el selector de un campo PARENT_CHILD (ver docs/97). */
export async function searchLinkableRecords(templateId: string, search: string): Promise<RuntimeRecordSummary[]> {
  const query = new URLSearchParams();
  if (search.trim()) query.set('search', search.trim());
  query.set('limit', '20');
  const response = await fetch(`${API_BASE_URL}/runtime/template/${templateId}/records/search?${query.toString()}`, { headers: authHeaders() });
  if (!response.ok) throw new Error('No fue posible consultar los registros enlazables.');
  const page = await response.json();
  return page.items ?? [];
}

/** Filas hijas reales de un campo LINKED_SUBFORM (ver docs/97) -- cada una es un RuntimeRecord propio. */
export async function fetchRuntimeRecordChildren(parentRecordId: string, fieldName: string): Promise<RuntimeRecordSummary[]> {
  const response = await fetch(`${API_BASE_URL}/runtime/record/${parentRecordId}/children/${encodeURIComponent(fieldName)}`, { headers: authHeaders() });
  if (!response.ok) throw new Error('No fue posible consultar las filas hijas.');
  return response.json();
}

/** Guarda una fila hija real de un campo LINKED_SUBFORM (ver docs/97). */
export async function saveRuntimeChildRecord(params: {
  projectId: string;
  templateId: string;
  parentRecordId: string;
  parentFieldName: string;
  values: RuntimeFormValues;
}): Promise<RuntimeRecordSummary> {
  const payload = {
    project_id: params.projectId,
    template_id: params.templateId,
    status: 'submitted',
    parent_record_id: params.parentRecordId,
    parent_field_name: params.parentFieldName,
    values: toRuntimeValueList(params.values),
  };
  const response = await fetch(`${API_BASE_URL}/runtime/save`, { method: 'POST', headers: authHeaders(), body: JSON.stringify(payload) });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'No fue posible guardar la fila hija.');
  }
  return response.json();
}

export async function uploadRuntimeFile(projectId: string, assetType: string, file: File): Promise<RuntimeFileValue> {
  const body = new FormData();
  body.append('project_id', projectId);
  body.append('asset_type', assetType);
  body.append('upload', file);
  const response = await fetch(`${API_BASE_URL}/files/upload`, { method: 'POST', headers: authorizationHeader(), body });
  if (!response.ok) throw new Error('No fue posible cargar la evidencia.');
  const asset = await response.json();
  return { file_asset_id: asset.id, name: asset.original_name, mime_type: asset.mime_type, size_bytes: asset.size_bytes };
}

export async function fetchRuntimeTemplate(templateId: string): Promise<RuntimeTemplate> {
  const response = await fetch(`${API_BASE_URL}/runtime/template/${templateId}`, {
    headers: authHeaders(),
  });

  if (!response.ok) {
    throw new Error('No fue posible cargar el formulario Runtime.');
  }

  return response.json();
}

export function toRuntimeValueList(values: RuntimeFormValues): { field_name: string; field_value_json: string }[] {
  return Object.entries(values).map(([fieldName, value]) => ({
    field_name: fieldName,
    field_value_json: JSON.stringify(value),
  }));
}

export async function saveRuntimeRecord(params: {
  projectId: string;
  templateId: string;
  versionId?: string | null;
  values: RuntimeFormValues;
}): Promise<unknown> {
  const payload = {
    project_id: params.projectId,
    template_id: params.templateId,
    version_id: params.versionId ?? null,
    status: 'submitted',
    values: toRuntimeValueList(params.values),
  };

  const response = await fetch(`${API_BASE_URL}/runtime/save`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error('No fue posible guardar la respuesta Runtime.');
  }

  return response.json();
}
