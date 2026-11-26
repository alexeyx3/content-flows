"""Validate the scholarly-study handoff for research-v3 article jobs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = re.compile(r"^research_v3_version:\s*1(?:\s|$)", re.M)
CHANNELS = {"catalogue", "direct_original", "repository"}
OUTCOMES = {"found", "none", "blocked"}
STATUSES = {"lead", "read_original", "rejected"}
TRANSFER_STATUSES = {"usable", "context_only", "not_transferable"}


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_url(value: object) -> bool:
    if not nonempty(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def enabled(job: Path) -> bool:
    config = job / "job.yaml"
    return config.exists() and bool(PROTOCOL.search(config.read_text(encoding="utf-8")))


def _read_json(path: Path, label: str, errors: list[str]) -> object | None:
    if not path.exists():
        errors.append(f"{label} is required")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return None


def _decision_ids(job: Path, errors: list[str]) -> set[str]:
    packet = _read_json(job / "research_map.json", "research_map.json", errors)
    if packet is None:
        return set()
    if not isinstance(packet, dict) or not isinstance(packet.get("decisions"), list):
        errors.append("research_map.json needs decisions list")
        return set()
    ids: set[str] = set()
    for i, decision in enumerate(packet["decisions"], 1):
        if not isinstance(decision, dict) or not re.fullmatch(r"Q-\d{2,}", str(decision.get("id", ""))):
            errors.append(f"research_map.json decision {i} needs Q-xx id")
            continue
        if decision["id"] in ids:
            errors.append(f"research_map.json repeats {decision['id']}")
        ids.add(decision["id"])
    if not ids:
        errors.append("research_map.json needs at least one decision")
    return ids


def _refs(value: object, ids: set[str], label: str, errors: list[str]) -> set[str]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} needs decision_refs")
        return set()
    refs: set[str] = set()
    for ref in value:
        if not isinstance(ref, str) or ref not in ids:
            errors.append(f"{label} has unknown decision_ref {ref!r}")
        else:
            refs.add(ref)
    return refs


def validate(job: Path) -> list[str]:
    if not enabled(job):
        return []
    errors: list[str] = []
    ids = _decision_ids(job, errors)
    packet = _read_json(job / "research.studies.json", "research.studies.json", errors)
    if packet is None:
        return errors
    if not isinstance(packet, dict):
        return errors + ["research.studies.json must be an object"]
    if packet.get("version") != 1:
        errors.append("research.studies.json version must be 1")

    search_log = packet.get("search_log")
    if not isinstance(search_log, list) or not search_log:
        errors.append("search_log needs actual searches")
        search_log = []
    channels: set[str] = set()
    covered: set[str] = set()
    for i, row in enumerate(search_log, 1):
        label = f"search_log {i}"
        if not isinstance(row, dict):
            errors.append(f"{label} must be an object")
            continue
        channel = row.get("channel")
        if channel not in CHANNELS:
            errors.append(f"{label} has invalid channel")
        else:
            channels.add(channel)
        if row.get("outcome") not in OUTCOMES:
            errors.append(f"{label} has invalid outcome")
        for key in ("query", "note"):
            if not nonempty(row.get(key)):
                errors.append(f"{label} needs {key}")
        covered.update(_refs(row.get("decision_refs"), ids, label, errors))
    if "catalogue" not in channels:
        errors.append("search_log needs an OpenAlex/Crossref catalogue attempt")
    if not channels.intersection({"direct_original", "repository"}):
        errors.append("search_log needs a direct original or repository search")
    for decision_id in sorted(ids - covered):
        errors.append(f"research decision {decision_id} has no scholarly search")

    candidates = packet.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates must be a list")
        candidates = []
    seen: set[str] = set()
    usable = False
    for i, candidate in enumerate(candidates, 1):
        label = f"candidate {i}"
        if not isinstance(candidate, dict):
            errors.append(f"{label} must be an object")
            continue
        cid = candidate.get("id")
        if not isinstance(cid, str) or not re.fullmatch(r"S-\d{2,}", cid):
            errors.append(f"{label} needs S-xx id")
        elif cid in seen:
            errors.append(f"duplicate candidate id {cid}")
        else:
            seen.add(cid)
        _refs(candidate.get("decision_refs"), ids, label, errors)
        status = candidate.get("status")
        if status not in STATUSES:
            errors.append(f"{label} has invalid status")
        if not valid_url(candidate.get("source_url")):
            errors.append(f"{label} needs source_url")
        if not nonempty(candidate.get("source_title")):
            errors.append(f"{label} needs source_title")
        if status in {"lead", "rejected"}:
            if not nonempty(candidate.get("reason")):
                errors.append(f"{label} {status} needs reason")
            if nonempty(candidate.get("finding")) or candidate.get("transfer_status") == "usable":
                errors.append(f"{label} unread study cannot report a verified finding")
            continue
        if status != "read_original":
            continue
        if not valid_url(candidate.get("original_url")):
            errors.append(f"{label} read_original needs original_url")
        if candidate.get("original_access") != "full_text":
            errors.append(f"{label} read_original needs original_access: full_text")
        for key in (
            "authors", "publisher", "access_note", "source_location",
            "study_design", "method", "population", "outcome", "finding",
            "decision_use", "transfer_risk",
        ):
            if not nonempty(candidate.get(key)):
                errors.append(f"{label} read_original needs {key}")
        year = candidate.get("publication_year")
        if isinstance(year, bool) or not isinstance(year, int) or year < 1600 or year > 2100:
            errors.append(f"{label} read_original needs plausible publication_year")
        transfer = candidate.get("transfer_status")
        if transfer not in TRANSFER_STATUSES:
            errors.append(f"{label} read_original needs transfer_status")
        elif transfer == "usable":
            usable = True
    if not usable and not nonempty(packet.get("no_transferable_study_reason")):
        errors.append("no usable read study needs no_transferable_study_reason")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    errors = validate(job)
    if errors:
        raise SystemExit("study research invalid:\n- " + "\n- ".join(errors))
    print(f"study research: OK ({job})")


if __name__ == "__main__":
    main()
