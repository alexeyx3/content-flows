/**
 * Blog article covers: the same technique as in the glossary cover script
 * (glossary-covers.mjs): outlines taken from the font file, so that the font is not replaced by a system one.
 *
 * The template is different, and that is not cosmetic: a term has a title of two or three words, while an
 * article has a sentence of 60-90 characters. So there is no "What is" kicker here,
 * the font size is smaller, up to four lines are allowed, and the frame sets the field inside
 * which the text lives.
 *
 *   node article-covers.mjs --slug=<slug>            # one article
 *   node article-covers.mjs --slug=<slug> --out=/tmp # file only
 *   node article-covers.mjs                          # all without a cover
 *
 * The tool is self-contained: fonts and logo live in assets/,
 * and the token is passed through STRAPI_TOKEN. It does not run on the Strapi server.
 *
 * Installation: npm install (sharp + opentype.js), see package.json next to this file.
 * The token is taken from STRAPI_TOKEN, the address from STRAPI_URL.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { createHash } from 'node:crypto'
import sharp from 'sharp'
import opentype from 'opentype.js'
import { createFont } from './lib-cover-font.mjs'

const ROOT = resolve(import.meta.dirname)
const ASSETS = join(ROOT, 'assets')

const { widthOf, pathOf, wrap } = createFont(ASSETS)

const WIDTH = 1200
const HEIGHT = 800
// Cover colours come from the site's design tokens; the fallbacks equal the template tokens.
const TOKENS_PATH = join(ROOT, '../../config/site-brand-tokens.json')
const TOKENS = existsSync(TOKENS_PATH) ? JSON.parse(readFileSync(TOKENS_PATH, 'utf8')) : {}
const YELLOW = TOKENS.yellow?.default ?? '#F2B544'
const DARK = TOKENS.black ?? '#101216'

const args = process.argv.slice(2)
const flag = (name) => {
  const values = args.filter((a) => a.startsWith(`--${name}=`))
  if (values.length > 1) throw new Error(`Duplicate --${name}`)
  return values[0]?.slice(name.length + 3)
}
const ONLY_SLUG = flag('slug')
const OUT_DIR = flag('out')
const LOCALE = flag('locale') ?? 'en'
const EXACT_ID = flag('id')
const INPUT_FILE = flag('file')
const QA_RECEIPT = flag('qa')
const UPLOAD_RECEIPT = flag('receipt')
const FORMAT = flag('format') ?? 'webp'
const FORCE = args.includes('--force')
const SHOW_LOGO = !args.includes('--no-logo')
if (!/^[a-z]{2}(?:-[A-Za-z]{2})?$/.test(LOCALE)) throw new Error('Invalid --locale')
if (LOCALE !== 'en' && !ONLY_SLUG) throw new Error('Non-English cover requires --slug')
if (EXACT_ID && (!ONLY_SLUG || !/^[1-9]\d*$/.test(EXACT_ID))) throw new Error('--id requires --slug and a positive integer')
if (!['png', 'webp'].includes(FORMAT)) throw new Error('--format must be png or webp')
if (INPUT_FILE && (OUT_DIR || !ONLY_SLUG || !EXACT_ID || !UPLOAD_RECEIPT)) {
  throw new Error('--file upload requires --slug, --id and --receipt, and cannot use --out')
}
if (QA_RECEIPT && !INPUT_FILE) throw new Error('--qa requires a pre-rendered --file')

const sha256 = (value) => createHash('sha256').update(value).digest('hex')
const writeJson = (path, value) => {
  mkdirSync(dirname(resolve(path)), { recursive: true })
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`)
}
const normalizedTitle = (value) => String(value ?? '').trim().replace(/\s+/g, ' ')
const fontSlices = ['Exo2-Bold.ttf', 'Exo2-Bold-cyrillic.ttf'].map((name) => {
  const bytes = readFileSync(join(ASSETS, name))
  return opentype.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength))
})
function requireGlyphs(title) {
  const missing = [...new Set([...title].filter((ch) => !fontSlices.some((font) => font.charToGlyph(ch).index !== 0)))]
  if (missing.length) throw new Error(`Cover font lacks glyphs: ${missing.map((ch) => `U+${ch.codePointAt(0).toString(16)}`).join(', ')}`)
}

const API = process.env.STRAPI_URL ?? 'https://cms.example.com'
const TOKEN_FILES = [
  resolve(ROOT, '../../config/strapi-api-token'),
]
function strapiToken() {
  if (process.env.STRAPI_TOKEN?.trim()) return process.env.STRAPI_TOKEN.trim()
  for (const path of TOKEN_FILES) {
    if (!existsSync(path)) continue
    const value = readFileSync(path, 'utf8').trim()
    if (value) return value
  }
  return ''
}
const TOKEN = strapiToken()
if (!TOKEN) throw new Error(`Strapi token not found. Checked STRAPI_TOKEN and ${TOKEN_FILES.join(', ')}`)

function logoMarkup(x, y, width) {
  const raw = readFileSync(join(ASSETS, 'logo.svg'), 'utf8')
  const inner = raw.replace(/^[\s\S]*?<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')
  return `<svg x="${x}" y="${y}" width="${width}" height="${(width * 28) / 144}" viewBox="0 0 144 28" color="#fff">${inner}</svg>`
}

// The outline is always taken in one configuration (origin at zero and the natural
// font size), because opentype.js 2.0.0 returns NaN at some font sizes.
// Position and scale go into transform. Details are in glossary-covers.mjs.
/** An article title is longer than a term, so the font size is chosen to fit the number of lines. */
function fitTitle(title, maxWidth) {
  if (!title) throw new Error('Cover title is empty')
  requireGlyphs(title)
  for (const size of [72, 64, 56, 48, 42, 38]) {
    const lines = wrap(title, size, maxWidth)
    const maxLines = size >= 42 ? 4 : 5
    if (lines.length <= maxLines && lines.length * size * 1.24 <= 400 && lines.every((line) => widthOf(line, size) <= maxWidth)) {
      if (lines.join(' ') !== title) throw new Error('Cover layout changed title text')
      return { size, lines }
    }
  }
  throw new Error('Full cover title cannot fit safely; no truncation is allowed')
}

