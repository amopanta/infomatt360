/** Planeador mensual (docs/144): metas, programación, tablero y Excel de tres hojas. */
import { authorizationHeader, jsonAuthHeaders } from '../auth/session';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type Metric = { target: number; executed: number; pending: number; over: number; compliance: number | null };
export type PlannerSettings = { count_policy: 'submitted' | 'approved'; family_key: 'participant' | 'document_id' | 'external_code' | 'field'; family_field: string | null; activity_date_field: string | null; municipality_field: string | null; timezone: string; can_manage?: boolean; supervise?: boolean };
export type MunicipalRow = { month: number; municipality: string; template_id: string; activity: string; population_families: number | null; activities: Metric; families: Metric; closed: boolean };
export type GestorRow = { month: number; coordinator: string; gestor: string; gestor_user_id: string | null; municipality: string; activity: string; start_date: string | null; end_date: string | null; planned_quantity: number; planned_participants: number; activities: Metric; families_executed: number; families_target: number; state: string; closed: boolean };
export type PlannerReport = { year: number; closed_months: number[]; totals: { activities: Metric & { unplanned: number; all_executed: number }; families: Metric & { unique_all: number; population: number | null; coverage: number | null } }; municipal: MunicipalRow[]; gestor: GestorRow[]; by_month: (Metric & { month: number; accumulated: Metric })[] };
export type PlannerTarget = { id: string; year: number; month: number; municipality: string; template_id: string; gestor_user_id: string | null; unit: 'records' | 'families'; target: number; version: number };
export type PlannerPlan = { id: string; gestor_user_id: string; template_id: string; municipality: string; coordinator_user_id: string | null; start_date: string; end_date: string; planned_quantity: number; planned_participants: number; status: 'scheduled' | 'rescheduled' | 'cancelled'; note: string | null; version: number };
export type PlannerPopulation = { id: string; year: number; municipality: string; families: number; participants: number; source: string | null; version: number };
export type PlannerCatalog = { activities: { id: string; name: string; status: string }[]; people: { id: string; full_name: string; email: string }[]; can_manage: boolean; supervise: boolean };
export type ImportRow = { row: number; status: string; message: string; before: number | null; after: number | null; municipality?: string; template?: string; month?: number };
export type ImportResult = { rows: ImportRow[]; errors: number; applied: number; total_before: number; total_after: number; preview_only: boolean };
export type Filters = { year: number; month?: number | ''; municipality?: string; gestor_user_id?: string; template_id?: string };

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}/planner${path}`, { ...init, headers: { ...jsonAuthHeaders(), ...(init.headers ?? {}) } });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'No fue posible completar la operación del planeador.');
  }
  return response.json() as Promise<T>;
}

function query(filters: Filters): string {
  const params = new URLSearchParams({ year: String(filters.year) });
  for (const key of ['month', 'municipality', 'gestor_user_id', 'template_id'] as const) {
    const value = filters[key];
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  return params.toString();
}

export const fetchCatalog = (projectId: string) => request<PlannerCatalog>(`/${projectId}/catalog`);
export const fetchSettings = (projectId: string) => request<PlannerSettings>(`/${projectId}/settings`);
export const saveSettings = (projectId: string, settings: PlannerSettings & { reason?: string }) => request<PlannerSettings>(`/${projectId}/settings`, { method: 'PUT', body: JSON.stringify(settings) });
export const fetchDashboard = (projectId: string, filters: Filters) => request<PlannerReport>(`/${projectId}/dashboard?${query(filters)}`);
export const fetchTargets = (projectId: string, year: number) => request<PlannerTarget[]>(`/${projectId}/targets?year=${year}`);
export const saveTarget = (projectId: string, target: Omit<PlannerTarget, 'id' | 'version'> & { reason?: string }) => request<{ outcome: string }>(`/${projectId}/targets`, { method: 'PUT', body: JSON.stringify(target) });
export const fetchPlans = (projectId: string, year: number) => request<PlannerPlan[]>(`/${projectId}/plans?year=${year}`);
export const createPlan = (projectId: string, plan: { template_id: string; gestor_user_id?: string | null; start_date: string; end_date: string; planned_quantity: number; planned_participants: number; note?: string }) => request<PlannerPlan>(`/${projectId}/plans`, { method: 'POST', body: JSON.stringify(plan) });
export const reschedulePlan = (planId: string, change: { start_date: string; end_date: string; planned_quantity: number; reason: string }) => request<PlannerPlan>(`/plans/${planId}/reschedule`, { method: 'PATCH', body: JSON.stringify(change) });
export const cancelPlan = (planId: string, reason: string) => request<PlannerPlan>(`/plans/${planId}/cancel`, { method: 'POST', body: JSON.stringify({ reason }) });
export const fetchPopulation = (projectId: string, year: number) => request<PlannerPopulation[]>(`/${projectId}/population?year=${year}`);
export const savePopulation = (projectId: string, row: { year: number; municipality: string; families: number; participants: number; source?: string; reason?: string }) => request<PlannerPopulation>(`/${projectId}/population`, { method: 'PUT', body: JSON.stringify(row) });
export const closeCut = (projectId: string, year: number, month: number) => request<{ id: string }>(`/${projectId}/cuts`, { method: 'POST', body: JSON.stringify({ year, month }) });

export async function importTargets(projectId: string, file: File, previewOnly: boolean): Promise<ImportResult> {
  const body = new FormData();
  body.append('upload', file);
  body.append('preview_only', String(previewOnly));
  const response = await fetch(`${API}/planner/${projectId}/targets/import`, { method: 'POST', headers: authorizationHeader(), body });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null))?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'No fue posible procesar el archivo de metas.');
  }
  return response.json();
}

async function download(url: string, filename: string, init: RequestInit = {}): Promise<void> {
  const response = await fetch(url, { ...init, headers: { ...authorizationHeader(), ...(init.headers ?? {}) } });
  if (!response.ok) throw new Error('No fue posible descargar el archivo.');
  const href = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(href);
}

export const downloadExcel = (projectId: string, filters: Filters) => download(`${API}/planner/${projectId}/export.xlsx?${query(filters)}`, `planeador_${filters.year}${filters.month ? `_${String(filters.month).padStart(2, '0')}` : ''}.xlsx`);
export const downloadTemplate = () => download(`${API}/planner/targets/template.csv`, 'plantilla_metas.csv');
export function downloadImportErrors(projectId: string, file: File): Promise<void> {
  const body = new FormData();
  body.append('upload', file);
  return download(`${API}/planner/${projectId}/targets/import/errors.csv`, 'errores_metas.csv', { method: 'POST', body });
}

/** «Sin meta» cuando no hay meta; el valor real aunque pase de 100 %. */
export function formatCompliance(value: number | null, noGoal: string): string {
  return value === null ? noGoal : `${value.toLocaleString('es-CO', { maximumFractionDigits: 2 })} %`;
}
