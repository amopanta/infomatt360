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

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function fetchReportSummary(projectId: string): Promise<ReportProjectSummary> {
  const response = await fetch(`${API_BASE_URL}/reports/project/${projectId}/summary`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible cargar el reporte del proyecto.');
  return response.json();
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
