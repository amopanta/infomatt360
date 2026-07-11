export type AuditLog = {
  id: string;
  project_id?: string | null;
  user_id?: string | null;
  module: string;
  action: string;
  entity_type?: string | null;
  entity_id?: string | null;
  before_json?: string | null;
  after_json?: string | null;
  ip_address?: string | null;
  device_info?: string | null;
  created_at: string;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function fetchAuditLogs(params: { projectId: string; module?: string; limit?: number }): Promise<AuditLog[]> {
  const query = new URLSearchParams({ project_id: params.projectId, limit: String(params.limit ?? 100) });
  if (params.module) query.set('module', params.module);
  const response = await fetch(`${API_BASE_URL}/audit/?${query.toString()}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible cargar la auditoría.');
  return response.json();
}
