"""Validate the shared decision map for parallel research in new blog jobs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = re.compile(r"^research_v3_version:\s*1(?:\s|$)", re.M)


def enabled(job: Path) -> bool:
    path = job / "job.yaml"
    return path.exists() and bool(PROTOCOL.search(path.read_text(encoding="utf-8")))


def validate(job: Path) -> list[str]:
    if not enabled(job):
        return []
    path = job / "research_map.json"
    if not path.exists():
        return ["research_map.json is required for research_v3_version: 1"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"research_map.json is invalid: {exc}"]
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return ["research_map.json version must be 1"]
    rows = payload.get("decisions")
    if not isinstance(rows, list) or not rows:
        return ["research_map.json needs at least one reader decision"]
    errors: list[str] = []
    ids: set[str] = set()
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append(f"decision {i} must be an object")
            continue
        qid = row.get("id")
        if not isinstance(qid, str) or not re.fullmatch(r"Q-\d{2,}", qid):
            errors.append(f"decision {i} needs Q-xx id")
        elif qid in ids:
            errors.append(f"duplicate decision id: {qid}")
        else:
            ids.add(qid)
        for field in ("question", "reader_action", "population", "outcome"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"decision {i} needs {field}")
    return errors


def decision_ids(job: Path) -> set[str]:
    """Return validated IDs; callers must report validation errors separately."""
    if validate(job):
        return set()
    return {row["id"] for row in json.loads((job / "research_map.json").read_text(encoding="utf-8"))["decisions"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    errors = validate(job)
    if errors:
        raise SystemExit("research map invalid:\n- " + "\n- ".join(errors))
    print(f"research map: OK ({job})")


if __name__ == "__main__":
    main()
