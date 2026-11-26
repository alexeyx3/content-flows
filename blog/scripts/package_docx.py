"""Convert a Markdown article to a properly formatted Word .docx.

CLI:
    python scripts/package_docx.py --input <md> --output <docx>
"""
from __future__ import annotations

import argparse
import re
import html as html_mod
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_COLOR_INDEX
from docx.opc.constants import RELATIONSHIP_TYPE as RT


# ---------------------------------------------------------------------------
# Inline-formatting parser
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _tokenize_bold_italic(text: str) -> list[tuple[str, bool, bool]]:
    """Scan left-to-right, detect ** or __ (bold) and * or _ (italic)."""
    tokens: list[tuple[str, bool, bool]] = []
    bold = False
    italic = False
    buf = ""
    i = 0
    n = len(text)

    while i < n:
        if i + 1 < n and text[i:i+2] in ("**", "__"):
            if buf:
                tokens.append((buf, bold, italic))
                buf = ""
            bold = not bold
            i += 2
            continue
        if text[i] in ("*", "_"):
            if buf:
                tokens.append((buf, bold, italic))
                buf = ""
            italic = not italic
            i += 1
            continue
        buf += text[i]
        i += 1

    if buf:
        tokens.append((buf, bold, italic))

    return tokens


def _clean_plain(text: str) -> str:
    """Strip HTML tags and unescape entities in a plain (non-link) text run."""
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html_mod.unescape(text)


def _parse_inline(text: str) -> list[tuple[str, bool, bool, str | None]]:
    """Return a list of (text, bold, italic, url) tuples by parsing inline MD markup.

    Handles:
    - **bold** and __bold__
    - *italic* and _italic_
    - [text](url) -> a real hyperlink run (url is None for plain runs)
    - <tag>...</tag> HTML inline tags: keep inner text, discard tags
    - Bare HTML tags: strip
    """
    tokens: list[tuple[str, bool, bool, str | None]] = []
    pos = 0
    for m in _LINK_RE.finditer(text):
        before = text[pos:m.start()]
        if before:
            for chunk, bold, italic in _tokenize_bold_italic(_clean_plain(before)):
                if chunk:
                    tokens.append((chunk, bold, italic, None))
        anchor_text = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(1)))
        url = html_mod.unescape(m.group(2).strip())
        if anchor_text:
            tokens.append((anchor_text, False, False, url))
        pos = m.end()

    tail = text[pos:]
    if tail:
        for chunk, bold, italic in _tokenize_bold_italic(_clean_plain(tail)):
            if chunk:
                tokens.append((chunk, bold, italic, None))

    return tokens


def _add_hyperlink(paragraph, text: str, url: str, bold: bool = False, italic: bool = False) -> None:
    """Append a real clickable w:hyperlink run (anchor text only, no visible URL)."""
    part = paragraph.part
    r_id = part.relate_to(url, RT.HYPERLINK, is_external=True)

    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    rStyle = OxmlElement("w:rStyle")
    rStyle.set(qn("w:val"), "Hyperlink")
    rPr.append(rStyle)

    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    rPr.append(color)

    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rPr.append(underline)

    if bold:
        rPr.append(OxmlElement("w:b"))
    if italic:
        rPr.append(OxmlElement("w:i"))

    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def _add_inline_runs(paragraph, text: str) -> None:
    """Add inline-formatted runs to *paragraph* by parsing MD bold/italic/links."""
    for chunk, bold, italic, url in _parse_inline(text):
        if not chunk:
            continue
        if url:
            _add_hyperlink(paragraph, chunk, url, bold, italic)
        else:
            run = paragraph.add_run(chunk)
            run.bold = bold
            run.italic = italic


# ---------------------------------------------------------------------------
# Numbering restart helper
# ---------------------------------------------------------------------------

def _next_numbering_id(doc: Document) -> int:
    """Return the next available w:numId integer in the document's numbering part."""
    numbering_part = doc.part.numbering_part
    if numbering_part is None:
        return 1
    existing = numbering_part._element.findall(qn("w:num"))
    if not existing:
        return 1
    return max(int(e.get(qn("w:numId"))) for e in existing) + 1


