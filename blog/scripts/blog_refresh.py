"""Track an approved article refresh without changing its published topic-sheet record.

`register` records a cycle locally. `sync` writes only refresh columns and the
Refresh history tab in the configured topic sheet. Both commands are dry-run by
default; neither command publishes an article.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

if __package__:
    from scripts import temnik
else:
    import temnik

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "var" / "blog-monitor.sqlite3"
MANIFEST = "refresh.json"
HISTORY_TAB = "Refresh history"
SUMMARY = ["Refresh: cycle", "Refresh: version", "Refresh: status",
           "Refresh: Google Doc", "Refresh: date", "Refresh: note"]
PUBLICATION_SUMMARY = ["Refresh: published", "Refresh: next check"]
HISTORY = ["cycle_id", "cluster_id", "version", "job", "status", "review_doc_url",
           "note", "updated_at"]
STATUSES = ("in progress", "in review", "published")
TRANSITIONS = {"in progress": {"in progress", "in review"},
               "in review": {"in review", "published"},
               "published": {"published"}}


class RefreshError(RuntimeError):
    pass


def job_path(value: str) -> Path:
    path = Path(value)
    path = (path if path.is_absolute() else ROOT / path).resolve()
    if not path.is_relative_to(ROOT / "jobs"):
        raise RefreshError("refresh job must be inside jobs/")
    return path


def read_job(value: str) -> dict[str, str]:
    job = job_path(value)
    raw = (job / "job.yaml").read_text(encoding="utf-8")
    if temnik.yaml_scalar(raw, "article_refresh_version") != "1":
        raise RefreshError("article_refresh_version: 1 is required")
    if temnik.yaml_scalar(raw, "workflow_version") != "2":
        raise RefreshError("workflow_version: 2 is required")
    cluster_id = temnik.yaml_scalar(raw, "temnik_cluster_id")
    manifest = json.loads((job / MANIFEST).read_text(encoding="utf-8"))
    cycle_id = str(manifest.get("cycle_id", "")).strip()
    source_job = str(manifest.get("source_job", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{3,127}", cycle_id):
        raise RefreshError("refresh.json needs a stable cycle_id (4–128 ASCII letters, digits, dots, underscores or hyphens)")
    source = job_path(source_job)
    if source == job or not (source / "job.yaml").exists():
        raise RefreshError("source_job must name an existing, distinct article job")
    source_raw = (source / "job.yaml").read_text(encoding="utf-8")
    source_cluster = temnik.yaml_scalar(source_raw, "temnik_cluster_id", required=False)
    if source_cluster and source_cluster != cluster_id:
        raise RefreshError("source_job and refresh job must have the same temnik_cluster_id")
    url = str(manifest.get("review_doc_url", "")).strip()
    if url and not re.fullmatch(r"https://docs\.google\.com/document/d/[A-Za-z0-9_-]+(?:/[^\s]*)?", url):
        raise RefreshError("review_doc_url must be a Google Docs URL")
    note = str(manifest.get("note", "")).strip()
    if len(note) > 1000:
        raise RefreshError("refresh note exceeds 1000 characters")
    cycle_number = manifest.get("cycle_number")
    if cycle_number is not None and (not isinstance(cycle_number, int) or cycle_number < 1):
        raise RefreshError("cycle_number must be a positive integer")
    return {"job": str(job), "cluster_id": cluster_id, "cycle_id": cycle_id,
            "source_job": str(source), "source_url": str(manifest.get("source_url", "")).strip(),
            "cycle_number": cycle_number, "review_doc_url": url, "note": note,
            "next_review_date": str(manifest.get("next_review_date", "")).strip()}


def connect_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS refresh_cycles (
        cycle_id TEXT PRIMARY KEY, cluster_id TEXT NOT NULL, version INTEGER NOT NULL,
        job TEXT NOT NULL UNIQUE, source_job TEXT NOT NULL, status TEXT NOT NULL,
        review_doc_url TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
        registered_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(cluster_id, version))""")
    db.execute("""CREATE TABLE IF NOT EXISTS cycle_baseline (
        cycle_id TEXT PRIMARY KEY REFERENCES refresh_cycles(cycle_id),
        source TEXT NOT NULL, property TEXT NOT NULL, source_url TEXT NOT NULL,
        recent_start TEXT NOT NULL, recent_end TEXT NOT NULL,
        previous_start TEXT NOT NULL, previous_end TEXT NOT NULL,
        recent_totals_json TEXT NOT NULL, previous_totals_json TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL, recorded_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS page_daily (
        source TEXT NOT NULL, property TEXT NOT NULL, source_url TEXT NOT NULL,
        date TEXT NOT NULL, clicks REAL, impressions REAL, ctr REAL, position REAL,
        raw_json TEXT NOT NULL, PRIMARY KEY(source, property, source_url, date))""")
    db.execute("""CREATE TABLE IF NOT EXISTS query_weekly (
        source TEXT NOT NULL, property TEXT NOT NULL, source_url TEXT NOT NULL,
        start_date TEXT NOT NULL, end_date TEXT NOT NULL, query TEXT NOT NULL,
        clicks REAL, impressions REAL, ctr REAL, position REAL, raw_json TEXT NOT NULL,
        PRIMARY KEY(source, property, source_url, start_date, end_date, query))""")
    db.execute("""CREATE TABLE IF NOT EXISTS refresh_publications (
        cycle_id TEXT PRIMARY KEY REFERENCES refresh_cycles(cycle_id),
        cms_id INTEGER NOT NULL, source_url TEXT NOT NULL, updated_at TEXT NOT NULL,
        original_published_at TEXT NOT NULL, next_review_date TEXT NOT NULL,
        article_sha256 TEXT NOT NULL, receipt_json TEXT NOT NULL)""")
    return db


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_cycle(db: sqlite3.Connection, data: dict[str, str]) -> sqlite3.Row | None:
    row = db.execute("SELECT * FROM refresh_cycles WHERE cycle_id=? OR job=?",
                     (data["cycle_id"], data["job"])).fetchone()
    if row and any(row[k] != data[k] for k in ("cycle_id", "cluster_id", "job", "source_job")):
        raise RefreshError("cycle_id or job is already registered with a different identity")
    return row


