export type ScheduledTask = {
  id: string;
  project_id: string;
  name: string;
  task_type: string;
  target_id?: string | null;
  frequency: string;
  config_json?: string | null;
  status: string;
  last_result?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
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

export async function fetchScheduledTasks(projectId: string): Promise<ScheduledTask[]> {
  const response = await fetch(`${API_BASE_URL}/scheduler/tasks/${projectId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar las tareas programadas.');
}

export async function createScheduledBackupTask(projectId: string, frequency: string): Promise<ScheduledTask> {
  const response = await fetch(`${API_BASE_URL}/scheduler/tasks`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ project_id: projectId, name: 'Respaldo automatico', task_type: 'backup', frequency }),
  });
  return parseOrThrow(response, 'No fue posible programar el respaldo automatico.');
}
