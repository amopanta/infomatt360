export type WhatsAppNotification = {
  id: string;
  project_id: string;
  recipient_user_id?: string | null;
  recipient_phone: string;
  message: string;
  reference_record_id?: string | null;
  status: string;
  error?: string | null;
  created_at: string;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function fetchWhatsAppNotifications(projectId: string): Promise<WhatsAppNotification[]> {
  const response = await fetch(`${API_BASE_URL}/whatsapp/notifications/project/${projectId}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible cargar el historial de notificaciones WhatsApp.');
  return response.json();
}
