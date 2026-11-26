"""Validate the original-document research handoff for new blog jobs."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse
if __package__:
    from .validate_research_map import decision_ids, enabled as research_v3_enabled, validate as validate_research_map
else:
    from validate_research_map import decision_ids, enabled as research_v3_enabled, validate as validate_research_map

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = re.compile(r"^primary_data_research_version:\s*1(?:\s|$)", re.M)
STATUSES = {"lead", "read_original", "rejected"}
CHART_STATUSES = {"chartable", "context_only", "unsuitable"}
VISUAL_TYPES = {"bar", "line", "none"}
OUTCOMES = {"found", "none", "blocked"}
FILE_TYPES = {
    "pdf", "ppt", "pptx", "doc", "docx", "xls", "xlsx",
    "csv", "json_dataset", "google_doc", "google_sheet",
    "html_dataset", "html_report",
}
FILE_FAMILIES = {
    "pdf": "pdf",
    "ppt": "slides", "pptx": "slides",
    "doc": "documents", "docx": "documents",
    "xls": "spreadsheets", "xlsx": "spreadsheets",
}
FILE_QUERY = re.compile(r"\bfiletype\s*:\s*(pdf|pptx?|docx?|xlsx?|xls)\b", re.I)


def enabled(job: Path) -> bool:
    config = job / "job.yaml"
    return config.exists() and bool(PROTOCOL.search(config.read_text(encoding="utf-8")))


def coverage_required(job: Path) -> bool:
    config = job / "job.yaml"
    return config.exists() and bool(re.search(r"^research_coverage_version:\s*1\b", config.read_text(encoding="utf-8"), re.M))


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_url(value: object) -> bool:
    if not nonempty(value):
        return False
    parsed = urlparse(str(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate(job: Path) -> list[str]:
    if not enabled(job):
        return []
    path = job / "research.data.json"
    if not path.exists():
        return ["research.data.json is required for primary_data_research_version: 1"]
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"research.data.json is invalid JSON: {exc}"]
    if not isinstance(packet, dict):
        return ["research.data.json must be an object"]

    errors: list[str] = []
    if packet.get("version") != 1:
        errors.append("research.data.json version must be 1")
    decisions = packet.get("reader_decisions")
    if not isinstance(decisions, list) or not decisions or not all(map(nonempty, decisions)):
        errors.append("reader_decisions needs at least one real reader decision")
    log = packet.get("search_log")
    if not isinstance(log, list) or not log:
        errors.append("search_log needs at least one search")
        log = []
    for i, row in enumerate(log, 1):
        if not isinstance(row, dict):
            errors.append(f"search_log {i} must be an object")
            continue
        for key in ("question", "channel", "query", "note"):
            if not nonempty(row.get(key)):
                errors.append(f"search_log {i} needs {key}")
        if row.get("outcome") not in OUTCOMES:
            errors.append(f"search_log {i} has invalid outcome")
    if coverage_required(job) and isinstance(decisions, list):
        searched: set[str] = set()
        for row in log:
            if not isinstance(row, dict):
                continue
            refs = row.get("decision_refs")
            if isinstance(refs, list):
                if not refs or not all(isinstance(ref, str) and ref.strip() in decisions for ref in refs):
                    errors.append("search_log decision_refs must name actual reader_decisions")
                searched.update(ref for ref in refs if isinstance(ref, str))
            else:
                searched.add(row.get("question", "").strip())
        for decision in decisions:
            if isinstance(decision, str) and decision.strip() not in searched:
                errors.append(f"reader decision has no covering search_log entry: {decision}")

    if research_v3_enabled(job):
        map_errors = validate_research_map(job)
        if map_errors:
            errors.extend(map_errors)
        elif not isinstance(decisions, list) or set(decisions) != decision_ids(job):
            errors.append("reader_decisions must equal the shared research_map.json Q-IDs")
        families: set[str] = set()
        institutional = False
        archived: dict[str, set[str]] = {}
        archive_paths = sorted((job / "raw").glob("document-search-*.csv"))
        if not archive_paths:
            errors.append("v3 document search needs raw/document-search-*.csv from the SERP collector")
        for path in archive_paths:
            try:
                with path.open(encoding="utf-8", newline="") as handle:
                    for result in csv.DictReader(handle):
                        query_value = result.get("query", "").strip()
                        if query_value:
                            archived.setdefault(query_value, set())
                            if result.get("result_type") == "organic" and valid_url(result.get("url")):
                                archived[query_value].add(result["url"])
            except (OSError, UnicodeError, csv.Error) as exc:
                errors.append(f"cannot read document search archive {path.name}: {exc}")
        for i, row in enumerate(log, 1):
            if not isinstance(row, dict):
                continue
            query = row.get("query", "")
            if not isinstance(query, str):
                continue
            file_matches = list(FILE_QUERY.finditer(query))
            families.update(FILE_FAMILIES[m.group(1).lower()] for m in file_matches)
            institutional |= bool(re.search(r"\b(?:site|inurl)\s*:", query, re.I))
            if file_matches and query not in archived:
                errors.append(f"search_log {i} filetype query is missing from raw document SERP archive")
            if row.get("outcome") == "found":
                urls = row.get("result_urls")
                if not isinstance(urls, list) or not urls or not all(map(valid_url, urls)):
                    errors.append(f"search_log {i} found result needs original result_urls")
                elif file_matches and query in archived and not set(urls) <= archived[query]:
                    errors.append(f"search_log {i} found result_urls are absent from archived SERP results")
        for family in ("pdf", "slides", "documents", "spreadsheets"):
            if family not in families:
                errors.append(f"v3 document search needs filetype query for {family}")
        if not institutional:
            errors.append("v3 document search needs an institution-restricted site:/inurl: query")

    candidates = packet.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates must be a list")
        candidates = []
    if not candidates and not nonempty(packet.get("no_data_reason")):
        errors.append("empty candidates need no_data_reason")
    seen: set[str] = set()
    for i, item in enumerate(candidates, 1):
        if not isinstance(item, dict):
            errors.append(f"candidate {i} must be an object")
            continue
        prefix = f"candidate {i}"
        cid = item.get("id")
        if not isinstance(cid, str) or not re.fullmatch(r"D-\d{2,}", cid):
            errors.append(f"{prefix} needs D-xx id")
        elif cid in seen:
            errors.append(f"duplicate candidate id {cid}")
        else:
            seen.add(cid)
        status = item.get("status")
        chart_status = item.get("chart_status")
        if status not in STATUSES:
            errors.append(f"{prefix} has invalid status")
        if chart_status not in CHART_STATUSES:
            errors.append(f"{prefix} has invalid chart_status")
        for key in ("question", "decision_use"):
            if not nonempty(item.get(key)):
                errors.append(f"{prefix} needs {key}")
        if not valid_url(item.get("source_url")):
            errors.append(f"{prefix} needs original source_url")
        if status in {"lead", "rejected"}:
            if not nonempty(item.get("reason")):
                errors.append(f"{prefix} {status} needs reason")
            if chart_status == "chartable":
                errors.append(f"{prefix} cannot be chartable before original is read")
            continue
        if status != "read_original":
            continue
        for key in (
            "proposed_section", "source_title", "publisher", "publication_date",
            "source_location", "unit", "period", "geography", "population",
            "denominator", "method", "transfer_risk",
        ):
            if not nonempty(item.get(key)):
                errors.append(f"{prefix} read_original needs {key}")
        if item.get("file_type") not in FILE_TYPES:
            errors.append(f"{prefix} has invalid file_type")
        if item.get("visual_type") not in VISUAL_TYPES:
            errors.append(f"{prefix} has invalid visual_type")
        if chart_status == "unsuitable" and not nonempty(item.get("reason")):
            errors.append(f"{prefix} unsuitable data need reason")
        points = item.get("points")
        if not isinstance(points, list):
            errors.append(f"{prefix} points must be a list")
            points = []
        if chart_status == "chartable":
            if item.get("visual_type") == "none":
                errors.append(f"{prefix} chartable needs visual_type")
            if len(points) < 2:
                errors.append(f"{prefix} chartable needs at least two comparable points")
            labels: set[str] = set()
            for pi, point in enumerate(points, 1):
                if not isinstance(point, dict):
                    errors.append(f"{prefix} point {pi} must be an object")
                    continue
                if not nonempty(point.get("label")) or not nonempty(point.get("source_location")):
                    errors.append(f"{prefix} point {pi} needs label and source_location")
                label = point.get("label")
                if isinstance(label, str):
                    if label in labels:
                        errors.append(f"{prefix} has duplicate point label {label}")
                    labels.add(label)
                value = point.get("value")
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    errors.append(f"{prefix} point {pi} needs a finite numeric value")
        elif chart_status == "context_only":
            if not nonempty(item.get("exact_value")):
                errors.append(f"{prefix} context_only needs exact_value")
            if item.get("visual_type") != "none":
                errors.append(f"{prefix} context_only visual_type must be none")
    if research_v3_enabled(job) and not any(
        isinstance(item, dict) and item.get("status") == "read_original"
        for item in candidates
    ):
        errors.append("v3 document research needs at least one read_original finding before brief")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    errors = validate(job)
    if errors:
        raise SystemExit("primary data research invalid:\n- " + "\n- ".join(errors))
    print(f"primary data research: OK ({job})")


if __name__ == "__main__":
    main()
