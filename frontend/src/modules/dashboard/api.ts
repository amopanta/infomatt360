export type DashboardSummary = {
  project_id: string;
  templates_total: number;
  published_templates: number;
  records_total: number;
  users_total: number;
  files_total: number;
  storage_bytes: number;
  records_by_status: Record<string, number>;
  recent_records: Array<{ id: string; template_id: string; template_name: string; status: string; submitted_by?: string | null; created_at: string }>;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function fetchDashboard(projectId: string): Promise<DashboardSummary> {
  const response = await fetch(`${API_BASE_URL}/dashboard/projects/${projectId}/summary`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible cargar el resumen del proyecto.');
  return response.json();
}
