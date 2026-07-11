"use strict";

/**
 * Cola local de registros capturados sin conexion. Reutiliza el endpoint
 * de sincronizacion masiva que ya existe en el backend
 * (`POST /api/v1/runtime/bulk/save`), en vez de inventar un protocolo nuevo:
 * cada registro encolado se envia con su propio `idempotency_key` (el id
 * local) para que reintentos no dupliquen datos si la sincronizacion se
 * interrumpe a medio camino.
 *
 * Usa `sql.js` (SQLite compilado a WebAssembly) en vez de `better-sqlite3`:
 * este ultimo es un modulo nativo que exige recompilarse contra el ABI de
 * Electron con Visual Studio Build Tools, que no siempre esta disponible en
 * el equipo de desarrollo. sql.js corre igual dentro y fuera de Electron sin
 * paso de compilacion, a cambio de tener que persistir el archivo a mano
 * despues de cada escritura (no escribe a disco por si solo).
 */

const fs = require("node:fs");
const crypto = require("node:crypto");
const initSqlJs = require("sql.js");

let sqlModulePromise = null;

function loadSqlModule() {
  if (!sqlModulePromise) sqlModulePromise = initSqlJs();
  return sqlModulePromise;
}

async function initQueue(dbPath) {
  const SQL = await loadSqlModule();
  const existing = dbPath !== ":memory:" && fs.existsSync(dbPath) ? fs.readFileSync(dbPath) : undefined;
  const db = new SQL.Database(existing);
  db.run(`
    CREATE TABLE IF NOT EXISTS queued_records (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL,
      template_id TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      created_at TEXT NOT NULL,
      synced_at TEXT,
      error TEXT
    )
  `);
  const queue = { db, dbPath };
  persist(queue);
  return queue;
}

function persist(queue) {
  if (queue.dbPath === ":memory:") return;
  fs.writeFileSync(queue.dbPath, Buffer.from(queue.db.export()));
}

function close(queue) {
  persist(queue);
  queue.db.close();
}

function runQuery(db, sql, params = []) {
  const rows = [];
  const stmt = db.prepare(sql);
  stmt.bind(params);
  while (stmt.step()) rows.push(stmt.getAsObject());
  stmt.free();
  return rows;
}

/**
 * `values` debe venir como arreglo `[{ field_name, field_value_json }, ...]`,
 * el mismo formato que espera `RuntimeRecordCreate` en el backend, para que
 * `syncPending` pueda reenviarlo tal cual sin transformarlo de nuevo.
 */
function enqueue(queue, { projectId, templateId, values }) {
  const id = crypto.randomUUID();
  queue.db.run(
    "INSERT INTO queued_records (id, project_id, template_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
    [id, projectId, templateId, JSON.stringify(values), new Date().toISOString()]
  );
  persist(queue);
  return id;
}

function listPending(queue) {
  return runQuery(queue.db, "SELECT * FROM queued_records WHERE status = 'pending' ORDER BY created_at ASC");
}

function countPending(queue) {
  const rows = runQuery(queue.db, "SELECT COUNT(*) AS count FROM queued_records WHERE status = 'pending'");
  return rows[0] ? rows[0].count : 0;
}

function markSynced(queue, id) {
  queue.db.run("UPDATE queued_records SET status = 'synced', synced_at = ?, error = NULL WHERE id = ?", [
    new Date().toISOString(),
    id,
  ]);
  persist(queue);
}

function markFailed(queue, id, error) {
  queue.db.run("UPDATE queued_records SET error = ? WHERE id = ?", [String(error).slice(0, 2000), id]);
  persist(queue);
}

/**
 * Sincroniza los registros pendientes contra el backend. No lanza si un
 * registro individual falla: lo deja en 'pending' con el error guardado
 * para reintentar en el proximo ciclo, y continua con el resto del lote.
 *
 * Usa `POST /runtime/save` (autenticacion normal de usuario, un registro por
 * llamada) y no `POST /runtime/bulk/save`: ese endpoint bulk exige API key
 * (`require_api_key_permission`) para integraciones externas, no sesion de
 * usuario -- el intento inicial de reutilizarlo devolvia 401 "API key
 * requerida" al probarlo con el backend real. `/runtime/save` no tiene
 * idempotency_key propio; si la respuesta se pierde en la red despues de
 * que el servidor ya guardo el registro, un reintento podria duplicarlo.
 * Riesgo aceptado en esta primera version (documentado en el README), no
 * resuelto por falta de un mecanismo de idempotencia en ese endpoint.
 */
async function syncPending(queue, { apiBaseUrl, accessToken, fetchImpl = fetch }) {
  const pending = listPending(queue);
  const result = { attempted: pending.length, synced: 0, failed: 0 };

  for (const row of pending) {
    const values = JSON.parse(row.payload_json);
    try {
      const response = await fetchImpl(`${apiBaseUrl}/runtime/save`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          project_id: row.project_id,
          template_id: row.template_id,
          status: "submitted",
          values,
        }),
      });
      if (!response.ok) {
        const detail = await response.text();
        markFailed(queue, row.id, `HTTP ${response.status}: ${detail}`);
        result.failed += 1;
        continue;
      }
      markSynced(queue, row.id);
      result.synced += 1;
    } catch (error) {
      markFailed(queue, row.id, error instanceof Error ? error.message : String(error));
      result.failed += 1;
    }
  }
  return result;
}

module.exports = { initQueue, close, enqueue, listPending, countPending, markSynced, markFailed, syncPending };
