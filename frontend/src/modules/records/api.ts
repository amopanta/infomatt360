export type RecordValue = { id: string; field_name: string; field_value_json: string };
export type RuntimeRecord = { id: string; status: string; submitted_by?: string | null; approval_flow_id?: string | null; approval_flow_version?: string | null; lock_version: number; created_at: string; updated_at: string; values: RecordValue[] };
export type RuntimeRecordPage = { items: RuntimeRecord[]; total: number; limit: number; offset: number };
export type TemplateSummary = { id: string; name: string; description?: string | null; status: string };
export type ReviewAction = { id: string; project_id: string; record_id: string; from_status?: string | null; to_status: string; action: string; notes?: string | null; rejected_field_name?: string | null; user_id: string; approval_flow_id?: string | null; approval_flow_version?: number | null; created_at?: string | null };
export type ReviewNextAction = { label: string; to_status: string; action: string; required_permission?: string | null; source: string };
export type ReviewApprovalProgress = {
  label: string;
  to_status: string;
  action: string;
  required_count: number;
  approved_count: number;
  pending_count: number;
  approved_user_ids: string[];
  pending_user_ids: string[];
  source: string;
};
export type ReviewFlowSnapshotStep = {
  step_order: number;
  name: string;
  action_label: string;
  action: string;
  status_after: string;
  required_permission: string;
  approver_user_id?: string | null;
  approver_role_id?: string | null;
  require_all: boolean;
  status: string;
};
export type ReviewFlowSnapshot = {
  flow_id?: string | null;
  flow_version?: string | null;
  name?: string | null;
  template_id?: string | null;
  steps: ReviewFlowSnapshotStep[];
};
export type ReviewFlowComparison = {
  has_snapshot: boolean;
  changed: boolean;
  differences: string[];
  snapshot?: ReviewFlowSnapshot | null;
  current?: ReviewFlowSnapshot | null;
};

import { authorizationHeader, jsonAuthHeaders } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
function headers() { return authorizationHeader(); }
function jsonHeaders() { return jsonAuthHeaders(); }

export async function fetchProjectTemplates(projectId: string): Promise<TemplateSummary[]> {
  const response = await fetch(`${API_BASE_URL}/builder/templates/${projectId}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar los formularios del proyecto.');
  return response.json();
}

export async function fetchReviewNextActions(recordId: string): Promise<ReviewNextAction[]> {
  const response = await fetch(`${API_BASE_URL}/review/records/${recordId}/next-actions`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar las acciones de revisión.');
  return response.json();
}

export async function fetchReviewApprovalProgress(recordId: string): Promise<ReviewApprovalProgress[]> {
  const response = await fetch(`${API_BASE_URL}/review/records/${recordId}/approval-progress`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar el progreso de aprobación.');
  return response.json();
}

export async function fetchReviewFlowComparison(recordId: string): Promise<ReviewFlowComparison> {
  const response = await fetch(`${API_BASE_URL}/review/records/${recordId}/flow-comparison`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible comparar el flujo del registro.');
  return response.json();
}

export async function fetchTemplateRecords(templateId: string): Promise<RuntimeRecord[]> {
  const response = await fetch(`${API_BASE_URL}/runtime/template/${templateId}/records`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar los registros.');
  return response.json();
}

/** Consulta un registro puntual por id, sin depender de paginacion/filtros de la busqueda. */
export async function fetchRecord(recordId: string): Promise<RuntimeRecord> {
  const response = await fetch(`${API_BASE_URL}/runtime/record/${recordId}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar el registro.');
  return response.json();
}

export async function searchTemplateRecords(params: { templateId: string; search?: string; status?: string; limit?: number; offset?: number }): Promise<RuntimeRecordPage> {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.status) query.set('status', params.status);
  query.set('limit', String(params.limit ?? 25));
  query.set('offset', String(params.offset ?? 0));
  const response = await fetch(`${API_BASE_URL}/runtime/template/${params.templateId}/records/search?${query.toString()}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar los registros.');
  return response.json();
}

export async function downloadTemplateRecords(templateId: string, filters: { search?: string; status?: string } = {}): Promise<void> {
  const query = new URLSearchParams();
  if (filters.search) query.set('search', filters.search);
  if (filters.status) query.set('status', filters.status);
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const response = await fetch(`${API_BASE_URL}/runtime/template/${templateId}/records/export.csv${suffix}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible exportar los registros.');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `registros-${templateId}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function fetchReviewActions(recordId: string): Promise<ReviewAction[]> {
  const response = await fetch(`${API_BASE_URL}/review/records/${recordId}/actions`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar el historial de revisión.');
  return response.json();
}

/** Corrige el valor de un campo de un registro devuelto ("returned"). Ver docs/92. */
export async function correctRecordField(payload: { recordId: string; fieldName: string; fieldValueJson: string; expectedLockVersion: number }): Promise<RuntimeRecord> {
  const response = await fetch(`${API_BASE_URL}/runtime/record/${payload.recordId}/correction`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify({
      field_name: payload.fieldName,
      field_value_json: payload.fieldValueJson,
      expected_lock_version: payload.expectedLockVersion,
    }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'No fue posible guardar la corrección.');
  }
  return response.json();
}

export async function applyReviewAction(payload: { projectId: string; recordId: string; toStatus: string; action: string; notes?: string; rejectedFieldName?: string }): Promise<ReviewAction> {
  const response = await fetch(`${API_BASE_URL}/review/actions`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({
      project_id: payload.projectId,
      record_id: payload.recordId,
      to_status: payload.toStatus,
      action: payload.action,
      notes: payload.notes || null,
      rejected_field_name: payload.rejectedFieldName || null,
    }),
  });
  if (!response.ok) throw new Error('No fue posible aplicar la acción de revisión.');
  return response.json();
}
