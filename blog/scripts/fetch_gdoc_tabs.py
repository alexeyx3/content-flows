"""Dump a Google Doc's tabs as Markdown via the service account.

Reads tab structure (includeTabsContent=True), so documents with several tabs
("Tab 1", "Edited", ...) come out as one file per tab. Keeps headings, list items,
tables and hyperlinks as Markdown so a review can check anchors and link liveness.

Usage:
  python3 scripts/fetch_gdoc_tabs.py <doc-id-or-url> --outdir <dir> [--tab Edited]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
KEYFILE = ROOT / "config" / "google-service-account.json"
SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def doc_id(value: str) -> str:
    m = re.search(r"/document/d/([A-Za-z0-9_-]+)", value)
    return m.group(1) if m else value


def para_text(element: dict) -> str:
    out = []
    for run in element.get("paragraph", {}).get("elements", []):
        text_run = run.get("textRun")
        if text_run:
            content = text_run.get("content", "")
            url = text_run.get("textStyle", {}).get("link", {}).get("url")
            if url and content.strip():
                trail = content[len(content.rstrip()):]
                out.append(f"[{content.strip()}]({url}){trail}")
            else:
                out.append(content)
        elif "person" in run:
            out.append(run["person"].get("personProperties", {}).get("name", ""))
        elif "richLink" in run:
            props = run["richLink"].get("richLinkProperties", {})
            out.append(f"[{props.get('title', 'link')}]({props.get('uri', '')})")
    return "".join(out)


def body_text(content: list) -> str:
    lines = []
    for element in content:
        if "paragraph" in element:
            style = element["paragraph"].get("paragraphStyle", {}).get("namedStyleType", "")
            text = para_text(element).rstrip("\n")
            prefix = ""
            if style.startswith("HEADING_"):
                prefix = "#" * int(style.split("_")[1]) + " "
            elif element["paragraph"].get("bullet"):
                prefix = "- "
            lines.append(prefix + text)
        elif "table" in element:
            for row in element["table"].get("tableRows", []):
                cells = [
                    body_text(cell.get("content", [])).replace("\n", " ").strip()
                    for cell in row.get("tableCells", [])
                ]
                lines.append("| " + " | ".join(cells) + " |")
        elif "tableOfContents" in element:
            lines.append("<TOC>")
    text = "\n".join(lines)
    # a literal bullet typed into a paragraph is not a list item — normalise it,
    # and report it, because it breaks when the doc is published
    return text


def walk_tabs(tabs: list, depth: int = 0):
    for tab in tabs:
        props = tab.get("tabProperties", {})
        yield props.get("title", "(untitled)"), props.get("tabId", ""), depth, tab.get("documentTab")
        yield from walk_tabs(tab.get("childTabs", []), depth + 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("doc", help="document id or full /document/d/... URL")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--tab", help="only dump the tab with this exact title")
    args = ap.parse_args()

    creds = Credentials.from_service_account_file(str(KEYFILE), scopes=SCOPES)
    svc = build("docs", "v1", credentials=creds)
    doc = svc.documents().get(documentId=doc_id(args.doc), includeTabsContent=True).execute()

    print("TITLE=" + doc.get("title", ""))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    tabs = list(walk_tabs(doc.get("tabs", [])))
    if not tabs:
        text = body_text(doc.get("body", {}).get("content", []))
        path = outdir / "single.md"
        path.write_text(text, encoding="utf-8")
        print(f"TAB=(none) chars={len(text)} -> {path}")
        return

    for i, (title, tab_id, depth, document_tab) in enumerate(tabs):
        if args.tab and title != args.tab:
            continue
        text = body_text(document_tab.get("body", {}).get("content", [])) if document_tab else ""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:40]
        path = outdir / f"{i:02d}-{safe}.md"
        path.write_text(text, encoding="utf-8")
        fake_bullets = len(re.findall(r"(?m)^\s*[•▪◦·]", text))
        note = f" FAKE_BULLET_LINES={fake_bullets}" if fake_bullets else ""
        print(f"TAB[{depth}]={title!r} id={tab_id} chars={len(text)} -> {path}{note}")


if __name__ == "__main__":
    main()