def next_version(db: sqlite3.Connection, cluster_id: str) -> int:
    return db.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM refresh_cycles WHERE cluster_id=?",
                      (cluster_id,)).fetchone()[0]


def require_transition(old: str, new: str) -> None:
    if new not in TRANSITIONS.get(old, set()):
        raise RefreshError(f"invalid refresh transition: {old!r} → {new!r}")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def metric(row: dict, name: str):
    value = row.get(name)
    return float(value) if isinstance(value, (int, float)) else None


def ingest_analytics(db: sqlite3.Connection, data: dict[str, str]) -> None:
    path = Path(data["job"]) / "raw" / "analytics.json"
    if not path.exists():
        return
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    source = "google_search_console"
    prop = str(snapshot.get("property", "")).strip()
    url = str(snapshot.get("source_url", "")).strip()
    if not prop or url != data["source_url"]:
        raise RefreshError("analytics property/source_url is missing or differs from refresh.json")
    periods = snapshot.get("periods", {})
    recent, previous = periods.get("recent28", {}), periods.get("previous28", {})
    for period in (recent, previous):
        if not all(period.get(k) for k in ("startDate", "endDate", "totals")):
            raise RefreshError("analytics baseline needs exact 28-day windows and totals")
    packed = canonical(snapshot)
    digest = hashlib.sha256(packed.encode("utf-8")).hexdigest()
    old = db.execute("SELECT snapshot_sha256 FROM cycle_baseline WHERE cycle_id=?",
                     (data["cycle_id"],)).fetchone()
    if old and old[0] != digest:
        raise RefreshError("cycle baseline already exists with different analytics; historical snapshot is immutable")
    if not old:
        db.execute("""INSERT INTO cycle_baseline VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (data["cycle_id"], source, prop, url, recent["startDate"], recent["endDate"],
                    previous["startDate"], previous["endDate"], canonical(recent["totals"]),
                    canonical(previous["totals"]), packed, digest, timestamp()))
    for row in snapshot.get("daily_page", {}).get("rows", []):
        day = row.get("date") or ((row.get("keys") or [None])[0])
        if not day:
            raise RefreshError("daily_page row has no date")
        db.execute("""INSERT INTO page_daily VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source,property,source_url,date) DO UPDATE SET
            clicks=excluded.clicks, impressions=excluded.impressions, ctr=excluded.ctr,
            position=excluded.position, raw_json=excluded.raw_json""",
            (source, prop, url, day, metric(row, "clicks"), metric(row, "impressions"),
             metric(row, "ctr"), metric(row, "position"), canonical(row)))
    for week in snapshot.get("weekly_queries", []):
        if not week.get("complete") or not week.get("startDate") or not week.get("endDate"):
            raise RefreshError("weekly_queries needs complete exact intervals")
        for row in week.get("rows", []):
            query = row.get("query") or ((row.get("keys") or [None])[0])
            if not query:
                raise RefreshError("weekly query row has no query")
            db.execute("""INSERT INTO query_weekly VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source,property,source_url,start_date,end_date,query) DO UPDATE SET
                clicks=excluded.clicks, impressions=excluded.impressions, ctr=excluded.ctr,
                position=excluded.position, raw_json=excluded.raw_json""",
                (source, prop, url, week["startDate"], week["endDate"], query,
                 metric(row, "clicks"), metric(row, "impressions"), metric(row, "ctr"),
                 metric(row, "position"), canonical(row)))


def register(data: dict[str, str], status: str, *, apply: bool, db_path: Path = DB_PATH) -> dict:
    if status != "in progress":
        raise RefreshError("register begins a cycle with status 'in progress'")
    if not apply and not db_path.exists():
        print(f"dry-run register {data['cycle_id']} v1 (database absent)")
        return {"version": 1, "status": status}
    with connect_db(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        prior = validate_cycle(db, data)
        if prior:
            if apply:
                ingest_analytics(db, data)
            print(f"cycle already registered: {data['cycle_id']} v{prior['version']} ({prior['status']})")
            return dict(prior)
        version = next_version(db, data["cluster_id"])
        if data.get("cycle_number") is not None and data["cycle_number"] != version:
            raise RefreshError(f"cycle_number {data['cycle_number']} differs from ledger version {version}")
        print(f"{'register' if apply else 'dry-run register'} {data['cycle_id']} v{version}")
        if apply:
            now = timestamp()
            db.execute("""INSERT INTO refresh_cycles
                (cycle_id,cluster_id,version,job,source_job,status,review_doc_url,note,registered_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (data["cycle_id"], data["cluster_id"], version, data["job"],
                 data["source_job"], status, data["review_doc_url"], data["note"], now, now))
            ingest_analytics(db, data)
        return {"version": version, "status": status}


