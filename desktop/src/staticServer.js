"use strict";

const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".webmanifest": "application/manifest+json",
  ".ico": "image/x-icon",
};

/**
 * Servidor HTTP estatico minimo con fallback de SPA (sirve index.html para
 * rutas que no coincidan con un archivo real, ej. /runtime/xyz).
 *
 * Se usa en vez de cargar el frontend directo via file://: bajo file://,
 * las rutas absolutas del build ("/assets/...") resuelven contra el
 * filesystem del sistema operativo, no contra la carpeta del HTML, lo que
 * rompe la carga de assets. Sirviendolo por HTTP en localhost, las mismas
 * rutas absolutas que usa el despliegue web normal funcionan igual aqui.
 */
function startStaticServer(rootDir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((request, response) => {
      const urlPath = decodeURIComponent((request.url || "/").split("?")[0]);
      const resolved = path.normalize(path.join(rootDir, urlPath));
      if (!resolved.startsWith(rootDir)) {
        response.writeHead(403);
        response.end();
        return;
      }
      fs.stat(resolved, (statError, stats) => {
        const filePath = statError || stats.isDirectory() ? path.join(rootDir, "index.html") : resolved;
        fs.readFile(filePath, (readError, content) => {
          if (readError) {
            response.writeHead(404);
            response.end("Not found");
            return;
          }
          const ext = path.extname(filePath);
          response.writeHead(200, { "Content-Type": MIME_TYPES[ext] || "application/octet-stream" });
          response.end(content);
        });
      });
    });
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolve({ server, port: typeof address === "object" && address ? address.port : 0 });
    });
  });
}

module.exports = { startStaticServer };
