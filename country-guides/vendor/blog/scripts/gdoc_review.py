"""Send an article to the shared drive for proofreading and pull the edits back.

push: puts the document into a subfolder named after the article slug on the shared drive
      for review documents. The second and later rounds are sent with changes highlighted
      against the previous version, so nobody has to diff by eye.
pull: fetches BOTH the comments (Drive API) AND the current document text (Docs API), plus
      a diff against the version that was sent. No editing style is imposed: reviewers can
      leave comments or edit the body directly, and both are picked up.

Usage:
  python3 scripts/gdoc_review.py push --job jobs/<job-dir> --round 1
  python3 scripts/gdoc_review.py push --job jobs/<job-dir> --round 2 \
      --baseline jobs/<job-dir>/review/01-sent.md
  python3 scripts/gdoc_review.py pull --job jobs/<job-dir> --round 1 --doc <id-or-url>
"""
from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
import json
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from article_materials import (IMAGE_LINE, digest, export_errors, is_v2, read_json, write_json)

ROOT = Path(__file__).resolve().parents[1]
KEYFILE = ROOT / "config" / "google-service-account.json"
DRIVE_ID = "REPLACE_WITH_SHARED_DRIVE_ID"          # shared drive for review documents
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents.readonly",
]


def services():
    creds = Credentials.from_service_account_file(str(KEYFILE), scopes=SCOPES)
    return build("drive", "v3", credentials=creds), build("docs", "v1", credentials=creds)


def doc_id(value: str) -> str:
    m = re.search(r"/document/d/([A-Za-z0-9_-]+)", value)
    return m.group(1) if m else value


def guide_base_url(job: Path) -> str | None:
    """Public guide route, supplied only for jobs with explicit guide metadata."""
    metadata_path = job / "job.yaml"
    if not metadata_path.exists():
        return None
    metadata = metadata_path.read_text(encoding="utf-8")
    country = re.search(r"^country_slug:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$", metadata, re.M)
    page = re.search(r"^page:\s*(country|eor|contractors)\s*$", metadata, re.M)
    if not country or not page:
        return None
    suffix = {"country": "", "eor": "employer-of-record/",
              "contractors": "independent-contractors/"}[page[1]]
    return f"https://example.com/guides/{country[1]}/{suffix}"


def ensure_folder(drive, name: str) -> str:
    """Subfolder named after the article slug: look it up first, then create it, so a second round does not create duplicate folders."""
    q = (f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
         f"and '{DRIVE_ID}' in parents and trashed = false")
    found = drive.files().list(
        q=q, corpora="drive", driveId=DRIVE_ID,
        includeItemsFromAllDrives=True, supportsAllDrives=True,
        fields="files(id,name)",
    ).execute().get("files", [])
    if found:
        return found[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [DRIVE_ID]}
    return drive.files().create(body=meta, supportsAllDrives=True, fields="id").execute()["id"]


def format_comments(comments: list[dict]) -> str:
    """Unresolved comments first: the work starts with them."""
    if not comments:
        return "# Comments from the document\n\nNo comments.\n"
    rows = sorted(comments, key=lambda c: bool(c.get("resolved")))
    out = ["# Comments from the document", ""]
    for c in rows:
        status = "resolved" if c.get("resolved") else "open"
        author = (c.get("author") or {}).get("displayName", "?")
        quote = ((c.get("quotedFileContent") or {}).get("value") or "").strip()
        out.append(f"## [{status}] {author}")
        if quote:
            out.append(f"> {quote}")
        out.append(c.get("content", "").strip())
        for r in c.get("replies") or []:
            ra = (r.get("author") or {}).get("displayName", "?")
            out.append(f"  - reply {ra}: {r.get('content', '').strip()}")
        out.append("")
    return "\n".join(out)


HEADING_MARK = re.compile(r"^#{1,6}\s+")
LIST_MARK = re.compile(r"^([-*]|\d+\.)\s+")
TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")
MD_LINK = re.compile(r"\[([^\]]+)\]\(\S+?\)")


def normalize_for_diff(text: str) -> list[str]:
    """Brings Markdown to the form it has in the Google document.

    The document returns plain text: markup lives there as formatting, not as characters.
    Without normalization the heading hashes, list markers and asterisks get into the diff
    as “edits”, and the real change drowns among them — checked on a trial document where
    one edit produced nine changed lines.
    """
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line or TABLE_SEP.match(line):
            continue
        image = IMAGE_LINE.fullmatch(line)
        if image:
            out.append(f"IMAGE: {image.group(2)} | {image.group(1)} | {image.group(3) or ''}")
            continue
        if line.startswith("Caption: "):
            line = line[9:]
        if line.startswith(">"):
            line = line.lstrip(">").strip()
        if line.startswith("|"):                       # a table row
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not any(cells):
                # The empty header of a parameter table (“| | |”) carries no text and is absent
                # from the document. Without this branch the diff shows a false deletion of “|”.
                continue
            line = " | ".join(cells)
        line = HEADING_MARK.sub("", line)
        line = LIST_MARK.sub("", line)
        line = MD_LINK.sub(r"\1", line)
        line = line.replace(r"\*", "*").replace("**", "").replace("`", "")
        line = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", line)
        line = line.strip()
        if line:
            out.append(line)
    return out


def build_diff(sent: str, current: str) -> str:
    return "".join(difflib.unified_diff(
        [ln + "\n" for ln in normalize_for_diff(sent)],
        [ln + "\n" for ln in normalize_for_diff(current)],
        fromfile="sent", tofile="in the document now", n=1,
    ))


