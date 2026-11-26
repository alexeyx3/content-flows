"""Create a Google Doc from a Markdown file, highlighting what changed vs a baseline.

Built for review copies: the reviewer sees the corrected article with every changed or new
passage highlighted, so nothing has to be diffed by eye. Headings, bullets, bold, links and
tables are rendered as real Google Docs structures.

The diff is paragraph-level and normalization-tolerant: re-bulleting, apostrophe/dash
unification and whitespace changes do NOT count as changes, only real text edits do.

Usage:
  python3 scripts/md_to_gdoc.py corrected.md --baseline original.md \
      --title "Article — corrected" --share someone@example.com
"""
from __future__ import annotations

import argparse
import difflib
import re
import json
import random
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from article_materials import IMAGE_LINE, placeholder_matches

ROOT = Path(__file__).resolve().parents[1]
KEYFILE = ROOT / "config" / "google-service-account.json"
ENV_PATH = ROOT / "config" / ".env"
SCOPES = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"]
HIGHLIGHT = {"red": 1.0, "green": 0.94, "blue": 0.55}

def load_env() -> dict:
    values = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LOCAL_LINK = re.compile(r"(\[[^\]\n]+\]\()((?:/(?!/)|#)[^)\s]*)(\))")


def resolve_review_links(text: str, base_url: str | None) -> str:
    """Render rooted guide links and section links using the page's public URL.

    Resolve only for the export; the reviewed source and its content hash stay intact.
    Legacy callers without a public page URL keep their existing behaviour.
    """
    if not base_url:
        return text
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute HTTP(S) page URL")
    return LOCAL_LINK.sub(lambda m: m[1] + urljoin(base_url, m[2]) + m[3], text)


# ---------------------------------------------------------------- parsing

def norm(text: str) -> str:
    """Normalise a paragraph for diffing: markers, quotes, dashes, whitespace."""
    t = LINK.sub(r"\1", text).replace(r"\*", "*")
    t = t.replace("**", "")
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
        if text.startswith(r"\*", i):
            out += "*"
            i += 2
            continue
        m_link = LINK.match(text, i)
        m_bold = BOLD.match(text, i)
        if m_link:
            start = len(out)
            out += m_link.group(1)
            spans.append((start, len(out), "link", m_link.group(2)))
            i = m_link.end()
        elif m_bold:
            start = len(out)
            out += m_bold.group(1)
            spans.append((start, len(out), "bold", None))
            i = m_bold.end()
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
                    rows.append([LINK.sub(r"\1", c).replace("**", "") for c in cells])
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


# ---------------------------------------------------------------- writing

def execute_quota_retry(request, retries: int = 8):
    """Retry explicit quota rejections, not ambiguous failed writes.

    Docs limits each service account to 60 writes per minute. Long review
    documents can reach that limit; preserve the exact rejected batch and
    wait with bounded exponential backoff. Other errors propagate normally.
    """
    for attempt in range(retries + 1):
        try:
            return request.execute()
        except HttpError as error:
            if error.resp.status != 429 or attempt == retries:
                raise
            time.sleep(min(2 ** attempt + random.random(), 32))


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
            else:
                reqs.append({"updateTextStyle": {
                    "range": sub, "textStyle": {"link": {"url": value}}, "fields": "link"}})
        if it["changed"]:
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": start, "endIndex": start + utf16_len(text)},
                "textStyle": {"backgroundColor": {"color": {"rgbColor": HIGHLIGHT}}},
                "fields": "backgroundColor"}})
    execute_quota_retry(svc.documents().batchUpdate(documentId=doc_id, body={"requests": reqs}))


