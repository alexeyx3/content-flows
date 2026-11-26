/** Create the exact-width mobile preview used by visual QA. */
import { createRequire } from 'node:module'
import { resolve, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const requireBrand = createRequire(join(root, 'tools/covers/package.json'))
const sharp = requireBrand('sharp')
const [source, output] = process.argv.slice(2)
if (!source || !output) throw new Error('source and output paths are required')
await sharp(source).resize({ width: 390 }).png({ compressionLevel: 9 }).toFile(output)
