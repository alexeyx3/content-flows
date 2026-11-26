"""Read and maintain the Example Co blog topic queue in Google Sheets.

The sheet is the source of truth for topic order and article lifecycle state.  Reads are
always safe. Mutating commands are dry-run by default and require ``--apply``.

Examples:
  python3 scripts/temnik.py setup --apply
  python3 scripts/temnik.py next --limit 10
  python3 scripts/temnik.py skip --cluster-id b-0123 --reason "Country guide" --apply
  python3 scripts/temnik.py start --cluster-id b-0123 --job jobs/<job> --apply
  python3 scripts/temnik.py ready --job jobs/<job> --apply
  python3 scripts/temnik.py review --job jobs/<job> --google-doc <url> --apply
  python3 scripts/temnik.py publish --job jobs/<job> --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import gspread
from google.oauth2.service_account import Credentials

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "temnik.json"
ENV_PATH = ROOT / "config" / ".env"
KEYFILE_FALLBACK = ROOT / "config" / "google-service-account.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = {
    "cluster": "Cluster ID",
    "topic": "Topic",
    "title": "Our Title",
    "description": "Our Description",
    "h1": "Our H1",
    "article_type": "Article type",
    "language": "Language",
    "url": "Our URL",
    "action": "Action",
    "rank": "own_product_rank",
    "author": "Author",
    "status": "Status",
    "google_doc": "Google Doc",
    "started": "Start date",
    "ready": "Ready date",
    "publication_url": "Publication URL",
    "published": "Publication date",
    "reason": "Skip reason",
}
FINAL_ACTIONS = {"duplicate", "skip"}
DATE_FMT = "%Y-%m-%d"
# Page monitoring is separate from the original article lifecycle and refresh
# delivery state. Only the explicitly evaluated row receives these values.
GOOGLE_MONITOR_HEADERS = ["Google: indexing", "Google: reason", "Google: checked",
                          "Google: canonical", "Google: last crawl", "Refresh: selection"]


class TemnikError(RuntimeError):
    pass


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def connect():
    cfg = load_config()
    env = load_env()
    keyfile = ROOT / env.get("GOOGLE_SA_KEYFILE", "config/google-service-account.json")
    if not keyfile.exists():
        keyfile = KEYFILE_FALLBACK
    creds = Credentials.from_service_account_file(str(keyfile), scopes=SCOPES)
    book = gspread.authorize(creds).open_by_key(cfg["spreadsheet_id"])
    sheet = book.get_worksheet_by_id(int(cfg["blog_tab_gid"]))
    if sheet is None or sheet.title != cfg["blog_tab_title"]:
        raise TemnikError("blog temnik tab was not found or its title changed")
    return book, sheet


def table(sheet) -> tuple[list[str], list[dict[str, str]]]:
    values = sheet.get_all_values()
    if not values:
        raise TemnikError("temnik sheet is empty")
    headers = values[0]
    rows: list[dict[str, str]] = []
    for number, raw in enumerate(values[1:], start=2):
        row = {name: (raw[i] if i < len(raw) else "") for i, name in enumerate(headers) if name}
        row["_row"] = str(number)
        rows.append(row)
    return headers, rows


def require_headers(headers: Iterable[str], names: Iterable[str]) -> None:
    missing = [name for name in names if name not in headers]
    if missing:
        raise TemnikError("missing temnik headers: " + ", ".join(missing))


def column_map(headers: list[str]) -> dict[str, int]:
    return {name: i + 1 for i, name in enumerate(headers) if name}


def find_row(rows: list[dict[str, str]], cluster_id: str) -> dict[str, str]:
    found = [r for r in rows if r.get(HEADERS["cluster"], "").strip() == cluster_id]
    if len(found) != 1:
        raise TemnikError(f"cluster {cluster_id!r}: expected one row, found {len(found)}")
    return found[0]


def yaml_scalar(text: str, key: str, required: bool = True) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.*?)\s*(?:#.*)?$", text, re.M)
    if not match or not match.group(1).strip():
        if required:
            raise TemnikError(f"job.yaml has no {key}")
        return ""
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def job_data(path: str) -> tuple[Path, dict[str, str]]:
    job = Path(path)
    if not job.is_absolute():
        job = ROOT / job
    yaml_path = job / "job.yaml"
    if not yaml_path.exists():
        raise TemnikError(f"missing {yaml_path}")
    raw = yaml_path.read_text(encoding="utf-8")
    data = {
        "cluster_id": yaml_scalar(raw, "temnik_cluster_id"),
        "topic": yaml_scalar(raw, "topic"),
        "language": yaml_scalar(raw, "language"),
        "article_type": yaml_scalar(raw, "article_type"),
        "rank": yaml_scalar(raw, "own_product_rank"),
        "author": yaml_scalar(raw, "author"),
        "duplicate_preflight_version": yaml_scalar(raw, "duplicate_preflight_version", required=False),
    }
    return job, data


META_RE = re.compile(r"^-?\s*(title|slug|metaTitle|metaDescription|summary)\s*:\s*(.+)$")


def read_meta(job: Path) -> dict[str, str]:
    path = job / "out" / "meta.md"
    if not path.exists():
        raise TemnikError(f"missing {path}")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if match := META_RE.match(line.strip()):
            result[match.group(1)] = match.group(2).strip()
    for key in ("title", "slug", "metaTitle", "metaDescription"):
        if not result.get(key):
            raise TemnikError(f"meta.md has no {key}")
    return result


def plan_updates(row: dict[str, str], values: dict[str, str], *, allowed_statuses: set[str] | None = None,
                 allowed_overwrites: set[str] | None = None,
                 force: bool = False) -> list[tuple[str, str, str]]:
    """Return (header, old, new), rejecting unintended overwrites."""
    changes: list[tuple[str, str, str]] = []
    for header, new in values.items():
        old = row.get(header, "").strip()
        new = str(new).strip()
        if old == new:
            continue
        if header == HEADERS["status"] and allowed_statuses is not None:
            if old not in allowed_statuses and not force:
                raise TemnikError(f"status conflict: {old!r} cannot transition to {new!r}")
        elif old and header not in (allowed_overwrites or set()) and not force:
            raise TemnikError(f"cell conflict in {header!r}: sheet has {old!r}, new value is {new!r}")
        changes.append((header, old, new))
    return changes


def apply_plan(sheet, headers: list[str], row_number: int, changes: list[tuple[str, str, str]], apply: bool) -> None:
    if not changes:
        print(f"row {row_number}: already current")
        return
    print(f"row {row_number}: {'apply' if apply else 'dry-run'}")
    for header, old, new in changes:
        print(f"  {header}: {old!r} -> {new!r}")
    if not apply:
        return
    columns = column_map(headers)
    payload = [
        {"range": gspread.utils.rowcol_to_a1(row_number, columns[header]), "values": [[new]]}
        for header, _old, new in changes
    ]
    sheet.batch_update(payload, value_input_option="RAW")


def ensure_reason_column(book, sheet, *, apply: bool) -> None:
    cfg = load_config()
    values = sheet.row_values(1)
    reason = cfg["skip_reason_header"]
    if reason in values:
        print(f"header {reason!r}: already present")
        return
    target_col = len(values) + 1
    print(f"header {reason!r}: {'add' if apply else 'would add'} at column {target_col}")
    if not apply:
        return
    sheet.update_cell(1, target_col, reason)
    # Preserve the existing header appearance and extend the basic filter to the new column.
    requests: list[dict] = []
    if target_col > 1:
        requests.append({"copyPaste": {
            "source": {"sheetId": sheet.id, "startRowIndex": 0, "endRowIndex": 1,
                       "startColumnIndex": target_col - 2, "endColumnIndex": target_col - 1},
            "destination": {"sheetId": sheet.id, "startRowIndex": 0, "endRowIndex": 1,
                            "startColumnIndex": target_col - 1, "endColumnIndex": target_col},
            "pasteType": "PASTE_FORMAT",
        }})
    metadata = book.fetch_sheet_metadata()
    sheet_meta = next(s["properties"] | {"basicFilter": s.get("basicFilter")} for s in metadata["sheets"]
                      if s["properties"]["sheetId"] == sheet.id)
    basic = sheet_meta.get("basicFilter")
    if basic:
        extended = dict(basic)
        extended["range"] = dict(extended["range"])
        extended["range"]["endColumnIndex"] = target_col
        requests.append({"setBasicFilter": {"filter": extended}})
    if requests:
        book.batch_update({"requests": requests})


def get_state(cluster_id: str):
    book, sheet = connect()
    headers, rows = table(sheet)
    require_headers(headers, [HEADERS[k] for k in HEADERS if k != "reason"])
    row = find_row(rows, cluster_id)
    return book, sheet, headers, row


def cmd_setup(args) -> None:
    book, sheet = connect()
    ensure_reason_column(book, sheet, apply=args.apply)


def cmd_next(args) -> None:
    _book, sheet = connect()
    headers, rows = table(sheet)
    require_headers(headers, [HEADERS["cluster"], HEADERS["topic"], HEADERS["action"], HEADERS["status"]])
    shown = 0
    for row in rows:
        if row.get(HEADERS["status"], "").strip():
            continue
        if row.get(HEADERS["action"], "").strip().lower() in FINAL_ACTIONS:
            continue
        print(f"{row['_row']}\t{row.get(HEADERS['cluster'], '')}\t{row.get(HEADERS['topic'], '')}")
        shown += 1
        if shown >= args.limit:
            break
    if shown == 0:
        print("no unprocessed topic rows")


def cmd_preflight(args) -> None:
    import topic_overlap

    _book, sheet, headers, row = get_state(args.cluster_id)
    require_headers(headers, ["Top keyword"])
    topic = row.get(HEADERS["topic"], "").strip()
    keyword = row.get("Top keyword", "").strip()
    if not topic:
        raise TemnikError("temnik row has no topic")
    report = topic_overlap.check(args.cluster_id, topic, keyword, stage="seed")
    print(f"{topic_overlap.report_path(args.cluster_id)}: "
          f"{report['published_count']} published, {report['job_count']} local jobs; "
          f"{len(report['candidates'])} candidates; {report['embedding_status']}")
    for candidate in report["candidates"]:
        print(f"  {candidate['url']}\t{candidate['title']}"
              f"\texact={candidate['exact_phrase']} lexical={candidate['lexical']} "
              f"embedding={candidate['embedding']}")


def require_overlap_decision(cluster_id: str, topic: str, keyword: str) -> None:
    import topic_overlap

    path = topic_overlap.report_path(cluster_id)
    if not path.exists():
        raise TemnikError(f"missing topic overlap report; run `python3 scripts/temnik.py preflight --cluster-id {cluster_id}`")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (report.get("cluster_id") != cluster_id or report.get("stage") != "seed"
            or report.get("topic") != topic or report.get("keyword") != keyword):
        raise TemnikError("topic overlap report does not match this temnik row; rerun preflight")
    checked = datetime.fromisoformat(report["checked_at"])
    age = (datetime.now(timezone.utc) - checked).total_seconds()
    if age < 0 or age > 24 * 3600:
        raise TemnikError("topic overlap report is older than 24 hours; rerun preflight")
    if report.get("decision") != "distinct" or len(report.get("reason", "").strip()) < 40:
        raise TemnikError("topic overlap decision is missing; review candidates and run topic_overlap.py decide")
    if report.get("catalog_fingerprint") != topic_overlap.fingerprint(topic_overlap.catalog(cluster_id=cluster_id)):
        raise TemnikError("published articles or local jobs changed after overlap review; rerun preflight")


def cmd_skip(args) -> None:
    _book, sheet, headers, row = get_state(args.cluster_id)
    if HEADERS["reason"] not in headers:
        raise TemnikError("run `python3 scripts/temnik.py setup --apply` first")
    action = "duplicate" if args.duplicate else "skip"
    values = {HEADERS["action"]: action, HEADERS["reason"]: args.reason}
    if args.url:
        values[HEADERS["url"]] = args.url
    changes = plan_updates(row, values, force=args.force)
    apply_plan(sheet, headers, int(row["_row"]), changes, args.apply)


def cmd_start(args) -> None:
    job, data = job_data(args.job)
    if data["cluster_id"] != args.cluster_id:
        raise TemnikError(
            f"job temnik_cluster_id is {data['cluster_id']!r}, not {args.cluster_id!r}; "
            "link the job explicitly before updating the sheet"
        )
    _book, sheet, headers, row = get_state(args.cluster_id)
    if data["duplicate_preflight_version"] == "1" and args.apply:
        require_headers(headers, ["Top keyword"])
        require_overlap_decision(args.cluster_id, row.get(HEADERS["topic"], "").strip(),
                                 row.get("Top keyword", "").strip())
    values = {
        HEADERS["action"]: "new",
        HEADERS["rank"]: data["rank"],
        HEADERS["author"]: data["author"],
        HEADERS["status"]: "in progress",
        HEADERS["started"]: args.date or date.today().strftime(DATE_FMT),
    }
    changes = plan_updates(row, values, allowed_statuses={"", "in progress"}, force=args.force)
    apply_plan(sheet, headers, int(row["_row"]), changes, args.apply)
    print(f"job: {job.relative_to(ROOT)}")


def cmd_ready(args) -> None:
    job, data = job_data(args.job)
    meta = read_meta(job)
    _book, sheet, headers, row = get_state(data["cluster_id"])
    values = {
        HEADERS["title"]: meta["metaTitle"],
        HEADERS["description"]: meta["metaDescription"],
        HEADERS["h1"]: meta["title"],
        HEADERS["article_type"]: data["article_type"],
        HEADERS["language"]: data["language"].lower(),
        HEADERS["status"]: "written",
        HEADERS["ready"]: args.date or date.today().strftime(DATE_FMT),
    }
    changes = plan_updates(
        row, values,
        allowed_statuses={"", "in progress", "written", "in review"},
        allowed_overwrites={
            HEADERS["title"], HEADERS["description"], HEADERS["h1"],
            HEADERS["article_type"], HEADERS["language"], HEADERS["ready"],
        },
        force=args.force,
    )
    apply_plan(sheet, headers, int(row["_row"]), changes, args.apply)


def cmd_review(args) -> None:
    _job, data = job_data(args.job)
    _book, sheet, headers, row = get_state(data["cluster_id"])
    values = {HEADERS["google_doc"]: args.google_doc, HEADERS["status"]: "in review"}
    changes = plan_updates(
        row, values,
        allowed_statuses={"", "in progress", "written", "in review"},
        allowed_overwrites={HEADERS["google_doc"]},
        force=args.force,
    )
    apply_plan(sheet, headers, int(row["_row"]), changes, args.apply)


def live_record(slug: str) -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    import strapi_publish  # local module; keeps the token lookup in one place

    try:
        record = (strapi_publish.api(f"/articles/{slug}/findBySlug").get("data") or {})
    except urllib.error.HTTPError as exc:
        raise TemnikError(f"Strapi live lookup failed for {slug}: HTTP {exc.code}") from exc
    if not record.get("publishedAt"):
        raise TemnikError(f"Strapi record {slug!r} is not published")
    if not record.get("cover"):
        raise TemnikError(f"Strapi record {slug!r} has no cover")
    url = f"https://example.com/blog/{slug}/"
    request = urllib.request.Request(url, headers={"User-Agent": "topic-sheet-sync/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise TemnikError(f"public URL returned HTTP {response.status}: {url}")
    except urllib.error.HTTPError as exc:
        raise TemnikError(f"public URL returned HTTP {exc.code}: {url}") from exc
    return record


def cmd_publish(args) -> None:
    job, data = job_data(args.job)
    meta = read_meta(job)
    record = live_record(meta["slug"])
    published_at = datetime.fromisoformat(record["publishedAt"].replace("Z", "+00:00"))
    public_url = f"https://example.com/blog/{meta['slug']}/"
    _book, sheet, headers, row = get_state(data["cluster_id"])
    values = {
        HEADERS["url"]: public_url,
        HEADERS["publication_url"]: public_url,
        HEADERS["status"]: "published",
        HEADERS["published"]: published_at.date().strftime(DATE_FMT),
    }
    changes = plan_updates(
        row, values,
        allowed_statuses={"", "in progress", "written", "in review", "published"},
        force=args.force,
    )
    apply_plan(sheet, headers, int(row["_row"]), changes, args.apply)


def common_mutation(parser) -> None:
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    parser.add_argument("--force", action="store_true", help="overwrite conflicting nonblank cells")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser("setup", help="add the skip-reason column if missing")
    command.add_argument("--apply", action="store_true")
    command.set_defaults(func=cmd_setup)

    command = sub.add_parser("next", help="show unprocessed rows in sheet order")
    command.add_argument("--limit", type=int, default=10)
    command.set_defaults(func=cmd_next)

    command = sub.add_parser("preflight", help="search published pages and local jobs for a topic")
    command.add_argument("--cluster-id", required=True)
    command.set_defaults(func=cmd_preflight)

    command = sub.add_parser("skip", help="record an unsuitable or duplicate topic")
    command.add_argument("--cluster-id", required=True)
    command.add_argument("--reason", required=True)
    command.add_argument("--duplicate", action="store_true")
    command.add_argument("--url")
    common_mutation(command)
    command.set_defaults(func=cmd_skip)

    command = sub.add_parser("start", help="mark an approved topic as in progress")
    command.add_argument("--cluster-id", required=True)
    command.add_argument("--job", required=True)
    command.add_argument("--date")
    common_mutation(command)
    command.set_defaults(func=cmd_start)

    command = sub.add_parser("ready", help="copy final metadata and mark article written")
    command.add_argument("--job", required=True)
    command.add_argument("--date")
    common_mutation(command)
    command.set_defaults(func=cmd_ready)

    command = sub.add_parser("review", help="record the Google Doc and mark it for review")
    command.add_argument("--job", required=True)
    command.add_argument("--google-doc", required=True)
    common_mutation(command)
    command.set_defaults(func=cmd_review)

    command = sub.add_parser("publish", help="verify live state and record publication")
    command.add_argument("--job", required=True)
    common_mutation(command)
    command.set_defaults(func=cmd_publish)

    args = parser.parse_args()
    try:
        args.func(args)
    except TemnikError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
