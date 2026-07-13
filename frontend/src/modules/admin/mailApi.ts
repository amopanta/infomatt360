export type MailProfile = {
  id: string;
  project_id: string;
  name: string;
  provider: string;
  sender_email: string;
  server_host?: string | null;
  server_port?: string | null;
  config_json?: string | null;
  is_default: boolean;
  status: string;
};

export type MailAutoconfigSuggestion = {
  found: boolean;
  sender_email?: string | null;
  server_host?: string | null;
  server_port?: string | null;
  use_tls?: boolean | null;
};

export type MailTestSendResponse = {
  sent: boolean;
  detail: string;
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

export async function suggestMailAutoconfig(email: string): Promise<MailAutoconfigSuggestion> {
  const response = await fetch(`${API_BASE_URL}/messages/profiles/autoconfig?email=${encodeURIComponent(email)}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar la sugerencia de configuracion.');
}

export async function fetchMailProfiles(projectId: string): Promise<MailProfile[]> {
  const response = await fetch(`${API_BASE_URL}/messages/profiles/${projectId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar los perfiles de correo.');
}

export type MailProfileCreatePayload = {
  projectId: string;
  name: string;
  senderEmail: string;
  serverHost?: string;
  serverPort?: string;
  useTls?: boolean;
  username?: string;
  password?: string;
  isDefault?: boolean;
};

export async function createMailProfile(payload: MailProfileCreatePayload): Promise<MailProfile> {
  const configJson = JSON.stringify({ use_tls: payload.useTls ?? true, username: payload.username || undefined, password: payload.password || undefined });
  const response = await fetch(`${API_BASE_URL}/messages/profiles`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      project_id: payload.projectId,
      name: payload.name,
      sender_email: payload.senderEmail,
      server_host: payload.serverHost || null,
      server_port: payload.serverPort || null,
      config_json: configJson,
      is_default: payload.isDefault ?? false,
    }),
  });
  return parseOrThrow(response, 'No fue posible crear el perfil de correo.');
}

export async function testSendMailProfile(profileId: string): Promise<MailTestSendResponse> {
  const response = await fetch(`${API_BASE_URL}/messages/profiles/${profileId}/test-send`, { method: 'POST', headers: headers() });
  return parseOrThrow(response, 'No fue posible enviar el correo de prueba.');
}
