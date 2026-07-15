/**
 * Tipo del puente expuesto por el shell de Electron (`desktop/src/preload.js`).
 * En el navegador normal `window.desktopBridge` no existe; todo lo que
 * depende de esto debe verificar `isDesktopApp()` primero.
 */

export type DesktopSyncResult = { attempted: number; synced: number; failed: number };

export type DesktopRecordValue = { field_name: string; field_value_json: string };

export type DesktopBridge = {
  enqueueRecord: (record: { projectId: string; templateId: string; values: DesktopRecordValue[] }) => Promise<string>;
  getPendingCount: () => Promise<number>;
  syncNow: (credentials: { apiBaseUrl: string; accessToken: string }) => Promise<DesktopSyncResult>;
  purgeOldSynced: (retentionDays: number) => Promise<number>;
};

declare global {
  interface Window {
    desktopBridge?: DesktopBridge;
  }
}

export function isDesktopApp(): boolean {
  return typeof window !== 'undefined' && Boolean(window.desktopBridge);
}
