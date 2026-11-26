"""Create a Google Doc from a Markdown file, highlighting what changed vs a baseline.

Built for review copies: the reviewer sees the corrected article with every changed or new
passage highlighted, so nothing has to be diffed by eye. Headings, bullets, bold, links and
tables are rendered as real Google Docs structures.

The default diff is paragraph-level. Opt-in word mode aligns content within
matching heading paths and table rows, then highlights changed text fragments.

Usage:
  python3 scripts/md_to_gdoc.py corrected.md --baseline original.md \
      --title "Article — corrected" --share someone@example.com
  python3 scripts/md_to_gdoc.py corrected.md --baseline original.md \
      --highlight-mode words --diff-report removed.json --title "Article — refreshed"
"""
from __future__ import annotations

import argparse
import difflib
import re
import json
import time
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
try:
    from .article_materials import IMAGE_LINE, PLACEHOLDERS
except ImportError:
    from article_materials import IMAGE_LINE, PLACEHOLDERS

ROOT = Path(__file__).resolve().parents[1]
KEYFILE = ROOT / "config" / "google-service-account.json"
ENV_PATH = ROOT / "config" / ".env"
SCOPES = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"]
HIGHLIGHT = {"red": 1.0, "green": 0.94, "blue": 0.55}

def execute_docs_write(request, *, sleep=time.sleep, max_attempts: int = 7):
    """Execute a Docs write, waiting out the per-user minute quota when necessary."""
    for attempt in range(max_attempts):
        try:
            return request.execute()
        except HttpError as exc:
            if getattr(exc.resp, "status", None) != 429 or attempt == max_attempts - 1:
                raise
            retry_after = exc.resp.get("retry-after") if hasattr(exc.resp, "get") else None
            delay = float(retry_after) if retry_after else min(30.0, 2.0 ** (attempt + 1))
            sleep(delay)

def load_env() -> dict:
    values = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


