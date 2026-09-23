import { authorizationHeader, jsonAuthHeaders } from '../auth/session';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type IndicatorDefinition = {
  code: string;
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
  sources: Array<{ template_id: string; key_field: string | null; required_status: string | null }>;
  combination: 'single' | 'sum' | 'union' | 'intersection' | 'all';
};

export type CommitteeDetails = {
  meeting_at: string | null;
  location: string;
  audience: string;
  activities: Array<{ title: string; progress: number }>;
  alerts: Array<{ title: string; description: string; priority: 'high' | 'medium' | 'low'; owner: string; next_action: string }>;
  budget: Array<{ component: string; planned: number; spent: number }>;
  previous_agreements: Array<{ title: string; owner: string; due_date: string; status: 'new' | 'pending' | 'in_progress' | 'done' }>;
  new_agreements: Array<{ title: string; owner: string; due_date: string; status: 'new' | 'pending' | 'in_progress' | 'done' }>;
};

export function blankCommittee(): CommitteeDetails {
  return { meeting_at: null, location: '', audience: '', activities: [], alerts: [], budget: [], previous_agreements: [], new_agreements: [] };
}

export type CatalogReportConfig = {
  project_id: string;
  name: string;
  description: string;
  report_kind: 'indicators' | 'committee';
  committee: CommitteeDetails;
  starts_at: string | null;
  ends_at: string | null;
  indicators: IndicatorDefinition[];
  indicator_ids: string[];
};

export type LibraryIndicator = { id: string; project_id: string; definition: IndicatorDefinition; created_at: string; updated_at: string };
export type IndicatorImportPreview = { indicators: IndicatorDefinition[]; errors: Array<{ row: number; error: string }> };

export type CatalogReport = CatalogReportConfig & { id: string; created_at: string };
export type IndicatorResult = { code: string; title: string; actual: number; goal: number; progress_percent: number | null; unit: string; view_kind: 'progress' | 'table' | 'bar'; municipalities: Array<{ municipality: string; value: number }> };
export type CatalogResult = { id: string; name: string; description: string; report_kind: 'indicators' | 'committee'; committee: CommitteeDetails; generated_at: string; indicators: IndicatorResult[] };
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

export function listLibraryIndicators(projectId: string): Promise<LibraryIndicator[]> {
  return fetch(`${API}/reports/indicators/project/${projectId}`, { headers: authorizationHeader() }).then(read<LibraryIndicator[]>);
}

export function saveLibraryIndicator(projectId: string, definition: IndicatorDefinition, id?: string): Promise<LibraryIndicator> {
  return fetch(`${API}/reports/indicators${id ? `/${id}` : ''}`, { method: id ? 'PUT' : 'POST', headers: jsonAuthHeaders(), body: JSON.stringify({ project_id: projectId, definition }) }).then(read<LibraryIndicator>);
}

async function indicatorWorkbook(endpoint: string, projectId: string, file: File) {
  const body = new FormData(); body.append('project_id', projectId); body.append('upload', file);
  return fetch(`${API}/reports/${endpoint}`, { method: 'POST', headers: authorizationHeader(), body });
}

export function previewIndicatorWorkbook(projectId: string, file: File): Promise<IndicatorImportPreview> {
  return indicatorWorkbook('indicators-import/preview', projectId, file).then(read<IndicatorImportPreview>);
}

export function applyIndicatorWorkbook(projectId: string, file: File): Promise<LibraryIndicator[]> {
  return indicatorWorkbook('indicators-import/apply', projectId, file).then(read<LibraryIndicator[]>);
}

export async function downloadIndicatorWorkbookTemplate(projectId: string): Promise<void> {
  const response = await fetch(`${API}/reports/indicators-template?project_id=${encodeURIComponent(projectId)}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No se pudo descargar la plantilla.');
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'plantilla_indicadores.xlsx'; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
