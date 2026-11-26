"""Build the local article package after QA PASS.

The command does not touch the network and publishes nothing. It takes the single H1 from
edited.md and the latest metadata values from brief.md, creates all files in out/
and checks the HTML with the same sanitizer that is used before Strapi.

Usage:
  python3 scripts/package_article.py --job jobs/<job-dir>
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from article_materials import bind_article_visuals, cms_image_html, is_v2, validate_inputs

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("metaTitle", "metaDescription", "summary", "slug")
LIMITS = {"metaTitle": 70, "metaDescription": 200, "summary": 400}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
YEAR_IN_SLUG = re.compile(r"(?:^|-)(?:19|20)\d\d(?:-|$)")
ALTERNATIVES_TITLE = re.compile(r"\balternatives\b", re.I)
ALTERNATIVES_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-alternatives$")
H1 = re.compile(r"^#\s+(.+?)\s*$")


def _label(line: str) -> tuple[str, str] | None:
    """Recognise current and legacy variants of the metadata lines in brief.md."""
    patterns = (
        r"^\s*-\s*\*\*(?P<key>metaTitle|metaDescription|summary|slug):\*\*\s*(?P<value>.*)$",
        r"^\s*-\s*\*\*(?P<key>metaTitle|metaDescription|summary|slug)\*\*\s*(?:\([^)]*\)\s*)?:\s*(?P<value>.*)$",
        r"^\s*-\s*`(?P<key>metaTitle|metaDescription|summary|slug)`\s*:\s*(?P<value>.*)$",
        r"^\s*-\s*(?P<key>metaTitle|metaDescription|summary|slug)\s*:\s*(?P<value>.*)$",
        r"^\s*\|\s*(?P<key>metaTitle|metaDescription|summary|slug)\s*\|\s*(?P<value>.*?)\s*\|\s*$",
    )
    for pattern in patterns:
        if match := re.match(pattern, line):
            return match.group("key"), match.group("value")
    return None


def _clean(value: str) -> str:
    value = " ".join(value.split()).strip()
    value = re.sub(r"\s*\*?\([^)]*(?:chars?|≤)[^)]*\)\*?\s*$", "", value,
                   flags=re.I).strip()
    value = re.sub(r"\s*\*?\(\d+\)\*?\s*$", "", value).strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        value = value[1:-1].strip()
    return value


def extract_metadata(brief: str) -> dict[str, str]:
    """Take the latest values: an early table of the brief may be a draft."""
    found: dict[str, str] = {}
    active: str | None = None
    chunks: list[str] = []

    def flush() -> None:
        nonlocal active, chunks
        if active is not None:
            found[active] = _clean(" ".join(chunks))
        active, chunks = None, []

    for line in brief.splitlines():
        if item := _label(line):
            flush()
            active, value = item
            chunks = [value]
        elif active is not None:
            if not line.strip() or line.lstrip().startswith(("#", "|", "- **", "- `")):
                flush()
            else:
                chunks.append(line.strip())
    flush()
    return found


def article_title(article: str) -> str:
    lines = article.replace("\r\n", "\n").splitlines()
    headings = [match.group(1).strip() for line in lines if (match := H1.match(line))]
    if not lines or not (first := H1.match(lines[0])):
        raise ValueError("edited.md must start with an H1")
    if len(headings) != 1:
        raise ValueError(f"edited.md must contain exactly one H1, found: {len(headings)}")
    return first.group(1).strip()


def validate(meta: dict[str, str], article_type: str | None = None) -> list[str]:
    errors = [f"brief.md: field {field} not found" for field in FIELDS if not meta.get(field)]
    errors.extend(
        f"brief.md: {field} contains an unfilled template {meta[field]}"
        for field in FIELDS if re.fullmatch(r"\{(?:\w+|\{\w+\})\}", meta.get(field, ""))
    )
    for field, cap in LIMITS.items():
        if len(meta.get(field, "")) > cap:
            errors.append(f"{field}: {len(meta[field])} characters, maximum {cap}")
    slug = meta.get("slug", "")
    if slug and not SLUG.fullmatch(slug):
        errors.append(f"slug: '{slug}' — only lowercase Latin letters, digits and hyphens are allowed")
    if slug and YEAR_IN_SLUG.search(slug):
        errors.append(f"slug: '{slug}' contains a year")
    title = meta.get("title", "")
    if (article_type in (None, "listicle", "comparison")
            and title and ALTERNATIVES_TITLE.search(title)
            and not ALTERNATIVES_SLUG.fullmatch(slug)):
        errors.append(
            f"slug: '{slug}' — for a 'competitor + Alternatives' article the address must have "
            "the form '<competitor>-alternatives' with nothing after alternatives"
        )
    return errors


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def package(job: Path, bind_visuals: bool = False) -> None:
    job = job.resolve()
    if is_v2(job):
        if problems := validate_inputs(job):
            raise SystemExit("package not built:\n- " + "\n- ".join(problems))
    edited_path, brief_path = job / "edited.md", job / "brief.md"
    sanitizer = ROOT / "tools" / "sanitize" / "check.js"
    if not (ROOT / "tools" / "sanitize" / "node_modules" / "sanitize-html").exists():
        raise SystemExit("package not built: first run cd tools/sanitize && npm ci")
    article = edited_path.read_text(encoding="utf-8")
    meta = extract_metadata(brief_path.read_text(encoding="utf-8"))
    meta["title"] = article_title(article)
    job_config_path = job / "job.yaml"
    job_config = job_config_path.read_text(encoding="utf-8") if job_config_path.exists() else ""
    article_type_match = re.search(r"^article_type:\s*([^\s#]+)", job_config, re.M)
    article_type = article_type_match.group(1).strip("\"'").lower() if article_type_match else None
    if problems := validate(meta, article_type):
        raise SystemExit("package not built:\n- " + "\n- ".join(problems))
    if bind_visuals and is_v2(job):
        bind_article_visuals(job)

    out = job / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta.md").write_text(
        "\n".join(f"{field}: {meta[field]}" for field in
                  ("title", "slug", "metaTitle", "metaDescription", "summary")) + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(edited_path, out / "article.md")
    run([sys.executable, str(ROOT / "scripts" / "build_internal_package.py"),
         "--job", str(job)])
    run([sys.executable, str(ROOT / "scripts" / "md_to_strapi_html.py"),
         "--input", str(edited_path), "--output", str(out / "article.html")])

    html = (out / "article.html").read_text(encoding="utf-8")
    if is_v2(job):
        html = cms_image_html(html)
        (out / "article.html").write_text(html, encoding="utf-8")
    checked = subprocess.run(
        ["node", str(sanitizer)],
        input=html, capture_output=True, text=True, check=True,
    )
    if checked.stdout != html:
        raise SystemExit("package not built: the Strapi sanitizer changes article.html")
    print(f"{out} — local package ready, sanitizer PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--bind-visuals", action="store_true", help="insert the ready images before QA")
    args = parser.parse_args()
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    package(job.resolve(), bind_visuals=args.bind_visuals)


if __name__ == "__main__":
    main()