LINK = re.compile(r"\[([^\]]+)\]\((https?://(?:[^()]|\([^()]*\))+)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
CODE = re.compile(r"`([^`]+)`")
ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


# ---------------------------------------------------------------- parsing

def norm(text: str) -> str:
    """Normalise a paragraph for diffing: markers, quotes, dashes, whitespace."""
    t = LINK.sub(r"\1", text)
    t = t.replace("**", "")
    t = CODE.sub(r"\1", t)
    t = ITALIC.sub(r"\1", t)
    t = re.sub(r"^\s*(#{1,6}\s*|[-*•]\s*)", "", t)
    t = t.replace("’", "'").replace("“", '"').replace("”", '"')
    t = t.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", t).strip().lower()


def inline(text: str):
    """Return (plain_text, spans) where spans are (start, end, kind, value)."""
    spans = []
    out = ""
    i = 0
    while i < len(text):
        m_link = LINK.match(text, i)
        m_bold = BOLD.match(text, i)
        m_code = CODE.match(text, i)
        m_italic = ITALIC.match(text, i)
        if m_link:
            start = len(out)
            label = CODE.sub(r"\1", m_link.group(1))
            label = BOLD.sub(r"\1", label)
            label = ITALIC.sub(r"\1", label)
            out += label
            spans.append((start, len(out), "link", m_link.group(2)))
            i = m_link.end()
        elif m_bold:
            start = len(out)
            out += m_bold.group(1)
            spans.append((start, len(out), "bold", None))
            i = m_bold.end()
        elif m_code:
            start = len(out)
            out += m_code.group(1)
            spans.append((start, len(out), "code", None))
            i = m_code.end()
        elif m_italic:
            start = len(out)
            out += m_italic.group(1)
            spans.append((start, len(out), "italic", None))
            i = m_italic.end()
        else:
            out += text[i]
            i += 1
    return out, spans


def parse(md: str) -> list:
    """Markdown -> list of blocks: ('heading',level,text) ('para',text) ('bullet',text) ('table',rows)."""
    blocks = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        image = IMAGE_LINE.fullmatch(line.strip())
        if image:
            blocks.append(("image", image.group(1), image.group(2), image.group(3) or ""))
            i += 1
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(("table", rows))
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            blocks.append(("heading", len(m.group(1)), m.group(2).strip()))
        elif re.match(r"^\s*[-*]\s+", line):
            blocks.append(("bullet", re.sub(r"^\s*[-*]\s+", "", line)))
        elif re.match(r"^\s*\d+\.\s+", line):
            blocks.append(("ordered", re.sub(r"^\s*\d+\.\s+", "", line)))
        elif line.lstrip().startswith(">"):
            content = line.lstrip()[1:].strip()
            if content:
                blocks.append(("quote", content))
        elif line.startswith("Caption: "):
            blocks.append(("caption", line[9:]))
        else:
            blocks.append(("para", line.strip()))
        i += 1
    return blocks


def mark_changed(blocks: list, baseline: str) -> list:
    """True for every block whose normalised text is new relative to the baseline."""
    base_blocks = parse(baseline)
    def block_text(b):
        if b[0] == "table":
            return norm(" ".join(" ".join(r) for r in b[1]))
        if b[0] == "image":
            return norm(" ".join(b[1:]))
        return norm(b[-1])
    base = [block_text(b) for b in base_blocks]
    new = []
    for b in blocks:
        new.append(block_text(b))
    changed = [True] * len(new)
    sm = difflib.SequenceMatcher(a=base, b=new, autojunk=False)
    for tag, _i1, _i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for j in range(j1, j2):
                changed[j] = False
    return changed


WORD = re.compile(r"\w+(?:['’]\w+)*|[^\w\s]", re.UNICODE)


def plain(block) -> str:
    if block[0] == "table":
        return " ".join(" ".join(inline(cell)[0] for cell in row) for row in block[1])
    if block[0] == "image":
        return " ".join(block[1:])
    return inline(block[2] if block[0] == "heading" else block[1])[0]


def word_spans(current: str, prior: str) -> tuple[list[tuple[int, int]], list[str]]:
    """Changed positions in plain current text, plus removed original tokens."""
    new = list(WORD.finditer(current))
    old = list(WORD.finditer(prior))
    normalized = lambda matches: [norm(match.group()) for match in matches]
    spans, removed = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            a=normalized(old), b=normalized(new), autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if tag in {"replace", "insert"}:
            spans.extend((match.start(), match.end()) for match in new[j1:j2])
        if tag in {"replace", "delete"}:
            removed.extend(match.group() for match in old[i1:i2])
    return spans, removed


def sections(blocks: list) -> dict[tuple, tuple[int | None, list[tuple[int, tuple]]]]:
    """Heading-path scopes prevent repeated prose crossing unrelated sections."""
    result = {(): (None, [])}
    stack: list[tuple[int, str]] = []
    repeats: dict[tuple, int] = {}
    scope: tuple = ()
    for index, block in enumerate(blocks):
        if block[0] == "heading":
            level = block[1]
            stack = [part for part in stack if part[0] < level]
            stack.append((level, norm(block[2])))
            path = tuple(stack)
            repeats[path] = repeats.get(path, 0) + 1
            scope = (path, repeats[path])
            result[scope] = (index, [])
        else:
            result[scope][1].append((index, block))
    return result


def table_plan(current: list[list[str]], prior: list[list[str]]) -> tuple[list, list[str]]:
    cells, removed = [], []
    keyed = {norm(inline(row[0])[0]): row for row in prior if row and norm(inline(row[0])[0])}
    for index, row in enumerate(current):
        old = keyed.get(norm(inline(row[0])[0])) if row else None
        if old is None and index < len(prior) and (index == 0 or not keyed):
            old = prior[index]
        row_plan = []
        for col, cell in enumerate(row):
            display = inline(cell)[0]
            if old is None or col >= len(old):
                row_plan.append([(0, len(display))] if display else [])
            else:
                spans, gone = word_spans(display, inline(old[col])[0])
                row_plan.append(spans)
                removed.extend(gone)
        cells.append(row_plan)
    current_keys = {norm(inline(row[0])[0]) for row in current if row}
    for row in prior:
        if row and norm(inline(row[0])[0]) not in current_keys:
            removed.append(" | ".join(inline(cell)[0] for cell in row))
    return cells, removed


def word_highlight_plan(blocks: list, baseline: str) -> tuple[list[dict], list[dict]]:
    """Return per-block highlight spans and a local record of removed text."""
    plans = [{"changed": False, "spans": [], "cells": []} for _ in blocks]
    removed: list[dict] = []
    base_blocks = parse(baseline)
    base_sections = sections(base_blocks)
    current_sections = sections(blocks)
    for scope, (heading_index, entries) in current_sections.items():
        if heading_index is not None and scope not in base_sections:
            plans[heading_index]["spans"] = [(0, len(plain(blocks[heading_index])))]
        old_entries = base_sections.get(scope, (None, []))[1]
        if scope not in base_sections:
            for index, block in entries:
                if block[0] == "table":
                    plans[index]["cells"] = [[[(0, len(inline(cell)[0]))] if inline(cell)[0] else []
                                                 for cell in row] for row in block[1]]
                elif block[0] != "image":
                    plans[index]["spans"] = [(0, len(plain(block)))]
                else:
                    plans[index]["changed"] = True
            continue
        old_keys = [(block[0], norm(plain(block))) for _, block in old_entries]
        new_keys = [(block[0], norm(plain(block))) for _, block in entries]
        matcher = difflib.SequenceMatcher(a=old_keys, b=new_keys, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            old_group, new_group = old_entries[i1:i2], entries[j1:j2]
            for offset, (index, block) in enumerate(new_group):
                prior = old_group[offset][1] if offset < len(old_group) else None
                if prior is None or block[0] != prior[0] or (
                    block[0] != "table" and difflib.SequenceMatcher(
                        a=norm(plain(prior)), b=norm(plain(block)), autojunk=False).ratio() < 0.35):
                    if block[0] == "table":
                        plans[index]["cells"] = [[[(0, len(inline(cell)[0]))] if inline(cell)[0] else []
                                                     for cell in row] for row in block[1]]
                    elif block[0] != "image":
                        plans[index]["spans"] = [(0, len(plain(block)))]
                    else:
                        plans[index]["changed"] = True
                    if prior is not None:
                        removed.append({"section": str(scope), "text": plain(prior)})
                    continue
                if block[0] == "table":
                    plans[index]["cells"], gone = table_plan(block[1], prior[1])
                elif block[0] == "image":
                    plans[index]["changed"] = plain(block) != plain(prior)
                    gone = []
                else:
                    plans[index]["spans"], gone = word_spans(plain(block), plain(prior))
                if gone:
                    removed.append({"section": str(scope), "text": " ".join(gone)})
            for _, block in old_group[len(new_group):]:
                removed.append({"section": str(scope), "text": plain(block)})
    for scope, (heading_index, entries) in base_sections.items():
        if scope not in current_sections:
            if heading_index is not None:
                removed.append({"section": str(scope), "text": plain(base_blocks[heading_index])})
            removed.extend({"section": str(scope), "text": plain(block)} for _, block in entries)
    return plans, removed


# ---------------------------------------------------------------- writing

def end_index(svc, doc_id: str) -> int:
    doc = svc.documents().get(documentId=doc_id, fields="body(content(endIndex))").execute()
    return doc["body"]["content"][-1]["endIndex"] - 1


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def append_run(svc, doc_id: str, items: list) -> None:
    """Append a run of paragraph items in ONE batchUpdate (indices computed locally).

    items: list of dicts {text, style, spans, changed, bullet}
    """
    items = [it for it in items if it["text"].strip()]
    if not items:
        return
    at = end_index(svc, doc_id)
    body = ""
    placed = []
    for it in items:
        placed.append((at + utf16_len(body), it))
        body += it["text"] + "\n"

    reqs = [{"insertText": {"location": {"index": at}, "text": body}}]
    for start, it in placed:
        text = it["text"]
        para_rng = {"startIndex": start, "endIndex": start + utf16_len(text) + 1}
        reqs.append({"updateParagraphStyle": {
            "range": para_rng,
            "paragraphStyle": {"namedStyleType": it["style"]},
            "fields": "namedStyleType"}})
        if it.get("bullet"):
            reqs.append({"createParagraphBullets": {
                "range": para_rng, "bulletPreset": ("NUMBERED_DECIMAL_ALPHA_ROMAN" if it["bullet"] == "ordered"
                                                      else "BULLET_DISC_CIRCLE_SQUARE")}})
        if it.get("quote"):
            reqs.append({"updateParagraphStyle": {"range": para_rng, "paragraphStyle": {
                "indentStart": {"magnitude": 14, "unit": "PT"},
                "indentEnd": {"magnitude": 14, "unit": "PT"}}, "fields": "indentStart,indentEnd"}})
        if it.get("caption"):
            reqs.append({"updateTextStyle": {"range": para_rng, "textStyle": {"italic": True},
                                             "fields": "italic"}})
        for s, e, kind, value in it["spans"]:
            if e <= s:
                continue
            sub = {"startIndex": start + utf16_len(text[:s]), "endIndex": start + utf16_len(text[:e])}
            if kind == "bold":
                reqs.append({"updateTextStyle": {"range": sub, "textStyle": {"bold": True},
                                                 "fields": "bold"}})
            elif kind == "italic":
                reqs.append({"updateTextStyle": {"range": sub, "textStyle": {"italic": True},
                                                 "fields": "italic"}})
            elif kind == "code":
                reqs.append({"updateTextStyle": {"range": sub, "textStyle": {
                    "weightedFontFamily": {"fontFamily": "Courier New"}},
                    "fields": "weightedFontFamily"}})
            else:
                reqs.append({"updateTextStyle": {
                    "range": sub, "textStyle": {"link": {"url": value}}, "fields": "link"}})
        highlight_spans = it.get("highlight_spans")
        if highlight_spans is not None:
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": start, "endIndex": start + utf16_len(text)},
                "textStyle": {}, "fields": "backgroundColor"}})
        if highlight_spans is None:
            highlight_spans = [(0, len(text))] if it["changed"] else []
        for s, e in highlight_spans:
            if e <= s:
                continue
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": start + utf16_len(text[:s]),
                          "endIndex": start + utf16_len(text[:e])},
                "textStyle": {"backgroundColor": {"color": {"rgbColor": HIGHLIGHT}}},
                "fields": "backgroundColor"}})
    execute_docs_write(svc.documents().batchUpdate(documentId=doc_id, body={"requests": reqs}))


