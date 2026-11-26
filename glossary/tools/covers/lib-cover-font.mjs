/**
 * Cover font: two subsets of Exo 2, Latin and Cyrillic. Fontsource ships them as
 * separate files and the Latin subset has no Cyrillic glyphs at all, so a Cyrillic
 * title used to render as boxes.
 *
 * A glyph is looked up in the Latin file first, then in the Cyrillic one. A missing
 * glyph is index 0 (.notdef): that is what charToGlyph returns when the font has no
 * such character.
 */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import opentype from 'opentype.js'

function load(dir, name) {
  const file = readFileSync(join(dir, name))
  return opentype.parse(file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength))
}

export function createFont(assetsDir) {
  const latin = load(assetsDir, 'Exo2-Bold.ttf')
  const cyrillic = load(assetsDir, 'Exo2-Bold-cyrillic.ttf')

  const glyphOf = (ch) => {
    const g = latin.charToGlyph(ch)
    if (g.index !== 0) return { glyph: g, font: latin }
    const c = cyrillic.charToGlyph(ch)
    return c.index !== 0 ? { glyph: c, font: cyrillic } : { glyph: g, font: latin }
  }

  const widthOf = (text, size) => {
    let width = 0
    for (const ch of text) {
      const { glyph, font } = glyphOf(ch)
      width += glyph.advanceWidth * (size / font.unitsPerEm)
    }
    return width
  }

  // The outline is always taken in one configuration, at the origin and at the font's
  // natural size, because opentype.js 2.0.0 returns NaN at some sizes and on a
  // fractional baseline. Position and scale go into the transform, where the renderer
  // computes them.
  const pathOf = (text, x, y, size, fill) => {
    const parts = []
    let cursor = 0
    for (const ch of text) {
      const { glyph, font } = glyphOf(ch)
      const scale = size / font.unitsPerEm
      const d = glyph.getPath(0, 0, font.unitsPerEm).toPathData(2)
      if (d.includes('NaN')) throw new Error(`Outline contains NaN at character «${ch}»`)
      if (d) {
        parts.push(
          `<path d="${d}" transform="translate(${(x + cursor).toFixed(2)} ${y.toFixed(2)}) scale(${scale.toFixed(5)})"/>`,
        )
      }
      cursor += glyph.advanceWidth * scale
    }
    return `<g fill="${fill}">${parts.join('')}</g>`
  }

  const wrap = (text, size, maxWidth) => {
    const words = text.split(/\s+/)
    const lines = []
    let line = ''
    for (const word of words) {
      const candidate = line ? `${line} ${word}` : word
      if (widthOf(candidate, size) > maxWidth && line) {
        lines.push(line)
        line = word
      } else {
        line = candidate
      }
    }
    if (line) lines.push(line)
    return lines
  }

  return { widthOf, pathOf, wrap }
}
