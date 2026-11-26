/** Render a data-backed visual from stdin. Uses the existing cover font and logo assets. */
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'
import { assertVisualGeometry, downwardArrowheadBox } from './visual_geometry.mjs'

const ROOT = resolve(fileURLToPath(new URL('..', import.meta.url)))
const brandDir = process.env.BLOG_BRAND_DIR || resolve(ROOT, 'tools/covers')
const requireBrand = createRequire(join(brandDir, 'package.json'))
const sharp = requireBrand('sharp')
const { createFont } = await import(pathToFileURL(join(brandDir, 'lib-cover-font.mjs')))
const font = createFont(join(brandDir, 'assets'))
const { createSiteChartFont } = await import(pathToFileURL(join(brandDir, 'lib-site-chart-font.mjs')))
const chartTitleFont = createSiteChartFont(join(brandDir, 'assets'), 'Exo2-SemiBold.ttf')
const chartBodyFont = createSiteChartFont(join(brandDir, 'assets'), 'Manrope-Regular.ttf')
const chartStrongFont = createSiteChartFont(join(brandDir, 'assets'), 'Manrope-SemiBold.ttf')
const logoPath = process.env.BLOG_LOGO_PATH || join(brandDir, 'assets/logo.svg')
const visual = JSON.parse(readFileSync(0, 'utf8'))
const output = process.argv[2]
if (!output) throw new Error('PNG output path is required')
const W = 1200
const sitePalette = JSON.parse(readFileSync(join(ROOT, 'config/site-brand-tokens.json'), 'utf8'))
const DARK = sitePalette.black, WHITE = sitePalette.white, MUTED = '#C5C9D4', YELLOW = sitePalette.yellow.default
const CHART_MUTED = sitePalette.gray.default, CHART_GRID = sitePalette.gray.dark
const COLORS = [YELLOW, WHITE, sitePalette.gray.default]
const shapes = []
const esc = (s) => String(s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;')
const number = (x) => new Intl.NumberFormat(visual.language === 'ru' ? 'ru-RU' : 'en-US', {
  maximumFractionDigits: 6,
}).format(x)
const axisNumber = (x) => new Intl.NumberFormat(visual.language === 'ru' ? 'ru-RU' : 'en-US', {
  maximumSignificantDigits: 3,
}).format(x)

function text(value, x, y, size = 32, color = WHITE, width = null, maxLines = 2, face = font) {
  const lines = width ? face.wrap(String(value), size, width) : [String(value)]
  if (lines.length > maxLines || lines.some(line => width && face.widthOf(line, size) > width)) {
    throw new Error(`Label is too long: ${value}. Shorten it; renderer never truncates.`)
  }
  lines.forEach((line, i) => shapes.push(face.pathOf(line, x, y + i * size * 1.22, size, color)))
  return lines.length * size * 1.22
}

function centeredText(value, x, y, size, color, width, maxLines, face = font) {
  const lines = face.wrap(String(value), size, width)
  if (lines.length > maxLines || lines.some(line => face.widthOf(line, size) > width)) {
    throw new Error(`Label is too long: ${value}. Shorten it; renderer never truncates.`)
  }
  lines.forEach((line, i) => {
    const lineWidth = face.widthOf(line, size)
    const left = Math.max(56, Math.min(x - lineWidth / 2, W - 56 - lineWidth))
    text(line, left, y + i * size * 1.22, size, color, null, 1, face)
  })
}

const isChart = ['bar', 'line'].includes(visual.type)
const isDiagram = ['process', 'decision'].includes(visual.type)
let headerHeight
let diagramTitleLineCount = 0
if (isDiagram) {
  const titleSize = 60
  const titleLines = chartTitleFont.wrap(visual.title, titleSize, 1088)
  diagramTitleLineCount = titleLines.length
  centeredText(visual.title, W / 2, 75, titleSize, WHITE, 1088, 2, chartTitleFont)
  headerHeight = 60 + titleLines.length * titleSize * 1.22
} else {
  headerHeight = 60 + text(visual.title, 56, 70, 50, WHITE, 1088, 3, chartTitleFont)
}
let y = headerHeight + (isChart ? 52 : 30)
let H

if (visual.type === 'bar') {
  const { categories, series, unit } = visual.data
  const unitHeight = text(unit, 56, y, 32, CHART_MUTED, 1050, 2, chartBodyFont)
  y += unitHeight + 14
  // A one-series chart gains no information from a legend: the bar colour is
  // already unambiguous, and the repeated label crowds the title on mobile.
  if (series.length > 1) {
    for (let i = 0; i < series.length; i++) {
      shapes.push(`<rect x="56" y="${y - 29}" width="30" height="30" fill="${COLORS[i]}" rx="4"/>`)
      text(series[i].name, 104, y, 36, WHITE, 970, 1, chartBodyFont)
      y += 54
    }
  }
  y += 20
  const observedMaximum = Math.max(...series.flatMap(s => s.values), 1)
  const fixedMaximum = visual.data.axis_max == null ? null : Number(visual.data.axis_max)
  if (fixedMaximum !== null && (!Number.isFinite(fixedMaximum) || fixedMaximum < observedMaximum)) {
    throw new Error('axis_max must be finite and at least the largest plotted value')
  }
  const maximum = fixedMaximum ?? observedMaximum
  const chartX = 56, chartWidth = 860
  for (let c = 0; c < categories.length; c++) {
    y += text(categories[c], chartX, y, 40, WHITE, 1040, 2, chartStrongFont) + 12
    for (let s = 0; s < series.length; s++) {
      const value = series[s].values[c]
      const width = value / maximum * chartWidth
      shapes.push(`<rect x="${chartX}" y="${y - 32}" width="${width.toFixed(2)}" height="36" rx="4" fill="${COLORS[s]}"/>`)
      text(`${number(value)}${visual.data.axis_suffix || ''}`, chartX + width + 14, y, 40, WHITE,
        W - 56 - chartX - width - 14, 1, chartStrongFont)
      y += 56
    }
    y += 16
  }
  if (fixedMaximum !== null) {
    y += 14
    shapes.push(`<path d="M${chartX},${y} H${chartX + chartWidth}" stroke="${CHART_GRID}" stroke-width="2"/>`)
    for (let i = 0; i <= 4; i++) {
      const tickX = chartX + chartWidth * i / 4
      shapes.push(`<path d="M${tickX},${y} V${y + 12}" stroke="${CHART_GRID}" stroke-width="2"/>`)
      centeredText(`${axisNumber(maximum * i / 4)}${visual.data.axis_suffix || ''}`,
        tickX, y + 44, 28, CHART_MUTED, 125, 1, chartBodyFont)
    }
    y += 68
  }
  H = y + 105
} else if (visual.type === 'line') {
  const { categories, series, unit, x_label } = visual.data
  const unitHeight = text(unit, 56, y, 40, CHART_MUTED, 1080, 2, chartBodyFont)
  y += unitHeight + 22
  for (let i = 0; i < series.length; i++) {
    shapes.push(`<rect x="56" y="${y - 29}" width="30" height="30" fill="${COLORS[i]}" rx="4"/>`)
    text(series[i].name, 104, y, 40, WHITE, 970, 1, chartBodyFont)
    y += 56
  }
  const top = y + 45, left = 160, plotWidth = 930, plotHeight = 450
  const maximum = Math.max(...series.flatMap(s => s.values), 1) * 1.15
  for (let i = 0; i <= 4; i++) {
    const yy = top + plotHeight * i / 4
    shapes.push(`<path d="M${left},${yy} H${left + plotWidth}" stroke="${CHART_GRID}" stroke-width="2"/>`)
    text(axisNumber(maximum * (4 - i) / 4), 24, yy + 12, 40, CHART_MUTED, 126, 1, chartBodyFont)
  }
  const xs = visual.data.x_values || categories.map((_, i) => i)
  const atX = i => left + plotWidth * (xs[i] - xs[0]) / (xs.at(-1) - xs[0])
  for (let i = 0; i < categories.length; i++) {
    const x = atX(i)
    const gaps = [i > 0 ? x - atX(i - 1) : Infinity,
      i < categories.length - 1 ? atX(i + 1) - x : Infinity]
    const labelWidth = Math.min(...gaps) - 12
    centeredText(categories[i], x, top + plotHeight + 58, 40, WHITE, labelWidth, 3, chartBodyFont)
  }
  series.forEach((s, si) => {
    const points = s.values.map((value, i) => [atX(i),
      top + plotHeight - value / maximum * plotHeight])
    shapes.push(`<polyline points="${points.map(p => p.join(',')).join(' ')}" fill="none" stroke="${COLORS[si]}" stroke-width="5"/>`)
    points.forEach(([x, yy]) => shapes.push(`<circle cx="${x}" cy="${yy}" r="7" fill="${COLORS[si]}"/>`))
  })
  y = top + plotHeight + 175
  text(x_label, 56, y, 40, CHART_MUTED, 1080, 2, chartBodyFont)
  H = y + 140
} else if (['process', 'decision'].includes(visual.type)) {
  const { nodes, edges } = visual.data
  const mergeLayout = visual.type === 'process' && visual.data.layout === 'two-input-merge'
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
  if (mergeLayout) {
    if (nodes.length !== 7) throw new Error('two-input-merge requires seven ordered nodes')
    const expected = [[0, 1], [1, 2], [1, 3], [2, 4], [3, 4], [4, 5], [5, 6]]
    if (edges.length !== expected.length || expected.some(([from, to]) =>
      !edges.some(e => e.from === nodes[from].id && e.to === nodes[to].id && !e.label))) {
      throw new Error('two-input-merge has an invalid edge pattern')
    }
    const depths = [0, 1, 2, 2, 3, 4, 5]
    nodes.forEach((n, i) => positions.set(n.id, {
      depth: depths[i], lane: 0, fixedX: i === 2 ? 320 : i === 3 ? 880 : 600,
      width: i === 2 || i === 3 ? 500 : 960,
    }))
    leaf = 2
    maxDepth = 5
  } else {
    layout(root.id, 0)
  }
  if (leaf > 3) throw new Error('Diagram has more than 3 leaf lanes; split into smaller diagrams.')
  // Give the title clear priority over the node labels. A wider node keeps
  // typical labels on one line at mobile article widths, while each row grows
  // only when its actual text needs more height.
  const requestedNodeFontSize = Number(visual.data.node_font_size)
  const nodeFontSize = Number.isFinite(requestedNodeFontSize) &&
    requestedNodeFontSize >= 36 && requestedNodeFontSize <= 44
    ? requestedNodeFontSize : 42
  const edgeFontSize = 28
  const laneWidth = 1088 / leaf, nodeWidth = Math.min(960, laneWidth - 32)
  const lineHeight = nodeFontSize * 1.16
  const rowHeights = Array(maxDepth + 1).fill(108)
  nodes.forEach(n => {
    const p = positions.get(n.id)
    p.width ??= nodeWidth
    const lines = chartStrongFont.wrap(n.label, nodeFontSize, p.width - 64)
    if (lines.length > 3 || lines.some(line => chartStrongFont.widthOf(line, nodeFontSize) > p.width - 64)) {
      throw new Error(`Label is too long: ${n.label}. Shorten it; renderer never truncates.`)
    }
    p.lines = lines
    p.height = Math.max(108, Math.ceil(24 + lines.length * lineHeight))
    rowHeights[p.depth] = Math.max(rowHeights[p.depth], p.height)
  })
  const baseY = y + 16
  const rowGaps = Array(maxDepth + 1).fill(80)
  // A visible edge label needs enough space to sit at the centre of its
  // connector without covering the arrowhead or either node.
  edges.forEach(e => {
    if (e.label) rowGaps[positions.get(e.to).depth] = 148
  })
  const rowYs = [baseY]
  for (let depth = 1; depth <= maxDepth; depth++) {
    rowYs[depth] = rowYs[depth - 1] + rowHeights[depth - 1] + rowGaps[depth]
  }
  for (const p of positions.values()) {
    p.x = p.fixedX ?? 56 + laneWidth * (p.lane + 0.5)
    p.y = rowYs[p.depth]
    p.height = rowHeights[p.depth]
  }
  const arrowheads = [], edgeLabels = []
  edges.forEach(e => {
    const a = positions.get(e.from), b = positions.get(e.to)
    const start = a.y + a.height, end = b.y - 12
    const middle = (start + end) / 2
    const targetX = mergeLayout && e.to === nodes[4].id
      ? b.x + (e.from === nodes[2].id ? -135 : 135) : b.x
    const dash = e.style === 'dashed' ? ' stroke-dasharray="14 10"' : ''
    shapes.push(`<path d="M${a.x},${start} V${middle} H${targetX} V${end}" fill="none" stroke="${YELLOW}" stroke-width="4"${dash} marker-end="url(#arrow)"/>`)
    arrowheads.push({ id: `arrow ${e.from}→${e.to}`, ...downwardArrowheadBox(targetX, end) })
    if (e.label) {
      const labelWidth = chartStrongFont.widthOf(e.label, edgeFontSize)
      if (labelWidth > 210) throw new Error(`Edge label is too long: ${e.label}`)
      const labelX = Math.max(60, Math.min(b.x - labelWidth / 2, W - 60 - labelWidth))
      const labelBaseline = (start + end) / 2 + edgeFontSize * 0.35
      const labelTop = labelBaseline - 35
      shapes.push(`<rect x="${labelX - 8}" y="${labelTop}" width="${labelWidth + 16}" height="40" fill="${DARK}"/>`)
      edgeLabels.push({ id: `edge label ${e.from}→${e.to}`, x: labelX - 8,
        y: labelTop, width: labelWidth + 16, height: 40 })
      text(e.label, labelX, labelBaseline, edgeFontSize, YELLOW, 210, 1, chartStrongFont)
    }
  })
  nodes.forEach(n => {
    const p = positions.get(n.id)
    shapes.push(`<rect x="${p.x - p.width / 2}" y="${p.y}" width="${p.width}" height="${p.height}" rx="18" fill="#1C202B" stroke="${YELLOW}" stroke-width="2"/>`)
    const baseline = p.y + (p.height - p.lines.length * lineHeight) / 2 + nodeFontSize * 0.86
    centeredText(n.label, p.x, baseline, nodeFontSize, WHITE, p.width - 64, 3, chartStrongFont)
  })
  H = rowYs[maxDepth] + rowHeights[maxDepth] + 100
  assertVisualGeometry({
    nodes: nodes.map(n => {
      const p = positions.get(n.id)
      return { id: `node ${n.id}`, x: p.x - p.width / 2, y: p.y,
        width: p.width, height: p.height }
    }),
    arrowheads,
    edgeLabels,
    title: { id: 'title', x: 56, y: 15, width: 1088,
      height: diagramTitleLineCount * 60 * 1.22 + 10 },
    footer: { id: 'footer/logo', x: 0, y: H - 80, width: W, height: 80 },
  })
} else {
  throw new Error(`Unsupported type: ${visual.type}. Illustrations require separate discussion.`)
}

const context = [visual.data.period, visual.data.geography].filter(Boolean).join(' · ')
if (isChart) {
  // The footer is part of the exported image, so it must remain readable when
  // the 1200 px chart is displayed at the blog's 390 px mobile width.
  const publishers = [...new Set((visual.sources || [])
    .filter(source => source.public !== false)
    .map(source => String(source.label || '').split(':')[0].trim())
    .filter(Boolean))]
  const ruleY = y + 22
  shapes.push(`<path d="M56,${ruleY} H1144" stroke="${CHART_GRID}" stroke-width="2"/>`)
  let footerY = ruleY + 44
  if (publishers.length) {
    footerY += text(`Source: ${publishers.join('; ')}`, 56, footerY, 30, MUTED, 820, 2, chartBodyFont) + 8
  }
  if (context) footerY += text(context, 56, footerY, 30, MUTED, 820, 2, chartBodyFont)
  H = Math.max(H, footerY + 30)
} else if (context) {
  text(context, 56, H - 46, 25, MUTED, 810, 1, chartBodyFont)
}
if (H > 2100) throw new Error('Visual is too tall; reduce or split the content.')
if (visual.show_logo !== false) {
  const logo = readFileSync(logoPath, 'utf8').replace(/<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')
    .replaceAll('currentColor', WHITE)
  shapes.push(`<g transform="translate(948 ${H - 74}) scale(1.36)">${logo}</g>`)
}
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${Math.ceil(H)}" viewBox="0 0 ${W} ${Math.ceil(H)}">
<title>${esc(visual.title)}</title><desc>${esc(visual.alt)}</desc>
<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="9" refY="5" orient="auto"><path d="M0,0 L0,10 L10,5 Z" fill="${YELLOW}"/></marker></defs>
<rect width="${W}" height="${Math.ceil(H)}" fill="${DARK}"/>
${shapes.join('\n')}</svg>`
writeFileSync(output.replace(/\.png$/, '.svg'), svg)
await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(output)
process.stdout.write(JSON.stringify({ width: W, height: Math.ceil(H) }) + '\n')
