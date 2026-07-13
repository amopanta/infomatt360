/** Cliente para la captura publica (sin sesion) de un formulario abierto por token. */

import { toRuntimeValueList } from '../runtime/api';
import type { RuntimeFormValues, RuntimeTemplate } from '../runtime/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

async function parseOrThrow<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  return response.json();
}

export async function fetchPublicForm(token: string): Promise<RuntimeTemplate> {
  const response = await fetch(`${API_BASE_URL}/public-forms/${encodeURIComponent(token)}`);
  return parseOrThrow(response, 'Este enlace no es valido o ya no esta disponible.');
}

export async function submitPublicForm(token: string, values: RuntimeFormValues, deviceId?: string): Promise<{ submitted: boolean; record_id: string }> {
  const response = await fetch(`${API_BASE_URL}/public-forms/${encodeURIComponent(token)}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values: toRuntimeValueList(values), device_id: deviceId || null }),
  });
  return parseOrThrow(response, 'No fue posible enviar la respuesta.');
}
