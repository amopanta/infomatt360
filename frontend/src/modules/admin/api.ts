export type AdminUser = { id: string; full_name: string; email: string; status: string; must_change_password: boolean; mfa_enabled: boolean };

import { jsonAuthHeaders } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
function headers() { return jsonAuthHeaders(); }

export async function fetchAdminUsers(projectId: string): Promise<AdminUser[]> {
  const response = await fetch(`${API_BASE_URL}/security/admin/projects/${projectId}/users`, { headers: headers() });
  if (!response.ok) throw new Error('No tienes permiso para administrar usuarios en este proyecto.');
  return response.json();
}

export async function updateUserEmail(projectId: string, userId: string, email: string, adminPassword: string): Promise<AdminUser> {
  const response = await fetch(`${API_BASE_URL}/security/admin/projects/${projectId}/users/${userId}/email`, { method: 'PATCH', headers: headers(), body: JSON.stringify({ email, admin_password: adminPassword }) });
  if (!response.ok) throw new Error('No fue posible actualizar el correo. Verifica permisos, contraseña y duplicados.');
  return response.json();
}

export async function resetUserPassword(projectId: string, userId: string, adminPassword: string, temporaryPassword?: string): Promise<{ message: string; temporary_password?: string | null }> {
  const response = await fetch(`${API_BASE_URL}/security/admin/projects/${projectId}/users/${userId}/password-reset`, { method: 'POST', headers: headers(), body: JSON.stringify({ admin_password: adminPassword, temporary_password: temporaryPassword || null }) });
  if (!response.ok) throw new Error('No fue posible reiniciar la contraseña. Verifica permisos y contraseña administrativa.');
  return response.json();
}

export async function resetUserMfa(projectId: string, userId: string, adminPassword: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/security/admin/projects/${projectId}/users/${userId}/mfa-reset`, { method: 'POST', headers: headers(), body: JSON.stringify({ admin_password: adminPassword }) });
  if (!response.ok) throw new Error('No fue posible reiniciar MFA. Verifica permisos y contraseña administrativa.');
  return (await response.json()).message;
}
