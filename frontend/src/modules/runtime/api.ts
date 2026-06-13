/**
 * Proyecto: InfoMatt360
 * Modulo: Runtime API Client
 * Responsabilidad: Centralizar llamadas HTTP del Runtime Renderer.
 * Notas: El token se lee desde localStorage para mantener simple el MVP.
 */

import type { RuntimeFormValues, RuntimeTemplate } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('infomatt360_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
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