function coverSvg(title) {
  const INSET = 56
  const PAD = INSET + 70
  const maxWidth = WIDTH - PAD * 2
  const { size, lines } = fitTitle(title, maxWidth)
  const lineHeight = size * 1.24

  const blockHeight = lines.length * lineHeight
  // Minus 40: the logo at the bottom weighs the bottom down, and a text block at the geometric
  // centre reads as shifted down. Shift it to the optical centre.
  const first = (HEIGHT - blockHeight) / 2 + size * 0.72 - 40

  const text = lines
    .map((line, i) =>
      pathOf(line, (WIDTH - widthOf(line, size)) / 2, first + i * lineHeight, size, '#FFFFFF'),
    )
    .join('')

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}">
  <defs>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.75">
      <stop offset="0" stop-color="${YELLOW}" stop-opacity="0.3"/>
      <stop offset="0.6" stop-color="${YELLOW}" stop-opacity="0.07"/>
      <stop offset="1" stop-color="${YELLOW}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="${DARK}"/>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#glow)"/>
  <rect x="${INSET}" y="${INSET}" width="${WIDTH - INSET * 2}" height="${HEIGHT - INSET * 2}" rx="28" fill="none" stroke="${YELLOW}" stroke-opacity="0.55" stroke-width="3"/>
  ${text}
  ${SHOW_LOGO ? logoMarkup((WIDTH - 168) / 2, HEIGHT - INSET - 76, 168) : ''}
</svg>`
}

async function api(path, init = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${TOKEN}`, ...(init.headers ?? {}) },
  })
  if (!res.ok) throw new Error(`${init.method ?? 'GET'} ${path} → HTTP ${res.status}`)
  return res.json()
}

