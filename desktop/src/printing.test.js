"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { zipSync } = require("fflate");
const { extractPdfEntries, summarizePrintResults } = require("./printing");

function fakePdf(text) {
  return new TextEncoder().encode(`%PDF-1.4 fake ${text}`);
}

test("extractPdfEntries ignora manifest.csv y ordena por nombre", () => {
  const zipBuffer = Buffer.from(
    zipSync({
      "b.pdf": fakePdf("b"),
      "a.pdf": fakePdf("a"),
      "manifest.csv": new TextEncoder().encode("record_id,status,error\n"),
    }),
  );
  assert.deepEqual(extractPdfEntries(zipBuffer).map((entry) => entry.name), ["a.pdf", "b.pdf"]);
});

test("extractPdfEntries ignora entradas que no terminan en .pdf", () => {
  const zipBuffer = Buffer.from(zipSync({ "a.pdf": fakePdf("a"), "readme.txt": new TextEncoder().encode("x") }));
  assert.equal(extractPdfEntries(zipBuffer).length, 1);
});

test("extractPdfEntries en un ZIP sin PDFs devuelve arreglo vacio", () => {
  const zipBuffer = Buffer.from(zipSync({ "manifest.csv": new TextEncoder().encode("record_id,status,error\n") }));
  assert.deepEqual(extractPdfEntries(zipBuffer), []);
});

test("summarizePrintResults: todos exitosos", () => {
  const result = summarizePrintResults([
    { name: "a.pdf", success: true, failureReason: null },
    { name: "b.pdf", success: true, failureReason: null },
  ]);
  assert.deepEqual(result, { printed: 2, failed: 0, errors: [] });
});

test("summarizePrintResults: fallas parciales quedan en errors con motivo", () => {
  const result = summarizePrintResults([
    { name: "a.pdf", success: true, failureReason: null },
    { name: "b.pdf", success: false, failureReason: "Printer offline" },
  ]);
  assert.deepEqual(result, { printed: 1, failed: 1, errors: [{ name: "b.pdf", reason: "Printer offline" }] });
});

test("summarizePrintResults: lote vacio", () => {
  assert.deepEqual(summarizePrintResults([]), { printed: 0, failed: 0, errors: [] });
});

test("summarizePrintResults: usa motivo por defecto si failureReason viene vacio", () => {
  const result = summarizePrintResults([{ name: "a.pdf", success: false, failureReason: "" }]);
  assert.equal(result.errors[0].reason, "Error desconocido al imprimir");
});
