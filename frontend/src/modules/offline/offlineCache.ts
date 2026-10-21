/**
 * Copia local de lo que el escritorio necesita para trabajar sin conexión:
 * formularios asignados, definición de cada formulario, participantes y
 * respuestas previas. Cada entrada se guarda por usuario, así dos personas
 * en el mismo equipo no ven los datos de la otra.
 *
 * Funciona como caché de lectura: con red se consulta el servidor y se
 * actualiza la copia; si falla el transporte (TypeError de fetch) se
 * devuelve la última copia guardada. Un error HTTP (permisos, 404) se
 * propaga igual que antes: la copia solo cubre la falta de red.
 *
 * Solo se activa en la app de escritorio. En un navegador compartido no se
 * guardan datos de participantes en el equipo.
 */

import { isDesktopApp } from '../desktop/desktopBridge';

const DB_NAME = 'infomatt360-offline-cache';
const STORE_NAME = 'entries';
const DB_VERSION = 1;

type CacheEntry = { key: string; userId: string; value: unknown; savedAt: string };

let currentUserId = '';

export function setOfflineCacheUser(userId: string): void {
  currentUserId = userId;
}

export function offlineCacheUser(): string {
  return currentUserId;
}

export function offlineCacheEnabled(): boolean {
  return isDesktopApp() && Boolean(currentUserId);
}

export function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore(STORE_NAME, { keyPath: 'key' });
      store.createIndex('userId', 'userId');
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  try {
    return await new Promise<T>((resolve, reject) => {
      const request = run(db.transaction(STORE_NAME, mode).objectStore(STORE_NAME));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  } finally {
    db.close();
  }
}

function scopedKey(userId: string, key: string): string {
  return `${userId}|${key}`;
}

export async function writeCache(key: string, value: unknown, userId = currentUserId): Promise<void> {
  if (!userId) return;
  const entry: CacheEntry = { key: scopedKey(userId, key), userId, value, savedAt: new Date().toISOString() };
  await withStore('readwrite', (store) => store.put(entry));
}

export async function readCache<T>(key: string, userId = currentUserId): Promise<{ value: T; savedAt: string } | null> {
  if (!userId) return null;
  const entry = await withStore<CacheEntry | undefined>('readonly', (store) => store.get(scopedKey(userId, key)));
  return entry ? { value: entry.value as T, savedAt: entry.savedAt } : null;
}

/** Borra la copia de un usuario (p. ej. al quitarle el acceso al equipo). */
export async function clearCacheForUser(userId: string): Promise<void> {
  const db = await openDb();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const request = tx.objectStore(STORE_NAME).index('userId').openCursor(IDBKeyRange.only(userId));
      request.onsuccess = () => {
        const cursor = request.result;
        if (cursor) { cursor.delete(); cursor.continue(); }
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

export const OFFLINE_CACHE_HIT_EVENT = 'infomatt360:offline-cache-hit';

/**
 * Consulta con respaldo local. Sin escritorio o sin usuario, es `loader()`
 * tal cual. Una falla al guardar la copia no rompe la consulta en línea.
 */
export async function cachedJson<T>(key: string, loader: () => Promise<T>): Promise<T> {
  if (!offlineCacheEnabled()) return loader();
  const userId = currentUserId;
  try {
    const value = await loader();
    await writeCache(key, value, userId).catch(() => undefined);
    return value;
  } catch (error) {
    if (!isNetworkError(error)) throw error;
    const cached = await readCache<T>(key, userId).catch(() => null);
    if (!cached) throw error;
    if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent(OFFLINE_CACHE_HIT_EVENT, { detail: { key, savedAt: cached.savedAt } }));
    return cached.value;
  }
}
