export type BackupJob = {
  id: string;
  project_id: string;
  storage_profile_id?: string | null;
  status: string;
  file_path?: string | null;
  size_bytes?: number | null;
  triggered_by?: string | null;
  error?: string | null;
  started_at: string;
  finished_at?: string | null;
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

export async function runBackup(projectId: string, storageProfileId?: string): Promise<BackupJob> {
  const query = new URLSearchParams({ project_id: projectId });
  if (storageProfileId) query.set('storage_profile_id', storageProfileId);
  const response = await fetch(`${API_BASE_URL}/backups/run?${query.toString()}`, { method: 'POST', headers: headers() });
  return parseOrThrow(response, 'No fue posible ejecutar el respaldo.');
}

export async function fetchBackups(projectId: string): Promise<BackupJob[]> {
  const response = await fetch(`${API_BASE_URL}/backups/project/${projectId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar el historial de respaldos.');
}
