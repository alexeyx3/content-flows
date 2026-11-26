"""Read back a refresh review Doc and verify its text, highlights and temnik link.

Only Docs/Sheets reads are made. Output is limited to review/<round>-*readback*
and review/<round>-delivery-verification.json inside the selected job.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
if __package__:
    from scripts import gdoc_review as review, md_to_gdoc as converter, temnik
else:
    import gdoc_review as review
    import md_to_gdoc as converter
    import temnik

LEGACY_REQUIRED = ("Status", "Google Doc", "Publication date", "Publication URL")


class VerificationError(RuntimeError):
    pass


def service_keyfile() -> Path:
    env = temnik.load_env()
    path = ROOT / env.get("GOOGLE_SA_KEYFILE", "config/google-service-account.json")
    if not path.is_file():
        raise VerificationError("Google service account keyfile is unavailable")
    return path


def docs_service():
    credentials = Credentials.from_service_account_file(
        str(service_keyfile()), scopes=["https://www.googleapis.com/auth/documents.readonly"])
    return build("docs", "v1", credentials=credentials, cache_discovery=False)


def temnik_service():
    credentials = Credentials.from_service_account_file(
        str(service_keyfile()), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    config = temnik.load_config()
    book = gspread.authorize(credentials).open_by_key(config["spreadsheet_id"])
    sheet = book.get_worksheet_by_id(int(config["blog_tab_gid"]))
    if sheet is None or sheet.title != config["blog_tab_title"]:
        raise VerificationError("configured temnik tab was not found")
    return book, sheet


def job_path(value: str) -> Path:
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    if not path.is_relative_to(ROOT / "jobs"):
        raise VerificationError("refresh job must be under jobs/")
    return path


def is_yellow(style: dict) -> bool:
    rgb = style.get("backgroundColor", {}).get("color", {}).get("rgbColor", {})
    return all(abs(rgb.get(key, -1) - value) < .01 for key, value in converter.HIGHLIGHT.items())


def body_bounds(doc: dict) -> tuple[int, int]:
    named = doc.get("namedRanges", {}).get("BLOG_ARTICLE_BODY", {}).get("namedRanges", [])
    ranges = named[-1].get("ranges", []) if named else []
    if not ranges:
        raise VerificationError("Google Doc has no BLOG_ARTICLE_BODY named range")
    return ranges[0]["startIndex"], ranges[0]["endIndex"]


def doc_readback(doc: dict, images: list[dict]) -> tuple[str, str, str, int, list[bool]]:
    """One Docs snapshot yields article text, visible yellow text and table count."""
    start, end = body_bounds(doc)
    image_map = {item["object_id"]: item for item in images}
    yellow, all_text = [], []
    actual_mask: list[bool] = []
    seen_images: set[str] = set()
    tables = 0

    def paragraph_text(paragraph: dict) -> str:
        pieces = []
        fragments = paragraph.get("elements", [])
        in_range = [fragment for fragment in fragments
                    if fragment.get("endIndex", 0) > start and fragment.get("startIndex", 0) < end]
        for index, fragment in enumerate(in_range):
            run = fragment.get("textRun")
            if run is not None:
                value = run.get("content", "")
                # Docs gives each paragraph one structural terminator. It may
                # inherit yellow, but is never a visible changed character.
                visible = value[:-1] if index == len(in_range) - 1 and value.endswith("\n") else value
                pieces.append(value)
                all_text.append(visible)
                highlighted = is_yellow(run.get("textStyle", {}))
                actual_mask.extend([highlighted] * len(visible))
                if highlighted:
                    yellow.append(visible)
            elif "inlineObjectElement" in fragment:
                object_id = fragment["inlineObjectElement"]["inlineObjectId"]
                expected = image_map.get(object_id)
                actual = (doc.get("inlineObjects", {}).get(object_id, {})
                          .get("inlineObjectProperties", {}).get("embeddedObject", {})
                          .get("imageProperties", {}).get("sourceUri", ""))
                if not expected or actual != expected["url"]:
                    raise VerificationError(f"inline image {object_id} is absent or differs from receipt")
                seen_images.add(object_id)
                pieces.append(f'![{expected["alt"]}]({expected["url"]} "{expected["title"]}")')
        return "".join(pieces)

    parts = []
    for element in doc.get("body", {}).get("content", []):
        if element.get("endIndex", 0) <= start or element.get("startIndex", 0) >= end:
            continue
        if "paragraph" in element:
            parts.append(paragraph_text(element["paragraph"]))
        elif "table" in element:
            tables += 1
            for row in element["table"].get("tableRows", []):
                cells = []
                for cell in row.get("tableCells", []):
                    cells.append(" ".join(paragraph_text(piece["paragraph"]).strip()
                                          for piece in cell.get("content", []) if "paragraph" in piece).strip())
                # Explicit outer pipes preserve an empty first header cell for
                # the Markdown/native-text comparison.
                parts.append("| " + " | ".join(cells) + " |\n")
    if seen_images != set(image_map):
        raise VerificationError("document receipt names inline images absent from article body")
    return "".join(parts), "".join(yellow), "".join(all_text), tables, actual_mask


def intended_yellow(sent: str, baseline: str) -> tuple[str, str, list[bool], int, int]:
    blocks = converter.parse(sent)
    plans, _ = converter.word_highlight_plan(blocks, baseline)
    expected = []
    visible = []
    expected_mask: list[bool] = []
    def add(text: str, spans: list[tuple[int, int]]) -> None:
        visible.append(text)
        mask = [False] * len(text)
        for begin, finish in spans:
            expected.append(text[begin:finish])
            mask[begin:finish] = [True] * (finish - begin)
        expected_mask.extend(mask)
    for block, plan in zip(blocks, plans):
        if block[0] == "table":
            for row_index, row in enumerate(block[1]):
                row_plan = plan["cells"][row_index] if row_index < len(plan["cells"]) else []
                for cell_index, cell in enumerate(row):
                    spans = row_plan[cell_index] if cell_index < len(row_plan) else []
                    text = converter.inline(cell)[0]
                    add(text, spans)
        elif block[0] != "image":
            text = converter.plain(block)
            add(text, plan["spans"])
    return ("".join(expected), "".join(visible), expected_mask,
            sum(block[0] == "table" for block in blocks), len(blocks))


def original_row(job: Path) -> dict[str, str]:
    data = json.loads((job / "baseline/temnik-row.json").read_text(encoding="utf-8"))
    if isinstance(data.get("row"), dict):
        data = data["row"]
    elif isinstance(data.get("values"), dict):
        data = data["values"]
    elif isinstance(data.get("headers"), list) and isinstance(data.get("values"), list):
        data = dict(zip(data["headers"], data["values"]))
    if not isinstance(data, dict) or any(field not in data for field in LEGACY_REQUIRED):
        raise VerificationError("baseline/temnik-row.json lacks original lifecycle fields")
    return {str(key): str(value or "") for key, value in data.items()}


def verify_temnik(job: Path, doc_url: str, cycle_id: str, cluster_id: str) -> tuple[int, int]:
    snapshot = original_row(job)
    book, sheet = temnik_service()
    headers, rows = temnik.table(sheet)
    row = temnik.find_row(rows, cluster_id)
    if row.get("Refresh: cycle") != cycle_id or row.get("Refresh: status") != "in review" or \
            row.get("Refresh: Google Doc") != doc_url:
        raise VerificationError("temnik refresh summary differs from current cycle/review URL/status")
    for field, value in snapshot.items():
        if field in headers and not field.startswith("Refresh:") and row.get(field, "") != value:
            raise VerificationError(f"original temnik field changed: {field}")
    history = book.worksheet("Refresh history").get_all_values()
    if not history:
        raise VerificationError("refresh history is empty")
    matches = [dict(zip(history[0], cells)) for cells in history[1:] if cells and cells[0] == cycle_id]
    if len(matches) != 1 or matches[0].get("review_doc_url") != doc_url or \
            matches[0].get("status") != "in review" or matches[0].get("cluster_id") != cluster_id:
        raise VerificationError("refresh history needs exactly one matching current-cycle row")
    return int(row["_row"]), len(matches)


def verify(job: Path, round_number: int, *, skip_temnik: bool = False,
           docs=None) -> dict:
    prefix = f"{round_number:02d}"
    review_dir = job / "review"
    sent = (review_dir / f"{prefix}-sent.md").read_text(encoding="utf-8")
    baseline = (job / "baseline/article.md").read_text(encoding="utf-8")
    url = (review_dir / f"{prefix}-doc-url.txt").read_text(encoding="utf-8").strip()
    receipt = json.loads((review_dir / f"{prefix}-document.json").read_text(encoding="utf-8"))
    document_id = review.doc_id(url)
    if receipt.get("document_id") != document_id:
        raise VerificationError("review URL and document receipt identify different Docs")
    if docs is None:
        docs = docs_service()
    doc = docs.documents().get(documentId=document_id).execute()
    current, actual_yellow, all_text, tables, actual_mask = doc_readback(doc, receipt.get("images", []))
    delta = review.build_diff(sent, current)
    expected_yellow, expected_visible, expected_mask, expected_tables, block_count = intended_yellow(sent, baseline)
    checks = [(not delta, "native Doc text differs from sent Markdown"),
              (tables == expected_tables, "native table count differs from sent Markdown"),
              (all_text == expected_visible and actual_mask == expected_mask and actual_yellow == expected_yellow,
               "actual yellow visible characters differ from word plan")]
    manifest = json.loads((job / "refresh.json").read_text(encoding="utf-8"))
    job_yaml = (job / "job.yaml").read_text(encoding="utf-8")
    cycle_id = manifest["cycle_id"]
    cluster_id = temnik.yaml_scalar(job_yaml, "temnik_cluster_id")
    row_number, history_count = (None, None) if skip_temnik else verify_temnik(
        job, url, cycle_id, cluster_id)
    report = {"google_doc": url, "text_roundtrip": "PASS" if checks[0][0] else "FAIL",
              "native_tables": tables, "body_blocks": block_count,
              "highlight_readback": "PASS" if checks[2][0] else "FAIL",
              "highlighted_characters": len(actual_yellow),
              "total_native_text_characters": len(all_text),
              "highlighted_character_share": round(len(actual_yellow) / len(all_text), 4) if all_text else 0,
              "highlight_comparison": "Exact visible text; structural paragraph terminators excluded",
              "temnik_row": row_number, "temnik_cluster_id": cluster_id,
              "refresh_status": "skipped" if skip_temnik else "in review",
              "history_rows_for_cycle": history_count,
              "legacy_fields_preserved": None if skip_temnik else True}
    review_dir.mkdir(exist_ok=True)
    (review_dir / f"{prefix}-readback.txt").write_text(current, encoding="utf-8")
    (review_dir / f"{prefix}-readback.diff").write_text(delta, encoding="utf-8")
    (review_dir / f"{prefix}-highlight-readback.json").write_text(json.dumps(
        {"actual": actual_yellow, "expected": expected_yellow}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (review_dir / f"{prefix}-delivery-verification.json").write_text(json.dumps(
        report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for passed, error in checks:
        if not passed:
            raise VerificationError(error)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--skip-temnik", action="store_true", help="local Doc-only verification")
    args = parser.parse_args()
    if args.round < 1:
        parser.error("--round must be positive")
    try:
        print(json.dumps(verify(job_path(args.job), args.round, skip_temnik=args.skip_temnik),
                         ensure_ascii=False, indent=2))
    except (VerificationError, OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
