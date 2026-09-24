import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type Participant = {
  id: string;
  project_id: string;
  external_code?: string | null;
  document_id?: string | null;
  full_name: string;
  participant_type: string;
  status: string;
  duplicate_flag: string;
  metadata_json?: string | null;
  department?: string | null;
  municipality?: string | null;
  group_name?: string | null;
};

export type ParticipantHistoryItem = {
  record_id: string;
  template_id: string;
  template_name: string;
  status: string;
  created_at: string;
  updated_at: string;
  submitted_by?: string | null;
};

function headers(): HeadersInit {
  return authorizationHeader();
}

export async function fetchProjectParticipants(projectId: string): Promise<Participant[]> {
  const response = await fetch(`${API_BASE_URL}/participants/project/${projectId}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar los participantes del proyecto.');
  return response.json();
}

export async function fetchParticipant(participantId: string): Promise<Participant> {
  const response = await fetch(`${API_BASE_URL}/participants/${participantId}`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar el participante.');
  return response.json();
}

export async function assignParticipantGroup(participantId: string, groupName: string): Promise<Participant> {
  const response = await fetch(`${API_BASE_URL}/participants/${participantId}/group`, { method: 'PATCH', headers: { ...headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ group_name: groupName }) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'No fue posible asignar el grupo.');
  return response.json();
}

export async function deleteParticipantGroup(projectId: string, groupName: string): Promise<number> {
  const response = await fetch(`${API_BASE_URL}/participants/project/${projectId}/groups/${encodeURIComponent(groupName)}`, { method: 'DELETE', headers: headers() });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'No fue posible eliminar el grupo.');
  return (await response.json()).updated;
}

export async function setParticipantGroupStatus(projectId: string, groupName: string, status: 'active' | 'inactive'): Promise<number> {
  const response = await fetch(`${API_BASE_URL}/participants/project/${projectId}/groups/${encodeURIComponent(groupName)}/status`, { method: 'PATCH', headers: { ...headers(), 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'No fue posible cambiar el estado del grupo.');
  return (await response.json()).updated;
}

export async function fetchParticipantHistory(participantId: string): Promise<ParticipantHistoryItem[]> {
  const response = await fetch(`${API_BASE_URL}/participants/${participantId}/history`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar el historial del participante.');
  return response.json();
}
