import 'fake-indexeddb/auto';
import { beforeEach, describe, expect, it } from 'vitest';
import { countPending, enqueue, listPending, markFailed, markSynced, purgeOldSynced } from './indexedDbQueue';

function sampleValues(text: string) {
  return [{ field_name: 'nombre', field_value_json: JSON.stringify(text) }];
}

/** Fuerza una fecha de sincronizacion pasada, para probar purgeOldSynced sin
 * depender de tiempo real. No hay un backdoor equivalente en el modulo de
 * produccion a proposito -- se reabre la base directo, igual que haria
 * cualquier otro codigo externo al modulo. */
function backdateSyncedAt(id: string, isoDate: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('infomatt360-offline-queue', 2);
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction('queued_records', 'readwrite');
      const store = tx.objectStore('queued_records');
      const getRequest = store.get(id);
      getRequest.onsuccess = () => {
        const record = getRequest.result as { syncedAt?: string };
        record.syncedAt = isoDate;
        store.put(record);
      };
      tx.oncomplete = () => {
        db.close();
        resolve();
      };
      tx.onerror = () => reject(tx.error);
    };
    request.onerror = () => reject(request.error);
  });
}

function daysAgo(days: number): string {
  return new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();
}

describe('indexedDbQueue', () => {
  beforeEach(() => {
    indexedDB = new IDBFactory();
  });

  it('enqueue guarda un registro pendiente y countPending lo refleja', async () => {
    expect(await countPending()).toBe(0);
    const id = await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    expect(await countPending()).toBe(1);
    const pending = await listPending();
    expect(pending[0].id).toBe(id);
    expect(pending[0].status).toBe('pending');
  });

  it('markSynced saca el registro de la lista de pendientes', async () => {
    const id = await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    await markSynced(id);
    expect(await countPending()).toBe(0);
  });

  it('markFailed mantiene el registro pendiente y guarda el error', async () => {
    const id = await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    await markFailed(id, 'HTTP 500: error interno');
    const pending = await listPending();
    expect(pending).toHaveLength(1);
    expect(pending[0].id).toBe(id);
    expect(pending[0].error).toMatch(/HTTP 500/);
  });

  it('mantiene varios registros pendientes de forma independiente', async () => {
    await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Beatriz') });
    expect(await countPending()).toBe(2);
  });

  it('purgeOldSynced borra los sincronizados vencidos y conserva los recientes y los pendientes', async () => {
    const oldId = await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Antiguo') });
    const recentId = await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Reciente') });
    const pendingId = await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Pendiente') });

    await markSynced(oldId);
    await backdateSyncedAt(oldId, daysAgo(10));
    await markSynced(recentId);
    await backdateSyncedAt(recentId, daysAgo(2));

    const purged = await purgeOldSynced(7);

    expect(purged).toBe(1);
    expect(await countPending()).toBe(1);
    const pending = await listPending();
    expect(pending[0].id).toBe(pendingId);
  });

  it('purgeOldSynced no borra nada si ningun sincronizado supera la retencion', async () => {
    const id = await enqueue({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    await markSynced(id);
    expect(await purgeOldSynced(7)).toBe(0);
  });
});
