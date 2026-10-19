import 'fake-indexeddb/auto';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cachedJson, clearCacheForUser, readCache, setOfflineCacheUser } from './offlineCache';
import { markCapturedOffline, prepareOfflinePackage, readOfflinePackageMeta } from './offlinePackage';
import { countPending, enqueue, listPending } from './indexedDbQueue';
import { clearOfflineSnapshot, hasOfflinePin, offlineSnapshotExpired, readOfflineSnapshot, saveOfflineSnapshot, setOfflinePin, verifyOfflinePin } from '../auth/offlineSession';
import { fetchCaptureParticipants } from '../runtime/api';
import { fetchMyFormAssignments } from '../builder/myFormsApi';

function installDesktop() {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  });
  vi.stubGlobal('window', { desktopBridge: {}, dispatchEvent: () => true });
}

const session = { user_id: 'u1', full_name: 'María', email: 'm@demo', must_change_password: false, projects: [{ id: 'p1', name: 'Proyecto' }] };

beforeEach(async () => {
  installDesktop();
  setOfflineCacheUser('u1');
  await clearCacheForUser('u1');
  await clearCacheForUser('u2');
});

afterEach(() => {
  vi.unstubAllGlobals();
  setOfflineCacheUser('');
});

describe('cachedJson', () => {
  it('guarda con red y devuelve la copia cuando falla el transporte', async () => {
    expect(await cachedJson('k', async () => ({ n: 1 }))).toEqual({ n: 1 });
    expect(await cachedJson('k', async () => { throw new TypeError('Failed to fetch'); })).toEqual({ n: 1 });
  });

  it('un error HTTP no se oculta con la copia', async () => {
    await cachedJson('k', async () => 'viejo');
    await expect(cachedJson('k', async () => { throw new Error('Sin permiso'); })).rejects.toThrow('Sin permiso');
  });

  it('separa la copia por usuario', async () => {
    await cachedJson('k', async () => 'de u1');
    setOfflineCacheUser('u2');
    await expect(cachedJson('k', async () => { throw new TypeError('offline'); })).rejects.toThrow('offline');
  });

  it('fuera del escritorio no guarda nada', async () => {
    vi.stubGlobal('window', { dispatchEvent: () => true });
    await cachedJson('solo-web', async () => 1);
    expect(await readCache('solo-web')).toBeNull();
  });
});

describe('paquete sin conexión', () => {
  const routes: Record<string, unknown> = {
    '/form-assignments/mine/p1': [{ template_id: 't1', template_name: 'Visita', template_status: 'published', access_mode: 'closed', participant_id: 'a', participant_name: 'Ana', document_id: '1', external_code: null, assignment_status: 'assigned', record_id: null }],
    '/builder/templates/p1': [{ id: 't2', name: 'Abierto', status: 'published', accepting_responses: true, participant_source: { access_mode: 'open' } }],
    '/runtime/template/t1': { template_id: 't1', pages: [] },
    '/runtime/template/t2': { template_id: 't2', pages: [] },
    '/builder/templates/detail/t1': { participant_source: { participant_key_field: 'document_id', access_mode: 'closed' } },
    '/builder/templates/detail/t1/eligible-participants': [{ id: 'a', full_name: 'Ana', document_id: '1' }],
    '/form-assignments/templates/t1': [{ participant_id: 'a', participant_name: 'Ana', document_id: '1', external_code: null, status: 'assigned', record_id: null }],
    '/builder/templates/detail/t2': { participant_source: { access_mode: 'open' } },
    '/builder/templates/detail/t2/eligible-participants': [],
    '/form-assignments/templates/t2': [],
    '/participants/a/history': [],
  };
  function serve() {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      const path = url.replace(/^.*\/api\/v1/, '');
      return path in routes ? new Response(JSON.stringify(routes[path]), { status: 200 }) : new Response('{}', { status: 404 });
    }));
  }

  it('baja formularios y participantes y los sirve sin red', async () => {
    serve();
    const meta = await prepareOfflinePackage('p1');
    expect(meta).toMatchObject({ forms: 2, participants: 1, failedForms: 0 });
    expect(await readOfflinePackageMeta('p1')).toMatchObject({ forms: 2 });

    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    const capture = await fetchCaptureParticipants('t1');
    expect(capture.keyField).toBe('document_id');
    expect(capture.participants.map((p) => p.id)).toEqual(['a']);

    await markCapturedOffline('p1', 't1', 'a');
    expect((await fetchCaptureParticipants('t1')).assignments[0].status).toBe('completed');
    expect((await fetchMyFormAssignments('p1'))[0].assignment_status).toBe('completed');
  });
});

describe('cola por usuario', () => {
  it('cada sesión solo ve sus pendientes y los antiguos sin dueño', async () => {
    const values = [{ field_name: 'x', field_value_json: '1' }];
    await enqueue({ projectId: 'p', templateId: 't', userId: 'q1', values });
    await enqueue({ projectId: 'p', templateId: 't', userId: 'q2', values });
    await enqueue({ projectId: 'p', templateId: 't', values });
    expect(await countPending('q1')).toBe(2);
    expect((await listPending('q2')).every((row) => !row.userId || row.userId === 'q2')).toBe(true);
    expect(await countPending()).toBeGreaterThanOrEqual(3);
  });
});

describe('sesión sin conexión', () => {
  it('guarda la copia solo en el escritorio y vence a los 7 días', () => {
    saveOfflineSnapshot(session);
    const snapshot = readOfflineSnapshot();
    expect(snapshot?.session.user_id).toBe('u1');
    expect(offlineSnapshotExpired(snapshot!)).toBe(false);
    expect(offlineSnapshotExpired(snapshot!, Date.now() + 8 * 24 * 60 * 60 * 1000)).toBe(true);
    clearOfflineSnapshot();
    expect(readOfflineSnapshot()).toBeNull();

    vi.stubGlobal('window', { dispatchEvent: () => true });
    saveOfflineSnapshot(session);
    expect(readOfflineSnapshot()).toBeNull();
  });

  it('valida el PIN, no lo guarda en claro y bloquea tras 5 fallos', async () => {
    await expect(setOfflinePin('u1', '12')).rejects.toThrow();
    await setOfflinePin('u1', '4321', 1000);
    expect(hasOfflinePin('u1')).toBe(true);
    expect(localStorage.getItem('infomatt360_offline_pin:u1')).not.toContain('4321');
    expect(await verifyOfflinePin('u1', '4321')).toEqual({ ok: true });
    for (let attempt = 1; attempt < 5; attempt += 1) {
      expect(await verifyOfflinePin('u1', '0000')).toEqual({ ok: false, reason: 'wrong', attemptsLeft: 5 - attempt });
    }
    expect(await verifyOfflinePin('u1', '0000')).toMatchObject({ ok: false, reason: 'locked' });
    expect(await verifyOfflinePin('u1', '4321')).toMatchObject({ ok: false, reason: 'locked' });
    expect(await verifyOfflinePin('u1', '4321', Date.now() + 6 * 60 * 1000)).toEqual({ ok: true });
    expect(await verifyOfflinePin('u2', '4321')).toMatchObject({ reason: 'missing' });
  });
});
