import { authorizationHeader, jsonAuthHeaders } from '../auth/session';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type IndicatorDefinition = {
  title: string;
  source_mode: 'automatic' | 'manual';
  template_id: string | null;
  value_field: string | null;
  aggregation: 'count' | 'sum' | 'average' | 'unique_count';
  goal: number;
  manual_actual: number | null;
  unit: string;
  municipality_field: string | null;
  view_kind: 'progress' | 'table' | 'bar';
};

export type CatalogReportConfig = {
  project_id: string;
  name: string;
  description: string;
  starts_at: string | null;
  ends_at: string | null;
  indicators: IndicatorDefinition[];
};

export type CatalogReport = CatalogReportConfig & { id: string; created_at: string };
export type IndicatorResult = { title: string; actual: number; goal: number; progress_percent: number | null; unit: string; view_kind: 'progress' | 'table' | 'bar'; municipalities: Array<{ municipality: string; value: number }> };
export type CatalogResult = { id: string; name: string; description: string; generated_at: string; indicators: IndicatorResult[] };
export type ReportLink = { id: string; expires_at: string | null; status: string };
export type IssuedLink = { id: string; token: string; expires_at: string };
export type FormReport = {
  template_id: string; template_name: string; description: string | null; status: string;
  records_total: number; records_by_status: Record<string, number>; last_record_at: string | null;
  months: Array<{ month: string; count: number }>;
  questions: Array<{ name: string; label: string; field_type: string; answered: number; missing: number; choices: Array<{ label: string; count: number }>; numeric_min: number | null; numeric_max: number | null; numeric_average: number | null }>;
};

async function read<T>(response: Response): Promise<T> {
  if (response.ok) return response.json();
  let detail = 'No fue posible completar la operación.';
  try { const body = await response.json(); if (typeof body.detail === 'string') detail = body.detail; } catch { /* HTTP sin cuerpo JSON */ }
  throw new Error(detail);
}

export function listCatalog(projectId: string): Promise<CatalogReport[]> {
  return fetch(`${API}/reports/catalog/project/${projectId}`, { headers: authorizationHeader() }).then(read<CatalogReport[]>);
}

export function saveCatalog(config: CatalogReportConfig, reportId?: string): Promise<CatalogReport> {
  return fetch(`${API}/reports/catalog${reportId ? `/${reportId}` : ''}`, { method: reportId ? 'PUT' : 'POST', headers: jsonAuthHeaders(), body: JSON.stringify(config) }).then(read<CatalogReport>);
}

export function getCatalog(reportId: string): Promise<CatalogResult> {
  return fetch(`${API}/reports/catalog/${reportId}`, { headers: authorizationHeader() }).then(read<CatalogResult>);
}

export function getSharedReport(token: string): Promise<CatalogResult> {
  return fetch(`${API}/reports/shared/${encodeURIComponent(token)}`).then(read<CatalogResult>);
}

export function listReportLinks(reportId: string): Promise<ReportLink[]> {
  return fetch(`${API}/reports/catalog/${reportId}/links`, { headers: authorizationHeader() }).then(read<ReportLink[]>);
}

export function issueReportLink(reportId: string): Promise<IssuedLink> {
  return fetch(`${API}/reports/catalog/${reportId}/links`, { method: 'POST', headers: jsonAuthHeaders(), body: '{}' }).then(read<IssuedLink>);
}

export function revokeReportLink(reportId: string, linkId: string): Promise<ReportLink> {
  return fetch(`${API}/reports/catalog/${reportId}/links/${linkId}/revoke`, { method: 'POST', headers: jsonAuthHeaders() }).then(read<ReportLink>);
}

export function getIndividualFormReport(templateId: string): Promise<FormReport> {
  return fetch(`${API}/reports/forms/${templateId}`, { headers: authorizationHeader() }).then(read<FormReport>);
}
