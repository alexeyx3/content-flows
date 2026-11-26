"""Assemble out/draft.md from the section files of the writer agent.

Needed only by the agent track (skill blog-article-agents): the script track writes draft.md
entirely by itself. The order comes from sections.json, not from file names: the agent writes in batches,
and sorting by name cannot be relied on, because section_10 would land between section_1 and section_2.

Usage:
  python3 scripts/assemble_sections.py --job jobs/<job-dir>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def article_title(job: Path) -> str | None:
    """The article title.

    Taken from the `title` field in sections.json: that is the writing contract, and it is the only one
    that names the ARTICLE heading. The first `# ` in brief.md does not work for this: in
    briefs written by an agent it holds "Strategy brief — X alternatives", and
    assembled drafts went to editing with that title.
    """
    data = json.loads((job / "sections.json").read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("title"):
        return str(data["title"]).strip()
    brief = (job / "brief.md").read_text(encoding="utf-8")
    for m in re.finditer(r"^#\s+(.+)$", brief, re.M):
        line = m.group(1).strip()
        if not re.match(r"(?i)^(strategy )?brief\b|^бриф\b", line):
            return line
    m = re.search(r'^\W*(?:metaTitle|title)\W*:\W*"?([^"\n]+)', brief, re.M | re.I)
    return m.group(1).strip() if m else None


def sections_order(job: Path) -> list[str]:
    data = json.loads((job / "sections.json").read_text(encoding="utf-8"))
    items = data["sections"] if isinstance(data, dict) else data
    return [s["id"] for s in items]


def collect(job: Path) -> tuple[str, list[str]]:
    """(article body, what is missing). A file is looked up both by number and by section id."""
    order = sections_order(job)
    parts, missing = [], []
    for n, sid in enumerate(order, 1):
        for name in (f"section_{n}.md", f"section_{n:02d}.md",
                     f"section_{sid}.md", f"{sid}.md"):
            path = job / "sections" / name
            if path.exists():
                parts.append(path.read_text(encoding="utf-8").strip())
                break
        else:
            missing.append(f"{n}. {sid}")
    return "\n\n".join(parts), missing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    args = ap.parse_args()

    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    body, missing = collect(job)
    if missing:
        sys.exit("sections missing:\n- " + "\n- ".join(missing))

    title = article_title(job)
    text = (f"# {title}\n\n{body}\n" if title and not body.lstrip().startswith("# ")
            else body + "\n")

    out = job / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "draft.md").write_text(text, encoding="utf-8")
    print(f"{out / 'draft.md'} — {len(text.split())} words, sections {len(sections_order(job))}")


if __name__ == "__main__":
    main()
