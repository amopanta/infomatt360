"use strict";

const { contextBridge, ipcRenderer } = require("electron");

const productionOrigin = new URL(process.env.INFOMATT360_DESKTOP_URL || "https://infomatt360.tecnomatt.com/").origin;
const isLocalDevelopment = /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(location.origin);
if (location.origin !== productionOrigin && !isLocalDevelopment) {
  // No habilitar IPC en una pagina ajena si se abriera por otro camino.
  return;
}

/**
 * Puente minimo hacia el proceso principal para la cola offline. El frontend
 * web (compartido con la version navegador) puede usar `window.desktopBridge`
 * cuando exista para encolar capturas sin conexion y disparar sincronizacion;
 * en el navegador normal esa propiedad simplemente no existe.
 */
contextBridge.exposeInMainWorld("desktopBridge", {
  enqueueRecord: (record) => ipcRenderer.invoke("desktop:enqueue-record", record),
  getPendingCount: () => ipcRenderer.invoke("desktop:pending-count"),
  syncNow: (credentials) => ipcRenderer.invoke("desktop:sync-now", credentials),
  purgeOldSynced: (retentionDays) => ipcRenderer.invoke("desktop:purge-old-synced", retentionDays),
  listPrinters: () => ipcRenderer.invoke("desktop:list-printers"),
  printDocument: (payload) => ipcRenderer.invoke("desktop:print-document", payload),
  printBatch: (payload) => ipcRenderer.invoke("desktop:print-batch", payload),
});
