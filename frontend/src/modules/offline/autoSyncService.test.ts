import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../auth/session', () => ({ currentAccessToken: vi.fn() }));
vi.mock('./offlineSync', () => ({ getPendingCount: vi.fn(), syncNow: vi.fn() }));

import { currentAccessToken } from '../auth/session';
import { getPendingCount, syncNow } from './offlineSync';
import * as autoSyncService from './autoSyncService';

const mockedToken = vi.mocked(currentAccessToken);
const mockedPendingCount = vi.mocked(getPendingCount);
const mockedSyncNow = vi.mocked(syncNow);

/**
 * `ensureStarted()` dispara el primer intento de inmediato (sin pasar por
 * un timer), asi que se resuelve por drenado normal de microtasks -- si en
 * cambio se usara `vi.runOnlyPendingTimersAsync()` justo despues, para el
 * momento en que esa funcion empieza a revisar que timers estan pendientes,
 * el primer tick ya termino de correr (via el mismo drenado de microtasks
 * que ocurre al hacer `await` sobre ella) y ya registro el SIGUIENTE timer
 * programado -- que tambien se ejecutaria de una, disparando syncNow dos
 * veces en vez de una. Por eso las pruebas del primer intento drenan
 * microtasks a mano, y solo usan avance de timers para los intentos
 * siguientes, ya con el estado del primero completamente asentado.
 */
async function flushMicrotasks(): Promise<void> {
  for (let i = 0; i < 5; i += 1) await Promise.resolve();
}

describe('autoSyncService', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    autoSyncService.stop();
    mockedToken.mockReset();
    mockedPendingCount.mockReset();
    mockedSyncNow.mockReset();
    vi.stubGlobal('navigator', { onLine: true });
    vi.stubGlobal('document', { visibilityState: 'visible' });
  });

  afterEach(() => {
    autoSyncService.stop();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('no intenta sincronizar sin sesion (sin token) y no lo cuenta como fallo', async () => {
    mockedToken.mockReturnValue('');
    autoSyncService.ensureStarted('http://api.test/api/v1');
    await flushMicrotasks();

    expect(mockedSyncNow).not.toHaveBeenCalled();
    expect(autoSyncService.getStatus().state).toBe('idle');
  });

  it('se pausa si esta offline, sin llamar a syncNow', async () => {
    mockedToken.mockReturnValue('tok-123');
    vi.stubGlobal('navigator', { onLine: false });
    autoSyncService.ensureStarted('http://api.test/api/v1');
    await flushMicrotasks();

    expect(mockedSyncNow).not.toHaveBeenCalled();
    expect(autoSyncService.getStatus().state).toBe('paused-offline');
  });

  it('se pausa si la pestana esta en segundo plano, sin llamar a syncNow', async () => {
    mockedToken.mockReturnValue('tok-123');
    vi.stubGlobal('document', { visibilityState: 'hidden' });
    autoSyncService.ensureStarted('http://api.test/api/v1');
    await flushMicrotasks();

    expect(mockedSyncNow).not.toHaveBeenCalled();
    expect(autoSyncService.getStatus().state).toBe('paused-hidden');
  });

  it('no llama a syncNow si no hay nada pendiente', async () => {
    mockedToken.mockReturnValue('tok-123');
    mockedPendingCount.mockResolvedValue(0);
    autoSyncService.ensureStarted('http://api.test/api/v1');
    await flushMicrotasks();

    expect(mockedSyncNow).not.toHaveBeenCalled();
    expect(autoSyncService.getStatus().state).toBe('idle');
  });

  it('sincroniza cuando hay pendientes y resetea el intervalo si no hubo fallos', async () => {
    mockedToken.mockReturnValue('tok-123');
    mockedPendingCount.mockResolvedValue(2);
    mockedSyncNow.mockResolvedValue({ attempted: 2, synced: 2, failed: 0 });

    autoSyncService.ensureStarted('http://api.test/api/v1');
    await flushMicrotasks();

    expect(mockedSyncNow).toHaveBeenCalledTimes(1);
    expect(autoSyncService.getStatus().state).toBe('waiting');
    expect(autoSyncService.getStatus().lastResult).toEqual({ attempted: 2, synced: 2, failed: 0 });
  });

  it('el intervalo crece con backoff exponencial cuando hay fallos, hasta el techo', async () => {
    mockedToken.mockReturnValue('tok-123');
    mockedPendingCount.mockResolvedValue(1);
    mockedSyncNow.mockResolvedValue({ attempted: 1, synced: 0, failed: 1 });

    autoSyncService.ensureStarted('http://api.test/api/v1');

    // Primer intento (inmediato) falla -> siguiente en BASE*2 = 60s.
    await flushMicrotasks();
    expect(mockedSyncNow).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(autoSyncService.BASE_INTERVAL_MS * 2);
    expect(mockedSyncNow).toHaveBeenCalledTimes(2);

    // Sigue fallando: 120s, 240s, y se topa en MAX_INTERVAL_MS (300s) en vez
    // de seguir creciendo indefinidamente.
    await vi.advanceTimersByTimeAsync(autoSyncService.BASE_INTERVAL_MS * 4);
    expect(mockedSyncNow).toHaveBeenCalledTimes(3);
    await vi.advanceTimersByTimeAsync(autoSyncService.MAX_INTERVAL_MS);
    expect(mockedSyncNow).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(autoSyncService.MAX_INTERVAL_MS);
    expect(mockedSyncNow).toHaveBeenCalledTimes(5);
  });

  it('ensureStarted es idempotente: llamarlo dos veces no dispara dos ciclos', async () => {
    mockedToken.mockReturnValue('tok-123');
    mockedPendingCount.mockResolvedValue(1);
    mockedSyncNow.mockResolvedValue({ attempted: 1, synced: 1, failed: 0 });

    autoSyncService.ensureStarted('http://api.test/api/v1');
    autoSyncService.ensureStarted('http://api.test/api/v1');
    await flushMicrotasks();

    expect(mockedSyncNow).toHaveBeenCalledTimes(1);
  });
});
