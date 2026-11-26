/** Render the existing Example Co glossary cover design locally, without CMS writes. */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import sharp from 'sharp'
import { createFont } from './lib-cover-font.mjs'

const ROOT = resolve(import.meta.dirname)
const ASSETS = join(ROOT, 'assets')
const { widthOf, pathOf, wrap } = createFont(ASSETS)
const WIDTH = 1200
const HEIGHT = 800
// Cover colours come from the blog's design tokens; the fallbacks equal the template tokens.
const TOKENS_PATH = join(ROOT, '../../../blog/config/site-brand-tokens.json')
const TOKENS = existsSync(TOKENS_PATH) ? JSON.parse(readFileSync(TOKENS_PATH, 'utf8')) : {}
const YELLOW = TOKENS.yellow?.default ?? '#F2B544'
const DARK = TOKENS.black ?? '#101216'

const args = process.argv.slice(2)
const flag = (name) => args.find((a) => a.startsWith(`--${name}=`))?.slice(name.length + 3)
const TERM = flag('term')
const OUT = flag('out')
if (!TERM || !OUT) throw new Error('Usage: node render-glossary-cover.mjs --term="Term" --out=/path/cover.webp')

function logoMarkup(x, y, width) {
  const raw = readFileSync(join(ASSETS, 'logo.svg'), 'utf8')
  const inner = raw.replace(/^[\s\S]*?<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')
  const height = (width * 28) / 144
  return `<svg x="${x}" y="${y}" width="${width}" height="${height}" viewBox="0 0 144 28" color="#fff">${inner}</svg>`
}

// Layout: "What is" kicker, highlighted term label, dark background, logo.
function coverSvg(term) {
  const PAD = 110
  const maxTextWidth = WIDTH - PAD * 2
  const termSize = term.length > 34 ? 60 : term.length > 22 ? 72 : 88
  const lines = wrap(term, termSize, maxTextWidth - 32)
  const lineHeight = termSize * 1.28
  const blockHeight = 56 * 1.4 + lines.length * lineHeight
  let y = (HEIGHT - blockHeight) / 2 + 56
  const kicker = pathOf('What is', PAD, y, 56, '#FFFFFF')
  y += 56 * 0.5 + lineHeight
  const termMarkup = lines.map((line, i) => {
    const textWidth = widthOf(line, termSize)
    const baseline = y + i * lineHeight
    const rect = `<rect x="${PAD - 16}" y="${baseline - termSize * 0.8}" width="${textWidth + 32}" height="${termSize * 1.08}" rx="12" fill="${YELLOW}"/>`
    return rect + pathOf(line, PAD, baseline, termSize, DARK)
  }).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}">
  <defs><radialGradient id="glow" cx="0.5" cy="0" r="0.85">
    <stop offset="0" stop-color="${YELLOW}" stop-opacity="0.34"/>
    <stop offset="0.55" stop-color="${YELLOW}" stop-opacity="0.08"/>
    <stop offset="1" stop-color="${YELLOW}" stop-opacity="0"/>
  </radialGradient></defs>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="${DARK}"/>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#glow)"/>
  ${kicker}
  ${termMarkup}
  ${logoMarkup(PAD, HEIGHT - 116, 168)}
</svg>`
}

mkdirSync(dirname(OUT), { recursive: true })
const image = await sharp(Buffer.from(coverSvg(TERM))).webp({ quality: 90 }).toBuffer()
writeFileSync(OUT, image)
console.log(`${OUT} (${image.length} bytes, ${WIDTH}x${HEIGHT})`)
