const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type InstallStatus = { installed: boolean; installer_enforced: boolean };

export type RequirementCheck = { key: string; label: string; status: 'ok' | 'warning' | 'error'; detail?: string | null };
export type InstallRequirements = { ready: boolean; checks: RequirementCheck[] };

export type MailSetup = { sender_email: string; server_host?: string; server_port?: string; username?: string; password?: string; use_tls?: boolean };
export type StorageSetup = { max_file_size_mb: number };
export type BackupSetup = { frequency: 'hourly' | 'daily' | 'weekly' };

export type BootstrapPayload = {
  organization_name: string;
  organization_slug: string;
  organization_public_url?: string;
  project_name: string;
  admin_full_name: string;
  admin_document_id: string;
  admin_email: string;
  admin_password: string;
  mail?: MailSetup;
  storage?: StorageSetup;
  backup?: BackupSetup;
};

export type BootstrapResult = {
  organization_id: string;
  project_id: string;
  role_id: string;
  user_id: string;
  mail_profile_id: string | null;
  storage_profile_id: string | null;
  scheduled_task_id: string | null;
};

/** Base externa PostgreSQL (docs/151). «bundled» = la base incluida. */
export type DatabaseSetup = { mode: 'bundled' | 'external'; host: string; port: number; name: string; username: string; password: string; sslmode?: string | null };
export type DatabaseCheck = { mode: string; server_version?: string | null; empty?: boolean | null; current_revision?: string | null; usable: boolean; foreign_tables: string[]; restarting: boolean };
export type MailServer = { host: string; port: number; username: string; password: string; use_tls: boolean; sender_email: string; test_recipient?: string };
export type RecoverAdmin = { email: string; full_name: string; document_id: string; password: string };

// El código de instalación se guarda solo en esta pestaña: se pierde al cerrarla.
const CODE_KEY = 'infomatt360_install_code';
export function storedInstallCode(): string { try { return sessionStorage.getItem(CODE_KEY) ?? ''; } catch { return ''; } }
export function storeInstallCode(code: string) { try { if (code) sessionStorage.setItem(CODE_KEY, code); else sessionStorage.removeItem(CODE_KEY); } catch { /* sin almacenamiento: se vuelve a pedir */ } }

async function post<T>(path: string, body: unknown, fallback: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/install${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Install-Code': storedInstallCode() },
      body: JSON.stringify(body),
    });
  } catch {
    // Sin respuesta (servidor apagado o reiniciándose): mensaje en español, no «Failed to fetch».
    throw new Error('No hay conexión con el servidor. Espera unos segundos e inténtalo de nuevo.');
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    // FastAPI devuelve los errores de validación como lista: se muestra el campo.
    if (Array.isArray(detail) && detail.length) {
      throw new Error(detail.map((item: { loc?: unknown[]; msg?: string }) => `${(item.loc ?? []).slice(1).join('.')}: ${item.msg ?? ''}`).join(' · '));
    }
    throw new Error(typeof detail === 'string' ? detail : fallback);
  }
  return response.json();
}

export async function fetchInstallStatus(): Promise<InstallStatus> {
  const response = await fetch(`${API_BASE_URL}/install/status`);
  if (!response.ok) throw new Error('No fue posible consultar el estado de instalacion.');
  return response.json();
}

export async function fetchInstallRequirements(): Promise<InstallRequirements> {
  const response = await fetch(`${API_BASE_URL}/install/requirements`);
  return response.json();
}

export const verifyInstallCode = (code: string) => post<{ valid: boolean; kind: 'setup' | 'recovery' }>('/code/verify', { code }, 'Código incorrecto.');
export const testDatabase = (setup: DatabaseSetup) => post<DatabaseCheck>('/database/test', setup, 'No se pudo probar la base de datos.');
export const applyDatabase = (setup: DatabaseSetup) => post<DatabaseCheck>('/database/apply', setup, 'No se pudo usar la base de datos.');
export const testMail = (server: MailServer) => post<{ sent: boolean }>('/mail/test', server, 'No se pudo enviar el correo de prueba.');
export const saveMail = (server: MailServer) => post<{ saved: boolean }>('/mail/save', server, 'No se pudo guardar el correo.');
export const recoverAdmin = (data: RecoverAdmin) => post<{ created: boolean; email: string; projects: string[] }>('/recover-admin', data, 'No se pudo recuperar el acceso.');
export const bootstrapInstallation = (payload: BootstrapPayload) => post<BootstrapResult>('/bootstrap', payload, 'No fue posible completar la instalacion.');

/** Tras cambiar la base, los servicios se reinician: espera a que respondan. */
export async function waitForServer(timeoutMs = 120000): Promise<boolean> {
  const started = Date.now();
  await new Promise((resolve) => setTimeout(resolve, 5000));
  while (Date.now() - started < timeoutMs) {
    try { if ((await fetch(`${API_BASE_URL}/install/status`)).ok) return true; } catch { /* reiniciando */ }
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  return false;
}
