"use strict";

const path = require("node:path");
const { app, BrowserWindow, ipcMain } = require("electron");
const { initQueue, close, enqueue, countPending, syncPending, purgeOldSynced } = require("./offlineQueue");
const { startStaticServer } = require("./staticServer");
const printing = require("./printing");

const PRODUCTION_URL = "https://infomatt360.tecnomatt.com/";

let queueDb = null;
let localServer = null;
let mainWindow = null;

async function resolveStartUrl() {
  if (process.env.ELECTRON_START_URL) return process.env.ELECTRON_START_URL;
  // El instalador usa el mismo origen del ERP: conserva cookies, CORS y
  // cache PWA, y no depende de un backend localhost inexistente en el PC.
  if (app.isPackaged) return process.env.INFOMATT360_DESKTOP_URL || PRODUCTION_URL;
  // En desarrollo sin ELECTRON_START_URL, usa el build local del frontend.
  // El servidor HTTP permite resolver las rutas absolutas de la SPA.
  const devBuildDir = path.join(__dirname, "..", "..", "frontend", "dist");
  const { server, port } = await startStaticServer(devBuildDir);
  localServer = server;
  return `http://127.0.0.1:${port}/`;
}

async function createWindow() {
  const startUrl = await resolveStartUrl();
  const appOrigin = new URL(startUrl).origin;
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  // El preload da acceso a la cola e impresoras; no lo exponemos a sitios
  // externos abiertos desde un enlace del ERP.
  window.webContents.on("will-navigate", (event, url) => {
    try {
      if (new URL(url).origin !== appOrigin) event.preventDefault();
    } catch {
      event.preventDefault();
    }
  });
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  try {
    await window.loadURL(startUrl);
  } catch {
    const retryUrl = startUrl.replaceAll("&", "&amp;").replaceAll('"', "&quot;");
    await window.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html><html lang="es"><meta charset="utf-8"><title>InfoMatt360</title><body style="font:16px Arial;padding:32px"><h1>Sin conexión</h1><p>Conéctate a internet para iniciar InfoMatt360. Si ya usaste esta aplicación, vuelve a intentarlo cuando regrese la conexión.</p><a href="${retryUrl}">Reintentar</a></body></html>`)}`);
  }
  mainWindow = window;
  return window;
}

function registerIpcHandlers() {
  ipcMain.handle("desktop:enqueue-record", (_event, record) => {
    return enqueue(queueDb, record);
  });

  ipcMain.handle("desktop:pending-count", () => {
    return countPending(queueDb);
  });

  ipcMain.handle("desktop:sync-now", async (_event, { apiBaseUrl, accessToken }) => {
    return syncPending(queueDb, { apiBaseUrl, accessToken });
  });

  ipcMain.handle("desktop:purge-old-synced", (_event, retentionDays) => {
    return purgeOldSynced(queueDb, retentionDays);
  });

  ipcMain.handle("desktop:list-printers", () => {
    return printing.listPrinters(mainWindow.webContents);
  });

  ipcMain.handle("desktop:print-document", (_event, { pdfBytes, deviceName, copies }) => {
    return printing.printPdfBuffer(Buffer.from(pdfBytes), { deviceName, copies });
  });

  ipcMain.handle("desktop:print-batch", (_event, { zipBytes, deviceName, copies }) => {
    return printing.printBatchZip(Buffer.from(zipBytes), { deviceName, copies });
  });
}

app.whenReady().then(async () => {
  queueDb = await initQueue(path.join(app.getPath("userData"), "offline-queue.db"));
  registerIpcHandlers();
  await createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow();
  });
});

app.on("window-all-closed", () => {
  if (queueDb) close(queueDb);
  if (localServer) localServer.close();
  if (process.platform !== "darwin") app.quit();
});