const attributes = (entry) => entry.attributes ?? entry
const coverId = (entry) => {
  const cover = attributes(entry).cover
  return cover?.data?.id ?? cover?.id ?? null
}
function requireIdentity(entry, expectedId, expectedTitle) {
  if (!entry || !Number.isSafeInteger(entry.id) || entry.id <= 0) throw new Error('Cover target has no exact numeric ID')
  const a = attributes(entry)
  if (a.locale !== LOCALE || (ONLY_SLUG && a.slug !== ONLY_SLUG)) throw new Error('Cover target locale/slug mismatch')
  if (expectedId !== undefined && entry.id !== Number(expectedId)) throw new Error('Cover target ID mismatch')
  if (expectedTitle !== undefined && normalizedTitle(a.title) !== expectedTitle) throw new Error('Cover target title changed')
  return entry
}
async function selectedTarget(expectedId, expectedTitle) {
  const response = await api(`/api/articles/${encodeURIComponent(ONLY_SLUG)}/findBySlug?locale=${encodeURIComponent(LOCALE)}`)
  return requireIdentity(response.data, expectedId, expectedTitle)
}

// The list via /api/articles does not see drafts: the controller hard-codes
// publicationState = 'live' and ignores the query parameter. So a specific slug
// is requested through findBySlug, which goes to the database directly and returns the record in any
// state. Needed for the blog pipeline: the cover is set on a draft, before publication.
let targets
if (ONLY_SLUG) {
  targets = [await selectedTarget(EXACT_ID)]
  console.log(`slug ${ONLY_SLUG}, locale ${LOCALE}: found`)
} else {
  const res = await api('/api/articles?pagination[pageSize]=100&populate=cover&locale=en')
  targets = res.data.filter((entry) => {
    requireIdentity(entry)
    const a = entry.attributes ?? entry
    return FORCE || OUT_DIR || !a.cover
  })
  console.log(`articles: ${res.data.length}, to render: ${targets.length}`)
}

