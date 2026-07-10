const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type InstallStatus = { installed: boolean; installer_enforced: boolean };

export type BootstrapPayload = {
  organization_name: string;
  organization_slug: string;
  project_name: string;
  admin_full_name: string;
  admin_document_id: string;
  admin_email: string;
  admin_password: string;
};

export async function fetchInstallStatus(): Promise<InstallStatus> {
  const response = await fetch(`${API_BASE_URL}/install/status`);
  if (!response.ok) throw new Error('No fue posible consultar el estado de instalacion.');
  return response.json();
}

export async function bootstrapInstallation(payload: BootstrapPayload): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/install/bootstrap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'No fue posible completar la instalacion.');
  }
}
