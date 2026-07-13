export type XlsformImportResult = {
  template_id: string;
  imported_fields: number;
  warnings: string[];
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

async function parseOrThrow<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  return response.json();
}

export async function importXlsform(projectId: string, file: File): Promise<XlsformImportResult> {
  const body = new FormData();
  body.append('project_id', projectId);
  body.append('upload', file);
  const response = await fetch(`${API_BASE_URL}/xlsform/import`, { method: 'POST', headers: authorizationHeader(), body });
  return parseOrThrow(response, 'No fue posible importar el archivo XLSForm.');
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
