export type ReportTemplateMetric = {
  template_id: string;
  template_name: string;
  template_status: string;
  records_total: number;
  records_by_status: Record<string, number>;
  percent_of_total: number;
  last_record_at?: string | null;
};

export type ReportProjectSummary = {
  project_id: string;
  records_total: number;
  records_by_status: Record<string, number>;
  templates: ReportTemplateMetric[];
  generated_at: string;
};

import { authorizationHeader, jsonAuthHeaders } from '../auth/session';
import type { ReportBoard, ReportWidget } from './types'; // solo tipos: sin ciclo en tiempo de ejecucion (types.ts importa ReportProjectSummary de este archivo)

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function fetchReportSummary(projectId: string): Promise<ReportProjectSummary> {
  const response = await fetch(`${API_BASE_URL}/reports/project/${projectId}/summary`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible cargar el reporte del proyecto.');
  return response.json();
}

/** Constructor visual de tableros (docs/96 item #6, docs/111). El servidor
 * resuelve todo en un solo response -- ver `ReportBoard` en ./types. */
export async function fetchReportBoard(projectId: string): Promise<ReportBoard> {
  const response = await fetch(`${API_BASE_URL}/reports/project/${projectId}/board`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error((await safeErrorDetail(response)) ?? 'No fue posible cargar el tablero.');
  return response.json();
}

export async function saveReportBoard(projectId: string, widgets: ReportWidget[]): Promise<ReportBoard> {
  const response = await fetch(`${API_BASE_URL}/reports/project/${projectId}/board`, {
    method: 'PUT',
    headers: jsonAuthHeaders(),
    body: JSON.stringify({ project_id: projectId, widgets }),
  });
  if (!response.ok) throw new Error((await safeErrorDetail(response)) ?? 'No fue posible guardar el tablero.');
  return response.json();
}

async function safeErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json();
    return typeof body?.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}

/** Mapa nombre-de-campo -> component_type, para saber en el constructor de
 * tableros que campos admiten agregaciones numericas (suma/promedio/min/max)
 * y cuales solo admiten conteo. Reusa el mismo endpoint que ya usa
 * `fetchTemplateFields` en el constructor de actas (docs/109), pero
 * conservando `component_type` en vez de descartarlo. */
export async function fetchTemplateFieldTypes(templateId: string): Promise<Record<string, string>> {
  const response = await fetch(`${API_BASE_URL}/builder/components/${templateId}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar los campos del formulario.');
  const components: Array<{ name: string; component_type: string }> = await response.json();
  return Object.fromEntries(components.map((component) => [component.name, component.component_type]));
}

export async function downloadReportSummary(projectId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/reports/project/${projectId}/summary.xlsx`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible exportar el reporte.');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `reporte-${projectId}.xlsx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
