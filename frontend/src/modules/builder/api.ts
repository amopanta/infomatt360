/**
 * Proyecto: InfoMatt360
 * Modulo: Builder API Client
 * Responsabilidad: Centralizar llamadas al backend del constructor visual.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('infomatt360_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function createTemplate(params: { projectId: string; name: string; description?: string }) {
  const response = await fetch(`${API_BASE_URL}/builder/templates`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ project_id: params.projectId, name: params.name, description: params.description ?? null }),
  });
  if (!response.ok) throw new Error('No fue posible crear la plantilla.');
  return response.json();
}

export async function createPage(params: { templateId: string; title: string; sortOrder?: number }) {
  const response = await fetch(`${API_BASE_URL}/builder/pages`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ template_id: params.templateId, title: params.title, sort_order: params.sortOrder ?? 0 }),
  });
  if (!response.ok) throw new Error('No fue posible crear la pagina.');
  return response.json();
}

export async function createSection(params: { pageId: string; title: string; sortOrder?: number }) {
  const response = await fetch(`${API_BASE_URL}/builder/sections`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ page_id: params.pageId, title: params.title, sort_order: params.sortOrder ?? 0 }),
  });
  if (!response.ok) throw new Error('No fue posible crear la seccion.');
  return response.json();
}

export async function createRow(params: { sectionId: string; sortOrder?: number }) {
  const response = await fetch(`${API_BASE_URL}/builder/rows`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ section_id: params.sectionId, sort_order: params.sortOrder ?? 0 }),
  });
  if (!response.ok) throw new Error('No fue posible crear la fila.');
  return response.json();
}

export async function createColumn(params: { rowId: string; desktopWidth: number; tabletWidth?: number; mobileWidth?: number; sortOrder?: number }) {
  const response = await fetch(`${API_BASE_URL}/builder/columns`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ row_id: params.rowId, desktop_width: params.desktopWidth, tablet_width: params.tabletWidth ?? 12, mobile_width: params.mobileWidth ?? 12, sort_order: params.sortOrder ?? 0 }),
  });
  if (!response.ok) throw new Error('No fue posible crear la columna.');
  return response.json();
}

export async function createComponent(params: { templateId: string; columnId: string; type: string; name: string; label: string; sortOrder?: number }) {
  const response = await fetch(`${API_BASE_URL}/builder/components`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ template_id: params.templateId, column_id: params.columnId, component_type: params.type, name: params.name, label: params.label, sort_order: params.sortOrder ?? 0 }),
  });
  if (!response.ok) throw new Error('No fue posible crear el componente.');
  return response.json();
}
