export type AiAuditConfig = {
  id: string;
  template_id: string;
  text_field_name: string;
  mode: string;
  created_at: string;
};

export type AiCheck = {
  id: string;
  project_id: string;
  record_id?: string | null;
  file_id?: string | null;
  check_type: string;
  status: string;
  result_json?: string | null;
  created_by?: string | null;
  created_at: string;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function headers(): HeadersInit {
  return { ...authorizationHeader(), 'Content-Type': 'application/json' };
}

async function parseOrThrow<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  return response.json();
}

export async function fetchChecks(projectId: string): Promise<AiCheck[]> {
  const response = await fetch(`${API_BASE_URL}/ai/checks/${projectId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible cargar las alertas de auditoria semantica.');
}

export async function createAuditConfig(payload: { templateId: string; textFieldName: string; mode: string }): Promise<AiAuditConfig> {
  const response = await fetch(`${API_BASE_URL}/ai-audit/config`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ template_id: payload.templateId, text_field_name: payload.textFieldName, mode: payload.mode }),
  });
  return parseOrThrow(response, 'No fue posible vincular la plantilla a la auditoria semantica.');
}

export async function fetchAuditConfig(templateId: string): Promise<AiAuditConfig | null> {
  const response = await fetch(`${API_BASE_URL}/ai-audit/config/${templateId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar la configuracion de la plantilla.');
}

export async function analyzeRecord(recordId: string): Promise<AiCheck | null> {
  const response = await fetch(`${API_BASE_URL}/ai-audit/records/${recordId}/analyze`, { method: 'POST', headers: headers() });
  return parseOrThrow(response, 'No fue posible reanalizar el registro.');
}
