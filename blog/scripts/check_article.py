"""All the article checking mechanics in one command.

Earlier the orchestrator ran these one by one: assemble sections, check paragraphs, linter,
overlaps with neighbours, HTML, sanitizer. A measurement showed why that is expensive: the article text
passed through the orchestrator's Bash sixteen times per article with a context of almost half a million
tokens. Now there is a single pass, and only a short report comes out.

Usage:
  python3 scripts/check_article.py --job jobs/<job>            # assemble and check
  python3 scripts/check_article.py --job jobs/<job> --no-assemble
  python3 scripts/check_article.py --job jobs/<job> --siblings jobs/a jobs/b
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def job_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / value


def subject_of(job: Path) -> str:
    y = job / "job.yaml"
    if y.exists():
        m = re.search(r'^topic:\s*"?([^"\n]+)', y.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return ""


def language_of(job: Path) -> str:
    y = job / "job.yaml"
    if y.exists():
        m = re.search(r"^language:\s*(\S+)", y.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip().lower()
    return "en"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--no-assemble", action="store_true",
                    help="do not assemble draft.md from sections/: the article is already in edited.md")
    ap.add_argument("--siblings", nargs="*", default=[],
                    help="folders of neighbouring runs for checking verbatim overlaps")
    args = ap.parse_args()

    job = job_path(args.job)
    problems: list[str] = []
    lines: list[str] = [f"# {job.name}"]

    # 1. assemble sections
    if not args.no_assemble and (job / "sections.json").exists() and any((job / "sections").glob("*.md")):
        code, out = run([PY, "scripts/assemble_sections.py", "--job", str(job)])
        lines.append("assembly: " + (out.strip().splitlines()[-1] if out.strip() else "—"))
        if code:
            problems.append("section assembly failed")

    target = job / "edited.md"
    if not target.exists():
        target = job / "out" / "draft.md"
    if not target.exists():
        print("neither edited.md nor out/draft.md exists: nothing to check")
        raise SystemExit(1)

    # 2. Paragraphs are checked by the editor for meaning. There is no numeric limit,
    # so the deterministic check must not change the text.
    lines.append("paragraphs: numeric limit disabled; text unchanged")

    # 3. prohibitions and manner
    code, out = run([PY, "scripts/lint_article.py", "--input", str(target),
                     "--subject", subject_of(job)])
    tail = [l for l in out.strip().splitlines() if l.strip()]
    lines += ["  " + l.strip() for l in tail if l.startswith(("  ", "запреты", "prohibitions", "H1", "заголовки", "headings"))]
    if code:
        problems.append("linter: violations found")

    # 4. verbatim overlaps with neighbours
    if args.siblings:
        files = [str(target)] + [str(job_path(s) / "edited.md") for s in args.siblings]
        files = [f for f in files if Path(f).exists()]
        if len(files) > 1:
            code, out = run([PY, "scripts/text_overlap.py", *files])
            worst = [l for l in out.splitlines() if "longest shared run overall" in l]
            lines.append("overlaps: " + (worst[0].split(":", 1)[-1].strip() if worst else "—"))
            if code:
                problems.append("overlap with a neighbouring article longer than 20 words")

    # 5. HTML and sanitizer
    html = job / "out" / "article.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    code, out = run([PY, "scripts/md_to_strapi_html.py", "--input", str(target), "--output", str(html)])
    if code:
        problems.append("HTML converter failed")
    else:
        body = html.read_text(encoding="utf-8")
        from article_materials import cms_image_html, is_v2
        if is_v2(job):
            body = cms_image_html(body)
            html.write_text(body, encoding="utf-8")
        r = subprocess.run(["node", "tools/sanitize/check.js"], input=body,
                           capture_output=True, text=True, cwd=ROOT)
        same = r.stdout.strip() == body.strip()
        lines.append("sanitizer: " + ("markup passes without loss" if same else "CUTS MARKUP"))
        if not same:
            problems.append("sanitizer changes the markup")
        singles = [m for m in re.findall(r"<ol><li>.*?</li></ol>", body, re.S) if m.count("<li>") == 1]
        if len(singles) >= 2:
            problems.append(f"numbered lists with a single item: {len(singles)}; on the site "
                            "the numbering will restart")

    # 6. copy for Strapi
    (job / "out" / "article.md").write_text(target.read_text(encoding="utf-8"), encoding="utf-8")

    print("\n".join(lines))
    if problems:
        print("\nNEEDS FIXING:")
        for p in problems:
            print(" -", p)
        raise SystemExit(1)
    print("\nall clean")


if __name__ == "__main__":
    main()
