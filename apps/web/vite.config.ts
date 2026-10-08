import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { createReadStream, existsSync, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { extname, join, normalize, resolve } from "node:path";

const DATA_DIR = resolve(import.meta.dirname, "../../data/build");
const TYPES: Record<string, string> = {
  ".json": "application/json",
  ".pmtiles": "application/octet-stream",
  ".geojsonl": "application/x-ndjson",
};

/** Serve the pipeline's static build at /data (dev + preview), with HTTP Range for PMTiles. */
function serveData(): Plugin {
  return {
    name: "milmap-serve-data",
    configureServer(server) {
      server.middlewares.use("/data", handler);
    },
    configurePreviewServer(server) {
      server.middlewares.use("/data", handler);
    },
  };
}

function handler(req: IncomingMessage, res: ServerResponse, next: () => void) {
  const rel = normalize(decodeURIComponent((req.url ?? "/").split("?")[0]!));
  const file = join(DATA_DIR, rel);
  if (!file.startsWith(DATA_DIR) || !existsSync(file) || !statSync(file).isFile()) return next();
  const size = statSync(file).size;
  res.setHeader("Content-Type", TYPES[extname(file)] ?? "application/octet-stream");
  res.setHeader("Accept-Ranges", "bytes");
  res.setHeader("Cache-Control", "no-cache");
  const m = /bytes=(\d+)-(\d*)/.exec(req.headers.range ?? "");
  if (m) {
    const start = Number(m[1]);
    const end = m[2] ? Number(m[2]) : size - 1;
    res.statusCode = 206;
    res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`);
    res.setHeader("Content-Length", String(end - start + 1));
    createReadStream(file, { start, end }).pipe(res);
    return;
  }
  res.setHeader("Content-Length", String(size));
  createReadStream(file).pipe(res);
}

export default defineConfig({
  plugins: [react(), serveData()],
  // MapLibre v6 is ESM-only and locates its module worker relative to import.meta.url;
  // dependency pre-bundling moves the file and breaks that ("Worker failed to load").
  // Dev: don't pre-bundle it. Prod: src/map/milmap.ts sets an explicit worker URL.
  optimizeDeps: { exclude: ["maplibre-gl"] },
  worker: { format: "es" },
  build: { target: "es2023", sourcemap: true },
  server: { port: 5173 },
});
