"""Check that evidence rows marked for publication are linked in the edited article."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_VALUES = {"required", "yes"}
CLAIM_ROW = re.compile(r"^\s*\|\s*\*{0,2}(E-\d+)\*{0,2}\s*\|", re.M)


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def markdown_table_rows(text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    rows: list[dict[str, str]] = []
    for index, line in enumerate(lines[:-1]):
        if "|" not in line:
            continue
        headers = table_cells(line)
        if "source_url" not in headers or "article_link" not in headers:
            continue
        separator = table_cells(lines[index + 1])
        if len(separator) != len(headers) or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator):
            continue
        for candidate in lines[index + 2 :]:
            if not candidate.lstrip().startswith("|"):
                break
            cells = table_cells(candidate)
            if len(cells) != len(headers):
                continue
            rows.append(dict(zip(headers, cells, strict=True)))
        break
    return rows


def evidence_table_errors(text: str) -> list[str]:
    """Fail early if an intervening blank line or malformed row hides claim sources."""
    ids = CLAIM_ROW.findall(text)
    parsed = [row.get("claim_id", "").strip("*") for row in markdown_table_rows(text)]
    missing = sorted(set(ids) - set(parsed))
    errors = []
    if missing:
        errors.append("Evidence rows are outside the parsed claim table or malformed: " + ", ".join(missing))
    if len(ids) != len(set(ids)):
        errors.append("Duplicate claim IDs in evidence.md")
    return errors


def evidence_reference_errors(evidence_text: str, article_text: str) -> list[str]:
    ids = {cid for cid in CLAIM_ROW.findall(evidence_text) if re.fullmatch(r"E-\d{2,}", cid)}
    # Unpadded E-1/E-2 are ordinary visa categories. Match the actual internal IDs.
    leaked = sorted(ids.intersection(re.findall(r"(?<![\w/-])E-\d{2,}(?![\w/-])", article_text)))
    return ["Internal evidence IDs in public copy: " + ", ".join(leaked)] if leaked else []


def markdown_links(text: str) -> list[str]:
    return re.findall(r"(?<!!)\[[^\]]+\]\((https?://[^)\s]+)(?:\s+[^)]*)?\)", text)


def check(evidence_text: str, article_text: str) -> tuple[list[dict[str, str]], list[str]]:
    rows = markdown_table_rows(evidence_text)
    required = [
        row for row in rows if row.get("article_link", "").strip().lower() in REQUIRED_VALUES
    ]
    links = markdown_links(article_text)
    missing = [row for row in required if row.get("source_url", "").strip() not in links]
    return missing, links


def source_policy_errors(job: Path, evidence_text: str, article_text: str) -> list[str]:
    config = job / "job.yaml"
    if not config.exists() or not re.search(r"^source_policy_version:\s*1\b", config.read_text(encoding="utf-8"), re.M):
        return []
    match = re.search(r"^##\s+(?:Sources|Источники)\s*$", article_text, re.I | re.M)
    if not match:
        return ["final H2 Sources/Источники section is missing"]
    tail = article_text[match.end():]
    next_heading = re.search(r"^#{1,2}\s+", tail, re.M)
    if next_heading:
        return ["Sources/Источники must be the final section"]
    source_links = markdown_links(tail)
    errors: list[str] = []
    if not source_links:
        errors.append("Sources/Источники has no clickable source links")
    if len(source_links) != len(set(source_links)):
        errors.append("a source URL is linked more than once in Sources/Источники")
    required = {row.get("source_url", "").strip() for row in markdown_table_rows(evidence_text)
                if row.get("article_link", "").strip().lower() in REQUIRED_VALUES}
    missing = required - set(source_links)
    if missing:
        errors.append("required evidence URLs missing from Sources/Источники: " + ", ".join(sorted(missing)))
    for name in ("visuals.json", "expert_quotes.json"):
        path = job / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"{name} cannot be read for source policy: {exc}")
            continue
        if name == "visuals.json":
            urls = {s.get("url") for v in data.get("visuals", []) for s in v.get("sources", []) if s.get("public", True)}
        else:
            urls = {q.get("source") for q in data.get("quotes", []) if q.get("speaker_kind") == "external" and q.get("status") != "rejected"}
        absent = {url for url in urls if url and url not in source_links}
        if absent:
            errors.append(f"{name} source URLs missing from Sources/Источники: " + ", ".join(sorted(absent)))
    body = article_text[:match.start()]
    for url in markdown_links(body):
        host = (urlparse(url).hostname or "").lower()
        if host != "example.com" and not host.endswith(".example.com"):
            errors.append(f"external source link outside Sources/Источники: {url}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()

    job = Path(args.job)
    evidence_path = job / "evidence.md"
    article_path = job / "edited.md"
    if not evidence_path.exists() or not article_path.exists():
        print("evidence.md and edited.md are required", file=sys.stderr)
        return 2

    evidence_text = evidence_path.read_text(encoding="utf-8")
    article_text = article_path.read_text(encoding="utf-8")
    rows = markdown_table_rows(evidence_text)
    if not rows:
        print("No evidence table with article_link column found", file=sys.stderr)
        return 2

    required = [row for row in rows if row.get("article_link", "").lower() in REQUIRED_VALUES]
    missing, article_links = check(evidence_text, article_text)
    policy_errors = (evidence_table_errors(evidence_text) + evidence_reference_errors(evidence_text, article_text)
                     + source_policy_errors(job, evidence_text, article_text))
    report_path = job / "metrics" / "research-links.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Research-link check",
        "",
        f"- Evidence rows marked required: {len(required)}",
        f"- Markdown links in article: {len(article_links)}",
        f"- Missing required research links: {len(missing)}",
        f"- Source-policy errors: {len(policy_errors)}",
        "",
    ]
    if missing:
        lines.extend(["## Missing", ""])
        for row in missing:
            lines.append(
                f"- `{row.get('claim_id', 'unknown')}` ({row.get('section', 'unknown')}): "
                f"{row.get('source_url', '[missing URL]')}"
            )
    elif not policy_errors:
        lines.append("PASS: every required research source is linked with its evidence URL.")
    if policy_errors:
        lines.extend(["", "## Source policy", "", *[f"- {error}" for error in policy_errors]])
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(report_path)
    return 1 if missing or policy_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
