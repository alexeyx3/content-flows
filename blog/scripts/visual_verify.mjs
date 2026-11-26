/** Require original dimensions; report pixel changes caused by CMS optimization for QA. */
import { readFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const brandDir = process.env.BLOG_BRAND_DIR || resolve(root, 'tools/covers')
const sharp = createRequire(join(brandDir, 'package.json'))('sharp')
const [local, remote] = await Promise.all([
  sharp(process.argv[2]).ensureAlpha().raw().toBuffer({ resolveWithObject: true }),
  sharp(readFileSync(0)).ensureAlpha().raw().toBuffer({ resolveWithObject: true }),
])
if (local.info.width !== remote.info.width || local.info.height !== remote.info.height ||
    local.info.channels !== remote.info.channels) {
  throw new Error('Uploaded PNG dimensions changed')
}

process.stdout.write(JSON.stringify({pixels_identical: local.data.equals(remote.data)}))
