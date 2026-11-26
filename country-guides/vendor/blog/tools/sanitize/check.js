// Reference copy: the options mirror the HTML allow-list of the CMS.
// Reads HTML from stdin and writes to stdout what will survive to the site. If the input and
// the output differ by even one byte, the converter loses markup.
// If the whitelist in the CMS changes, change it here too: otherwise the check lies.
const sanitizeHtml = require('sanitize-html')

const OPTIONS = {
  allowedTags: [
    'p', 'strong', 'em', 'br',
    's', 'u', 'sub', 'sup',
    'h2', 'h3', 'h4',
    'ul', 'ol', 'li',
    'a', 'blockquote', 'code', 'pre', 'hr',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'figure', 'img', 'figcaption',
  ],
  allowedAttributes: {
    a: ['href', 'target', 'rel'],
    img: ['src', 'alt', 'width', 'height'],
    th: ['colspan', 'rowspan', 'scope'],
    td: ['colspan', 'rowspan', 'scope'],
  },
  allowedClasses: { figure: ['table', 'image'] },
  allowedSchemes: ['http', 'https', 'mailto'],
  exclusiveFilter: (frame) => frame.tag === 'img' && !frame.attribs.src,
  transformTags: {
    i: 'em',
    b: 'strong',
    a: (tagName, attribs) => {
      const href = attribs.href ?? ''
      if (!/^(https?:|mailto:|\/|#)/i.test(href)) return { tagName: 'span', attribs: {} }
      if (attribs.target === '_blank') attribs.rel = 'noopener noreferrer'
      return { tagName, attribs }
    },
  },
}
const EMPTY_FIGURE = /<figure\b[^>]*>\s*<\/figure>/gi

let input = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', (chunk) => (input += chunk))
process.stdin.on('end', () => {
  process.stdout.write(sanitizeHtml(input, OPTIONS).replace(EMPTY_FIGURE, ''))
})
