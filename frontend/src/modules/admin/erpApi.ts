export type ErpInventoryItem = {
  id: string;
  project_id: string;
  sku: string;
  name: string;
  unit: string;
  quantity_on_hand: string;
  created_at: string;
};

export type ErpInventoryMovement = {
  id: string;
  item_id: string;
  quantity_delta: string;
  reference_record_id?: string | null;
  reason: string;
  created_at: string;
};

export type ErpPayrollEntry = {
  id: string;
  project_id: string;
  gestor_user_id: string;
  amount: string;
  reference_record_id?: string | null;
  status: string;
  created_at: string;
  paid_at?: string | null;
};

export type ErpTemplateConfig = {
  id: string;
  template_id: string;
  sku_field_name: string;
  quantity_field_name: string;
  fee_amount: string;
  created_at: string;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function headers(): HeadersInit {
  return { ...authorizationHeader(), 'Content-Type': 'application/json' };
}

async function parseOrThrow<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  return response.json();
}

export async function fetchInventoryItems(projectId: string): Promise<ErpInventoryItem[]> {
  const response = await fetch(`${API_BASE_URL}/erp/inventory/project/${projectId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar el inventario.');
}

export async function createInventoryItem(payload: { projectId: string; sku: string; name: string; unit: string; quantityOnHand: string }): Promise<ErpInventoryItem> {
  const response = await fetch(`${API_BASE_URL}/erp/inventory`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ project_id: payload.projectId, sku: payload.sku, name: payload.name, unit: payload.unit, quantity_on_hand: payload.quantityOnHand }),
  });
  return parseOrThrow(response, 'No fue posible crear el item de inventario.');
}

export async function fetchInventoryMovements(itemId: string): Promise<ErpInventoryMovement[]> {
  const response = await fetch(`${API_BASE_URL}/erp/inventory/${itemId}/movements`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar los movimientos.');
}

export async function fetchPayrollEntries(projectId: string, gestorUserId?: string): Promise<ErpPayrollEntry[]> {
  const params = new URLSearchParams();
  if (gestorUserId) params.set('gestor_user_id', gestorUserId);
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/erp/payroll/project/${projectId}${query}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar los honorarios.');
}

export async function markPayrollEntryPaid(entryId: string): Promise<ErpPayrollEntry> {
  const response = await fetch(`${API_BASE_URL}/erp/payroll/${entryId}/mark-paid`, { method: 'PATCH', headers: headers() });
  return parseOrThrow(response, 'No fue posible marcar el honorario como pagado.');
}

export async function createTemplateConfig(payload: { templateId: string; skuFieldName: string; quantityFieldName: string; feeAmount: string }): Promise<ErpTemplateConfig> {
  const response = await fetch(`${API_BASE_URL}/erp/template-config`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ template_id: payload.templateId, sku_field_name: payload.skuFieldName, quantity_field_name: payload.quantityFieldName, fee_amount: payload.feeAmount }),
  });
  return parseOrThrow(response, 'No fue posible vincular la plantilla al ERP.');
}

export async function fetchTemplateConfig(templateId: string): Promise<ErpTemplateConfig | null> {
  const response = await fetch(`${API_BASE_URL}/erp/template-config/${templateId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar la configuracion de la plantilla.');
}