def append_table(svc, doc_id: str, rows: list, changed: bool, cell_spans: list | None = None) -> None:
    at = end_index(svc, doc_id)
    cols = max(len(r) for r in rows)
    execute_docs_write(svc.documents().batchUpdate(documentId=doc_id, body={"requests": [
        {"insertTable": {"location": {"index": at}, "rows": len(rows), "columns": cols}}]}))

    doc = svc.documents().get(documentId=doc_id).execute()
    table = None
    for element in doc["body"]["content"]:
        if "table" in element and element["startIndex"] >= at:
            table = element
            break
    if table is None:
        raise RuntimeError("inserted table not found")

    cells = []
    for r, row in enumerate(table["table"]["tableRows"]):
        for c, cell in enumerate(row["tableCells"]):
            raw = rows[r][c] if c < len(rows[r]) else ""
            text, inline_spans = inline(raw)
            highlights = (cell_spans[r][c] if cell_spans is not None and r < len(cell_spans)
                          and c < len(cell_spans[r]) else [] if cell_spans is not None else None)
            cells.append((cell["content"][0]["startIndex"], text, r == 0, inline_spans, highlights))
    reqs = []
    for start, text, header, inline_spans, highlights in reversed(cells):  # reverse: earlier indices stay valid
        if not text:
            continue
        reqs.append({"insertText": {"location": {"index": start}, "text": text}})
        if header:
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": start, "endIndex": start + utf16_len(text)},
                "textStyle": {"bold": True}, "fields": "bold"}})
        for s, e, kind, value in inline_spans:
            style = ({"bold": True} if kind == "bold" else {"italic": True} if kind == "italic"
                     else {"weightedFontFamily": {"fontFamily": "Courier New"}} if kind == "code"
                     else {"link": {"url": value}})
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": start + utf16_len(text[:s]),
                          "endIndex": start + utf16_len(text[:e])},
                "textStyle": style, "fields": ",".join(style)}})
        if highlights is not None:
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": start, "endIndex": start + utf16_len(text)},
                "textStyle": {}, "fields": "backgroundColor"}})
        for s, e in (highlights if highlights is not None else [(0, len(text))] if changed else []):
            if e > s:
                reqs.append({"updateTextStyle": {
                    "range": {"startIndex": start + utf16_len(text[:s]),
                              "endIndex": start + utf16_len(text[:e])},
                    "textStyle": {"backgroundColor": {"color": {"rgbColor": HIGHLIGHT}}},
                    "fields": "backgroundColor"}})
    if reqs:
        execute_docs_write(svc.documents().batchUpdate(documentId=doc_id, body={"requests": reqs}))


