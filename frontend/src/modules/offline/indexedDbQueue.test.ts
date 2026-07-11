import 'fake-indexeddb/auto';
import { beforeEach, describe, expect, it } from 'vitest';
import { countPending, enqueue, listPending, markFailed, markSynced } from './indexedDbQueue';

function sampleValues(text: string) {
  return [{ field_name: 'nombre', field_value_json: JSON.stringify(text) }];
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
});
