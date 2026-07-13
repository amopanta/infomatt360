const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type InstallStatus = { installed: boolean; installer_enforced: boolean };

export type RequirementCheck = { key: string; label: string; status: 'ok' | 'warning' | 'error'; detail?: string | null };
export type InstallRequirements = { ready: boolean; checks: RequirementCheck[] };

export type MailSetup = { sender_email: string; server_host?: string; server_port?: string };
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

export async function fetchInstallStatus(): Promise<InstallStatus> {
  const response = await fetch(`${API_BASE_URL}/install/status`);
  if (!response.ok) throw new Error('No fue posible consultar el estado de instalacion.');
  return response.json();
}

export async function fetchInstallRequirements(): Promise<InstallRequirements> {
  const response = await fetch(`${API_BASE_URL}/install/requirements`);
  return response.json();
}

export async function bootstrapInstallation(payload: BootstrapPayload): Promise<BootstrapResult> {
  const response = await fetch(`${API_BASE_URL}/install/bootstrap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'No fue posible completar la instalacion.');
  }
  return response.json();
}
