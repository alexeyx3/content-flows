"""Build one complete-H2 assignment per turn for the persistent article writer.

The plan is read-only. --next is for recovery; ordinary drafting loads the plan
once and advances on the writer's completion event without polling files.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADING = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.M)


def writing_units(job: Path) -> list[dict]:
    payload = json.loads((job / "sections.json").read_text(encoding="utf-8"))
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list) or not sections:
        raise ValueError("sections.json must have a non-empty sections list")
    units = []
    seen = set()
    for number, section in enumerate(sections, 1):
        sid, title = section.get("id"), section.get("title")
        if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9-]+", sid) or sid in seen:
            raise ValueError("section IDs must be unique kebab-case values")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{sid}: missing H2 title")
        seen.add(sid)
        headings = [{"level": 2, "title": title}]
        previous_level = 2
        for child in section.get("subheadings", []):
            level, child_title = child.get("level"), child.get("title")
            if level not in (3, 4) or level > previous_level + 1 or not isinstance(child_title, str) or not child_title.strip():
                raise ValueError(f"{sid}: invalid H3/H4 hierarchy")
            headings.append({"level": level, "title": child_title})
            previous_level = level
        units.append({"number": number, "section_id": sid, "requested_unit": title,
                      "path": f"sections/section_{number}.md", "headings": headings})
    return units


def unit_errors(job: Path, unit: dict, text: str | None = None) -> list[str]:
    if text is None:
        path = job / unit["path"]
        if not path.exists():
            return [f"missing {unit['path']}"]
        text = path.read_text(encoding="utf-8")
    text = text.strip()
    if not text:
        return [f"empty {unit['path']}"]
    # Do not interpret headings inside fenced code examples as article structure.
    structural = re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.M | re.S)
    actual = [{"level": len(match[1]), "title": match[2]} for match in HEADING.finditer(structural)]
    if actual != unit["headings"]:
        return [f"{unit['path']}: incomplete or changed approved H2-H4 hierarchy"]
    if not re.sub(HEADING, "", structural).strip():
        return [f"{unit['path']}: headings without content"]
    matches = list(HEADING.finditer(structural))
    for index, match in enumerate(matches):
        following = matches[index + 1] if index + 1 < len(matches) else None
        if following and len(following[1]) > len(match[1]):
            continue  # A parent heading may lead straight into its child subsections.
        body = structural[match.end():following.start() if following else len(structural)]
        if not re.sub(r"<!--.*?-->", "", body, flags=re.S).strip():
            return [f"{unit['path']}: empty subsection {match[2]}"]
    return []


def dispatch_plan(job: Path) -> dict:
    return {"version": 1, "granularity": "complete_h2", "units": writing_units(job)}


def next_unit(job: Path) -> dict | None:
    for unit in writing_units(job):
        if unit_errors(job, unit):
            return unit
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--next", action="store_true", help="First incomplete H2, for recovery only")
    mode.add_argument("--check", action="store_true", help="Validate all saved H2 assignments")
    args = parser.parse_args()
    job = Path(args.job)
    job = (job if job.is_absolute() else ROOT / job).resolve()
    try:
        if args.check:
            problems = [problem for unit in writing_units(job) for problem in unit_errors(job, unit)]
            if problems:
                raise ValueError("\n".join(problems))
            print("PASS: all complete H2 assignments saved with approved H3/H4 hierarchy")
        else:
            print(json.dumps(next_unit(job) if args.next else dispatch_plan(job), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
