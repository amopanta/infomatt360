export type ApiKeyItem = {
  id: string;
  project_id: string;
  name: string;
  key_id: string;
  permissions: string[];
  rate_limit_profile: string;
  status: string;
  created_by?: string | null;
  created_at?: string | null;
  last_used_at?: string | null;
  revoked_at?: string | null;
  expires_at?: string | null;
};

export type ApiKeyCreateResponse = ApiKeyItem & { api_key: string };

import { authorizationHeader, jsonAuthHeaders } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
function headers() { return authorizationHeader(); }
function jsonHeaders() { return jsonAuthHeaders(); }

export async function fetchApiKeys(projectId: string): Promise<ApiKeyItem[]> {
  const response = await fetch(`${API_BASE_URL}/api-keys/${projectId}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar las API keys.');
  return response.json();
}

export async function createApiKey(payload: { projectId: string; name: string; permissions: string[]; rateLimitProfile: string; expiresAt?: string }): Promise<ApiKeyCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/api-keys/`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ project_id: payload.projectId, name: payload.name, permissions: payload.permissions, rate_limit_profile: payload.rateLimitProfile, expires_at: payload.expiresAt || null }),
  });
  if (!response.ok) throw new Error('No fue posible crear la API key. Verifica permisos administrativos.');
  return response.json();
}

export async function revokeApiKey(projectId: string, keyId: string): Promise<ApiKeyItem> {
  const response = await fetch(`${API_BASE_URL}/api-keys/${projectId}/${keyId}`, { method: 'DELETE', headers: headers() });
  if (!response.ok) throw new Error('No fue posible revocar la API key.');
  return response.json();
}
