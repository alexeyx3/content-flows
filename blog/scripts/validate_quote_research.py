"""Validate the independent outside-quote research packet for new blog jobs."""
from __future__ import annotations

import argparse
from datetime import date
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = re.compile(r"^research_v3_version:\s*1(?:\s|$)", re.M)
CHANNELS = {"x", "linkedin", "web_search", "original_source"}
OUTCOMES = {"found", "none", "blocked"}
STATUSES = {"verified_original", "lead", "rejected"}
SOURCE_KINDS = {
    "x_post", "linkedin_post", "interview", "signed_article", "association",
    "conference_transcript", "webinar_transcript", "podcast_transcript",
    "original_report", "other_original",
}
SEARCH_HOSTS = {"google.com", "www.google.com", "bing.com", "www.bing.com"}


def enabled(job: Path) -> bool:
    config = job / "job.yaml"
    return config.exists() and bool(PROTOCOL.search(config.read_text(encoding="utf-8")))


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_url(value: object) -> bool:
    if not nonempty(value):
        return False
    parsed = urlparse(str(value))
    return parsed.scheme == "https" and bool(parsed.netloc)


def valid_date(value: object) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _read_json(path: Path, label: str, errors: list[str]) -> dict:
    if not path.exists():
        errors.append(f"{label} is required for research_v3_version: 1")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def _decision_refs(value: object, ids: set[str], label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} needs decision_refs")
        return
    if any(not isinstance(ref, str) or ref not in ids for ref in value):
        errors.append(f"{label} decision_refs must name research_map.json Q-IDs")
    if len(value) != len(set(ref for ref in value if isinstance(ref, str))):
        errors.append(f"{label} has duplicate decision_refs")


def validate(job: Path) -> list[str]:
    if not enabled(job):
        return []
    errors: list[str] = []
    decision_map = _read_json(job / "research_map.json", "research_map.json", errors)
    decisions = decision_map.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        errors.append("research_map.json needs decisions")
        decisions = []
    ids = {
        item.get("id") for item in decisions
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if any(not re.fullmatch(r"Q-\d{2,}", ref) for ref in ids):
        errors.append("research_map.json decision IDs must use Q-xx")

    packet = _read_json(job / "research.quotes.json", "research.quotes.json", errors)
    if not packet:
        return errors
    if packet.get("version") != 1:
        errors.append("research.quotes.json version must be 1")
    log = packet.get("search_log")
    if not isinstance(log, list) or not log:
        errors.append("search_log needs search entries")
        log = []
    seen_channels: set[str] = set()
    for i, row in enumerate(log, 1):
        label = f"search_log {i}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be an object")
            continue
        channel = row.get("channel")
        if channel not in CHANNELS:
            errors.append(f"{label} has invalid channel")
        else:
            seen_channels.add(channel)
        _decision_refs(row.get("decision_refs"), ids, label, errors)
        for field in ("query", "note"):
            if not nonempty(row.get(field)):
                errors.append(f"{label} needs {field}")
        if row.get("outcome") not in OUTCOMES:
            errors.append(f"{label} has invalid outcome")
        if channel == "original_source" and row.get("source_kind") not in SOURCE_KINDS - {"x_post", "linkedin_post"}:
            errors.append(f"{label} needs an original-first source_kind")
        if row.get("outcome") == "blocked" and not nonempty(row.get("access_problem")):
            errors.append(f"{label} blocked search needs access_problem")
    for channel in sorted(CHANNELS - seen_channels):
        errors.append(f"search_log needs a {channel} search")

    if not nonempty(packet.get("coverage_note")):
        errors.append("coverage_note must explain quote-worthy decisions and omissions")
    candidates = packet.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates must be a list")
        candidates = []
    seen_ids: set[str] = set()
    verified_count = 0
    for i, candidate in enumerate(candidates, 1):
        label = f"candidate {i}"
        if not isinstance(candidate, dict):
            errors.append(f"{label} must be an object")
            continue
        cid = candidate.get("id")
        if not isinstance(cid, str) or not re.fullmatch(r"XQ-\d{2,}", cid):
            errors.append(f"{label} needs XQ-xx id")
        elif cid in seen_ids:
            errors.append(f"duplicate candidate id {cid}")
        else:
            seen_ids.add(cid)
        _decision_refs(candidate.get("decision_refs"), ids, label, errors)
        status = candidate.get("status")
        if status not in STATUSES:
            errors.append(f"{label} has invalid status")
        if candidate.get("source_kind") not in SOURCE_KINDS:
            errors.append(f"{label} has invalid source_kind")
        if not valid_url(candidate.get("source_url")):
            errors.append(f"{label} needs HTTPS source_url")
        if status in {"lead", "rejected"}:
            if not nonempty(candidate.get("reason")):
                errors.append(f"{label} {status} needs reason")
            if nonempty(candidate.get("quote")):
                errors.append(f"{label} cannot carry exact quote before verification")
            continue
        if status != "verified_original":
            continue
        verified_count += 1
        for field in (
            "source_title", "source_location", "author_name", "author_role",
            "quote", "context", "decision_value", "source_scope",
        ):
            if not nonempty(candidate.get(field)):
                errors.append(f"{label} verified_original needs {field}")
        if candidate.get("source_access") != "full_original":
            errors.append(f"{label} verified_original needs full_original access")
        if not valid_date(candidate.get("publication_date")):
            errors.append(f"{label} verified_original needs YYYY-MM-DD publication_date")
        quote = candidate.get("quote")
        if nonempty(quote) and len(str(quote).split()) > 25:
            errors.append(f"{label} quote exceeds 25 words")
        url = candidate.get("source_url")
        if valid_url(url):
            parsed = urlparse(str(url))
            if parsed.netloc.lower() in SEARCH_HOSTS and parsed.path.startswith("/search"):
                errors.append(f"{label} source_url is a search result, not an original")
            host = (parsed.hostname or "").lower()
            if candidate.get("source_kind") == "x_post" and not (
                host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
                and re.search(r"/status/\d+", parsed.path)
            ):
                errors.append(f"{label} x_post needs a direct post URL")
            if candidate.get("source_kind") == "linkedin_post" and not (
                host in {"linkedin.com", "www.linkedin.com"}
                and re.search(r"/(posts|feed/update)/", parsed.path)
            ):
                errors.append(f"{label} linkedin_post needs a direct post URL")
    if verified_count == 0 and not nonempty(packet.get("no_verified_quote_reason")):
        errors.append("no_verified_quote_reason required when no original quote was verified")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    errors = validate(job)
    if errors:
        raise SystemExit("quote research invalid:\n- " + "\n- ".join(errors))
    print(f"quote research: OK ({job})")


if __name__ == "__main__":
    main()
