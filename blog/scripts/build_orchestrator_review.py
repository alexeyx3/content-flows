"""Build a compact final-review packet for the thin article coordinator."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from lint_article import BRAND, BRAND_RULES, SITE_HOST, any_of
from package_article import article_title, extract_metadata


ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
# Company policy comes from config/brand-rules.json (loaded by lint_article.py): banned
# topics, the labels the brand never carries and the industry term that is not its label.
# A denied label is permitted wording, but its context and the number of repeats are for
# the coordinator to judge, so every denial is listed.
_BRAND = re.escape(BRAND)
_TERM = re.escape(BRAND_RULES["industry_term_not_a_label"]["term"])
_LABELS = any_of([rule["pattern"] for rule in BRAND_RULES["self_forbidden"]["rules"]
                  if rule["kind"] == "label"]).pattern
RISK_PATTERNS = (
    ("banned topic", any_of([rule["pattern"] for rule in BRAND_RULES["banned_topics"]["rules"]])),
    (f"{BRAND} label denial",
     re.compile(_BRAND + r"[^\n.]{0,100}\bnot (?:an? |the )?(?:" + _LABELS + r")", re.I)),
    (f"{BRAND} industry-term label",
     re.compile(r"(?:" + _BRAND + r"[^\n|.]{0,100}" + _TERM + r"|" + _TERM + r"[^\n|.]{0,100}" + _BRAND + r")", re.I)),
    ("future-product date", re.compile(r"\bQ[1-4]\s*20\d\d\b|\b(?:planned|coming|launching)\s+(?:in|for)\s+20\d\d\b", re.I)),
    ("internal placeholder", re.compile(r"\b(?:TODO|FIXME|lorem)\b|\{\{.+?\}\}|\[\[.+?\]\]", re.I)),
)
INTERNAL_LINK = re.compile(r"https?://(?:www\.)?" + re.escape(SITE_HOST) + r"(?:/|$)")


def resolve_job(value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def numbered_blocks(text: str, needle: re.Pattern[str]) -> list[tuple[int, str]]:
    lines = text.splitlines()
    out: list[tuple[int, str]] = []
    start = 0
    while start < len(lines):
        while start < len(lines) and not lines[start].strip():
            start += 1
        if start >= len(lines):
            break
        end = start + 1
        while end < len(lines) and lines[end].strip():
            end += 1
        block = "\n".join(lines[start:end])
        if needle.search(block):
            out.append((start + 1, block))
        start = end + 1
    return out


def qa_summary(text: str) -> list[str]:
    lines = text.splitlines()
    selected: list[str] = []
    manual = False
    for line in lines:
        if line.startswith("- Gate ") or line.startswith("# QA report"):
            selected.append(line)
        if line.strip().lower() == "## needs_manual_confirmation":
            manual = True
            selected.extend(["", line])
            continue
        if manual:
            if line.startswith("## "):
                manual = False
            else:
                selected.append(line)
    return selected


def build(job: Path) -> Path:
    article_path = job / "edited.md"
    brief_path = job / "brief.md"
    qa_path = job / "qa_report.md"
    if not article_path.exists() or not brief_path.exists():
        raise SystemExit("edited.md and brief.md are required")
    article = article_path.read_text(encoding="utf-8")
    meta = extract_metadata(brief_path.read_text(encoding="utf-8"))
    title = article_title(article)

    lines = [
        "# Thin-coordinator final review",
        "",
        "## Metadata",
        "",
        f"- title ({len(title)}): {title}",
    ]
    for key in ("slug", "metaTitle", "metaDescription", "summary"):
        value = meta.get(key, "[missing]")
        lines.append(f"- {key} ({len(value)}): {value}")

    lines.extend(["", f"## {BRAND} excerpts", ""])
    excerpts = numbered_blocks(article, re.compile(_BRAND, re.I))
    if not excerpts:
        lines.append("- none")
    for line_no, block in excerpts:
        lines.extend([f"### Line {line_no}", "", block, ""])

    lines.extend(["## Risk-language hits", ""])
    any_risk = False
    for label, pattern in RISK_PATTERNS:
        for line_no, line in enumerate(article.splitlines(), 1):
            if pattern.search(line):
                any_risk = True
                lines.append(f"- {label}, line {line_no}: {line.strip()}")
    if not any_risk:
        lines.append("- none")

    lines.extend(["", "## Links", ""])
    links = MARKDOWN_LINK.findall(article)
    if not links:
        lines.append("- none")
    for label, url in links:
        kind = "internal" if INTERNAL_LINK.match(url) else "external"
        lines.append(f"- {kind}: [{label}]({url})")

    lines.extend(["", "## QA", ""])
    if qa_path.exists():
        lines.extend(qa_summary(qa_path.read_text(encoding="utf-8")) or ["- no gate lines found"])
    else:
        lines.append("- qa_report.md missing")

    editor_issues = job / "editor_issues.md"
    lines.extend(["", "## Editor issues", ""])
    lines.append(editor_issues.read_text(encoding="utf-8").strip() if editor_issues.exists() else "- none recorded")
    lines.append("")

    target = job / "out" / "orchestrator_review.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    print(build(resolve_job(args.job)))


if __name__ == "__main__":
    main()
