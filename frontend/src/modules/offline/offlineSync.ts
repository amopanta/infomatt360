/**
 * Fachada unica de sincronizacion offline: delega a `window.desktopBridge`
 * cuando corre dentro de Electron (Fase 3), o a la cola IndexedDB del
 * navegador/PWA en cualquier otro caso. El resto de la app (boton de
 * sincronizar, guardado de Runtime) llama esta fachada sin saber cual de
 * las dos implementaciones esta activa.
 */

import { isDesktopApp } from '../desktop/desktopBridge';
import type { DesktopRecordValue } from '../desktop/desktopBridge';
import * as indexedDbQueue from './indexedDbQueue';

export type OfflineSyncResult = { attempted: number; synced: number; failed: number };

/** Se dispara cada vez que se encola o sincroniza un registro, para que
 * `OfflineSyncStatus` actualice el contador sin esperar su poll periodico. */
export const OFFLINE_QUEUE_CHANGED_EVENT = 'infomatt360:offline-queue-changed';

function notifyQueueChanged(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(OFFLINE_QUEUE_CHANGED_EVENT));
}

export async function enqueueRecord(record: { projectId: string; templateId: string; values: DesktopRecordValue[] }): Promise<string> {
  const id = isDesktopApp() ? await window.desktopBridge!.enqueueRecord(record) : await indexedDbQueue.enqueue(record);
  notifyQueueChanged();
  return id;
}

export async function getPendingCount(): Promise<number> {
  if (isDesktopApp()) return window.desktopBridge!.getPendingCount();
  return indexedDbQueue.countPending();
}

/**
 * Igual que `desktop/src/offlineQueue.js:syncPending`: usa
 * `POST /runtime/save` (sesion normal de usuario), no
 * `POST /runtime/bulk/save` (ese exige API key para integraciones externas
 * y devuelve 401 con una sesion de usuario normal -- ya se probo con el
 * backend real en la verificacion de escritorio).
 */
export async function syncNow(credentials: { apiBaseUrl: string; accessToken: string }): Promise<OfflineSyncResult> {
  if (isDesktopApp()) {
    const result = await window.desktopBridge!.syncNow(credentials);
    notifyQueueChanged();
    return result;
  }

  const pending = await indexedDbQueue.listPending();
  const result: OfflineSyncResult = { attempted: pending.length, synced: 0, failed: 0 };

  for (const record of pending) {
    try {
      const response = await fetch(`${credentials.apiBaseUrl}/runtime/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${credentials.accessToken}` },
        body: JSON.stringify({
          project_id: record.projectId,
          template_id: record.templateId,
          status: 'submitted',
          values: record.values,
        }),
      });
      if (!response.ok) {
        await indexedDbQueue.markFailed(record.id, `HTTP ${response.status}: ${await response.text()}`);
        result.failed += 1;
        continue;
      }
      await indexedDbQueue.markSynced(record.id);
      result.synced += 1;
    } catch (error) {
      await indexedDbQueue.markFailed(record.id, error instanceof Error ? error.message : String(error));
      result.failed += 1;
    }
  }
  notifyQueueChanged();
  return result;
}
