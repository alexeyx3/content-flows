#!/usr/bin/env python3
"""Verify an uploaded glossary Google Doc against its packaged review copy."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from glossary_materials import IMAGE, enriched, read as read_material

import markdown
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def tokens(value: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", value, flags=re.UNICODE)


def doc_content(document: dict) -> tuple[list[tuple[str, str]], str, list[str]]:
    headings: list[tuple[str, str]] = []
    chunks: list[str] = []
    image_ids: list[str] = []
    for block in document["body"]["content"]:
        paragraph = block.get("paragraph")
        if paragraph:
            value = "".join(el.get("textRun", {}).get("content", "") for el in paragraph.get("elements", []))
            image_ids.extend(el["inlineObjectElement"]["inlineObjectId"]
                             for el in paragraph.get("elements", []) if "inlineObjectElement" in el)
            chunks.append(value)
            style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
            if style.startswith("HEADING_"):
                headings.append((style, value.strip()))
        for row in block.get("table", {}).get("tableRows", []):
            for cell in row.get("tableCells", []):
                for inner in cell.get("content", []):
                    chunks.append("".join(el.get("textRun", {}).get("content", "") for el in inner.get("paragraph", {}).get("elements", [])))
    return headings, " ".join(chunks), image_ids


def verify_image_objects(document: dict, source: str, receipt: dict, manifest: list[dict] | None = None) -> int:
    expected_images = IMAGE.findall(source)
    actual_image_ids = doc_content(document)[2]
    recorded = receipt.get("images", [])
    if receipt.get("document_id") != document.get("documentId") or len(recorded) != len(expected_images):
        raise ValueError("native image receipt missing or belongs to another document")
    if actual_image_ids != [item.get("object_id") for item in recorded]:
        raise ValueError("inline image count/order differs from sent review")
    for expected, item in zip(expected_images, recorded):
        if expected != (item.get("alt"), item.get("url"), item.get("title")):
            raise ValueError("inline image metadata differs from sent review")
        embedded = document.get("inlineObjects", {}).get(item["object_id"], {}).get("inlineObjectProperties", {}).get("embeddedObject", {})
        if embedded.get("imageProperties", {}).get("sourceUri") != item["url"]:
            raise ValueError("inline image URL differs from sent review")
    # The article determines image order; the visual manifest may list images
    # by planning order instead of their position in the final article.
    if manifest is not None and Counter(v.get("asset", {}).get("url") for v in manifest) != Counter(image[1] for image in expected_images):
        raise ValueError("inline images differ from verified visual manifest")
    return len(actual_image_ids)


def verify(job: Path, round_number: int, pdf_out: Path | None) -> None:
    config = json.loads((ROOT / "config/google-drive.json").read_text(encoding="utf-8"))
    file_info = json.loads((job / "review" / f"{round_number:02d}-file.json").read_text(encoding="utf-8"))
    source = (job / "review" / f"{round_number:02d}-sent.md").read_text(encoding="utf-8")
    current = (job / "out" / "review.md").read_text(encoding="utf-8")
    if source != current:
        raise ValueError("sent review copy differs from the current packaged copy")

    credentials = Credentials.from_service_account_file(
        str(ROOT / config["service_account_keyfile"]),
        scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents"],
    )
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    docs = build("docs", "v1", credentials=credentials, cache_discovery=False)
    remote_file = drive.files().get(fileId=file_info["id"], supportsAllDrives=True, fields="id,name,mimeType,parents").execute()
    if config["review_folder_id"] not in remote_file.get("parents", []):
        raise ValueError("Google Doc is outside the glossary review folder")
    document = docs.documents().get(documentId=file_info["id"]).execute()
    actual_headings, actual_text, actual_image_ids = doc_content(document)
    expected_headings = [
        (f"HEADING_{len(marks)}", title)
        for marks, title in re.findall(r"^(#{1,4}) (.+)$", source, flags=re.MULTILINE)
    ]
    parsed = VisibleText()
    # The shared native-image exporter renders the caption under the image and
    # omits the Markdown's editorial "Caption: " label from the visible text.
    comparison_source = re.sub(r"(?m)^Caption: ", "", source) if IMAGE.search(source) else source
    parsed.feed(markdown.markdown(comparison_source, extensions=["tables", "sane_lists"]))
    expected_tokens = tokens(" ".join(parsed.parts))
    actual_tokens = tokens(actual_text)
    if actual_headings != expected_headings:
        raise ValueError(f"heading mismatch: {actual_headings!r} != {expected_headings!r}")
    if actual_tokens != expected_tokens:
        raise ValueError(f"text mismatch: {len(actual_tokens)} imported vs {len(expected_tokens)} expected tokens")
    if IMAGE.search(source) or actual_image_ids:
        receipt = read_material(job / "review" / f"{round_number:02d}-document.json")
        manifest = read_material(job / "visuals.json")["visuals"] if enriched(job) else None
        verify_image_objects(document, source, receipt, manifest)
    if pdf_out:
        pdf_out.parent.mkdir(parents=True, exist_ok=True)
        pdf_out.write_bytes(drive.files().export(fileId=file_info["id"], mimeType="application/pdf").execute())
    print(f"PASS: {len(actual_headings)} headings; {len(actual_tokens)} tokens; {len(actual_image_ids)} native images; glossary folder confirmed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--pdf-out")
    args = parser.parse_args()
    try:
        verify(Path(args.job).resolve(), args.round, Path(args.pdf_out) if args.pdf_out else None)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