def doc_text(docs, did: str, images: list | None = None) -> str:
    """Document text including tables: an edit inside a table must be visible too."""
    doc = docs.documents().get(documentId=did).execute()
    image_map = {x["object_id"]: x for x in images or []}
    named = doc.get("namedRanges", {}).get("BLOG_ARTICLE_BODY", {}).get("namedRanges", [])
    ranges = named[-1].get("ranges", []) if named else []
    start = ranges[0]["startIndex"] if ranges else 0
    end = ranges[0]["endIndex"] if ranges else float("inf")

    def para_text(para: dict) -> str:
        pieces = []
        for r in para.get("elements", []):
            if r.get("endIndex", 0) <= start or r.get("startIndex", 0) >= end:
                continue
            if "textRun" in r:
                pieces.append(r["textRun"].get("content", ""))
            elif "inlineObjectElement" in r:
                oid = r["inlineObjectElement"]["inlineObjectId"]
                embedded = doc.get("inlineObjects", {}).get(oid, {}).get("inlineObjectProperties", {}).get("embeddedObject", {})
                uri = embedded.get("imageProperties", {}).get("sourceUri", "")
                original = image_map.get(oid)
                if original and (not uri or uri == original["url"]):
                    pieces.append(f'![{original["alt"]}]({original["url"]} "{original["title"]}")')
                else:
                    pieces.append(f'![Changed image]({uri or "unknown-image"})')
        return "".join(pieces)

    parts: list[str] = []
    for el in doc.get("body", {}).get("content", []):
        if para := el.get("paragraph"):
            parts.append(para_text(para))
            continue
        if table := el.get("table"):
            for row in table.get("tableRows", []):
                cells = []
                for cell in row.get("tableCells", []):
                    cells.append(" ".join(
                        para_text(c["paragraph"]).strip()
                        for c in cell.get("content", []) if "paragraph" in c
                    ).strip())
                parts.append(" | ".join(cells) + "\n")
    return "".join(parts)


def cmd_push(args) -> None:
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    review = job / "review"
    errors = export_errors(job, "review")
    if errors:
        sys.exit("not sent for proofreading:\n- " + "\n- ".join(errors))
    review.mkdir(exist_ok=True)
    slug = job.name
    drive, _ = services()
    folder = ensure_folder(drive, slug)

    sent = review / f"{args.round:02d}-sent.md"
    sent.write_text((job / "edited.md").read_text(encoding="utf-8"), encoding="utf-8")

    cmd = [sys.executable, str(ROOT / "scripts" / "md_to_gdoc.py"), str(sent),
           "--title", f"{args.round:02d} — {slug}", "--folder", folder,
           "--receipt", str(review / f"{args.round:02d}-document.json")]
    public_url = guide_base_url(job)
    if public_url:
        cmd += ["--base-url", public_url]
    if is_v2(job):
        quotes = [q for q in read_json(job / "expert_quotes.json")["quotes"] if q["status"] == "proposed"]
        if quotes:
            preface = review / f"{args.round:02d}-preface.md"
            note = ["## Expert comments for approval", "",
                    "The article below contains prepared wording. Please confirm or correct it:", ""]
            note += [f'- {q["attribution"]}: «{q["text"][:120]}…»' for q in quotes]
            preface.write_text("\n".join(note) + "\n", encoding="utf-8")
            cmd += ["--preface", str(preface)]
    if args.baseline:
        cmd += ["--baseline", args.baseline]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout or r.stderr)
    if r.returncode != 0:
        sys.exit("md_to_gdoc failed: the document was not created")
    receipt_path = review / f"{args.round:02d}-document.json"
    receipt = read_json(receipt_path)
    receipt["article_sha256"] = digest(sent.read_bytes())
    write_json(receipt_path, receipt)
    print(f"sent for proofreading: round {args.round}, folder «{slug}»")


def cmd_pull(args) -> None:
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    review = job / "review"
    did = doc_id(args.doc)
    drive, docs = services()

    comments = drive.comments().list(
        fileId=did,
        fields=("comments(id,content,resolved,author/displayName,"
                "quotedFileContent/value,replies(content,author/displayName))"),
        pageSize=100,
    ).execute().get("comments", [])
    (review / f"{args.round:02d}-comments.md").write_text(
        format_comments(comments), encoding="utf-8")

    receipt_path = review / f"{args.round:02d}-document.json"
    receipt = read_json(receipt_path) if receipt_path.exists() else {}
    if receipt.get("document_id") and receipt["document_id"] != did:
        sys.exit("the document does not match the saved proofreading round")
    current = doc_text(docs, did, receipt.get("images"))
    (review / f"{args.round:02d}-current.txt").write_text(current, encoding="utf-8")
    sent = (review / f"{args.round:02d}-sent.md").read_text(encoding="utf-8")
    diff = build_diff(sent, current)
    (review / f"{args.round:02d}-diff.txt").write_text(diff, encoding="utf-8")

    open_count = sum(1 for c in comments if not c.get("resolved"))
    print(f"comments: {len(comments)} (open {open_count})")
    print(f"body edits: {'yes' if diff.strip() else 'no'}")
    print(f"files: {review}/{args.round:02d}-comments.md, {args.round:02d}-diff.txt")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("push")
    p.add_argument("--job", required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--baseline", help="previous round: changes will arrive highlighted")
    p.set_defaults(func=cmd_push)

    p = sub.add_parser("pull")
    p.add_argument("--job", required=True)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--doc", required=True)
    p.set_defaults(func=cmd_pull)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
