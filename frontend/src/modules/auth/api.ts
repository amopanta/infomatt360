import type { AuthSession } from './types';
import { currentAccessToken, setAccessToken } from './session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type TokenPair = { access_token: string; refresh_token?: string | null };
type LoginResult = { access_token?: string | null; refresh_token?: string | null; mfa_required: boolean; mfa_challenge_token?: string | null };

export async function login(email: string, password: string): Promise<LoginResult> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error('Correo o contraseña incorrectos.');
  return response.json();
}

export async function verifyMfa(challengeToken: string, code: string): Promise<TokenPair> {
  const response = await fetch(`${API_BASE_URL}/auth/mfa/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ challenge_token: challengeToken, code }),
  });
  if (!response.ok) throw new Error('El código MFA no es válido o ya fue utilizado.');
  return response.json();
}

export async function fetchSession(token = currentAccessToken()): Promise<AuthSession> {
  let activeToken = token;
  let response = await fetch(`${API_BASE_URL}/auth/session`, { headers: { Authorization: `Bearer ${activeToken}` } });
  if (response.status === 401) {
    activeToken = await refreshAccessToken();
    response = await fetch(`${API_BASE_URL}/auth/session`, { headers: { Authorization: `Bearer ${activeToken}` } });
  }
  if (!response.ok) throw new Error('La sesión expiró.');
  return response.json();
}

export async function refreshAccessToken(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({}),
  });
  if (!response.ok) throw new Error('La sesión expiró.');
  const tokens: TokenPair = await response.json();
  setAccessToken(tokens.access_token);
  return tokens.access_token;
}

export async function logout(token = currentAccessToken()): Promise<void> {
  if (!token) return;
  await fetch(`${API_BASE_URL}/auth/logout`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    credentials: 'include',
  });
}

export async function requestPasswordReset(email: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/password/forgot`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email }) });
  if (!response.ok) throw new Error('No fue posible procesar la solicitud.');
  return (await response.json()).message;
}

export async function resetPassword(token: string, newPassword: string, confirmPassword: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/password/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, new_password: newPassword, confirm_password: confirmPassword }) });
  if (!response.ok) throw new Error('El enlace es inválido, venció o la contraseña no cumple la política.');
  return (await response.json()).message;
}

export async function changePassword(token: string, currentPassword: string, newPassword: string, confirmPassword: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/password/change`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ current_password: currentPassword, new_password: newPassword, confirm_password: confirmPassword }) });
  if (!response.ok) throw new Error('No fue posible cambiar la contraseña. Verifica la contraseña actual y usa al menos 15 caracteres.');
  return (await response.json()).message;
}