HEADING = {1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3",
           4: "HEADING_4", 5: "HEADING_5", 6: "HEADING_6"}


def append_image(svc, did, block):
    """A real inline object, with its own paragraph; fail if Docs rejects the URL."""
    _, alt, url, title = block
    at = end_index(svc, did)
    result = execute_docs_write(svc.documents().batchUpdate(documentId=did, body={"requests": [
        {"insertText": {"location": {"index": at}, "text": "\n"}},
        {"insertInlineImage": {"location": {"index": at}, "uri": url,
                               "objectSize": {"width": {"magnitude": 440, "unit": "PT"},
                                              "height": {"magnitude": 540, "unit": "PT"}}}},
    ]}))
    object_id = result["replies"][1].get("insertInlineImage", {}).get("objectId")
    if not object_id:
        raise RuntimeError("Google Docs did not confirm the image insertion")
    # Docs REST has no setter for image alt/title. Keep metadata in the receipt;
    # public HTML and Strapi media have them; review shows the real image + caption.
    return {"object_id": object_id, "alt": alt, "url": url, "title": title}


def write_blocks(docs, did, blocks, changed):
    run, images = [], []
    for block, decision in zip(blocks, changed):
        is_changed = decision.get("changed", False) if isinstance(decision, dict) else decision
        if block[0] in {"table", "image"}:
            append_run(docs, did, run)
            run = []
            if block[0] == "table":
                append_table(docs, did, block[1], is_changed,
                             decision.get("cells") if isinstance(decision, dict) else None)
            else:
                images.append(append_image(docs, did, block))
            continue
        text, spans = inline(block[2] if block[0] == "heading" else block[1])
        run.append({"text": text, "style": HEADING[block[1]] if block[0] == "heading" else "NORMAL_TEXT",
                    "spans": spans, "changed": is_changed,
                    "highlight_spans": decision.get("spans") if isinstance(decision, dict) else None,
                    "bullet": block[0] if block[0] in {"bullet", "ordered"} else False,
                    "quote": block[0] == "quote", "caption": block[0] == "caption"})
    append_run(docs, did, run)
    return images


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--baseline", help="original text to diff against (changes get highlighted)")
    ap.add_argument("--highlight-mode", choices=("blocks", "words"), default="blocks",
                    help="baseline highlighting granularity; default preserves block highlighting")
    ap.add_argument("--diff-report", help="local JSON report of removed baseline text in word mode")
    ap.add_argument("--title", required=True)
    ap.add_argument("--share", action="append", default=[], help="email to grant writer access")
    ap.add_argument("--preface", help="file with a note to put above the article")
    ap.add_argument("--folder", help="Drive folder id (default: GOOGLE_DRIVE_FOLDER_ID from config/.env)")
    ap.add_argument("--replace", help="doc id to rewrite in place (keeps the URL) instead of creating one")
    ap.add_argument("--receipt", help="JSON receipt with document id and verified inline images")
    args = ap.parse_args()

    source = Path(args.source).read_text(encoding="utf-8")
    if PLACEHOLDERS.search(source):
        raise SystemExit("not sent: the article still contains a service placeholder")
    blocks = parse(source)
    removed = []
    if args.baseline:
        baseline = Path(args.baseline).read_text(encoding="utf-8")
        if args.highlight_mode == "words":
            changed, removed = word_highlight_plan(blocks, baseline)
        else:
            changed = mark_changed(blocks, baseline)
    else:
        changed = [False] * len(blocks)
    if args.highlight_mode == "words" and args.baseline:
        report_path = Path(args.diff_report) if args.diff_report else Path(args.source).with_suffix(".diff.json")
        report_path.write_text(json.dumps({"baseline": args.baseline, "removed": removed},
                                          ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    creds = Credentials.from_service_account_file(str(KEYFILE), scopes=SCOPES)
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    if args.replace:
        doc_id = args.replace
        end = end_index(docs, doc_id)
        if end > 1:
            execute_docs_write(docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
                {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end}}}]}))
        drive.files().update(fileId=doc_id, body={"name": args.title},
                             supportsAllDrives=True, fields="id").execute()
    else:
        # Docs API documents.create is refused for this service account (403), and its own My Drive
        # has no storage quota — so the file is created through Drive in the publications Shared Drive
        # folder (org-owned storage), then filled through the Docs API.
        folder = args.folder or load_env().get("GOOGLE_DRIVE_FOLDER_ID")
        meta = {"name": args.title, "mimeType": "application/vnd.google-apps.document"}
        if folder:
            meta["parents"] = [folder]
        doc_id = drive.files().create(body=meta, fields="id",
                                      supportsAllDrives=True).execute()["id"]

    preface = []
    if args.preface:
        preface = parse(Path(args.preface).read_text(encoding="utf-8"))
    try:
        write_blocks(docs, doc_id, preface, [False] * len(preface))
        article_start = end_index(docs, doc_id)
        images = write_blocks(docs, doc_id, blocks, changed)
        execute_docs_write(docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
            {"createNamedRange": {"name": "BLOG_ARTICLE_BODY", "range": {
                "startIndex": article_start, "endIndex": end_index(docs, doc_id)}}}
        ]}))
        doc = docs.documents().get(documentId=doc_id).execute()
        inline_objects = doc.get("inlineObjects", {})
        for item in images:
            if item["object_id"] not in inline_objects:
                raise RuntimeError("the image is missing in the document after insertion")
        if args.receipt:
            Path(args.receipt).write_text(json.dumps({"document_id": doc_id, "images": images},
                ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        if not args.replace:
            drive.files().update(fileId=doc_id, body={"trashed": True}, supportsAllDrives=True).execute()
        raise

    for email in args.share:
        drive.permissions().create(
            fileId=doc_id, sendNotificationEmail=False, supportsAllDrives=True,
            body={"type": "user", "role": "writer", "emailAddress": email}).execute()

    print(f"DOC_ID={doc_id}")
    print(f"URL=https://docs.google.com/document/d/{doc_id}/edit")
    highlighted = (sum(bool(item.get("changed") or item.get("spans") or
                            any(any(cell for cell in row) for row in item.get("cells", [])))
                       for item in changed) if args.highlight_mode == "words" and args.baseline
                   else sum(changed))
    print(f"BLOCKS={len(blocks)} HIGHLIGHTED={highlighted}")
    print(f"IMAGES={len(images)} VERIFIED=yes")


if __name__ == "__main__":
    main()
