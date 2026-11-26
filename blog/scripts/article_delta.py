"""Create a scoped article diff for editor/QA rework.

The first QA pass remains full. Before a targeted editor correction, snapshot
``edited.md``; after the correction, generate a unified diff and the names of
the Markdown sections touched. The same QA thread can then inspect only this
delta plus the previously failed gates.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
WORD = re.compile(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9'’-]*")


def resolve_job(value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def rework_dir(job: Path) -> Path:
    return job / "metrics" / "rework"


def before_path(job: Path, round_number: int) -> Path:
    return rework_dir(job) / f"round-{round_number}.before.md"


def report_path(job: Path, round_number: int) -> Path:
    return rework_dir(job) / f"round-{round_number}.diff.md"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def headings(lines: list[str]) -> list[tuple[int, str]]:
    return [
        (index, match.group(2).strip())
        for index, line in enumerate(lines)
        if (match := HEADING.match(line))
    ]


def section_for_line(lines: list[str], index: int) -> str:
    current = "(preamble)"
    for line_no, title in headings(lines):
        if line_no > index:
            break
        current = title
    return current


def changed_sections(before: str, after: str) -> list[str]:
    old_lines = before.splitlines()
    new_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    changed: list[str] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if new_lines:
            indexes = range(j1, max(j1 + 1, j2))
            for index in indexes:
                title = section_for_line(new_lines, min(index, len(new_lines) - 1))
                if title not in changed:
                    changed.append(title)
        elif "(article removed)" not in changed:
            changed.append("(article removed)")
    return changed


def heading_signature(text: str) -> list[tuple[int, str]]:
    return [
        (len(match.group(1)), match.group(2).strip())
        for line in text.splitlines()
        if (match := HEADING.match(line))
    ]


def word_count(text: str) -> int:
    return len(WORD.findall(text))


def h2_sections(text: str) -> list[tuple[str, str]]:
    """Return article preamble/H2 sections in reader order."""
    lines = text.splitlines()
    starts = [
        (index, match.group(1).strip())
        for index, line in enumerate(lines)
        if (match := re.match(r"^##\s+(.+?)\s*$", line))
    ]
    sections: list[tuple[str, str]] = []
    first = starts[0][0] if starts else len(lines)
    preamble = "\n".join(lines[:first]).strip()
    if preamble:
        sections.append(("(title and preamble)", preamble))
    for position, (start, title) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        sections.append((title, "\n".join(lines[start:end]).strip()))
    return sections


def editor_report(job: Path) -> Path:
    before_path = job / "out" / "draft.md"
    after_path = job / "edited.md"
    if not before_path.exists():
        raise SystemExit(f"draft not found: {before_path}")
    if not after_path.exists():
        raise SystemExit(f"edited.md not found: {after_path}")

    before = before_path.read_text(encoding="utf-8")
    after = after_path.read_text(encoding="utf-8")
    before_sections = h2_sections(before)
    after_sections = h2_sections(after)
    before_map = dict(before_sections)
    after_map = dict(after_sections)
    order = [name for name, _ in before_sections]
    order.extend(name for name, _ in after_sections if name not in before_map)

    before_total = word_count(before)
    after_total = word_count(after)
    total_delta = after_total - before_total
    total_percent = (total_delta / before_total * 100) if before_total else 0.0

    before_headings = Counter(heading_signature(before))
    after_headings = Counter(heading_signature(after))
    removed_headings = list((before_headings - after_headings).elements())
    added_headings = list((after_headings - before_headings).elements())

    lines = [
        "# Editor delta",
        "",
        "> Deterministic coverage signal only. Word reduction is not an acceptance gate.",
        "",
        f"- Draft words: {before_total}",
        f"- Edited words: {after_total}",
        f"- Delta: {total_delta:+d} ({total_percent:+.1f}%)",
        "",
        "## Section word deltas",
        "",
        "| Section | Draft | Edited | Delta | Change |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in order:
        old_count = word_count(before_map.get(name, ""))
        new_count = word_count(after_map.get(name, ""))
        delta = new_count - old_count
        percent = (delta / old_count * 100) if old_count else 0.0
        safe_name = name.replace("|", "\\|")
        lines.append(
            f"| {safe_name} | {old_count} | {new_count} | {delta:+d} | {percent:+.1f}% |"
        )

    lines.extend(["", "## Heading changes", ""])
    if not removed_headings and not added_headings:
        lines.append("- None.")
    for level, title in removed_headings:
        lines.append(f"- Removed H{level}: {title}")
    for level, title in added_headings:
        lines.append(f"- Added H{level}: {title}")
    lines.extend(
        [
            "",
            "## Review instruction",
            "",
            "Inspect substantial removals and every removed heading against brief.md and sections.json. "
            "Accept deletion of repetition, unsupported claims, and process narration; block when approved "
            "coverage, evidence-backed reasoning, or a required structural element was lost.",
            "",
        ]
    )

    target = rework_dir(job).parent / "editor-delta.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def snapshot(job: Path, round_number: int) -> Path:
    source = job / "edited.md"
    if not source.exists():
        raise SystemExit(f"edited.md not found: {source}")
    target = before_path(job, round_number)
    if target.exists():
        raise SystemExit(f"rework snapshot already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    metadata = {
        "round": round_number,
        "source": str(source),
        "sha256": digest(source.read_text(encoding="utf-8")),
    }
    (target.with_suffix(".json")).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


def build_report(job: Path, round_number: int) -> tuple[Path, list[str], bool]:
    old_path = before_path(job, round_number)
    new_path = job / "edited.md"
    if not old_path.exists():
        raise SystemExit(f"rework snapshot not found: {old_path}")
    if not new_path.exists():
        raise SystemExit(f"edited.md not found: {new_path}")
    before = old_path.read_text(encoding="utf-8")
    after = new_path.read_text(encoding="utf-8")
    sections = changed_sections(before, after)
    structural = heading_signature(before) != heading_signature(after)
    diff = "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=old_path.name,
        tofile="edited.md",
        n=3,
    ))
    target = report_path(job, round_number)
    target.parent.mkdir(parents=True, exist_ok=True)
    section_lines = [f"- {name}" for name in sections] or ["- none"]
    body = [
        f"# Article delta — round {round_number}",
        "",
        f"- Before SHA-256: `{digest(before)}`",
        f"- After SHA-256: `{digest(after)}`",
        f"- Structural change: **{'yes' if structural else 'no'}**",
        "",
        "## Changed sections",
        "",
        *section_lines,
        "",
        "## Unified diff",
        "",
        "````diff",
        diff.rstrip() or "(no textual changes)",
        "````",
        "",
    ]
    target.write_text("\n".join(body), encoding="utf-8")
    return target, sections, structural


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "report"):
        command = sub.add_parser(name)
        command.add_argument("--job", required=True)
        command.add_argument("--round", type=int, required=True)
    editor_command = sub.add_parser("editor-report")
    editor_command.add_argument("--job", required=True)
    args = parser.parse_args()
    job = resolve_job(args.job)
    if args.command == "editor-report":
        print(editor_report(job))
        return
    if args.round < 1:
        raise SystemExit("--round must be positive")
    if args.command == "snapshot":
        print(snapshot(job, args.round))
        return
    path, sections, structural = build_report(job, args.round)
    print(path)
    print("changed_sections=" + json.dumps(sections, ensure_ascii=False))
    print(f"structural_change={str(structural).lower()}")


if __name__ == "__main__":
    main()
