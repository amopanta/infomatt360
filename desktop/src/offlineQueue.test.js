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

test("syncPending marca como sincronizado cuando el backend responde exitoso", async () => {
  const queue = await initQueue(":memory:");
  enqueue(queue, { projectId: "p1", templateId: "t1", values: sampleValues("Ana") });

  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return { ok: true, json: async () => ({ id: "srv-1", status: "submitted" }) };
  };

  const result = await syncPending(queue, { apiBaseUrl: "http://api.test/api/v1", accessToken: "tok-123", fetchImpl });

  assert.deepEqual(result, { attempted: 1, synced: 1, failed: 0 });
  assert.equal(countPending(queue), 0);
  assert.equal(calls[0].url, "http://api.test/api/v1/runtime/save");
  assert.equal(calls[0].body.status, "submitted");
  assert.equal(calls[0].body.values[0].field_name, "nombre");
});

test("syncPending deja el registro pendiente y guarda el error si el backend falla", async () => {
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
    return { ok: true, json: async () => ({ id: "srv-1", status: "submitted" }) };
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
