export type AdminUser = { id: string; full_name: string; email: string; status: string; must_change_password: boolean; mfa_enabled: boolean; role_id?: string | null; role_name?: string | null; assignment_status?: string; permissions?: string[]; inherited_permissions?: string[] };
export type AdminRole = { id: string; name: string; permissions: string[] };

import { jsonAuthHeaders } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
function headers() { return jsonAuthHeaders(); }

async function managementRequest<T>(projectId: string, path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/security/admin/projects/${projectId}/${path}`, {
    method, headers: headers(), ...(body ? { body: JSON.stringify(body) } : {}),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof result?.detail === 'string' ? result.detail : 'No fue posible completar la gestión de usuarios.');
  return result;
}

export const fetchAdminRoles = (projectId: string) => managementRequest<AdminRole[]>(projectId, 'roles');
export const fetchGrantablePermissions = (projectId: string) => managementRequest<string[]>(projectId, 'grantable-permissions');
export const createAdminRole = (projectId: string, name: string, permissions: string[], adminPassword: string) =>
  managementRequest<AdminRole>(projectId, 'roles', 'POST', { name, permissions, admin_password: adminPassword });
export const createAdminUser = (projectId: string, data: { full_name: string; document_id: string; email: string; role_id: string }, adminPassword: string) =>
  managementRequest<{ user: AdminUser; temporary_password: string }>(projectId, 'users', 'POST', { ...data, admin_password: adminPassword });
export const updateAdminAccess = (projectId: string, userId: string, roleId: string, assignmentStatus: string, adminPassword: string) =>
  managementRequest<AdminUser>(projectId, `users/${userId}/access`, 'PATCH', { role_id: roleId, assignment_status: assignmentStatus, admin_password: adminPassword });

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

export async function generateEnrollmentQr(projectId: string, userId: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/enrollment/qr`, { method: 'POST', headers: headers(), body: JSON.stringify({ project_id: projectId, user_id: userId }) });
  if (!response.ok) throw new Error('No fue posible generar el codigo QR. Verifica permisos y que el usuario pertenezca al proyecto.');
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
