/** Render a data-backed visual from stdin. Uses the existing cover font and logo assets. */
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'

const ROOT = resolve(fileURLToPath(new URL('..', import.meta.url)))
const brandDir = process.env.BLOG_BRAND_DIR || resolve(ROOT, '../brand')
const requireBrand = createRequire(join(brandDir, 'package.json'))
const sharp = requireBrand('sharp')
const { createFont } = await import(pathToFileURL(join(brandDir, 'lib-cover-font.mjs')))
const font = createFont(join(brandDir, 'assets'))
const logoPath = process.env.BLOG_LOGO_PATH || resolve(brandDir, 'logo.svg')
const visual = JSON.parse(readFileSync(0, 'utf8'))
const output = process.argv[2]
if (!output) throw new Error('PNG output path is required')
const W = 1200
// Colours come from country-guides/config/site-brand-tokens.json; the fallbacks equal the template tokens.
const tokensPath = resolve(ROOT, '../../config/site-brand-tokens.json')
const tokens = existsSync(tokensPath) ? JSON.parse(readFileSync(tokensPath, 'utf8')) : {}
const DARK = tokens.black ?? '#101216', WHITE = tokens.white ?? '#FFFFFF', MUTED = '#C5C9D4'
const YELLOW = tokens.yellow?.default ?? '#F2B544'
const COLORS = [YELLOW, WHITE, tokens.gray?.default ?? '#A9A9A2']
const shapes = []
const esc = (s) => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;')
const number = (x) => new Intl.NumberFormat(visual.language === 'ru' ? 'ru-RU' : 'en-US', {
  maximumFractionDigits: 6,
}).format(x)

function text(value, x, y, size = 32, color = WHITE, width = null, maxLines = 2) {
  const lines = width ? font.wrap(String(value), size, width) : [String(value)]
  if (lines.length > maxLines || lines.some(line => width && font.widthOf(line, size) > width)) {
    throw new Error(`Label is too long: ${value}. Shorten it; renderer never truncates.`)
  }
  lines.forEach((line, i) => shapes.push(font.pathOf(line, x, y + i * size * 1.22, size, color)))
  return lines.length * size * 1.22
}

function centeredText(value, x, y, size, color, width, maxLines) {
  const lines = font.wrap(String(value), size, width)
  if (lines.length > maxLines || lines.some(line => font.widthOf(line, size) > width)) {
    throw new Error(`Label is too long: ${value}. Shorten it; renderer never truncates.`)
  }
  lines.forEach((line, i) => {
    const lineWidth = font.widthOf(line, size)
    const left = Math.max(56, Math.min(x - lineWidth / 2, W - 56 - lineWidth))
    text(line, left, y + i * size * 1.22, size, color)
  })
}

const headerHeight = 60 + text(visual.title, 56, 70, 42, WHITE, 1088, 3)
let y = headerHeight + 30
let H

