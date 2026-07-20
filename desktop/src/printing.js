"use strict";

/**
 * Impresion nativa desde el shell de Electron (docs/96 item #10): imprime
 * los PDF de acta que el backend ya genera (docs/109/110) usando el
 * selector de impresora del sistema operativo (Electron 43,
 * webContents.print/getPrintersAsync), sin pasar por el dialogo de
 * impresion del navegador. Las funciones que tocan la API real de Electron
 * solo pueden ejercitarse dentro de un proceso de Electron real -- no hay
 * forma de probarlas con node --test (mismo precedente de honestidad que
 * docs/113 para el camino Postgres/PostGIS real y docs/114 para Tableau
 * Desktop real). extractPdfEntries y summarizePrintResults son logica
 * pura (nunca tocan electron) y si estan cubiertas por
 * desktop/src/printing.test.js.
 */

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { pathToFileURL } = require("node:url");
const { app, BrowserWindow } = require("electron");
const { unzipSync } = require("fflate");

/** Lista las impresoras del sistema operativo via el webContents de una
 * ventana ya cargada (se reusa la ventana principal, no hace falta crear
 * una oculta solo para listar). Solo ejercitable dentro de Electron real. */
async function listPrinters(webContents) {
  const printers = await webContents.getPrintersAsync();
  return printers.map((printer) => ({
    name: printer.name,
    displayName: printer.displayName || printer.name,
    isDefault: Boolean(printer.isDefault),
  }));
}

function tempPdfPath() {
  return path.join(app.getPath("temp"), `infomatt360-acta-${crypto.randomUUID()}.pdf`);
}

/** Borrado del temporal en el mejor esfuerzo: un fallo al limpiar no debe
 * ocultar el resultado real de la impresion, que ya se resolvio antes. */
async function removeTempFileQuietly(tempPath) {
  try {
    await fs.promises.unlink(tempPath);
  } catch {
    // Limpieza best-effort; el archivo queda en el directorio temporal del
    // SO, que el propio SO purga eventualmente.
  }
}

/** Ventana oculta reutilizable: carga PDFs via file:// (Chromium trae su
 * visor de PDF nativo) y expone webContents.print. pathToFileURL evita
 * los problemas de rutas absolutas de Windows (unidad C:\...) que
 * loadFile con rutas fuera del bundle de la app no maneja de forma
 * confiable. */
async function createHiddenPdfWindow() {
  return new BrowserWindow({
    show: false,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
}

/** Carga un PDF ya escrito a disco en `window` y lo imprime. deviceName
 * ausente/vacio deja que Electron use la impresora predeterminada del SO
 * -- se omite la clave en vez de mandarla undefined explicito. */
async function printLoadedPdf(window, tempPath, { deviceName, copies = 1, silent = true } = {}) {
  await window.loadURL(pathToFileURL(tempPath).toString());
  const options = { silent, printBackground: true, copies };
  if (deviceName) options.deviceName = deviceName;
  return new Promise((resolve) => {
    window.webContents.print(options, (success, failureReason) => {
      resolve({ success, failureReason: success ? null : failureReason });
    });
  });
}

/** Imprime un solo PDF (acta de un registro, docs/109). Crea y destruye su
 * propia ventana oculta -- para un solo documento no vale la pena
 * mantenerla viva. */
async function printPdfBuffer(pdfBuffer, options = {}) {
  const tempPath = tempPdfPath();
  await fs.promises.writeFile(tempPath, pdfBuffer);
  const window = await createHiddenPdfWindow();
  try {
    return await printLoadedPdf(window, tempPath, options);
  } finally {
    window.destroy();
    await removeTempFileQuietly(tempPath);
  }
}

/**
 * Extrae las entradas imprimibles de un ZIP de actas en lote (docs/96 item
 * #5, docs/110): ignora manifest.csv y cualquier entrada que no termine
 * en .pdf, ordena por nombre para un orden de impresion determinista.
 * Logica pura (solo usa fflate, sin electron) -- probable con
 * node --test.
 */
function extractPdfEntries(zipBuffer) {
  const files = unzipSync(new Uint8Array(zipBuffer));
  return Object.keys(files)
    .filter((name) => name !== "manifest.csv" && name.toLowerCase().endsWith(".pdf"))
    .sort()
    .map((name) => ({ name, bytes: files[name] }));
}

/**
 * Resume una lista de resultados por item en {printed, failed, errors},
 * mismo espiritu "por item, uno que falla no aborta el lote" que ya usa
 * acta_service.render_pdf_batch/manifest.csv en el backend y
 * syncPending en offlineQueue.js. Logica pura -- probable con
 * node --test.
 */
function summarizePrintResults(items) {
  const errors = items
    .filter((item) => !item.success)
    .map((item) => ({ name: item.name, reason: item.failureReason || "Error desconocido al imprimir" }));
  return { printed: items.length - errors.length, failed: errors.length, errors };
}

/**
 * Imprime cada PDF de un ZIP de actas en lote, secuencialmente, sobre una
 * unica ventana oculta reutilizada (evitar crear hasta 200 procesos de
 * renderizado -- ver settings.acta_batch_max_records en
 * backend/app/core/config.py, docs/110). Un item que falla no aborta el
 * lote; el resultado final mimica la forma de manifest.csv.
 */
async function printBatchZip(zipBuffer, options = {}) {
  const entries = extractPdfEntries(zipBuffer);
  const window = await createHiddenPdfWindow();
  const items = [];
  try {
    for (const entry of entries) {
      const tempPath = tempPdfPath();
      await fs.promises.writeFile(tempPath, entry.bytes);
      try {
        const result = await printLoadedPdf(window, tempPath, options);
        items.push({ name: entry.name, success: result.success, failureReason: result.failureReason });
      } catch (error) {
        items.push({ name: entry.name, success: false, failureReason: error instanceof Error ? error.message : String(error) });
      } finally {
        await removeTempFileQuietly(tempPath);
      }
    }
  } finally {
    window.destroy();
  }
  return summarizePrintResults(items);
}

module.exports = { listPrinters, printPdfBuffer, printBatchZip, extractPdfEntries, summarizePrintResults };
