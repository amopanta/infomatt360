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

  it('syncNow agrupa la cola en un solo lote a /runtime/session/bulk-save (no un request por registro)', async () => {
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Beatriz') });

    const calls: { url: string; body: { project_id: string; template_id: string; idempotency_key: string; records: unknown[] } }[] = [];
    vi.stubGlobal('fetch', async (url: string, options: RequestInit) => {
      calls.push({ url, body: JSON.parse(options.body as string) });
      return {
        ok: true,
        json: async () => ({
          results: [
            { index: 0, id: 'srv-1', status: 'created' },
            { index: 1, id: 'srv-2', status: 'created' },
          ],
        }),
      };
    });

    const result = await syncNow({ apiBaseUrl: 'http://api.test/api/v1', accessToken: 'tok-123' });

    expect(result).toEqual({ attempted: 2, synced: 2, failed: 0 });
    expect(await getPendingCount()).toBe(0);
    expect(calls).toHaveLength(1); // un solo request, no dos
    expect(calls[0].url).toBe('http://api.test/api/v1/runtime/session/bulk-save');
    expect(calls[0].body.project_id).toBe('p1');
    expect(calls[0].body.template_id).toBe('t1');
    expect(calls[0].body.records).toHaveLength(2);
    expect(calls[0].body.idempotency_key).toMatch(/^[0-9a-f]{64}$/);
  });

  it('agrupa por plantilla: dos plantillas distintas generan dos lotes separados', async () => {
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    await enqueueRecord({ projectId: 'p1', templateId: 't2', values: sampleValues('Beatriz') });

    const calls: { body: { template_id: string } }[] = [];
    vi.stubGlobal('fetch', async (_url: string, options: RequestInit) => {
      calls.push({ body: JSON.parse(options.body as string) });
      return { ok: true, json: async () => ({ results: [{ index: 0, status: 'created' }] }) };
    });

    const result = await syncNow({ apiBaseUrl: 'http://api.test/api/v1', accessToken: 'tok-123' });

    expect(result).toEqual({ attempted: 2, synced: 2, failed: 0 });
    expect(calls).toHaveLength(2);
    expect(new Set(calls.map((call) => call.body.template_id))).toEqual(new Set(['t1', 't2']));
  });

  it('deja pendiente solo el registro que el servidor reporta como fallido dentro del lote', async () => {
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Ana') });
    await enqueueRecord({ projectId: 'p1', templateId: 't1', values: sampleValues('Beatriz') });

    vi.stubGlobal('fetch', async () => ({
      ok: true,
      json: async () => ({
        results: [
          { index: 0, id: 'srv-1', status: 'created' },
          { index: 1, status: 'failed', error: 'contenido invalido' },
        ],
      }),
    }));

    const result = await syncNow({ apiBaseUrl: 'http://api.test/api/v1', accessToken: 'tok-123' });

    expect(result).toEqual({ attempted: 2, synced: 1, failed: 1 });
    expect(await getPendingCount()).toBe(1);
  });

  it('deja todo el lote pendiente si el backend responde con error HTTP', async () => {
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