def append_table(svc, doc_id: str, rows: list, changed: bool) -> None:
    at = end_index(svc, doc_id)
    cols = max(len(r) for r in rows)
    execute_quota_retry(svc.documents().batchUpdate(documentId=doc_id, body={"requests": [
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
            text = rows[r][c] if c < len(rows[r]) else ""
            cells.append((cell["content"][0]["startIndex"], text, r == 0))
    reqs = []
    for start, text, header in reversed(cells):          # reverse: earlier indices stay valid
        if not text:
            continue
        reqs.append({"insertText": {"location": {"index": start}, "text": text}})
        style = {"bold": True} if header else {}
        if changed:
            style["backgroundColor"] = {"color": {"rgbColor": HIGHLIGHT}}
        if style:
            reqs.append({"updateTextStyle": {
                "range": {"startIndex": start, "endIndex": start + utf16_len(text)},
                "textStyle": style,
                "fields": ",".join(style.keys())}})
    if reqs:
        execute_quota_retry(svc.documents().batchUpdate(documentId=doc_id, body={"requests": reqs}))


HEADING = {1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3",
           4: "HEADING_4", 5: "HEADING_5", 6: "HEADING_6"}


def append_image(svc, did, block):
    """A real inline object, with its own paragraph; fail if Docs rejects the URL."""
    _, alt, url, title = block
    at = end_index(svc, did)
    result = execute_quota_retry(svc.documents().batchUpdate(documentId=did, body={"requests": [
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
    for block, is_changed in zip(blocks, changed):
        if block[0] in {"table", "image"}:
            append_run(docs, did, run)
            run = []
            if block[0] == "table":
                append_table(docs, did, block[1], is_changed)
            else:
                images.append(append_image(docs, did, block))
            continue
        text, spans = inline(block[2] if block[0] == "heading" else block[1])
        run.append({"text": text, "style": HEADING[block[1]] if block[0] == "heading" else "NORMAL_TEXT",
                    "spans": spans, "changed": is_changed,
                    "bullet": block[0] if block[0] in {"bullet", "ordered"} else False,
                    "quote": block[0] == "quote", "caption": block[0] == "caption"})
    append_run(docs, did, run)
    return images


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--baseline", help="original text to diff against (changes get highlighted)")
    ap.add_argument("--title", required=True)
    ap.add_argument("--share", action="append", default=[], help="email to grant writer access")
    ap.add_argument("--preface", help="file with a note to put above the article")
    ap.add_argument("--folder", help="Drive folder id (default: GOOGLE_DRIVE_FOLDER_ID from config/.env)")
    ap.add_argument("--replace", help="doc id to rewrite in place (keeps the URL) instead of creating one")
    ap.add_argument("--receipt", help="JSON receipt with document id and verified inline images")
    ap.add_argument("--base-url", help="public page URL for rooted links and section links")
    args = ap.parse_args()

    source = resolve_review_links(Path(args.source).read_text(encoding="utf-8"), args.base_url)
    if next(placeholder_matches(source), None):
        raise SystemExit("not sent: a service placeholder remains in the article")
    blocks = parse(source)
    changed = (mark_changed(blocks, resolve_review_links(
                   Path(args.baseline).read_text(encoding="utf-8"), args.base_url))
               if args.baseline else [False] * len(blocks))

    creds = Credentials.from_service_account_file(str(KEYFILE), scopes=SCOPES)
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    if args.replace:
        doc_id = args.replace
        end = end_index(docs, doc_id)
        if end > 1:
            execute_quota_retry(docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
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
        preface = parse(resolve_review_links(Path(args.preface).read_text(encoding="utf-8"), args.base_url))
    try:
        write_blocks(docs, doc_id, preface, [False] * len(preface))
        article_start = end_index(docs, doc_id)
        images = write_blocks(docs, doc_id, blocks, changed)
        execute_quota_retry(docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
            {"createNamedRange": {"name": "BLOG_ARTICLE_BODY", "range": {
                "startIndex": article_start, "endIndex": end_index(docs, doc_id)}}}
        ]}))
        doc = docs.documents().get(documentId=doc_id).execute()
        inline_objects = doc.get("inlineObjects", {})
        for item in images:
            if item["object_id"] not in inline_objects:
                raise RuntimeError("an image is missing from the document after insertion")
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
    print(f"BLOCKS={len(blocks)} HIGHLIGHTED={sum(changed)}")
    print(f"IMAGES={len(images)} VERIFIED=yes")


if __name__ == "__main__":
    main()
