export type ApprovalFlow = {
  id: string;
  project_id: string;
  template_id?: string | null;
  name: string;
  description?: string | null;
  flow_version: number;
  status: string;
  created_at?: string | null;
};

export type ApprovalFlowStep = {
  id: string;
  flow_id: string;
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
  created_at?: string | null;
};

export type ApprovalFlowDetail = ApprovalFlow & { steps: ApprovalFlowStep[] };

import { authorizationHeader, jsonAuthHeaders } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function headers() {
  return authorizationHeader();
}

function jsonHeaders() {
  return jsonAuthHeaders();
}

export async function fetchApprovalFlows(projectId: string, templateId = ''): Promise<ApprovalFlow[]> {
  const query = templateId.trim() ? `?template_id=${encodeURIComponent(templateId.trim())}` : '';
  const response = await fetch(`${API_BASE_URL}/approval-flows/${projectId}${query}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar los flujos de aprobación.');
  return response.json();
}

export async function fetchApprovalFlowDetail(flowId: string): Promise<ApprovalFlowDetail> {
  const response = await fetch(`${API_BASE_URL}/approval-flows/detail/${flowId}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar el detalle del flujo.');
  return response.json();
}

export async function createApprovalFlow(payload: {
  projectId: string;
  templateId?: string;
  name: string;
  description?: string;
  status: string;
}): Promise<ApprovalFlow> {
  const response = await fetch(`${API_BASE_URL}/approval-flows/`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({
      project_id: payload.projectId,
      template_id: payload.templateId?.trim() || null,
      name: payload.name,
      description: payload.description || null,
      status: payload.status,
    }),
  });
  if (!response.ok) throw new Error('No fue posible crear el flujo. Verifica permisos administrativos.');
  return response.json();
}

export async function updateApprovalFlow(flowId: string, payload: {
  templateId?: string | null;
  name?: string;
  description?: string | null;
  status?: string;
}): Promise<ApprovalFlow> {
  const response = await fetch(`${API_BASE_URL}/approval-flows/${flowId}`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify({
      template_id: payload.templateId,
      name: payload.name,
      description: payload.description,
      status: payload.status,
    }),
  });
  if (!response.ok) throw new Error('No fue posible actualizar el flujo.');
  return response.json();
}

export async function addApprovalFlowStep(payload: {
  flowId: string;
  stepOrder: number;
  name: string;
  actionLabel: string;
  action: string;
  statusAfter: string;
  requiredPermission: string;
  approverUserId?: string;
  approverRoleId?: string;
  requireAll: boolean;
  status: string;
}): Promise<ApprovalFlowStep> {
  const response = await fetch(`${API_BASE_URL}/approval-flows/steps`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({
      flow_id: payload.flowId,
      step_order: payload.stepOrder,
      name: payload.name,
      action_label: payload.actionLabel,
      action: payload.action,
      status_after: payload.statusAfter,
      required_permission: payload.requiredPermission,
      approver_user_id: payload.approverUserId?.trim() || null,
      approver_role_id: payload.approverRoleId?.trim() || null,
      require_all: payload.requireAll,
      status: payload.status,
    }),
  });
  if (!response.ok) throw new Error('No fue posible agregar el paso al flujo.');
  return response.json();
}

export async function updateApprovalFlowStep(stepId: string, payload: {
  stepOrder?: number;
  name?: string;
  actionLabel?: string;
  action?: string;
  statusAfter?: string;
  requiredPermission?: string;
  approverUserId?: string | null;
  approverRoleId?: string | null;
  requireAll?: boolean;
  status?: string;
}): Promise<ApprovalFlowStep> {
  const response = await fetch(`${API_BASE_URL}/approval-flows/steps/${stepId}`, {
    method: 'PATCH',
    headers: jsonHeaders(),
    body: JSON.stringify({
      step_order: payload.stepOrder,
      name: payload.name,
      action_label: payload.actionLabel,
      action: payload.action,
      status_after: payload.statusAfter,
      required_permission: payload.requiredPermission,
      approver_user_id: payload.approverUserId,
      approver_role_id: payload.approverRoleId,
      require_all: payload.requireAll,
      status: payload.status,
    }),
  });
  if (!response.ok) throw new Error('No fue posible actualizar el paso.');
  return response.json();
}
