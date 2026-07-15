"use strict";

/**
 * Cola local de registros capturados sin conexion. Sincroniza contra
 * `POST /api/v1/runtime/session/bulk-save` (sesion normal de usuario, ver
 * docs/106) agrupando los pendientes por (proyecto, plantilla) -- un lote
 * por grupo, no una solicitud HTTP por registro. Cada lote lleva su propio
 * `idempotency_key` (hash de los ids locales que lo componen) para que un
 * reintento tras una respuesta perdida no duplique datos.
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
  // Ver auditoria tecnica de julio 2026, hallazgo SYNC-004: listPending ya
  // filtraba con WHERE en SQL (no un full scan en JS como IndexedDB), pero
  // sin indice sigue siendo un recorrido completo de la tabla a partir de
  // cierto volumen de cola.
  db.run("CREATE INDEX IF NOT EXISTS idx_queued_records_status ON queued_records(status)");
  db.run("CREATE INDEX IF NOT EXISTS idx_queued_records_created_at ON queued_records(created_at)");
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

function groupByTemplate(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = `${row.project_id}::${row.template_id}`;
    const group = groups.get(key);
    if (group) group.push(row);
    else groups.set(key, [row]);
  }
  return groups;
}

/** Hash estable del conjunto de ids locales de un lote, usado como
 * idempotency_key -- ver mismo mecanismo en frontend/src/modules/offline/offlineSync.ts. */
function hashIds(ids) {
  const sorted = [...ids].sort();
  return crypto.createHash("sha256").update(sorted.join(",")).digest("hex");
}

/**
 * Sincroniza los registros pendientes contra el backend, agrupados por
 * (proyecto, plantilla): un lote por grupo via
 * `POST /runtime/session/bulk-save` (sesion normal de usuario), no una
 * solicitud HTTP por registro (ver auditoria tecnica de julio 2026,
 * hallazgo SYNC-001, y docs/106). No lanza si un registro individual del
 * lote falla: lo deja en 'pending' con el error guardado para reintentar
 * en el proximo ciclo, y continua con el resto.
 *
 * Distinto de `POST /runtime/bulk/save`: ese endpoint bulk exige API key
 * (`require_api_key_permission`) para integraciones externas, no sesion de
 * usuario -- el intento inicial de reutilizarlo devolvia 401 "API key
 * requerida" al probarlo con el backend real.
 */
async function syncPending(queue, { apiBaseUrl, accessToken, fetchImpl = fetch }) {
  const pending = listPending(queue);
  const result = { attempted: pending.length, synced: 0, failed: 0 };

  for (const group of groupByTemplate(pending).values()) {
    const { project_id: projectId, template_id: templateId } = group[0];
    const idempotencyKey = hashIds(group.map((row) => row.id));
    try {
      const response = await fetchImpl(`${apiBaseUrl}/runtime/session/bulk-save`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          project_id: projectId,
          template_id: templateId,
          idempotency_key: idempotencyKey,
          records: group.map((row) => ({
            project_id: row.project_id,
            template_id: row.template_id,
            status: "submitted",
            values: JSON.parse(row.payload_json),
          })),
        }),
      });
      if (!response.ok) {
        const detail = await response.text();
        for (const row of group) markFailed(queue, row.id, `HTTP ${response.status}: ${detail}`);
        result.failed += group.length;
        continue;
      }
      const data = await response.json();
      for (const item of data.results) {
        const row = group[item.index];
        if (!row) continue;
        if (item.status === "created") {
          markSynced(queue, row.id);
          result.synced += 1;
        } else {
          markFailed(queue, row.id, item.error || "Error desconocido al sincronizar");
          result.failed += 1;
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      for (const row of group) markFailed(queue, row.id, message);
      result.failed += group.length;
    }
  }
  return result;
}

module.exports = { initQueue, close, enqueue, listPending, countPending, markSynced, markFailed, syncPending };
