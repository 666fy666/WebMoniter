import { readdirSync, readFileSync, statSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
const assets = new URL('../dist/assets/', import.meta.url)
let total = 0
for (const name of readdirSync(assets)) {
  if (/\.(js|css)$/.test(name)) total += gzipSync(readFileSync(new URL(name, assets))).length
}
console.log(`全部 JS/CSS gzip: ${(total / 1024).toFixed(1)} KiB（预算 250 KiB）`)
if (total > 250 * 1024) process.exit(1)
