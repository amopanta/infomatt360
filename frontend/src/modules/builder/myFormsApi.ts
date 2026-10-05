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

export async function fetchMyFormAssignments(projectId: string): Promise<MyFormAssignment[]> {
  const response = await fetch(`${API_BASE_URL}/form-assignments/mine/${projectId}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible consultar tus formularios asignados.');
  return response.json();
}
