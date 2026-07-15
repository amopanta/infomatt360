"use strict";

const { contextBridge, ipcRenderer } = require("electron");

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
});