def _ensure_abstract_num(doc: Document, fmt: str) -> int:
    """Ensure an abstractNum for *fmt* ('bullet' or 'decimal') exists; return its id."""
    numbering_part = doc.part.numbering_part
    if numbering_part is None:
        # Force creation of the numbering part by adding a temporary list para
        # We'll just use the API to bootstrap it
        _tmp = doc.add_paragraph("x", style="List Bullet")
        _tmp._element.getparent().remove(_tmp._element)
        numbering_part = doc.part.numbering_part

    nElem = numbering_part._element

    # Look for an existing abstractNum with the right numFmt
    for an in nElem.findall(qn("w:abstractNum")):
        lvl0 = an.find(qn("w:lvl"))
        if lvl0 is not None:
            nf = lvl0.find(qn("w:numFmt"))
            if nf is not None and nf.get(qn("w:val")) == fmt:
                return int(an.get(qn("w:abstractNumId")))

    # Create a new abstractNum
    existing_ids = [int(a.get(qn("w:abstractNumId"))) for a in nElem.findall(qn("w:abstractNum"))]
    new_id = max(existing_ids, default=-1) + 1

    an_elem = OxmlElement("w:abstractNum")
    an_elem.set(qn("w:abstractNumId"), str(new_id))

    mlt = OxmlElement("w:multiLevelType")
    mlt.set(qn("w:val"), "hybridMultilevel")
    an_elem.append(mlt)

    lvl = OxmlElement("w:lvl")
    lvl.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:start")
    start.set(qn("w:val"), "1")
    lvl.append(start)
    nf_elem = OxmlElement("w:numFmt")
    nf_elem.set(qn("w:val"), fmt)
    lvl.append(nf_elem)
    lvlText = OxmlElement("w:lvlText")
    lvlText.set(qn("w:val"), "•" if fmt == "bullet" else "%1.")
    lvl.append(lvlText)
    lvlJc = OxmlElement("w:lvlJc")
    lvlJc.set(qn("w:val"), "left")
    lvl.append(lvlJc)
    pPr = OxmlElement("w:pPr")
    ind = OxmlElement("w:ind")
    ind.set(qn("w:left"), "720")
    ind.set(qn("w:hanging"), "360")
    pPr.append(ind)
    lvl.append(pPr)
    an_elem.append(lvl)

    # Insert before any existing w:num elements so the schema stays valid
    first_num = nElem.find(qn("w:num"))
    if first_num is not None:
        nElem.insert(list(nElem).index(first_num), an_elem)
    else:
        nElem.append(an_elem)

    return new_id


def _create_num_instance(doc: Document, abstract_num_id: int) -> int:
    """Create a fresh w:num element referencing *abstract_num_id*; return its numId.

    Each call produces a new numId so ordered lists restart numbering at 1.
    """
    numbering_part = doc.part.numbering_part
    nElem = numbering_part._element
    new_num_id = _next_numbering_id(doc)

    num_elem = OxmlElement("w:num")
    num_elem.set(qn("w:numId"), str(new_num_id))
    abs_ref = OxmlElement("w:abstractNumId")
    abs_ref.set(qn("w:val"), str(abstract_num_id))
    num_elem.append(abs_ref)

    # Append at end of numbering part (after all abstractNums, alongside other nums)
    nElem.append(num_elem)

    return new_num_id


def _set_list_style(para, num_id: int, style_name: str) -> None:
    """Apply list style and wire the numId into the paragraph's pPr."""
    para.style = style_name
    pPr = para._p.get_or_add_pPr()
    numPr = OxmlElement("w:numPr")
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    numPr.append(ilvl)
    numId_elem = OxmlElement("w:numId")
    numId_elem.set(qn("w:val"), str(num_id))
    numPr.append(numId_elem)
    pPr.append(numPr)


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def _add_md_table(doc: Document, rows: list[list[str]]) -> None:
    """Add a Word table from a list of row/cell lists (first row = header)."""
    if not rows:
        return
    col_count = max(len(r) for r in rows)
    tbl = doc.add_table(rows=0, cols=col_count)
    tbl.style = "Table Grid"
    for row_idx, row_data in enumerate(rows):
        tr = tbl.add_row()
        for col_idx in range(col_count):
            cell = tr.cells[col_idx]
            cell_text = row_data[col_idx] if col_idx < len(row_data) else ""
            para = cell.paragraphs[0]
            _add_inline_runs(para, cell_text.strip())
            if row_idx == 0:
                for run in para.runs:
                    run.bold = True


def _clean_cell(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_html_table(block: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr_match in re.finditer(r"<tr[^>]*>(.*?)</tr>", block, re.IGNORECASE | re.DOTALL):
        cells = [
            _clean_cell(m.group(1))
            for m in re.finditer(r"<t[hd][^>]*>(.*?)</t[hd]>", tr_match.group(1), re.IGNORECASE | re.DOTALL)
        ]
        if cells:
            rows.append(cells)
    return rows


# ---------------------------------------------------------------------------
# Main converter
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,5})\s+(.*)")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)")
_ORDERED_RE = re.compile(r"^\d+\.\s+(.*)")
_MD_TABLE_ROW_RE = re.compile(r"^\|.*\|")
_MD_SEP_RE = re.compile(r"^[|\s:-]+$")

