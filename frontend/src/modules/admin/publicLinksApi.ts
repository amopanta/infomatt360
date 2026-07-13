export type PublicFormLink = {
  id: string;
  project_id: string;
  template_id: string;
  label?: string | null;
  max_submissions?: number | null;
  submission_count: number;
  expires_at?: string | null;
  revoked_at?: string | null;
  created_at: string;
};

export type PublicFormLinkIssued = PublicFormLink & { token: string };

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

export async function fetchPublicLinks(templateId: string): Promise<PublicFormLink[]> {
  const response = await fetch(`${API_BASE_URL}/public-forms/links/${templateId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar los enlaces publicos.');
}

export async function createPublicLink(payload: { templateId: string; label?: string; maxSubmissions?: number; expiresInHours?: number }): Promise<PublicFormLinkIssued> {
  const response = await fetch(`${API_BASE_URL}/public-forms/links`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      template_id: payload.templateId,
      label: payload.label || null,
      max_submissions: payload.maxSubmissions || null,
      expires_in_hours: payload.expiresInHours || null,
    }),
  });
  return parseOrThrow(response, 'No fue posible generar el enlace publico.');
}

export async function revokePublicLink(linkId: string): Promise<PublicFormLink> {
  const response = await fetch(`${API_BASE_URL}/public-forms/links/${linkId}/revoke`, { method: 'POST', headers: headers() });
  return parseOrThrow(response, 'No fue posible revocar el enlace publico.');
}