for (const entry of targets) {
  requireIdentity(entry, EXACT_ID)
  const a = attributes(entry)
  const title = normalizedTitle(a.title)
  const titleLayout = fitTitle(title, WIDTH - (56 + 70) * 2)
  let buf, format, renderReceipt
  if (INPUT_FILE) {
    const path = resolve(INPUT_FILE)
    buf = readFileSync(path)
    const receiptPath = `${path}.render.json`
    if (!existsSync(receiptPath)) throw new Error('Reviewed local image needs its render receipt')
    renderReceipt = JSON.parse(readFileSync(receiptPath, 'utf8'))
    if (renderReceipt.version !== 1 || renderReceipt.target_id !== entry.id || renderReceipt.locale !== LOCALE ||
        renderReceipt.slug !== a.slug || renderReceipt.title !== title || renderReceipt.file_sha256 !== sha256(buf)) {
      throw new Error('Existing local image/render receipt differs from target or bytes')
    }
    if (QA_RECEIPT) {
      const qa = JSON.parse(readFileSync(QA_RECEIPT, 'utf8'))
      const identity = ['target_id', 'slug', 'locale', 'file_sha256', 'preview_sha256']
      if (qa.verdict !== 'PASS' || qa.viewed_full !== true || qa.viewed_mobile !== true ||
          typeof qa.reviewer !== 'string' || !qa.reviewer.trim() ||
          identity.some((key) => qa[key] !== renderReceipt[key]) ||
          qa.render_receipt_sha256 !== sha256(readFileSync(receiptPath)) ||
          qa.preview_sha256 !== sha256(readFileSync(renderReceipt.preview_path))) {
        throw new Error('Independent two-size cover QA is missing or stale')
      }
    }
    const metadata = await sharp(buf).metadata()
    format = metadata.format
    if (!['png', 'webp'].includes(format) || metadata.width !== WIDTH || metadata.height !== HEIGHT || renderReceipt.format !== format) {
      throw new Error('Existing local cover format/dimensions differ')
    }
  } else {
    format = FORMAT
    const image = sharp(Buffer.from(coverSvg(title)))
    buf = format === 'png' ? await image.png().toBuffer() : await image.webp({ quality: 90 }).toBuffer()
  }

  if (OUT_DIR) {
    mkdirSync(OUT_DIR, { recursive: true })
    const path = resolve(OUT_DIR, `${a.slug}.${format}`)
    const preview = resolve(OUT_DIR, `${a.slug}.390.png`)
    writeFileSync(path, buf)
    await sharp(buf).resize({ width: 390 }).png().toFile(preview)
    writeJson(`${path}.render.json`, {
      version: 1, target_id: entry.id, locale: LOCALE, slug: a.slug, title,
      file_path: path, file_sha256: sha256(buf), format, width: WIDTH, height: HEIGHT,
      preview_path: preview, preview_sha256: sha256(readFileSync(preview)), preview_width: 390,
      glyph_coverage: 'PASS', full_title_preserved: true, title_layout: titleLayout,
    })
    console.log(`  ${a.slug}.${format} → ${OUT_DIR} (${(buf.length / 1024).toFixed(0)} KB), preview 390px`)
    continue
  }

  let upload = UPLOAD_RECEIPT && existsSync(UPLOAD_RECEIPT) ? JSON.parse(readFileSync(UPLOAD_RECEIPT, 'utf8')) : null
  if (upload && (upload.target_id !== entry.id || upload.locale !== LOCALE || upload.slug !== a.slug || upload.file_sha256 !== sha256(buf))) {
    throw new Error('Saved cover upload receipt belongs to different target or image bytes')
  }
  const fresh = ONLY_SLUG ? await selectedTarget(entry.id, title) : requireIdentity((await api(`/api/articles/${entry.id}`)).data, entry.id, title)
  let file
  if (upload) {
    if (!Number.isSafeInteger(upload.media_id) || upload.media_id <= 0) throw new Error('Prior upload outcome is ambiguous; never repeat POST automatically')
    file = { id: upload.media_id, url: upload.media_url }
    if (![upload.cover_before, file.id].includes(coverId(fresh))) throw new Error('Target cover changed since saved upload')
  } else {
    if (coverId(fresh) !== coverId(entry)) throw new Error('Target cover changed before upload')
    upload = { version: 1, status: 'upload_pending', target_id: entry.id, locale: LOCALE, slug: a.slug, title,
      file_path: INPUT_FILE ? resolve(INPUT_FILE) : null, file_sha256: sha256(buf), format,
      cover_before: coverId(fresh), media_id: null, media_url: null }
    if (UPLOAD_RECEIPT) writeJson(UPLOAD_RECEIPT, upload)
    const form = new FormData()
    form.append('files', new Blob([buf], { type: `image/${format}` }), `article-${a.slug}${LOCALE === 'en' ? '' : `-${LOCALE}`}.${format}`)
    const response = await api('/api/upload', { method: 'POST', body: form })
    file = response[0]
    if (!Number.isSafeInteger(file?.id) || file.id <= 0 || !file.url) throw new Error('Media upload returned no durable ID/URL')
    upload = { ...upload, status: 'uploaded', media_id: file.id, media_url: file.url }
    if (UPLOAD_RECEIPT) writeJson(UPLOAD_RECEIPT, upload)
  }
  const beforeAssociation = ONLY_SLUG ? await selectedTarget(entry.id, title) : requireIdentity((await api(`/api/articles/${entry.id}`)).data, entry.id, title)
  if (![upload.cover_before, file.id].includes(coverId(beforeAssociation))) throw new Error('Target cover changed before association')
  if (coverId(beforeAssociation) !== file.id) {
    await api(`/api/articles/${entry.id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: { cover: file.id } }),
    })
  }
  const stored = ONLY_SLUG ? await selectedTarget(entry.id, title) : requireIdentity((await api(`/api/articles/${entry.id}`)).data, entry.id, title)
  if (coverId(stored) !== file.id) throw new Error('Target cover readback differs from uploaded media')
  if (UPLOAD_RECEIPT) writeJson(UPLOAD_RECEIPT, { ...upload, status: 'complete' })
  console.log(`  ${a.slug}: cover uploaded (${(buf.length / 1024).toFixed(0)} KB)`)
}