HEADING_LEVELS = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}


def convert_markdown_to_docx(markdown_path: Path, output_path: Path) -> None:
    doc = Document()

    markdown = markdown_path.read_text(encoding="utf-8")
    lines = markdown.splitlines()
    i = 0
    n = len(lines)

    # Skip YAML front-matter (--- ... ---)
    if lines and lines[0].strip() == "---":
        i = 1
        while i < n and lines[i].strip() != "---":
            i += 1
        i += 1  # skip closing ---

    # We need abstract num IDs for bullet and decimal lists
    # They'll be created lazily on first use
    bullet_abstract_id: int | None = None
    decimal_abstract_id: int | None = None

    def get_bullet_num_id() -> int:
        nonlocal bullet_abstract_id
        if bullet_abstract_id is None:
            bullet_abstract_id = _ensure_abstract_num(doc, "bullet")
        return _create_num_instance(doc, bullet_abstract_id)

    def get_decimal_num_id() -> int:
        nonlocal decimal_abstract_id
        if decimal_abstract_id is None:
            decimal_abstract_id = _ensure_abstract_num(doc, "decimal")
        return _create_num_instance(doc, decimal_abstract_id)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # --- blank line ---
        if not stripped:
            doc.add_paragraph("")
            i += 1
            continue

        # --- Markdown table ---
        if _MD_TABLE_ROW_RE.match(stripped):
            rows: list[list[str]] = []
            while i < n and _MD_TABLE_ROW_RE.match(lines[i].strip()):
                raw = lines[i].strip()
                cells = [c.strip() for c in raw.strip("|").split("|")]
                # Skip separator rows (e.g. |---|---|)
                if not all(re.fullmatch(r":?-{3,}:?", c or "-") for c in cells):
                    rows.append(cells)
                i += 1
            _add_md_table(doc, rows)
            continue

        # --- HTML table ---
        if re.match(r"<table[\s>]", stripped, re.IGNORECASE):
            raw_lines: list[str] = []
            while i < n:
                raw_lines.append(lines[i])
                if "</table>" in lines[i].lower():
                    i += 1
                    break
                i += 1
            block = "\n".join(raw_lines)
            html_rows = _parse_html_table(block)
            _add_md_table(doc, html_rows)
            continue

        # --- Headings ---
        m = _HEADING_RE.match(stripped)
        if m:
            hashes = m.group(1)
            heading_text = m.group(2).strip()
            level = HEADING_LEVELS[len(hashes)]
            para = doc.add_heading(level=level)
            para.clear()
            _add_inline_runs(para, heading_text)
            i += 1
            continue

        # --- Bullet list (contiguous block) ---
        if _BULLET_RE.match(stripped):
            num_id = get_bullet_num_id()
            while i < n and _BULLET_RE.match(lines[i].strip()):
                item_text = _BULLET_RE.match(lines[i].strip()).group(1)
                para = doc.add_paragraph(style="List Bullet")
                para.clear()
                _set_list_style(para, num_id, "List Bullet")
                _add_inline_runs(para, item_text)
                i += 1
            continue

        # --- Ordered list — blank lines between items do NOT restart numbering ---
        if _ORDERED_RE.match(stripped):
            num_id = get_decimal_num_id()  # fresh instance = restart at 1
            while i < n:
                cur = lines[i].strip()
                item = _ORDERED_RE.match(cur)
                if item:
                    para = doc.add_paragraph(style="List Number")
                    para.clear()
                    _set_list_style(para, num_id, "List Number")
                    _add_inline_runs(para, item.group(1))
                    i += 1
                    continue
                if not cur:
                    # blank inside a list: continue the same list only if the next
                    # non-blank line is an ordered item that does not restart at "1."
                    j = i + 1
                    while j < n and not lines[j].strip():
                        j += 1
                    if j < n and _ORDERED_RE.match(lines[j].strip()) and not lines[j].strip().startswith("1."):
                        i = j
                        continue
                break
            continue

        # --- Horizontal rule (bare ---) — skip / emit blank ---
        if stripped == "---":
            doc.add_paragraph("")
            i += 1
            continue

        # --- Normal paragraph ---
        para = doc.add_paragraph()
        _add_inline_runs(para, stripped)
        i += 1

    doc.save(str(output_path))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a Markdown article to DOCX (Word styles, lists, tables, inline formatting)."
    )
    parser.add_argument("--input", required=True, help="Path to input Markdown file")
    parser.add_argument("--output", required=True, help="Path to output .docx file")
    args = parser.parse_args()
    convert_markdown_to_docx(markdown_path=Path(args.input), output_path=Path(args.output))
