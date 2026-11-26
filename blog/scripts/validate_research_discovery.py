"""Check that new article jobs record the bounded GIST discovery work."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from validate_research_map import enabled as research_v3_enabled

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = re.compile(r"^research_discovery_version:\s*1(?:\s|$)", re.M)
HEADINGS = (
    "Decision map",
    "Search log",
    "Insight cards",
    "External quote candidates",
)
CHANNELS = {"primary", "scholarly", "social"}
OUTCOMES = {"found", "none", "blocked", "not_applicable"}


def enabled(job: Path) -> bool:
    config = job / "job.yaml"
    return config.exists() and bool(PROTOCOL.search(config.read_text(encoding="utf-8")))


def validate(job: Path) -> list[str]:
    if not enabled(job):
        return []
    path = job / "research.discovery.md"
    if not path.exists():
        return ["research.discovery.md is required for research_discovery_version: 1"]
    value = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    current = ""
    for line in value.splitlines():
        match = re.fullmatch(r"##\s+(.+?)\s*", line)
        if match:
            current = match.group(1)
            sections.setdefault(current, "")
        elif current:
            sections[current] += line + "\n"
    errors = []
    for heading in HEADINGS:
        if not sections.get(heading, "").strip():
            errors.append(f"research.discovery.md needs nonempty '## {heading}'")

    rows = []
    for line in sections.get("Search log", "").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if cells and cells[0].lower() in CHANNELS:
            rows.append(cells)
    found = {row[0].lower() for row in rows}
    required_channels = {"primary"} if research_v3_enabled(job) else CHANNELS
    for channel in sorted(required_channels - found):
        errors.append(f"Search log needs a {channel} row")
    for row in rows:
        if len(row) < 4:
            errors.append(f"Search log {row[0]} row needs channel, query, outcome, note")
            continue
        channel, query, outcome, note = row[:4]
        if outcome.lower() not in OUTCOMES:
            errors.append(f"Search log {channel} has invalid outcome: {outcome}")
        if not query and outcome.lower() != "not_applicable":
            errors.append(f"Search log {channel} needs a query")
        if not note:
            errors.append(f"Search log {channel} needs a result or exclusion note")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    errors = validate(job)
    if errors:
        raise SystemExit("research discovery invalid:\n- " + "\n- ".join(errors))
    print(f"research discovery: OK ({job})")


if __name__ == "__main__":
    main()
