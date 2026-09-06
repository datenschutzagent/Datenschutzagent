#!/usr/bin/env node
// Prints raw and gzip sizes of every JS/CSS chunk in a Vite output directory,
// largest first, plus totals. Used by CI (test.yml) to publish a bundle-size
// artifact; no dependencies beyond Node's standard library.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const dir = process.argv[2] ?? "dist/assets";
const rows = readdirSync(dir)
  .filter((f) => /\.(js|css)$/.test(f))
  .map((f) => {
    const path = join(dir, f);
    const raw = statSync(path).size;
    const gzip = gzipSync(readFileSync(path)).length;
    return { file: f, raw, gzip };
  })
  .sort((a, b) => b.gzip - a.gzip);

const kb = (n) => `${(n / 1024).toFixed(1).padStart(8)} kB`;
console.log(`${"chunk".padEnd(48)} ${"raw".padStart(11)} ${"gzip".padStart(11)}`);
for (const r of rows) {
  console.log(`${r.file.padEnd(48)} ${kb(r.raw)} ${kb(r.gzip)}`);
}
const total = rows.reduce((acc, r) => ({ raw: acc.raw + r.raw, gzip: acc.gzip + r.gzip }), {
  raw: 0,
  gzip: 0,
});
console.log(`${"TOTAL".padEnd(48)} ${kb(total.raw)} ${kb(total.gzip)}  (${rows.length} chunks)`);
