import { authorizationHeader } from '../auth/session';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
export type GestorTeam = { id: string; project_id: string; name: string; user_ids: string[]; participant_ids: string[] };
export type GestorTeamSummary = { id: string; project_id: string; name: string; user_count: number; participant_count: number };
export type TeamSearchResult = { id: string; name: string; identifier: string; selected: boolean };
export type TeamBulkPreview = { rows: number; teams_to_create: number; new_members: number; already_members: number; issues: string[]; applied: number };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}/gestor-teams${path}`, { ...init, headers: { ...authorizationHeader(), ...(init?.body ? { 'Content-Type': 'application/json' } : {}) } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'No fue posible guardar el equipo.');
  return response.json();
}

export const fetchGestorTeams = (projectId: string) => request<GestorTeam[]>(`/project/${projectId}`);
export const fetchGestorTeamSummaries = (projectId: string) => request<GestorTeamSummary[]>(`/project/${projectId}/summaries`);
export const searchGestorTeamMembers = (teamId: string, kind: 'gestor' | 'participante', q: string) => request<TeamSearchResult[]>(`/${teamId}/members/search?kind=${kind}&q=${encodeURIComponent(q)}&limit=50`);
export const addGestorTeamMember = (teamId: string, kind: 'gestor' | 'participante', memberId: string) => request<{ selected: boolean }>(`/${teamId}/members/${kind}`, { method: 'POST', body: JSON.stringify({ member_id: memberId }) });
export const removeGestorTeamMember = (teamId: string, kind: 'gestor' | 'participante', memberId: string) => request<{ selected: boolean }>(`/${teamId}/members/${kind}/${memberId}`, { method: 'DELETE' });
export async function bulkImportGestorTeams(projectId: string, file: File, previewOnly: boolean): Promise<TeamBulkPreview> {
  const body = new FormData(); body.set('upload', file); body.set('preview_only', String(previewOnly));
  const response = await fetch(`${API}/gestor-teams/project/${projectId}/bulk-import`, { method: 'POST', headers: authorizationHeader(), body });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'No fue posible validar el archivo.');
  return response.json();
}
export async function downloadGestorTeamTemplate(projectId: string): Promise<void> {
  const response = await fetch(`${API}/gestor-teams/project/${projectId}/bulk-template`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible descargar la plantilla.');
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = 'plantilla_equipos_gestores.csv'; link.click();
  URL.revokeObjectURL(url);
}
export const createGestorTeam = (projectId: string, name: string) => request<GestorTeam>(`/project/${projectId}`, { method: 'POST', body: JSON.stringify({ name }) });
export const renameGestorTeam = (teamId: string, name: string) => request<GestorTeam>(`/${teamId}`, { method: 'PATCH', body: JSON.stringify({ name }) });
export const saveGestorTeamMembers = (teamId: string, userIds: string[], participantIds: string[]) => request<GestorTeam>(`/${teamId}/members`, { method: 'PUT', body: JSON.stringify({ user_ids: userIds, participant_ids: participantIds }) });
export const deleteGestorTeam = (teamId: string) => request<{ deleted: boolean }>(`/${teamId}`, { method: 'DELETE' });
