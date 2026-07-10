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
    values: Object.entries(params.values).map(([fieldName, value]) => ({
      field_name: fieldName,
      field_value_json: JSON.stringify(value),
    })),
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
