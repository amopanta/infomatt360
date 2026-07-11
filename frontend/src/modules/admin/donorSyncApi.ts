export type IntegrationSource = {
  id: string;
  project_id: string;
  name: string;
  source_type: string;
  base_url?: string | null;
  config_json?: string | null;
  status: string;
  has_credentials: boolean;
};

export type IntegrationMap = {
  id: string;
  source_id: string;
  template_id?: string | null;
  name: string;
  target_table: string;
  fields_json: string;
  filters_json?: string | null;
  status: string;
};

export type IntegrationJob = {
  id: string;
  source_id: string;
  map_id?: string | null;
  reference_record_id?: string | null;
  mode: string;
  status: string;
  last_result?: string | null;
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

export async function fetchSources(projectId: string): Promise<IntegrationSource[]> {
  const response = await fetch(`${API_BASE_URL}/integrations/sources/${projectId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar las fuentes de integracion.');
}

export async function createSource(payload: { projectId: string; name: string; sourceType: string; baseUrl: string; credentials: string; configJson: string }): Promise<IntegrationSource> {
  const response = await fetch(`${API_BASE_URL}/integrations/sources`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      project_id: payload.projectId,
      name: payload.name,
      source_type: payload.sourceType,
      base_url: payload.baseUrl || null,
      credentials: payload.credentials || null,
      config_json: payload.configJson || null,
    }),
  });
  return parseOrThrow(response, 'No fue posible crear la fuente de integracion.');
}

export async function fetchMaps(sourceId: string): Promise<IntegrationMap[]> {
  const response = await fetch(`${API_BASE_URL}/integrations/maps/${sourceId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar los mapeos.');
}

export async function createMap(payload: { sourceId: string; templateId: string; name: string; targetTable: string; fieldsJson: string }): Promise<IntegrationMap> {
  const response = await fetch(`${API_BASE_URL}/integrations/maps`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      source_id: payload.sourceId,
      template_id: payload.templateId || null,
      name: payload.name,
      target_table: payload.targetTable,
      fields_json: payload.fieldsJson,
    }),
  });
  return parseOrThrow(response, 'No fue posible crear el mapeo.');
}

export async function fetchJobs(sourceId: string): Promise<IntegrationJob[]> {
  const response = await fetch(`${API_BASE_URL}/integrations/jobs/${sourceId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar el historial de envios.');
}
