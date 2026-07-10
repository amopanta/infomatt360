import { jsonAuthHeaders } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function headers() {
  return jsonAuthHeaders();
}

export async function fetchMfaStatus(): Promise<{ enabled: boolean; recovery_codes_remaining: number }> {
  const response = await fetch(`${API_BASE_URL}/auth/mfa/status`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar MFA.');
  return response.json();
}

export async function setupMfa(currentPassword: string): Promise<{ secret: string; provisioning_uri: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/mfa/setup`, { method: 'POST', headers: headers(), body: JSON.stringify({ current_password: currentPassword }) });
  if (!response.ok) throw new Error('No fue posible iniciar la activación. Verifica tu contraseña.');
  return response.json();
}

export async function confirmMfa(code: string): Promise<{ message: string; recovery_codes: string[] }> {
  const response = await fetch(`${API_BASE_URL}/auth/mfa/confirm`, { method: 'POST', headers: headers(), body: JSON.stringify({ code }) });
  if (!response.ok) throw new Error('El código no es válido.');
  return response.json();
}

export async function disableMfa(currentPassword: string, code: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/mfa/disable`, { method: 'POST', headers: headers(), body: JSON.stringify({ current_password: currentPassword, code }) });
  if (!response.ok) throw new Error('No fue posible desactivar MFA.');
}
