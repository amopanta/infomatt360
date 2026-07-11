"use strict";

const path = require("node:path");
const { app, BrowserWindow, ipcMain } = require("electron");
const { initQueue, close, enqueue, countPending, syncPending } = require("./offlineQueue");
const { startStaticServer } = require("./staticServer");

let queueDb = null;
let localServer = null;

async function resolveStartUrl() {
  if (process.env.ELECTRON_START_URL) return process.env.ELECTRON_START_URL;
  // Empaquetado: el frontend construido se copia como recurso extra (ver
  // "extraResources" en package.json). En desarrollo sin ELECTRON_START_URL,
  // cae al build local del frontend si ya existe. Se sirve por HTTP local
  // (no file://) para que las rutas absolutas del build ("/assets/...")
  // resuelvan igual que en un despliegue web real, incluyendo rutas
  // profundas de la SPA como /runtime/xyz.
  const packagedDir = path.join(process.resourcesPath, "frontend-dist");
  const devBuildDir = path.join(__dirname, "..", "..", "frontend", "dist");
  const rootDir = app.isPackaged ? packagedDir : devBuildDir;
  const { server, port } = await startStaticServer(rootDir);
  localServer = server;
  return `http://127.0.0.1:${port}/`;
}

async function createWindow() {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  window.loadURL(await resolveStartUrl());
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
