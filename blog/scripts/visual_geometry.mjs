/** Geometry checks for generated diagrams before rasterizing their SVG. */

const intersects = (a, b, clearance = 0) =>
  a.x < b.x + b.width + clearance && a.x + a.width + clearance > b.x &&
  a.y < b.y + b.height + clearance && a.y + a.height + clearance > b.y

// SVG markerUnits defaults to strokeWidth. For the renderer's 12 x 12 marker,
// refX=9, refY=5 and arrow path M0,0 L0,10 L10,5, the visible triangle
// extends 36 px behind the endpoint and 4 px beyond it at strokeWidth=4.
export function downwardArrowheadBox(x, endY, strokeWidth = 4) {
  return {
    x: x - 5 * strokeWidth,
    y: endY - 9 * strokeWidth,
    width: 10 * strokeWidth,
    height: 10 * strokeWidth,
  }
}

export function visualCollisions({ nodes, arrowheads, edgeLabels = [], title, footer }) {
  const issues = []
  const protectedBoxes = [
    ...nodes.map(box => ({ ...box, kind: 'node' })),
    { ...title, kind: 'title' },
    { ...footer, kind: 'footer' },
  ]
  for (let i = 0; i < protectedBoxes.length; i++) {
    for (let j = i + 1; j < protectedBoxes.length; j++) {
      if (intersects(protectedBoxes[i], protectedBoxes[j], 6)) {
        issues.push(`${protectedBoxes[i].id} overlaps ${protectedBoxes[j].id}`)
      }
    }
  }
  for (const arrow of arrowheads) {
    for (const box of protectedBoxes) {
      if (intersects(arrow, box, 4)) issues.push(`${arrow.id} overlaps ${box.id}`)
    }
  }
  for (const label of edgeLabels) {
    for (const box of [...protectedBoxes, ...arrowheads]) {
      if (intersects(label, box, 4)) issues.push(`${label.id} overlaps ${box.id}`)
    }
  }
  return issues
}

export function assertVisualGeometry(layout) {
  const issues = visualCollisions(layout)
  if (issues.length) throw new Error(`Visual elements overlap: ${issues.join('; ')}`)
}
