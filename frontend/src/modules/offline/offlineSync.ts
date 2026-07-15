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

/** Ver auditoria tecnica de julio 2026, hallazgo SYNC-005: ventana de
 * retencion de registros ya sincronizados en la cola local, acordada con
 * el usuario (coincide con el minimo que ya recomienda docs/63 para
 * backups, como referencia de una semana razonable). */
export const DEFAULT_RETENTION_DAYS = 7;

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

/** Borra los registros ya sincronizados hace mas de `retentionDays` de la
 * cola local. Se llama automaticamente al final de `syncNow`, y tambien
 * queda expuesta para un boton manual (ver docs/107). */
export async function purgeOldSynced(retentionDays: number = DEFAULT_RETENTION_DAYS): Promise<number> {
  const purged = isDesktopApp() ? await window.desktopBridge!.purgeOldSynced(retentionDays) : await indexedDbQueue.purgeOldSynced(retentionDays);
  if (purged > 0) notifyQueueChanged();
  return purged;
}

function groupByTemplate(records: indexedDbQueue.QueuedRecord[]): Map<string, indexedDbQueue.QueuedRecord[]> {
  const groups = new Map<string, indexedDbQueue.QueuedRecord[]>();
  for (const record of records) {
    const key = `${record.projectId}::${record.templateId}`;
    const group = groups.get(key);
    if (group) group.push(record);
    else groups.set(key, [record]);
  }
  return groups;
}

/** Clave de idempotencia del lote: hash estable del conjunto de ids locales
 * que lo componen. Si la respuesta se pierde en la red despues de que el
 * servidor ya creo los registros, reintentar con el mismo conjunto de ids
 * reutiliza la respuesta cacheada (BulkImportJob) en vez de duplicar. */
async function hashIds(ids: string[]): Promise<string> {
  const sorted = [...ids].sort();
  const data = new TextEncoder().encode(sorted.join(','));
  const digest = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

type BulkSaveResult = { index: number; id?: string; status: string; error?: string };
type BulkSaveResponse = { results: BulkSaveResult[] };

/**
 * Sincroniza la cola pendiente agrupada por (proyecto, plantilla) contra
 * `POST /runtime/session/bulk-save` -- un lote por grupo en vez de una
 * solicitud HTTP por registro (ver auditoria tecnica de julio 2026,
 * hallazgo SYNC-001, y docs/106). Distinto de `POST /runtime/bulk/save`
 * (ese exige API key para integraciones externas, no sesion de usuario).
 */
export async function syncNow(credentials: { apiBaseUrl: string; accessToken: string }): Promise<OfflineSyncResult> {
  if (isDesktopApp()) {
    const result = await window.desktopBridge!.syncNow(credentials);
    await purgeOldSynced();
    notifyQueueChanged();
    return result;
  }

  const pending = await indexedDbQueue.listPending();
  const result: OfflineSyncResult = { attempted: pending.length, synced: 0, failed: 0 };

  for (const group of groupByTemplate(pending).values()) {
    const [{ projectId, templateId }] = group;
    const idempotencyKey = await hashIds(group.map((record) => record.id));
    try {
      const response = await fetch(`${credentials.apiBaseUrl}/runtime/session/bulk-save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${credentials.accessToken}` },
        body: JSON.stringify({
          project_id: projectId,
          template_id: templateId,
          idempotency_key: idempotencyKey,
          records: group.map((record) => ({
            project_id: record.projectId,
            template_id: record.templateId,
            status: 'submitted',
            values: record.values,
          })),
        }),
      });
      if (!response.ok) {
        const detail = await response.text();
        for (const record of group) await indexedDbQueue.markFailed(record.id, `HTTP ${response.status}: ${detail}`);
        result.failed += group.length;
        continue;
      }
      const data = (await response.json()) as BulkSaveResponse;
      for (const item of data.results) {
        const record = group[item.index];
        if (!record) continue;
        if (item.status === 'created') {
          await indexedDbQueue.markSynced(record.id);
          result.synced += 1;
        } else {
          await indexedDbQueue.markFailed(record.id, item.error ?? 'Error desconocido al sincronizar');
          result.failed += 1;
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      for (const record of group) await indexedDbQueue.markFailed(record.id, message);
      result.failed += group.length;
    }
  }
  await purgeOldSynced();
  notifyQueueChanged();
  return result;
}