if (visual.type === 'bar') {
  const { categories, series, unit } = visual.data
  text(unit, 56, y, 28, MUTED, 1050, 2)
  y += 52
  for (let i = 0; i < series.length; i++) {
    shapes.push(`<rect x="56" y="${y - 24}" width="22" height="22" fill="${COLORS[i]}" rx="3"/>`)
    text(series[i].name, 94, y, 28, WHITE, 1000, 1)
    y += 42
  }
  y += 24
  const maximum = Math.max(...series.flatMap(s => s.values), 1)
  // One decimal rule per chart: 1,521.60 next to 1,515.49, not 1,521.6.
  const decimals = visual.data.value_decimals ?? (series.some(s => s.values.some(v => !Number.isInteger(v))) ? 2 : 0)
  if (!Number.isInteger(decimals) || decimals < 0 || decimals > 6) throw new Error('value_decimals must be an integer from 0 to 6')
  const barNumber = (x) => new Intl.NumberFormat(visual.language === 'ru' ? 'ru-RU' : 'en-US', {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(x)
  const chartX = 56, chartWidth = 860
  for (let c = 0; c < categories.length; c++) {
    y += text(categories[c], chartX, y, 32, WHITE, 1040, 2) + 8
    for (let s = 0; s < series.length; s++) {
      const value = series[s].values[c]
      const width = value / maximum * chartWidth
      shapes.push(`<rect x="${chartX}" y="${y - 25}" width="${width.toFixed(2)}" height="28" rx="4" fill="${COLORS[s]}"/>`)
      text(barNumber(value), chartX + width + 14, y, 26, WHITE, W - 56 - chartX - width - 14, 1)
      y += 44
    }
    y += 16
  }
  H = y + 105
} else if (visual.type === 'line') {
  const { categories, series, unit, x_label } = visual.data
  text(unit, 56, y, 28, MUTED, 1080, 2)
  y += 60
  for (let i = 0; i < series.length; i++) {
    shapes.push(`<rect x="56" y="${y - 24}" width="22" height="22" fill="${COLORS[i]}" rx="3"/>`)
    text(series[i].name, 94, y, 28, WHITE, 1000, 1)
    y += 42
  }
  if (series.some(s => s.announced_from_index !== undefined)) {
    shapes.push(`<path d="M56,${y - 10} H116" fill="none" stroke="${MUTED}" stroke-width="5" stroke-dasharray="12 9"/>`)
    shapes.push(`<circle cx="86" cy="${y - 10}" r="7" fill="${DARK}" stroke="${MUTED}" stroke-width="3"/>`)
    const futureLabel = visual.data.future_rate_label ?? (visual.language === 'ru' ? 'Объявлено: ещё не действует' : 'Announced: not yet in force')
    if (typeof futureLabel !== 'string' || !futureLabel.trim() || futureLabel.length > 80) throw new Error('future_rate_label must be a nonempty string of at most 80 characters')
    text(futureLabel, 138, y, 28, WHITE, 1000, 1)
    y += 42
  }
  const top = y + 30, left = 140, plotWidth = 950, plotHeight = 390
  // Round the axis up to a clean step (1, 2, 2.5, 5 × 10^n) so the four tick labels read as
  // 5, 10, 15, 20 — not 6.12375, 12.2475 (found on the country guides).
  const raw = Math.max(...series.flatMap(s => s.values), 1) * 1.15
  const unitStep = 10 ** Math.floor(Math.log10(raw / 4))
  const maximum = [1, 2, 2.5, 5, 10].map(m => m * unitStep).find(step => step * 4 >= raw) * 4
  for (let i = 0; i <= 4; i++) {
    const yy = top + plotHeight * i / 4
    shapes.push(`<path d="M${left},${yy} H${left + plotWidth}" stroke="#444B5C" stroke-width="2"/>`)
    text(number(maximum * (4 - i) / 4), 24, yy + 9, 24, MUTED, 108, 1)
  }
  const xs = visual.data.x_values || categories.map((_, i) => i)
  const atX = i => left + plotWidth * (xs[i] - xs[0]) / (xs.at(-1) - xs[0])
  for (let i = 0; i < categories.length; i++) {
    const x = atX(i)
    const gaps = [i > 0 ? x - atX(i - 1) : Infinity,
      i < categories.length - 1 ? atX(i + 1) - x : Infinity]
    const labelWidth = Math.min(...gaps) - 12
    centeredText(categories[i], x, top + plotHeight + 48, 26, WHITE, labelWidth, 3)
  }
  series.forEach((s, si) => {
    const points = s.values.map((value, i) => [atX(i),
      top + plotHeight - value / maximum * plotHeight])
    const announced = s.announced_from_index
    if (announced !== undefined && (!Number.isInteger(announced) || announced < 1 || announced >= points.length)) {
      throw new Error('announced_from_index must identify a future point after at least one historical point')
    }
    const solid = announced === undefined ? points : points.slice(0, announced)
    shapes.push(`<polyline points="${solid.map(p => p.join(',')).join(' ')}" fill="none" stroke="${COLORS[si]}" stroke-width="5"/>`)
    if (announced !== undefined) {
      shapes.push(`<polyline points="${points.slice(announced - 1).map(p => p.join(',')).join(' ')}" fill="none" stroke="${COLORS[si]}" stroke-width="5" stroke-dasharray="12 9"/>`)
    }
    points.forEach(([x, yy], i) => shapes.push(announced !== undefined && i >= announced
      ? `<circle cx="${x}" cy="${yy}" r="7" fill="${DARK}" stroke="${COLORS[si]}" stroke-width="3"/>`
      : `<circle cx="${x}" cy="${yy}" r="7" fill="${COLORS[si]}"/>`))
  })
  y = top + plotHeight + 155
  text(x_label, 56, y, 28, MUTED, 1080, 2)
  H = y + 140
} else if (['process', 'decision'].includes(visual.type)) {
  const { nodes, edges } = visual.data
  const children = new Map(nodes.map(n => [n.id, edges.filter(e => e.from === n.id)]))
  const root = nodes.find(n => !edges.some(e => e.to === n.id))
  const positions = new Map()
  let leaf = 0, maxDepth = 0
  function layout(id, depth) {
    maxDepth = Math.max(maxDepth, depth)
    const kids = children.get(id)
    const lanes = kids.length ? kids.map(e => layout(e.to, depth + 1)) : [leaf++]
    const lane = lanes.reduce((a, b) => a + b, 0) / lanes.length
    positions.set(id, { lane, depth })
    return lane
  }
  layout(root.id, 0)
  if (leaf > 3) throw new Error('Diagram has more than 3 leaf lanes; split into smaller diagrams.')
  const laneWidth = 1088 / leaf, nodeWidth = Math.min(820, laneWidth - 26), nodeHeight = 122
  const baseY = y + 30, step = 225
  for (const p of positions.values()) {
    p.x = 56 + laneWidth * (p.lane + 0.5)
    p.y = baseY + p.depth * step
  }
  edges.forEach(e => {
    const a = positions.get(e.from), b = positions.get(e.to)
    const middle = a.y + nodeHeight + 45
    shapes.push(`<path d="M${a.x},${a.y + nodeHeight} V${middle} H${b.x} V${b.y - 10}" fill="none" stroke="${YELLOW}" stroke-width="3" marker-end="url(#arrow)"/>`)
    if (e.label) {
      const labelWidth = font.widthOf(e.label, 25)
      if (labelWidth > 210) throw new Error(`Edge label is too long: ${e.label}`)
      const labelX = Math.max(60, Math.min((a.x + b.x) / 2 - labelWidth / 2, W - 60 - labelWidth))
      shapes.push(`<rect x="${labelX - 8}" y="${middle - 22}" width="${labelWidth + 16}" height="36" fill="${DARK}"/>`)
      text(e.label, labelX, middle + 6, 25, YELLOW, 210, 1)
    }
  })
  nodes.forEach(n => {
    const p = positions.get(n.id)
    shapes.push(`<rect x="${p.x - nodeWidth / 2}" y="${p.y}" width="${nodeWidth}" height="${nodeHeight}" rx="18" fill="#1C202B" stroke="${YELLOW}" stroke-width="2"/>`)
    const lineCount = font.wrap(n.label, 30, nodeWidth - 40).length
    const baseline = p.y + nodeHeight / 2 - (lineCount - 1) * 30 * 1.22 / 2 + 11
    text(n.label, p.x - nodeWidth / 2 + 20, baseline, 30, WHITE, nodeWidth - 40, 3)
  })
  H = baseY + maxDepth * step + nodeHeight + 125
} else {
  throw new Error(`Unsupported type: ${visual.type}. Illustrations require separate discussion.`)
}

if (H > 2100) throw new Error('Visual is too tall; reduce or split the content.')
const logo = readFileSync(logoPath, 'utf8').replace(/<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')
  .replaceAll('currentColor', WHITE)
const context = [visual.data.period, visual.data.geography].filter(Boolean).join(' · ')
if (context) text(context, 56, H - 46, 25, MUTED, 810, 1)
shapes.push(`<g transform="translate(948 ${H - 74}) scale(1.36)">${logo}</g>`)
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${Math.ceil(H)}" viewBox="0 0 ${W} ${Math.ceil(H)}">
<title>${esc(visual.title)}</title><desc>${esc(visual.alt)}</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 Z" fill="${YELLOW}"/></marker></defs>
<rect width="${W}" height="${Math.ceil(H)}" fill="${DARK}"/>
${shapes.join('\n')}</svg>`
writeFileSync(output.replace(/\.png$/, '.svg'), svg)
await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(output)
process.stdout.write(JSON.stringify({ width: W, height: Math.ceil(H) }) + '\n')