def ensure_columns(sheet, headers: list[str], *, apply: bool, names=None) -> list[str]:
    missing = [header for header in (SUMMARY if names is None else names) if header not in headers]
    if missing:
        print(f"{'add' if apply else 'would add'} refresh columns: {', '.join(missing)}")
    if apply:
        for header in missing:
            headers.append(header)
            sheet.update_cell(1, len(headers), header)
    return headers


def history_sheet(book, *, apply: bool):
    try:
        sheet = book.worksheet(HISTORY_TAB)
    except temnik.gspread.WorksheetNotFound:
        if not apply:
            print(f"would create tab {HISTORY_TAB}")
            return None
        sheet = book.add_worksheet(title=HISTORY_TAB, rows=1000, cols=len(HISTORY))
        sheet.append_row(HISTORY, value_input_option="RAW")
    existing = sheet.row_values(1)
    if existing != HISTORY:
        raise RefreshError(f"{HISTORY_TAB} headers differ from expected schema")
    return sheet


def verify_publication(data: dict[str, str]) -> dict:
    """Require the exact reviewed CMS and live body before marking a cycle published."""
    import requests
    from lxml import html as html_parser
    if __package__:
        from scripts import strapi_publish as cms
    else:
        import strapi_publish as cms
    job = Path(data["job"])
    path = job / "out/refresh-publication.json"
    if not path.exists():
        raise RefreshError("publication requires verified CMS evidence; missing refresh-publication.json")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    article_hash = hashlib.sha256((job / "edited.md").read_bytes()).hexdigest()
    content = cms.cms_image_html((job / "out/article.html").read_text(encoding="utf-8"))
    if (receipt.get("url") != data["source_url"] or receipt.get("article_sha256") != article_hash
            or receipt.get("content_sha256") != hashlib.sha256(content.encode()).hexdigest()):
        raise RefreshError("publication evidence differs from current article or source URL")
    current = cms.api(f"/articles/{receipt['slug']}/findBySlug").get("data") or {}
    current_id = current.get("id")
    current = current.get("attributes", current)
    if (current_id != receipt["id"] or current.get("content") != content
            or current.get("publishedAt") != receipt["publishedAt"]
            or current.get("updatedAt") != receipt["updatedAt"]
            or current.get("indexable") is not True or not current.get("cover")):
        raise RefreshError("current CMS record differs from publication evidence")
    response = requests.get(data["source_url"], timeout=30)
    response.raise_for_status()
    # The public app emits UTF-8 HTML; Requests otherwise guesses Latin-1 when
    # Content-Type omits charset, corrupting typographic quotes/dashes in readback.
    response.encoding = "utf-8"
    page = html_parser.fromstring(response.text)
    canonical_urls = page.xpath('//link[@rel="canonical"]/@href')
    bodies = page.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," prose ")]')
    expected = html_parser.fragment_fromstring(content, create_parent="div")
    visible = lambda node: " ".join(node.text_content().split())
    if (response.url != data["source_url"] or canonical_urls != [data["source_url"]]
            or len(bodies) != 1 or visible(bodies[0]) != visible(expected)):
        raise RefreshError("public canonical/body does not yet match the published update")
    try:
        next_date = date.fromisoformat(data.get("next_review_date", ""))
        updated_date = date.fromisoformat(receipt["updatedAt"][:10])
    except (ValueError, KeyError) as exc:
        raise RefreshError("next_review_date and actual update date are required") from exc
    if not 15 <= (next_date - updated_date).days <= 30:
        raise RefreshError("next_review_date must be 15–30 days after the actual update")
    return {**receipt, "next_review_date": next_date.isoformat()}


