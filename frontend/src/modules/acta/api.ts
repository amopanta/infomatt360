import { authorizationHeader, jsonAuthHeaders } from '../auth/session';
import type { ActaFieldOption, ActaLayout, ActaTemplateSummary } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

/** Fetch compartido por las 4 variantes de generación de acta (descarga y
 * ahora impresión, docs/96 item #10): mismo POST + headers + manejo de
 * error, solo cambia qué se hace con la respuesta binaria. */
async function fetchActaBinary(url: string, body: unknown, errorMessage: string): Promise<Response> {
  const response = await fetch(url, { method: 'POST', headers: jsonAuthHeaders(), body: JSON.stringify(body) });
  if (!response.ok) throw new Error((await safeErrorDetail(response)) ?? errorMessage);
  return response;
}

function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function fetchActaTemplates(projectId: string): Promise<ActaTemplateSummary[]> {
  const response = await fetch(`${API_BASE_URL}/acta-templates/project/${projectId}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar las plantillas de acta.');
  return response.json();
}

export async function createActaLayoutTemplate(payload: { project_id: string; name: string; template_id: string; layout: ActaLayout }): Promise<ActaTemplateSummary> {
  const response = await fetch(`${API_BASE_URL}/acta-templates/layout`, { method: 'POST', headers: jsonAuthHeaders(), body: JSON.stringify(payload) });
  if (!response.ok) throw new Error((await safeErrorDetail(response)) ?? 'No fue posible crear la plantilla de acta.');
  return response.json();
}

export async function updateActaLayoutTemplate(templateId: string, payload: { project_id: string; name: string; template_id: string; layout: ActaLayout }): Promise<ActaTemplateSummary> {
  const response = await fetch(`${API_BASE_URL}/acta-templates/${templateId}/layout`, { method: 'PUT', headers: jsonAuthHeaders(), body: JSON.stringify(payload) });
  if (!response.ok) throw new Error((await safeErrorDetail(response)) ?? 'No fue posible guardar la plantilla de acta.');
  return response.json();
}

/** Descarga el PDF generado a partir de un registro real, mismo patron de
 * blob que `downloadReportSummary` (ver frontend/src/modules/reports/api.ts). */
export async function renderActaFromRecord(templateId: string, recordId: string, fileNameHint: string): Promise<void> {
  const response = await fetchActaBinary(`${API_BASE_URL}/acta-templates/${templateId}/render-from-record`, { record_id: recordId }, 'No fue posible generar el acta.');
  downloadBlob(await response.blob(), `${fileNameHint}.pdf`);
}

/** Imprime el acta de un registro en el cliente de escritorio (docs/96 item
 * #10): pide el mismo PDF que `renderActaFromRecord` pero via
 * `arrayBuffer()` en vez de disparar una descarga, y lo entrega a
 * `window.desktopBridge` para impresión nativa (`webContents.print`). Solo
 * disponible dentro de Electron -- lanza si `desktopBridge` no existe. */
export async function printActaFromRecord(templateId: string, recordId: string, deviceName: string | undefined, copies: number) {
  if (!window.desktopBridge) throw new Error('La impresión nativa solo está disponible en el cliente de escritorio.');
  const response = await fetchActaBinary(`${API_BASE_URL}/acta-templates/${templateId}/render-from-record`, { record_id: recordId }, 'No fue posible generar el acta.');
  const pdfBytes = await response.arrayBuffer();
  return window.desktopBridge.printDocument({ pdfBytes, deviceName, copies });
}

export type ActaBatchSelection = { recordIds?: string[]; search?: string; status?: string; unlinkedOnly?: boolean };
export type ActaBatchPayload = { record_ids: string[] | null; search: string | null; status: string | null; unlinked_only: boolean };

/** `record_ids` tiene prioridad sobre los filtros -- nunca se combinan ambos
 * caminos, mismo criterio que `ActaRenderBatchRequest` en el backend (ver
 * docs/110). Extraida como funcion pura para poder probarla sin mockear
 * `fetch` (ver `frontend/src/modules/enrollment/api.test.ts`). */
export function buildBatchPayload(selection: ActaBatchSelection): ActaBatchPayload {
  return {
    record_ids: selection.recordIds?.length ? selection.recordIds : null,
    search: selection.search || null,
    status: selection.status || null,
    unlinked_only: selection.unlinkedOnly ?? false,
  };
}

/** Descarga un ZIP con un PDF por registro (docs/96 item #5, docs/110),
 * mismo patron de blob que `renderActaFromRecord`. */
export async function renderActaBatch(templateId: string, selection: ActaBatchSelection, fileNameHint: string): Promise<void> {
  const response = await fetchActaBinary(`${API_BASE_URL}/acta-templates/${templateId}/render-batch`, buildBatchPayload(selection), 'No fue posible generar el lote de actas.');
  downloadBlob(await response.blob(), `${fileNameHint}.zip`);
}

/** Imprime un lote de actas (docs/96 items #5/#10): mismo ZIP que
 * `renderActaBatch`, entregado a `window.desktopBridge.printBatch` para
 * que el proceso principal lo desempaquete e imprima secuencialmente
 * (`desktop/src/printing.js::printBatchZip`). */
export async function printActaBatch(templateId: string, selection: ActaBatchSelection, deviceName: string | undefined, copies: number) {
  if (!window.desktopBridge) throw new Error('La impresión nativa solo está disponible en el cliente de escritorio.');
  const response = await fetchActaBinary(`${API_BASE_URL}/acta-templates/${templateId}/render-batch`, buildBatchPayload(selection), 'No fue posible generar el lote de actas.');
  const zipBytes = await response.arrayBuffer();
  return window.desktopBridge.printBatch({ zipBytes, deviceName, copies });
}

/** Reusa `GET /builder/components/{template_id}` (ya existente para el
 * constructor de formularios) para poblar los selectores de campo del
 * bloque tabla y el helper de tokens del bloque encabezado. */
export async function fetchTemplateFields(templateId: string): Promise<ActaFieldOption[]> {
  const response = await fetch(`${API_BASE_URL}/builder/components/${templateId}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar los campos del formulario.');
  const components: Array<{ name: string; label: string }> = await response.json();
  return components.map((component) => ({ name: component.name, label: component.label }));
}

async function safeErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = await response.json();
    return typeof body?.detail === 'string' ? body.detail : null;
  } catch {
    return null;
  }
}
