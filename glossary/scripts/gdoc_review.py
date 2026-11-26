#!/usr/bin/env python3
"""Upload one packaged glossary review round to the configured shared-drive folder."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from glossary_materials import BLOG_V2, enriched, read as read_material

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "google-drive.json"


def extract_text(document: dict) -> str:
    chunks = []
    for block in document.get("body", {}).get("content", []):
        for element in block.get("paragraph", {}).get("elements", []):
            chunks.append(element.get("textRun", {}).get("content", ""))
        for row in block.get("table", {}).get("tableRows", []):
            for cell in row.get("tableCells", []):
                for inner in cell.get("content", []):
                    for element in inner.get("paragraph", {}).get("elements", []):
                        chunks.append(element.get("textRun", {}).get("content", ""))
    return "".join(chunks)


def layout_requests(document: dict) -> list[dict]:
    requests = []
    content = document.get("body", {}).get("content", [])
    list_intro_chain = set()
    for i, block in enumerate(content):
        text = "".join(e.get("textRun", {}).get("content", "")
                       for e in block.get("paragraph", {}).get("elements", [])).rstrip()
        if not text.endswith(":"):
            continue
        j, blanks = i + 1, []
        while j < len(content) and "paragraph" in content[j]:
            elements = content[j]["paragraph"].get("elements", [])
            if any("inlineObjectElement" in e for e in elements) or "".join(
                    e.get("textRun", {}).get("content", "") for e in elements).strip():
                break
            blanks.append(j)
            j += 1
        following = content[j] if j < len(content) else {}
        if "bullet" in following.get("paragraph", {}) or "table" in following:
            list_intro_chain.update([i, *blanks])
    for i, block in enumerate(content):
        if "table" in block:
            requests.append({"updateTableRowStyle": {
                "tableStartLocation": {"index": block["startIndex"]},
                "tableRowStyle": {"preventOverflow": True},
                "fields": "preventOverflow",
            }})
            continue
        paragraph = block.get("paragraph")
        if not paragraph:
            continue
        style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
        elements = paragraph.get("elements", [])
        introduces_list = i in list_intro_chain
        has_image = any("inlineObjectElement" in e for e in elements)
        paragraph_style = {"keepLinesTogether": True}
        if style in ("HEADING_1", "HEADING_2", "HEADING_3", "HEADING_4") or has_image or introduces_list:
            paragraph_style["keepWithNext"] = True
        requests.append({"updateParagraphStyle": {
            "range": {"startIndex": block["startIndex"], "endIndex": block["endIndex"]},
            "paragraphStyle": paragraph_style, "fields": ",".join(paragraph_style),
        }})
    requests.append({"updateDocumentStyle": {
        "documentStyle": {"marginTop": {"magnitude": 42, "unit": "PT"},
                          "marginBottom": {"magnitude": 42, "unit": "PT"}},
        "fields": "marginTop,marginBottom",
    }})
    return requests


def apply_review_layout(docs, document_id: str) -> None:
    imported = docs.documents().get(documentId=document_id).execute()
    docs.documents().batchUpdate(documentId=document_id,
                                 body={"requests": layout_requests(imported)}).execute()


def push(job: Path, round_number: int, apply: bool) -> None:
    if round_number < 1:
        raise ValueError("round must be positive")
    review = job / "review"
    review.mkdir(exist_ok=True)
    target = review / f"{round_number:02d}-url.txt"
    if target.exists():
        print(target.read_text(encoding="utf-8").strip())
        return
    source = job / "out" / "review.md"
    content = source.read_text(encoding="utf-8")
    if not content.startswith("# "):
        raise ValueError("out/review.md must start with H1")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    folder_id = config["review_folder_id"]
    title = content.splitlines()[0][2:].strip()
    if not apply:
        print(f"DRY RUN: would create Google Doc '{title}' in folder {config['review_folder_name']} ({folder_id})")
        return

    import markdown
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaInMemoryUpload

    html = markdown.markdown(content, extensions=["tables", "sane_lists"])
    keyfile = ROOT / config["service_account_keyfile"]
    credentials = Credentials.from_service_account_file(
        str(keyfile),
        scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents"],
    )
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    folder = drive.files().get(fileId=folder_id, supportsAllDrives=True, fields="id,name,mimeType,parents").execute()
    if folder["name"] != config["review_folder_name"] or config["shared_drive_id"] not in folder.get("parents", []):
        raise ValueError("configured Google Drive folder does not match the expected shared drive")
    visuals = read_material(job / "visuals.json")["visuals"] if enriched(job) else []
    if visuals:
        # The blog v2 exporter writes native Docs inline images and a receipt.
        # Reuse it with the glossary folder; the HTML importer drops image objects.
        receipt = review / f"{round_number:02d}-document.json"
        script = ROOT / "scripts" / "glossary_md_to_gdoc.py"
        result = subprocess.run([sys.executable, str(script), str(source), "--title",
                                 f"{title} — review {round_number}", "--folder", folder_id,
                                 "--receipt", str(receipt)], capture_output=True, text=True, check=True)
        document_id = re.search(r"^DOC_ID=([A-Za-z0-9_-]+)$", result.stdout, re.M)
        if not document_id:
            raise RuntimeError("native Google Docs exporter returned no document ID")
        document = drive.files().get(fileId=document_id.group(1), supportsAllDrives=True,
                                     fields="id,name,mimeType,parents,webViewLink").execute()
    else:
        document = drive.files().create(
            body={"name": f"{title} — review {round_number}", "mimeType": "application/vnd.google-apps.document", "parents": [folder_id]},
            media_body=MediaInMemoryUpload(html.encode("utf-8"), mimetype="text/html", resumable=False),
            supportsAllDrives=True,
            fields="id,name,mimeType,parents,webViewLink",
        ).execute()
    url = document.get("webViewLink") or f"https://docs.google.com/document/d/{document['id']}/edit"

    docs = build("docs", "v1", credentials=credentials, cache_discovery=False)
    imported = docs.documents().get(documentId=document["id"]).execute()
    requests = layout_requests(imported)
    if requests:
        docs.documents().batchUpdate(
            documentId=document["id"], body={"requests": requests}
        ).execute()
    imported_text = re.sub(r"\s+", " ", extract_text(imported))
    if title not in imported_text or len(imported_text) < 200:
        raise RuntimeError(f"Document created at {url}, but imported text requires manual inspection")
    target.write_text(url + "\n", encoding="utf-8")
    (review / f"{round_number:02d}-sent.md").write_text(content, encoding="utf-8")
    (review / f"{round_number:02d}-file.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(url)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--apply", action="store_true", help="Create a Google Doc; otherwise only preview destination")
    args = parser.parse_args()
    try:
        push(Path(args.job).resolve(), args.round, args.apply)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
