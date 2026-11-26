"""Article Markdown -> HTML for the contentHtml field in Strapi.

The tag whitelist matches the sanitizer of the CMS: everything that is not in it silently
disappears on the site. So the output of this script must pass through
tools/sanitize/check.js without a single change — that is the acceptance test.

Two things that are easy to forget:
- H1 does not go into the body. The page renders the heading from the title field, and a
  second first-level heading would give the page two H1s.
- Headings deeper than the fourth level are lowered to H4. The sanitizer would strip the tag,
  and the heading would turn into an ordinary paragraph in the middle of the article.

Usage:
  python3 scripts/md_to_strapi_html.py --input jobs/<job>/edited.md \
      --output jobs/<job>/out/article.html
"""
from __future__ import annotations

import argparse
import re
from html import escape
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET = re.compile(r"^[-*]\s+(.*)$")
ORDERED = re.compile(r"^\d+\.\s+(.*)$")
TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")
IMAGE = re.compile(r'^!\[([^\]]*)\]\((\S+?)(?:\s+"([^"\n]*)")?\)$')
FENCE = re.compile(r"^```")


def inline(s: str) -> str:
    """Escaping plus inline markup. The order matters: escape first."""
    # Keep escaped literal stars out of emphasis parsing, including inside sources.
    literal_star = "\ue000escaped-star\ue001"
    while literal_star in s:
        literal_star += "\ue001"
    s = s.replace(r"\*", literal_star)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"!\[([^\]]*)\]\((\S+?)\)", r'<img src="\2" alt="\1" />', s)
    s = re.sub(r"\[([^\]]+)\]\((\S+?)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s.replace(literal_star, "*")


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _breaks_paragraph(s: str) -> bool:
    return bool(
        HEADING.match(s) or BULLET.match(s) or ORDERED.match(s) or FENCE.match(s) or IMAGE.match(s)
        or s.startswith(">") or s.startswith("|") or s in ("---", "***", "___")
    )


def _collect_list(lines: list[str], i: int, pattern: re.Pattern) -> tuple[list[str], int]:
    """An empty line between items does not break the list — the numbering continues.

    An indented continuation paragraph (“1. Item”, an empty line, “   explanation”) also stays
    inside the item. Without this every item became a separate <ol> and the numbering on the
    site started again: a vendor comparison would have had eleven lists of “1.” in a row
    (found by QA).
    """
    items: list[str] = []
    n = len(lines)
    while i < n:
        cur = lines[i].strip()
        m = pattern.match(cur)
        if m:
            items.append(m.group(1))
            i += 1
            continue
        if not cur:
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n and pattern.match(lines[j].strip()):
                i = j
                continue
            # An indent of four spaces or fewer is a continuation of the item, not a new paragraph
            if j < n and items and lines[j].startswith("  ") and not lines[j].startswith("     "):
                block: list[str] = []
                while j < n and lines[j].strip() and not pattern.match(lines[j].strip()):
                    block.append(lines[j].strip())
                    j += 1
                items[-1] = items[-1] + " " + " ".join(block)
                i = j
                continue
        break
    return items, i


def convert(md: str) -> tuple[str | None, str]:
    """Returns (title from the H1 or None, body HTML)."""
    lines = md.replace("\r\n", "\n").split("\n")
    title: str | None = None
    out: list[str] = []
    i, n = 0, len(lines)

    while i < n:
        stripped = lines[i].strip()

        if not stripped:
            i += 1
            continue

        if FENCE.match(stripped):
            i += 1
            body: list[str] = []
            while i < n and not FENCE.match(lines[i].strip()):
                body.append(lines[i])
                i += 1
            i += 1
            escaped = ("\n".join(body)
                       .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            out.append(f"<pre><code>{escaped}</code></pre>")
            continue

        m = HEADING.match(stripped)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1:
                if title is None:
                    title = text
                i += 1
                continue
            level = min(level, 4)
            out.append(f"<h{level}>{inline(text)}</h{level}>")
            i += 1
            continue

        if stripped in ("---", "***", "___"):
            out.append("<hr />")
            i += 1
            continue

        m = IMAGE.match(stripped)
        if m:
            alt, src = escape(m.group(1), quote=True), escape(m.group(2), quote=True)
            title_attr = f' title="{escape(m.group(3), quote=True)}"' if m.group(3) else ''
            # Explicit caption syntax, to avoid swallowing the next paragraph.
            caption = ''
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n and lines[j].startswith('Caption: '):
                caption = '<figcaption>' + inline(lines[j][9:]) + '</figcaption>'
                i = j
            out.append(f'<figure class="image"><img src="{src}" alt="{alt}"{title_attr} />{caption}</figure>')
            i += 1
            continue

        if stripped.startswith(">"):
            quote: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            paragraphs = "\n".join(quote).split("\n\n")
            out.append("<blockquote>" + "".join("<p>" + inline(" ".join(p.splitlines())) + "</p>"
                                               for p in paragraphs if p.strip()) + "</blockquote>")
            continue

        if stripped.startswith("|") and i + 1 < n and TABLE_SEP.match(lines[i + 1].strip()):
            head = _cells(stripped)
            i += 2
            rows: list[list[str]] = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_cells(lines[i].strip()))
                i += 1
            body_rows = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows
            )
            if any(c.strip() for c in head):
                th = "".join(f"<th>{inline(c)}</th>" for c in head)
                out.append(f"<table><thead><tr>{th}</tr></thead>"
                           f"<tbody>{body_rows}</tbody></table>")
            else:
                # A parameter table is written without headers (“| | |”). An empty thead would
                # put an empty band above every such table on the page.
                out.append(f"<table><tbody>{body_rows}</tbody></table>")
            continue

        if stripped.startswith("|"):
            raise ValueError(f"line {i + 1}: table requires a Markdown separator row after its header")

        for pattern, tag in ((BULLET, "ul"), (ORDERED, "ol")):
            if pattern.match(stripped):
                items, i = _collect_list(lines, i, pattern)
                out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
                break
        else:
            para: list[str] = []
            while i < n and lines[i].strip() and not _breaks_paragraph(lines[i].strip()):
                para.append(lines[i].strip())
                i += 1
            out.append("<p>" + inline(" ".join(para)) + "</p>")

    return title, "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    title, html = convert(Path(args.input).read_text(encoding="utf-8"))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"H1: {title}")
    print(f"{out} — {len(html)} characters")


if __name__ == "__main__":
    main()
