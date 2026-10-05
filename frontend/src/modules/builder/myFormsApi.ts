import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type MyFormAssignment = {
  template_id: string;
  template_name: string;
  template_status: string;
  participant_id: string;
  participant_name: string;
  document_id: string | null;
  assignment_status: string;
  record_id: string | null;
};

export type MyFormSummary = { assignment_count: number; form_count: number; pending: Array<Pick<MyFormAssignment, 'template_id' | 'template_name' | 'participant_id' | 'participant_name' | 'document_id'>> };

export async function fetchMyFormSummary(projectId: string): Promise<MyFormSummary> {
  const response = await fetch(`${API_BASE_URL}/form-assignments/mine/${projectId}/summary`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar el resumen de formularios asignados.');
  return response.json();
}

export async function fetchMyFormAssignments(projectId: string): Promise<MyFormAssignment[]> {
  const response = await fetch(`${API_BASE_URL}/form-assignments/mine/${projectId}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar tus formularios asignados.');
  return response.json();
}

export async function fetchMyProjectAssignmentCounts(): Promise<Record<string, number>> {
  const response = await fetch(`${API_BASE_URL}/form-assignments/projects/my-assignment-counts`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar los formularios por proyecto.');
  return response.json();
}
