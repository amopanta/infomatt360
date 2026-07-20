/**
 * Tipo del puente expuesto por el shell de Electron (`desktop/src/preload.js`).
 * En el navegador normal `window.desktopBridge` no existe; todo lo que
 * depende de esto debe verificar `isDesktopApp()` primero.
 */

export type DesktopSyncResult = { attempted: number; synced: number; failed: number };

export type DesktopRecordValue = { field_name: string; field_value_json: string };

/** Impresión nativa (docs/96 item #10): el proceso principal de Electron
 * expone las impresoras del sistema operativo y ejecuta webContents.print
 * sobre los PDF que el backend ya genera (docs/109/110) -- ver
 * desktop/src/printing.js. */
export type PrinterInfo = { name: string; displayName: string; isDefault: boolean };

export type DesktopPrintResult = { success: boolean; failureReason: string | null };

export type DesktopBatchPrintResult = { printed: number; failed: number; errors: Array<{ name: string; reason: string }> };

export type DesktopBridge = {
  enqueueRecord: (record: { projectId: string; templateId: string; values: DesktopRecordValue[] }) => Promise<string>;
  getPendingCount: () => Promise<number>;
  syncNow: (credentials: { apiBaseUrl: string; accessToken: string }) => Promise<DesktopSyncResult>;
  purgeOldSynced: (retentionDays: number) => Promise<number>;
  listPrinters: () => Promise<PrinterInfo[]>;
  printDocument: (payload: { pdfBytes: ArrayBuffer; deviceName?: string; copies?: number }) => Promise<DesktopPrintResult>;
  printBatch: (payload: { zipBytes: ArrayBuffer; deviceName?: string; copies?: number }) => Promise<DesktopBatchPrintResult>;
};

declare global {
  interface Window {
    desktopBridge?: DesktopBridge;
  }
}

export function isDesktopApp(): boolean {
  return typeof window !== 'undefined' && Boolean(window.desktopBridge);
}
