#!/usr/bin/env python3
"""Track glossary jobs in the topic sheet, with dry-run by default."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "temnik.json"
REQUIRED = ("Cluster ID", "Term", "Slug", "Language", "Action", "Status", "Start date")


def connect():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    env = {}
    for line in (ROOT / cfg["credentials_env_file"]).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    keyfile = ROOT / cfg["credentials_root"] / env["GOOGLE_SA_KEYFILE"]
    creds = Credentials.from_service_account_file(
        str(keyfile), scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    book = gspread.authorize(creds).open_by_key(cfg["spreadsheet_id"])
    sheet = book.get_worksheet_by_id(cfg["glossary_tab_gid"])
    if sheet is None or sheet.title != cfg["glossary_tab_title"]:
        raise ValueError("Glossary topic-sheet tab missing or renamed")
    return sheet


def start(job: Path, when: str, apply: bool) -> None:
    request = json.loads((job / "request.json").read_text(encoding="utf-8"))
    cluster = request["temnik_cluster_id"]
    sheet = connect()
    values = sheet.get_all_values()
    headers = values[0]
    missing = [name for name in REQUIRED if name not in headers]
    if missing:
        raise ValueError(f"Missing topic-sheet columns: {missing}")
    index = {name: headers.index(name) for name in REQUIRED}
    matches = [(i, row) for i, row in enumerate(values[1:], start=2)
               if len(row) > index["Cluster ID"] and row[index["Cluster ID"]] == cluster]
    if len(matches) != 1:
        raise ValueError(f"Expected one row for {cluster}, found {len(matches)}")
    row_number, raw = matches[0]
    current = {name: raw[column] if column < len(raw) else "" for name, column in index.items()}
    if current["Slug"] != request["slug"] or current["Language"] != request["locale"]:
        raise ValueError(f"Row {row_number} slug/locale conflicts with job {job.name}")
    planned = {"Action": "new", "Status": "in progress", "Start date": when}
    for name, target in planned.items():
        if current[name] not in ("", target):
            raise ValueError(f"Row {row_number} {name} conflict: {current[name]!r}")
    changes = [(name, value) for name, value in planned.items() if current[name] != value]
    print(f"{cluster} row {row_number} {request['term']}: " +
          (", ".join(f"{name}={value}" for name, value in changes) or "already current") +
          (" [apply]" if apply else " [dry-run]"))
    if not apply or not changes:
        return
    sheet.batch_update([
        {"range": gspread.utils.rowcol_to_a1(row_number, index[name] + 1), "values": [[value]]}
        for name, value in changes
    ], value_input_option="RAW")
    updated = sheet.row_values(row_number)
    if any((updated[index[name]] if index[name] < len(updated) else "") != value
           for name, value in planned.items()):
        raise RuntimeError(f"Row {row_number} did not match planned values after update")


def review(job: Path, when: str, apply: bool, round_number: int = 1) -> None:
    if round_number < 1:
        raise ValueError("review round must be positive")
    request = json.loads((job / "request.json").read_text(encoding="utf-8"))
    meta = json.loads((job / "meta.json").read_text(encoding="utf-8"))
    report = (job / "qa_report.md").read_text(encoding="utf-8")
    if not report.startswith("Verdict: PASS\n"):
        raise ValueError(f"{job.name}: QA PASS required")
    if not (job / "out/review.md").exists():
        raise ValueError(f"{job.name}: packaged review text missing")
    url = (job / "review" / f"{round_number:02d}-url.txt").read_text(encoding="utf-8").strip()
    previous_url = ((job / "review" / f"{round_number - 1:02d}-url.txt").read_text(encoding="utf-8").strip()
                    if round_number > 1 else None)
    if not re.fullmatch(r"https://docs\.google\.com/document/d/[A-Za-z0-9_-]+/edit(?:\?[^\s]+)?", url):
        raise ValueError(f"{job.name}: invalid Google Doc URL")
    if meta["slug"] != request["slug"] or meta["term"] != request["term"]:
        raise ValueError(f"{job.name}: metadata conflicts with request")

    sheet = connect()
    values = sheet.get_all_values()
    headers = values[0]
    needed = REQUIRED + ("Our Title", "Our Description", "Our H1", "Google Doc", "Ready date")
    missing = [name for name in needed if name not in headers]
    if missing:
        raise ValueError(f"Missing topic-sheet columns: {missing}")
    index = {name: headers.index(name) for name in needed}
    cluster = request["temnik_cluster_id"]
    matches = [(i, row) for i, row in enumerate(values[1:], start=2)
               if len(row) > index["Cluster ID"] and row[index["Cluster ID"]] == cluster]
    if len(matches) != 1:
        raise ValueError(f"Expected one row for {cluster}, found {len(matches)}")
    row_number, raw = matches[0]
    current = {name: raw[column] if column < len(raw) else "" for name, column in index.items()}
    if current["Slug"] != request["slug"] or current["Language"] != request["locale"]:
        raise ValueError(f"Row {row_number} slug/locale conflicts with job {job.name}")
    if current["Status"] not in ("in progress", "in review"):
        raise ValueError(f"Row {row_number} unexpected status: {current['Status']!r}")
    planned = {
        "Our Title": meta["metaTitle"],
        "Our Description": meta["metaDescription"],
        "Our H1": meta["term"],
        "Google Doc": url,
        "Ready date": when,
        "Status": "in review",
    }
    for name, target in planned.items():
        if name == "Status":
            continue
        permitted = ("", target, previous_url) if name == "Google Doc" and previous_url else ("", target)
        if current[name] not in permitted:
            raise ValueError(f"Row {row_number} {name} conflict: {current[name]!r}")
    changes = [(name, value) for name, value in planned.items() if current[name] != value]
    print(f"{cluster} row {row_number} {request['term']}: " +
          (", ".join(f"{name}={value}" for name, value in changes) or "already current") +
          (" [apply]" if apply else " [dry-run]"))
    if not apply or not changes:
        return
    sheet.batch_update([
        {"range": gspread.utils.rowcol_to_a1(row_number, index[name] + 1), "values": [[value]]}
        for name, value in changes
    ], value_input_option="RAW")
    updated = sheet.row_values(row_number)
    if any((updated[index[name]] if index[name] < len(updated) else "") != value
           for name, value in planned.items()):
        raise RuntimeError(f"Row {row_number} did not match planned values after update")


def publish(job: Path, when: str, apply: bool) -> None:
    request = json.loads((job / "request.json").read_text(encoding="utf-8"))
    state = json.loads((job / "out/strapi-record.json").read_text(encoding="utf-8"))
    if (state.get("status") != "published" or not state.get("coverMediaId")
            or state.get("slug") != request["slug"] or state.get("locale") != request["locale"]):
        raise ValueError(f"{job.name}: published Strapi record with cover required")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/strapi_glossary.py"), "verify", "--job", str(job)],
        check=True, capture_output=True, text=True,
    )
    url = f"https://example.com/glossary/{request['slug']}/"
    sheet = connect()
    values = sheet.get_all_values()
    headers = values[0]
    needed = REQUIRED + ("Publication URL", "Publication date")
    missing = [name for name in needed if name not in headers]
    if missing:
        raise ValueError(f"Missing topic-sheet columns: {missing}")
    index = {name: headers.index(name) for name in needed}
    cluster = request["temnik_cluster_id"]
    matches = [(i, row) for i, row in enumerate(values[1:], start=2)
               if len(row) > index["Cluster ID"] and row[index["Cluster ID"]] == cluster]
    if len(matches) != 1:
        raise ValueError(f"Expected one row for {cluster}, found {len(matches)}")
    row_number, raw = matches[0]
    current = {name: raw[column] if column < len(raw) else "" for name, column in index.items()}
    if current["Slug"] != request["slug"] or current["Language"] != request["locale"]:
        raise ValueError(f"Row {row_number} slug/locale conflicts with job {job.name}")
    if current["Status"] not in ("in review", "published"):
        raise ValueError(f"Row {row_number} unexpected status: {current['Status']!r}")
    planned = {"Status": "published", "Publication URL": url, "Publication date": when}
    for name in ("Publication URL", "Publication date"):
        if current[name] not in ("", planned[name]):
            raise ValueError(f"Row {row_number} {name} conflict: {current[name]!r}")
    changes = [(name, value) for name, value in planned.items() if current[name] != value]
    print(f"{cluster} row {row_number} {request['term']}: " +
          (", ".join(f"{name}={value}" for name, value in changes) or "already current") +
          (" [apply]" if apply else " [dry-run]"))
    if not apply or not changes:
        return
    sheet.batch_update([
        {"range": gspread.utils.rowcol_to_a1(row_number, index[name] + 1), "values": [[value]]}
        for name, value in changes
    ], value_input_option="RAW")
    updated = sheet.row_values(row_number)
    if any((updated[index[name]] if index[name] < len(updated) else "") != value
           for name, value in planned.items()):
        raise RuntimeError(f"Row {row_number} did not match planned values after update")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "review", "publish"])
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--round", type=int, default=1, help="Google Doc review round")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    date.fromisoformat(args.date)
    if args.command == "start":
        start(args.job.resolve(), args.date, args.apply)
    elif args.command == "review":
        review(args.job.resolve(), args.date, args.apply, args.round)
    else:
        publish(args.job.resolve(), args.date, args.apply)


if __name__ == "__main__":
    main()
