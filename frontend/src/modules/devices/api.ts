import { authorizationHeader } from '../auth/session';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type DeviceLevel = 'ok' | 'warning' | 'danger';
export type FieldDeviceStatus = {
  device_id: string;
  user_id: string;
  user_name: string;
  user_email: string;
  device_name: string;
  platform: string;
  app_version: string;
  pending_count: number;
  error_count: number;
  conflict_count: number;
  draft_count: number;
  pending_evidence_count: number;
  oldest_pending_at: string | null;
  last_sync_at: string | null;
  last_seen_at: string;
  last_error: string | null;
  recent_errors: { at: string | null; message: string }[];
  last_latitude: number | null;
  last_longitude: number | null;
  last_location_at: string | null;
  level: DeviceLevel;
  alerts: string[];
};
export type RoutePoint = { latitude: number; longitude: number; accuracy_m: number | null; recorded_at: string };
export type RouteSummary = { user_id: string; user_name: string; point_count: number; distance_km: number; first_at: string | null; last_at: string | null; points: RoutePoint[] };

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API}/field-devices${path}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'No fue posible consultar los equipos.');
  return response.json();
}

/** El servidor guarda UTC sin zona; se marca como UTC para mostrar hora local. */
export function serverDate(value: string | null): Date | null {
  if (!value) return null;
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
}

export const fetchDeviceStatus = (projectId: string) => request<FieldDeviceStatus[]>(`/project/${projectId}/status`);

/** Recorridos de un día local (todo el equipo, o los puntos de un gestor). */
export function fetchRoutes(projectId: string, day: string, userId?: string) {
  const start = new Date(`${day}T00:00:00`);
  const end = new Date(start); end.setDate(end.getDate() + 1);
  const params = new URLSearchParams({ date_from: start.toISOString(), date_to: end.toISOString() });
  if (userId) params.set('user_id', userId);
  return request<RouteSummary[]>(`/project/${projectId}/routes?${params}`);
}
