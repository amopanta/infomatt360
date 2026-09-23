export type XlsformImportResult = {
  template_id: string;
  imported_fields: number;
  warnings: string[];
  replaced: boolean;
};
export type XlsformPreview = { format: string; filename: string; file_sha256: string; target_sha256: string | null; added: string[]; removed: string[]; modified: Array<{ name: string; changes: string[] }>; warnings: string[]; errors: string[] };
export type FormVersionSummary = { id: string; version_number: number; status: string; created_at: string; question_count: number };

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

async function parseOrThrow<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  return response.json();
}

export async function importXlsform(projectId: string, file: File, replaceTemplateId?: string, preview?: XlsformPreview): Promise<XlsformImportResult> {
  const body = new FormData();
  body.append('project_id', projectId);
  body.append('upload', file);
  if (replaceTemplateId) body.append('replace_template_id', replaceTemplateId);
  if (preview) { body.append('expected_file_sha256', preview.file_sha256); if (preview.target_sha256) body.append('expected_target_sha256', preview.target_sha256); }
  const response = await fetch(`${API_BASE_URL}/xlsform/import`, { method: 'POST', headers: authorizationHeader(), body });
  return parseOrThrow(response, 'No fue posible importar el archivo XLSForm.');
}

export async function previewXlsform(projectId: string, file: File, replaceTemplateId?: string): Promise<XlsformPreview> {
  const body = new FormData(); body.append('project_id', projectId); body.append('upload', file);
  if (replaceTemplateId) body.append('replace_template_id', replaceTemplateId);
  const response = await fetch(`${API_BASE_URL}/xlsform/preview`, { method: 'POST', headers: authorizationHeader(), body });
  return parseOrThrow(response, 'No se pudo validar el XLSForm.');
}

export function listFormVersions(templateId: string): Promise<FormVersionSummary[]> {
  return fetch(`${API_BASE_URL}/xlsform/versions/${templateId}`, { headers: authorizationHeader() }).then((response) => parseOrThrow(response, 'No se pudo consultar el historial.'));
}

export function restoreFormVersion(templateId: string, versionId: string): Promise<FormVersionSummary> {
  return fetch(`${API_BASE_URL}/xlsform/versions/${templateId}/${versionId}/restore`, { method: 'POST', headers: authorizationHeader() }).then((response) => parseOrThrow(response, 'No se pudo restaurar la versión.'));
}

async function downloadBlob(url: string, filename: string, fallbackMessage: string): Promise<void> {
  const response = await fetch(url, { headers: authorizationHeader() });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

export async function exportXlsform(templateId: string, templateName: string): Promise<void> {
  const filename = `${templateName.replace(/[^a-zA-Z0-9-_]+/g, '_') || 'formulario'}.xlsx`;
  await downloadBlob(`${API_BASE_URL}/xlsform/export/${templateId}`, filename, 'No fue posible exportar la plantilla a XLSForm.');
}

export async function downloadMasterTemplate(projectId: string): Promise<void> {
  await downloadBlob(`${API_BASE_URL}/xlsform/master-template?project_id=${encodeURIComponent(projectId)}`, 'plantilla_maestra_infomatt360.xlsx', 'No fue posible descargar la plantilla maestra.');
}
