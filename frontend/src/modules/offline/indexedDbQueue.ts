/**
 * Cola offline en IndexedDB para el navegador/PWA. Simetrica a
 * `desktop/src/offlineQueue.js` (misma forma de datos, mismo endpoint de
 * sincronizacion), pero implementada con la API nativa de IndexedDB en vez
 * de sql.js: en el navegador no hace falta un archivo real de SQLite, y
 * IndexedDB ya viene soportado sin dependencias adicionales.
 */

const DB_NAME = 'infomatt360-offline-queue';
const STORE_NAME = 'queued_records';
// v2 agrega indices por status/createdAt (ver auditoria tecnica de julio
// 2026, hallazgo SYNC-004): listPending() antes hacia getAll() + filtraba
// en JS, un full scan a partir de cierto volumen de cola.
const DB_VERSION = 2;
const STATUS_INDEX = 'status';
const CREATED_AT_INDEX = 'createdAt';

export type QueuedValue = { field_name: string; field_value_json: string };

export type QueuedRecord = {
  id: string;
  projectId: string;
  templateId: string;
  values: QueuedValue[];
  status: 'pending' | 'synced';
  createdAt: string;
  syncedAt?: string;
  error?: string;
};

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      const store = db.objectStoreNames.contains(STORE_NAME)
        ? request.transaction!.objectStore(STORE_NAME)
        : db.createObjectStore(STORE_NAME, { keyPath: 'id' });
      if (!store.indexNames.contains(STATUS_INDEX)) store.createIndex(STATUS_INDEX, 'status');
      if (!store.indexNames.contains(CREATED_AT_INDEX)) store.createIndex(CREATED_AT_INDEX, 'createdAt');
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function requestToPromise<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE_NAME, mode);
    const result = await requestToPromise(run(tx.objectStore(STORE_NAME)));
    return result;
  } finally {
    db.close();
  }
}

export async function enqueue(record: { projectId: string; templateId: string; values: QueuedValue[] }): Promise<string> {
  const id = crypto.randomUUID();
  const entry: QueuedRecord = {
    id,
    projectId: record.projectId,
    templateId: record.templateId,
    values: record.values,
    status: 'pending',
    createdAt: new Date().toISOString(),
  };
  await withStore('readwrite', (store) => store.add(entry));
  return id;
}

export async function listPending(): Promise<QueuedRecord[]> {
  return withStore<QueuedRecord[]>('readonly', (store) => store.index(STATUS_INDEX).getAll('pending'));
}

export async function countPending(): Promise<number> {
  return (await listPending()).length;
}

async function updateRecord(id: string, mutate: (record: QueuedRecord) => void): Promise<void> {
  const db = await openDb();
  try {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const record = await requestToPromise(store.get(id) as IDBRequest<QueuedRecord>);
    if (!record) return;
    mutate(record);
    await requestToPromise(store.put(record));
  } finally {
    db.close();
  }
}

export async function markSynced(id: string): Promise<void> {
  await updateRecord(id, (record) => {
    record.status = 'synced';
    record.syncedAt = new Date().toISOString();
    record.error = undefined;
  });
}

export async function markFailed(id: string, error: string): Promise<void> {
  await updateRecord(id, (record) => {
    record.error = error.slice(0, 2000);
  });
}