def sync(data: dict[str, str], status: str, *, apply: bool, db_path: Path = DB_PATH) -> None:
    if status not in STATUSES:
        raise RefreshError(f"unknown refresh status {status!r}")
    publication = verify_publication(data) if status == "published" else None
    if not db_path.exists():
        raise RefreshError("cycle is not registered; run register --apply first")
    with connect_db(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = validate_cycle(db, data)
        if row is None:
            raise RefreshError("cycle is not registered; run register --apply first")
        if data.get("cycle_number") is not None and data["cycle_number"] != row["version"]:
            raise RefreshError("cycle_number differs from registered version")
        require_transition(row["status"], status)
        if publication:
            prior = db.execute("SELECT receipt_json FROM refresh_publications WHERE cycle_id=?", (data["cycle_id"],)).fetchone()
            if prior and prior[0] != canonical(publication):
                raise RefreshError("published cycle evidence is immutable")
        if status == "in review" and not data["review_doc_url"]:
            raise RefreshError("review_doc_url is required for 'in review'")
        if row["status"] == "published" and (row["review_doc_url"] != data["review_doc_url"] or row["note"] != data["note"]):
            raise RefreshError("published refresh history is immutable")
        book, sheet = temnik.connect()
        headers, rows = temnik.table(sheet)
        temnik.require_headers(headers, [temnik.HEADERS["cluster"], temnik.HEADERS["status"]])
        original = temnik.find_row(rows, data["cluster_id"])
        # Some legacy published rows have an empty lifecycle cell. Require the
        # original public URL, and never write to any legacy lifecycle field.
        if not original.get(temnik.HEADERS["url"], "").strip():
            raise RefreshError("source temnik row has no original public URL")
        if data.get("source_url") and original[temnik.HEADERS["url"]].strip() != data["source_url"]:
            raise RefreshError("source_url differs from original temnik URL")
        existing_cycle = original.get(SUMMARY[0], "").strip()
        existing_version = original.get(SUMMARY[1], "").strip()
        if existing_cycle and existing_cycle != data["cycle_id"]:
            if not existing_version.isdigit() or int(existing_version) >= row["version"]:
                raise RefreshError("temnik refresh summary has a newer or unknown cycle")
        headers = ensure_columns(sheet, headers, apply=apply)
        if publication:
            headers = ensure_columns(sheet, headers, apply=apply, names=PUBLICATION_SUMMARY)
        now = timestamp()
        values = dict(zip(SUMMARY, [data["cycle_id"], str(row["version"]), status,
                                    data["review_doc_url"], now[:10], data["note"]]))
        if publication:
            values.update(dict(zip(PUBLICATION_SUMMARY, [publication["updatedAt"], publication["next_review_date"]])))
        changes = temnik.plan_updates(original, values, allowed_overwrites=set(SUMMARY + PUBLICATION_SUMMARY))
        hist = history_sheet(book, apply=apply)
        historical = None
        if hist is not None:
            all_values = hist.get_all_values()
            matches = [(idx, cells) for idx, cells in enumerate(all_values[1:], start=2)
                       if cells and cells[0] == data["cycle_id"]]
            if len(matches) > 1:
                raise RefreshError("duplicate cycle_id in refresh history")
            historical = matches[0] if matches else None
            if historical and (len(historical[1]) < 4 or historical[1][1:4] !=
                               [data["cluster_id"], str(row["version"]), data["job"]]):
                raise RefreshError("cycle_id history identity conflict")
        history_values = [data["cycle_id"], data["cluster_id"], str(row["version"]),
                          data["job"], status, data["review_doc_url"], data["note"], now]
        if not apply:
            print(f"dry-run sync {data['cycle_id']} v{row['version']}: {status}; "
                  f"{len(changes)} summary cells; {'update' if historical else 'append'} history")
            return
        # A previous cycle's history row remains untouched. The active cycle is
        # updated in place, keyed by cycle_id, so retries do not append duplicates.
        temnik.apply_plan(sheet, headers, int(original["_row"]), changes, True)
        if historical:
            old = historical[1] + [""] * (len(HISTORY) - len(historical[1]))
            if old[:7] != history_values[:7]:
                hist.update(f"A{historical[0]}:H{historical[0]}", [history_values], value_input_option="RAW")
        else:
            hist.append_row(history_values, value_input_option="RAW")
        if row["status"] != status or row["review_doc_url"] != data["review_doc_url"] or row["note"] != data["note"]:
            db.execute("""UPDATE refresh_cycles SET status=?, review_doc_url=?, note=?, updated_at=?
                          WHERE cycle_id=?""", (status, data["review_doc_url"], data["note"], now, data["cycle_id"]))
        if publication:
            db.execute("INSERT OR IGNORE INTO refresh_publications VALUES (?,?,?,?,?,?,?,?)",
                       (data["cycle_id"], publication["id"], data["source_url"], publication["updatedAt"],
                        publication["publishedAt"], publication["next_review_date"],
                        publication["article_sha256"], canonical(publication)))
        print(f"synced refresh cycle {data['cycle_id']} v{row['version']}: {status}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("register", "sync"):
        command = sub.add_parser(name)
        command.add_argument("--job", required=True)
        command.add_argument("--status", required=True, choices=STATUSES)
        command.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        data = read_job(args.job)
        if args.command == "register":
            register(data, args.status, apply=args.apply)
        else:
            sync(data, args.status, apply=args.apply)
    except (RefreshError, temnik.TemnikError, FileNotFoundError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
