"""Internal package for the article: the source map and what needs confirmation.

Goes to the publisher together with the article and is NOT published. Built from the run artefacts;
nothing is rewritten by hand, otherwise the source map drifts away from the evidence.

Usage:
  python3 scripts/build_internal_package.py --job jobs/<job-dir>
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from article_materials import is_v2, read_json

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r"https?://[^\s|]+")
# Evidence agents use legacy IDs (PKG-01A), descriptive slugs
# (vendor-northwind), and short numbered IDs (A01, C01, A05b).
# The numbered form still excludes the Markdown header cell and ordinary prose.
CLAIM_ID = re.compile(r"^(?:[A-Za-z]{1,8}\d{1,4}[A-Za-z]?|[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+)+)$")


def source_rows(evidence: str) -> list[tuple[str, str, str]]:
    """(id, claim, address) from the evidence table: rows of the form "| ID | claim | … | url |"."""
    rows = []
    for line in evidence.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not CLAIM_ID.fullmatch(cells[0]):
            continue
        url = next((m.group(0) for c in cells for m in [URL.search(c)] if m), "—")
        rows.append((cells[0], cells[1], url))
    return rows


def section(text: str, title_pattern: str) -> str:
    """A markdown section by heading, up to the next heading of the same level."""
    m = re.search(rf"^(#{{1,4}})\s*{title_pattern}.*$", text, re.M | re.I)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    return (m.group(0) + rest[: nxt.start()] if nxt else m.group(0) + rest).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    args = ap.parse_args()

    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    evidence = (job / "evidence.md").read_text(encoding="utf-8")
    rows = source_rows(evidence)

    parts = [f"# Internal package: {job.name}", "",
             "Not for publication. Source map, open questions and SERP summary.", "",
             f"## Source map ({len(rows)} rows)", "",
             "| ID | Claim | Source |", "|---|---|---|"]
    for rid, claim, url in rows:
        parts.append(f"| {rid} | {claim[:180]} | {url} |")

    for title in (
        r"Needs manual confirmation(?:\s*/\s*use restrictions)?",
        "needs_manual_confirmation",
        "Открытые вопросы",
    ):
        block = section(evidence, title)
        if block:
            parts += ["", "## Needs confirmation by the publisher", "", block]
            break

    serp = job / "serp.serp_synthesis.md"
    if serp.exists():
        parts += ["", "## SERP summary", "", serp.read_text(encoding="utf-8").strip()]

    if is_v2(job):
        parts += ["", "## Visuals and sources", ""]
        for visual in read_json(job / "visuals.json")["visuals"]:
            parts += [f'- {visual["id"]}: {visual["title"]} (QA: {visual.get("asset", {}).get("remote_path", "not uploaded")})']
            parts += [f'  - {source["label"]}: {source["url"]}' for source in visual["sources"]]
        parts += ["", "## Expert comments", ""]
        for quote in read_json(job / "expert_quotes.json")["quotes"]:
            parts += [f'- {quote["id"]}: {quote["status"]}, {quote["attribution"]}', quote["text"]]
    out = job / "out" / "internal_package.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"{out} — {len(rows)} sources, {len(out.read_text(encoding='utf-8'))} characters")


if __name__ == "__main__":
    main()
