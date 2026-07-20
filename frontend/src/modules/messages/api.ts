export type InternalMessage = {
  id: string;
  project_id: string;
  recipient_id: string;
  subject: string;
  body: string;
  sender_id?: string | null;
  status: 'unread' | 'read' | 'archived';
  created_at?: string | null;
};

export type MessageCounts = { unread: number; inbox: number; sent: number };
export type MessageUser = { id: string; full_name: string; email: string; status: string };

export type ExternalMailMessage = {
  id: string;
  project_id: string;
  mail_profile_id: string;
  uid: number;
  from_address: string;
  subject: string;
  body: string;
  received_at?: string | null;
  fetched_at: string;
  status: 'unread' | 'read' | 'archived';
};

import { jsonAuthHeaders } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
function headers() { return jsonAuthHeaders(); }

export async function fetchInbox(projectId: string): Promise<InternalMessage[]> {
  const response = await fetch(`${API_BASE_URL}/messages/internal/${projectId}/inbox`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible cargar la bandeja de entrada.');
  return response.json();
}

export async function fetchSent(projectId: string): Promise<InternalMessage[]> {
  const response = await fetch(`${API_BASE_URL}/messages/internal/${projectId}/sent`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible cargar los mensajes enviados.');
  return response.json();
}

export async function fetchCounts(projectId: string): Promise<MessageCounts> {
  const response = await fetch(`${API_BASE_URL}/messages/internal/${projectId}/counts`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible consultar los conteos de mensajes.');
  return response.json();
}

export async function sendMessage(projectId: string, recipientId: string, subject: string, body: string): Promise<InternalMessage> {
  const response = await fetch(`${API_BASE_URL}/messages/internal`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ project_id: projectId, recipient_id: recipientId, subject, body }),
  });
  if (!response.ok) throw new Error('No fue posible enviar el mensaje. Verifica que el destinatario pertenezca al proyecto.');
  return response.json();
}

export async function markMessageRead(projectId: string, messageId: string): Promise<InternalMessage> {
  const response = await fetch(`${API_BASE_URL}/messages/internal/${projectId}/${messageId}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify({ status: 'read' }),
  });
  if (!response.ok) throw new Error('No fue posible marcar el mensaje como leído.');
  return response.json();
}

export async function fetchProjectUsers(projectId: string): Promise<MessageUser[]> {
  const response = await fetch(`${API_BASE_URL}/security/admin/projects/${projectId}/users`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible cargar usuarios del proyecto.');
  return response.json();
}

export async function fetchExternalInbox(projectId: string): Promise<ExternalMailMessage[]> {
  const response = await fetch(`${API_BASE_URL}/messages/external/${projectId}/inbox`, { headers: headers() });
  if (!response.ok) throw new Error('No fue posible cargar la bandeja externa.');
  return response.json();
}

export async function markExternalRead(projectId: string, messageId: string): Promise<ExternalMailMessage> {
  const response = await fetch(`${API_BASE_URL}/messages/external/${projectId}/${messageId}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify({ status: 'read' }),
  });
  if (!response.ok) throw new Error('No fue posible marcar el mensaje externo como leído.');
  return response.json();
}
