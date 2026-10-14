import { jsonAuthHeaders } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
function headers() { return jsonAuthHeaders(); }

export type MirrorTarget = {
  id: string;
  project_id: string;
  name: string;
  engine: string;
  status: string;
};

export type MirrorPlan = {
  id: string;
  target_id: string;
  name: string;
  schedule_mode: string;
  status: string;
  last_result: string | null;
};

export type MirrorRun = {
  id: string;
  plan_id: string;
  status: string;
  records_synced: number;
  values_synced: number;
  triggered_by: string | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type MirrorTargetCreate = {
  project_id: string;
  name: string;
  engine: 'postgres' | 'sqlite' | 'mysql' | 'mssql';
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  file_path?: string;
};

export type MirrorPlanCreate = {
  target_id: string;
  name: string;
  schedule_mode: 'full_mirror' | 'insert_only' | 'incremental';
};

export async function fetchMirrorTargets(projectId: string): Promise<MirrorTarget[]> {
  const res = await fetch(`${API_BASE_URL}/mirror/targets/${projectId}`, { headers: headers() });
  if (!res.ok) throw new Error('Error al cargar destinos de espejo');
  return res.json();
}

export async function createMirrorTarget(payload: MirrorTargetCreate): Promise<MirrorTarget> {
  const res = await fetch(`${API_BASE_URL}/mirror/targets`, { method: 'POST', headers: headers(), body: JSON.stringify(payload) });
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? 'Error al crear destino'); }
  return res.json();
}

export async function testMirrorConnection(targetId: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE_URL}/mirror/targets/${targetId}/test-connection`, { method: 'POST', headers: headers() });
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? 'Error de conexion'); }
  return res.json();
}

export async function fetchMirrorPlans(targetId: string): Promise<MirrorPlan[]> {
  const res = await fetch(`${API_BASE_URL}/mirror/plans/${targetId}`, { headers: headers() });
  if (!res.ok) throw new Error('Error al cargar planes de espejo');
  return res.json();
}

export async function createMirrorPlan(payload: MirrorPlanCreate): Promise<MirrorPlan> {
  const res = await fetch(`${API_BASE_URL}/mirror/plans`, { method: 'POST', headers: headers(), body: JSON.stringify(payload) });
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? 'Error al crear plan'); }
  return res.json();
}

export async function runMirrorPlan(planId: string): Promise<MirrorRun> {
  const res = await fetch(`${API_BASE_URL}/mirror/plans/${planId}/run`, { method: 'POST', headers: headers() });
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? 'Error al ejecutar espejo'); }
  return res.json();
}

export async function fetchMirrorRuns(planId: string): Promise<MirrorRun[]> {
  const res = await fetch(`${API_BASE_URL}/mirror/plans/${planId}/runs`, { headers: headers() });
  if (!res.ok) throw new Error('Error al cargar ejecuciones');
  return res.json();
}

export type BIConnectionInfo = {
  engine: string;
  host: string;
  port: number;
  database: string;
  username: string;
  tables: string[];
  jdbc_url: string;
  tools: Record<string, Record<string, string>>;
};

export async function fetchBIConnectionInfo(targetId: string): Promise<BIConnectionInfo> {
  const res = await fetch(`${API_BASE_URL}/mirror/targets/${targetId}/bi-connection`, { headers: headers() });
  if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail ?? 'Error al obtener info BI'); }
  return res.json();
}
