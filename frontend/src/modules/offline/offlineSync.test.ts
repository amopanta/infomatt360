import 'fake-indexeddb/auto';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { enqueueRecord, getPendingCount, syncNow } from './offlineSync';

function sampleValues(text: string) {
  return [{ field_name: 'nombre', field_value_json: JSON.stringify(text) }];
}

describe('offlineSync (modo navegador, sin desktopBridge)', () => {
  beforeEach(() => {
    indexedDB = new IDBFactory();
  });

  it('encola y cuenta pendientes a traves de IndexedDB', async () => {
    expect(await getPendingCount()).toBe(0);
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    expect(await getPendingCount()).toBe(1);
  });

  it('syncNow llama a /runtime/save (no /runtime/bulk/save) y marca sincronizado', async () => {
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });

    const calls: { url: string; body: unknown }[] = [];
    vi.stubGlobal('fetch', async (url: string, options: RequestInit) => {
      calls.push({ url, body: JSON.parse(options.body as string) });
      return { ok: true, text: async () => '', json: async () => ({ id: 'srv-1' }) };
    });

    const result = await syncNow({ apiBaseUrl: 'http://api.test/api/v1', accessToken: 'tok-123' });

    expect(result).toEqual({ attempted: 1, synced: 1, failed: 0 });
    expect(await getPendingCount()).toBe(0);
    expect(calls[0].url).toBe('http://api.test/api/v1/runtime/save');
    expect((calls[0].body as { status: string }).status).toBe('submitted');
    expect((calls[0].body as { values: { field_name: string }[] }).values[0].field_name).toBe('nombre');
  });

  it('deja el registro pendiente si el backend responde con error', async () => {
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    vi.stubGlobal('fetch', async () => ({ ok: false, status: 500, text: async () => 'error interno' }));

    const result = await syncNow({ apiBaseUrl: 'http://api.test/api/v1', accessToken: 'tok-123' });

    expect(result).toEqual({ attempted: 1, synced: 0, failed: 1 });
    expect(await getPendingCount()).toBe(1);
  });

  it('maneja un error de red sin lanzar', async () => {
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    vi.stubGlobal('fetch', async () => {
      throw new TypeError('Failed to fetch');
    });

    const result = await syncNow({ apiBaseUrl: 'http://api.test/api/v1', accessToken: 'tok-123' });

    expect(result).toEqual({ attempted: 1, synced: 0, failed: 1 });
    expect(await getPendingCount()).toBe(1);
  });
});
