/**
 * Reintento automatico de sincronizacion offline en segundo plano (ver
 * auditoria tecnica de julio 2026, hallazgo SYNC-003, y docs/107). Antes,
 * la sincronizacion solo ocurria si el usuario presionaba el boton, volvia
 * la conexion, o algo mas llamaba `syncNow()` explicitamente -- el
 * temporizador de 30s de `OfflineSyncStatus` solo refrescaba el contador
 * visible, nunca reintentaba nada.
 *
 * Singleton a nivel de modulo (no un hook de React): `AppShell`/
 * `OfflineSyncStatus` se vuelven a montar en cada navegacion (este proyecto
 * no tiene un layout persistente), y el backoff no debe reiniciarse por eso.
 * `ensureStarted()` es idempotente -- se puede llamar en cada montaje sin
 * problema.
 *
 * Nota de honestidad: el documento original tambien pedia "pausar por
 * bateria". La Battery Status API fue removida de Chrome/Firefox/Safari por
 * privacidad, y Electron no la expone sin un modulo nativo adicional -- no
 * se implementa (no hay forma real de hacerlo hoy), solo se pausa por falta
 * de red o pestana/ventana en segundo plano (Page Visibility API), que si
 * son reales y soportadas.
 */

import { currentAccessToken } from '../auth/session';
import { getPendingCount, syncNow } from './offlineSync';
import type { OfflineSyncResult } from './offlineSync';

export const BASE_INTERVAL_MS = 30_000;
export const MAX_INTERVAL_MS = 5 * 60_000;
const PAUSED_RECHECK_MS = 5_000;

export type AutoSyncState = 'idle' | 'syncing' | 'waiting' | 'paused-offline' | 'paused-hidden';

export type AutoSyncStatus = {
  state: AutoSyncState;
  nextAttemptAt: string | null;
  lastResult: OfflineSyncResult | null;
};

export const AUTO_SYNC_STATUS_CHANGED_EVENT = 'infomatt360:auto-sync-status-changed';

let started = false;
let apiBaseUrlRef = '';
let currentIntervalMs = BASE_INTERVAL_MS;
let timerId: ReturnType<typeof setTimeout> | null = null;
let status: AutoSyncStatus = { state: 'idle', nextAttemptAt: null, lastResult: null };

function notifyStatusChanged(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTO_SYNC_STATUS_CHANGED_EVENT));
}

function setStatus(partial: Partial<AutoSyncStatus>): void {
  status = { ...status, ...partial };
  notifyStatusChanged();
}

export function getStatus(): AutoSyncStatus {
  return status;
}

function isOnline(): boolean {
  return typeof navigator === 'undefined' || navigator.onLine !== false;
}

function isVisible(): boolean {
  return typeof document === 'undefined' || document.visibilityState !== 'hidden';
}

function scheduleNext(delayMs: number): void {
  if (timerId !== null) clearTimeout(timerId);
  setStatus({ nextAttemptAt: new Date(Date.now() + delayMs).toISOString() });
  timerId = setTimeout(() => void tick(), delayMs);
}

async function tick(): Promise<void> {
  const token = currentAccessToken();
  if (!token) {
    // Sin sesion (deslogueado): no cuenta como fallo, no crece el backoff.
    currentIntervalMs = BASE_INTERVAL_MS;
    setStatus({ state: 'idle', nextAttemptAt: null });
    scheduleNext(BASE_INTERVAL_MS);
    return;
  }
  if (!isOnline()) {
    setStatus({ state: 'paused-offline' });
    scheduleNext(PAUSED_RECHECK_MS);
    return;
  }
  if (!isVisible()) {
    setStatus({ state: 'paused-hidden' });
    scheduleNext(PAUSED_RECHECK_MS);
    return;
  }

  const pending = await getPendingCount();
  if (pending === 0) {
    currentIntervalMs = BASE_INTERVAL_MS;
    setStatus({ state: 'idle' });
    scheduleNext(BASE_INTERVAL_MS);
    return;
  }

  setStatus({ state: 'syncing' });
  try {
    const result = await syncNow({ apiBaseUrl: apiBaseUrlRef, accessToken: token });
    currentIntervalMs = result.failed === 0 ? BASE_INTERVAL_MS : Math.min(currentIntervalMs * 2, MAX_INTERVAL_MS);
    setStatus({ state: 'waiting', lastResult: result });
  } catch {
    currentIntervalMs = Math.min(currentIntervalMs * 2, MAX_INTERVAL_MS);
    setStatus({ state: 'waiting' });
  }
  scheduleNext(currentIntervalMs);
}

/** Arranca el reintento automatico si no esta corriendo ya (idempotente).
 * Dispara un primer intento de inmediato en vez de esperar el intervalo
 * base, para no hacer esperar a un usuario que abre la app con datos
 * pendientes de una sesion anterior. */
export function ensureStarted(apiBaseUrl: string): void {
  apiBaseUrlRef = apiBaseUrl;
  if (started) return;
  started = true;
  void tick();
}

/** Detiene el reintento automatico y reinicia su estado. Util para pruebas
 * y, a futuro, para desconectarlo explicitamente al cerrar sesion. */
export function stop(): void {
  if (timerId !== null) clearTimeout(timerId);
  timerId = null;
  started = false;
  currentIntervalMs = BASE_INTERVAL_MS;
  status = { state: 'idle', nextAttemptAt: null, lastResult: null };
}
