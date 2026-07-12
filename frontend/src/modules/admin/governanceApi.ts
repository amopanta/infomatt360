export type TenantCleanResult = {
  organization_id: string;
  projects_purged: string[];
  deleted_counts: Record<string, number>;
};

export type EmergencyAccessKey = {
  id: string;
  project_id: string;
  user_id: string;
  issued_by: string;
  purpose?: string | null;
  expires_at: string;
  used_at?: string | null;
  revoked_at?: string | null;
  created_at: string;
};

export type EmergencyAccessKeyIssued = EmergencyAccessKey & { code: string };

export type SupportTicket = {
  id: string;
  project_id: string;
  created_by: string;
  subject: string;
  description: string;
  status: string;
  resolution_channel: string;
  matched_rule?: string | null;
  auto_response_text?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
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

export async function runTenantClean(payload: { organizationId: string; confirmSlug: string; totpCode: string }): Promise<TenantCleanResult> {
  const response = await fetch(`${API_BASE_URL}/organizations/${payload.organizationId}/tenant-clean`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ confirm_slug: payload.confirmSlug, totp_code: payload.totpCode }),
  });
  return parseOrThrow(response, 'No fue posible ejecutar la purga de la organizacion.');
}

export async function issueEmergencyKey(payload: { projectId: string; userId: string; hoursValid: number; purpose?: string }): Promise<EmergencyAccessKeyIssued> {
  const response = await fetch(`${API_BASE_URL}/emergency-access/keys`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ project_id: payload.projectId, user_id: payload.userId, hours_valid: payload.hoursValid, purpose: payload.purpose || null }),
  });
  return parseOrThrow(response, 'No fue posible emitir la credencial de emergencia.');
}

export async function fetchEmergencyKeys(projectId: string): Promise<EmergencyAccessKey[]> {
  const response = await fetch(`${API_BASE_URL}/emergency-access/keys/project/${projectId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar las credenciales de emergencia.');
}

export async function revokeEmergencyKey(keyId: string): Promise<EmergencyAccessKey> {
  const response = await fetch(`${API_BASE_URL}/emergency-access/keys/${keyId}/revoke`, { method: 'POST', headers: headers() });
  return parseOrThrow(response, 'No fue posible revocar la credencial.');
}

export async function createSupportTicket(payload: { projectId: string; subject: string; description: string }): Promise<SupportTicket> {
  const response = await fetch(`${API_BASE_URL}/support/tickets`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ project_id: payload.projectId, subject: payload.subject, description: payload.description }),
  });
  return parseOrThrow(response, 'No fue posible reportar el ticket de soporte.');
}

export async function fetchSupportTickets(projectId: string, statusFilter?: string): Promise<SupportTicket[]> {
  const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : '';
  const response = await fetch(`${API_BASE_URL}/support/tickets/project/${projectId}${query}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar los tickets de soporte.');
}

export async function resolveSupportTicket(ticketId: string): Promise<SupportTicket> {
  const response = await fetch(`${API_BASE_URL}/support/tickets/${ticketId}/resolve`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({}),
  });
  return parseOrThrow(response, 'No fue posible resolver el ticket.');
}
