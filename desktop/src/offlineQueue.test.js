"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { initQueue, enqueue, listPending, countPending, syncPending } = require("./offlineQueue");

function sampleValues(text) {
  return [{ field_name: "nombre", field_value_json: JSON.stringify(text) }];
}

test("enqueue guarda un registro pendiente y countPending lo refleja", async () => {
  const queue = await initQueue(":memory:");
  assert.equal(countPending(queue), 0);
  const id = enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Ana") });
  assert.equal(countPending(queue), 1);
  assert.equal(listPending(queue)[0].id, id);
});

test("syncPending agrupa la cola en un solo lote a /runtime/session/bulk-save", async () => {
  const queue = await initQueue(":memory:");
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Ana") });
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Beatriz") });

  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return {
      ok: true,
      json: async () => ({
        results: [
          { index: 0, id: "srv-1", status: "created" },
          { index: 1, id: "srv-2", status: "created" },
        ],
      }),
    };
  };

  const result = await syncPending(queue, { apiBaseUrl: "http://api.test/api/v1", accessToken: "tok-123", fetchImpl });

  assert.deepEqual(result, { attempted: 2, synced: 2, failed: 0 });
  assert.equal(countPending(queue), 0);
  assert.equal(calls.length, 1); // un solo request, no dos
  assert.equal(calls[0].url, "http://api.test/api/v1/runtime/session/bulk-save");
  assert.equal(calls[0].body.project_id, "p1");
  assert.equal(calls[0].body.template_id, "t1");
  assert.equal(calls[0].body.records.length, 2);
  assert.match(calls[0].body.idempotency_key, /^[0-9a-f]{64}$/);
  assert.equal(calls[0].body.records[0].values[0].field_name, "nombre");
});

test("syncPending agrupa por plantilla: dos plantillas distintas generan dos lotes separados", async () => {
  const queue = await initQueue(":memory:");
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Ana") });
  enqueue(queue, { projectId: "p1", templateId: "t2", values: sampleValues("Beatriz") });

  const calls = [];
  const fetchImpl = async (_url, options) => {
    calls.push({ body: JSON.parse(options.body) });
    return { ok: true, json: async () => ({ results: [{ index: 0, status: "created" }] }) };
  };

  const result = await syncPending(queue, { apiBaseUrl: "http://api.test/api/v1", accessToken: "tok-123", fetchImpl });

  assert.deepEqual(result, { attempted: 2, synced: 2, failed: 0 });
  assert.equal(calls.length, 2);
  assert.deepEqual(new Set(calls.map((call) => call.body.template_id)), new Set(["t1", "t2"]));
});

test("syncPending deja pendiente solo el registro que el servidor reporta como fallido dentro del lote", async () => {
  const queue = await initQueue(":memory:");
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Ana") });
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Beatriz") });

  const fetchImpl = async () => ({
    ok: true,
    json: async () => ({
      results: [
        { index: 0, id: "srv-1", status: "created" },
        { index: 1, status: "failed", error: "contenido invalido" },
      ],
    }),
  });

  const result = await syncPending(queue, { apiBaseUrl: "http://api.test/api/v1", accessToken: "tok-123", fetchImpl });

  assert.deepEqual(result, { attempted: 2, synced: 1, failed: 1 });
  assert.equal(countPending(queue), 1);
  assert.match(listPending(queue)[0].error, /contenido invalido/);
});

test("syncPending deja todo el lote pendiente y guarda el error si el backend falla", async () => {
  const queue = await initQueue(":memory:");
  const id = enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Ana") });

  const fetchImpl = async () => ({ ok: false, status: 500, text: async () => "error interno" });
  const result = await syncPending(queue, { apiBaseUrl: "http://api.test/api/v1", accessToken: "tok-123", fetchImpl });

  assert.deepEqual(result, { attempted: 1, synced: 0, failed: 1 });
  assert.equal(countPending(queue), 1);
  const row = listPending(queue)[0];
  assert.equal(row.id, id);
  assert.match(row.error, /HTTP 500/);
});

test("syncPending no reintenta registros ya sincronizados (idempotencia local)", async () => {
  const queue = await initQueue(":memory:");
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Ana") });

  let callCount = 0;
  const fetchImpl = async () => {
    callCount += 1;
    return { ok: true, json: async () => ({ results: [{ index: 0, status: "created" }] }) };
  };

  await syncPending(queue, { apiBaseUrl: "http://api.test/api/v1", accessToken: "tok-123", fetchImpl });
  const second = await syncPending(queue, { apiBaseUrl: "http://api.test/api/v1", accessToken: "tok-123", fetchImpl });

  assert.equal(callCount, 1);
  assert.deepEqual(second, { attempted: 0, synced: 0, failed: 0 });
});

test("syncPending maneja un error de red (fetch rechaza) sin lanzar", async () => {
  const queue = await initQueue(":memory:");
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Ana") });

  const fetchImpl = async () => {
    throw new Error("ECONNREFUSED");
  };
  const result = await syncPending(queue, { apiBaseUrl: "http://api.test/api/v1", accessToken: "tok-123", fetchImpl });

  assert.deepEqual(result, { attempted: 1, synced: 0, failed: 1 });
  assert.match(listPending(queue)[0].error, /ECONNREFUSED/);
});

test("initQueue persiste en disco y recupera los datos al reabrir", async () => {
  const os = require("node:os");
  const path = require("node:path");
  const fs = require("node:fs");
  const dbPath = path.join(os.tmpdir(), `infomatt360-offline-queue-test-${Date.now()}.sqlite`);

  const queue = await initQueue(dbPath);
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Persistido") });

  const reopened = await initQueue(dbPath);
  assert.equal(countPending(reopened), 1);
  assert.equal(JSON.parse(listPending(reopened)[0].payload_json)[0].field_value_json, JSON.stringify("Persistido"));

  fs.unlinkSync(dbPath);
});
