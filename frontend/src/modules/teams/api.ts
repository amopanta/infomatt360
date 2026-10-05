import { authorizationHeader } from '../auth/session';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
export type GestorTeam = { id: string; project_id: string; name: string; user_ids: string[]; participant_ids: string[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}/gestor-teams${path}`, { ...init, headers: { ...authorizationHeader(), ...(init?.body ? { 'Content-Type': 'application/json' } : {}) } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'No fue posible guardar el equipo.');
  return response.json();
}

export const fetchGestorTeams = (projectId: string) => request<GestorTeam[]>(`/project/${projectId}`);
export const createGestorTeam = (projectId: string, name: string) => request<GestorTeam>(`/project/${projectId}`, { method: 'POST', body: JSON.stringify({ name }) });
export const renameGestorTeam = (teamId: string, name: string) => request<GestorTeam>(`/${teamId}`, { method: 'PATCH', body: JSON.stringify({ name }) });
export const saveGestorTeamMembers = (teamId: string, userIds: string[], participantIds: string[]) => request<GestorTeam>(`/${teamId}/members`, { method: 'PUT', body: JSON.stringify({ user_ids: userIds, participant_ids: participantIds }) });
export const deleteGestorTeam = (teamId: string) => request<{ deleted: boolean }>(`/${teamId}`, { method: 'DELETE' });
