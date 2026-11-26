#!/usr/bin/env python3
"""Create, assemble, and package isolated Example Co glossary jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from datetime import datetime, timezone

from glossary_materials import (
    bind_visuals, enriched, digest, read as read_material,
    run_blog_visual_script, validate as validate_materials,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL_ROUTING = ROOT / "config" / "codex-model-routing.json"
AUTHORS_FILE = ROOT.parent / "blog" / "config" / "blog-authors.json"
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
H2 = re.compile(r"^## (.+)$", re.M)
HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.M)
SANITIZER = ROOT / "tools" / "sanitize" / "check.js"
LIMITS = {"definition": 300, "metaTitle": 70, "metaDescription": 200}


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sections(job: Path) -> list[dict]:
    items = read_json(job / "sections.json").get("sections")
    if not isinstance(items, list) or not items:
        raise ValueError("sections.json: nonempty sections list required")
    ids = set()
    titles = set()
    for item in items:
        if not isinstance(item, dict) or not SLUG.fullmatch(str(item.get("id", ""))):
            raise ValueError("sections.json: each section needs a kebab-case id")
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("sections.json: each section needs a title")
        if item["id"] in ids or title in titles:
            raise ValueError("sections.json: duplicate id or H2 title")
        ids.add(item["id"])
        titles.add(title)
    return items


def validate_meta(meta: dict) -> None:
    for key in ("term", "slug", "locale", "definition", "metaTitle", "metaDescription"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise ValueError(f"meta.json: {key} is required")
    if meta["locale"] != "en":
        raise ValueError("meta.json: current glossary locale must be en")
    if not SLUG.fullmatch(meta["slug"]):
        raise ValueError("meta.json: invalid slug")
    for key, cap in LIMITS.items():
        if len(meta[key]) > cap:
            raise ValueError(f"meta.json: {key} has {len(meta[key])} characters; limit {cap}")
    if "\n" in meta["definition"] or "\r" in meta["definition"]:
        raise ValueError("meta.json: definition must be one paragraph")
    if not isinstance(meta.get("indexable", True), bool):
        raise ValueError("meta.json: indexable must be boolean")


def validate_body(body: str, items: list[dict], *, allow_visual_markers: bool = False) -> None:
    if not body.lstrip().startswith("## "):
        raise ValueError("edited.md: body must start with H2")
    headings = HEADING.findall(body)
    if any(len(marks) == 1 or len(marks) > 4 for marks, _ in headings):
        raise ValueError("edited.md: H1 and headings deeper than H4 are forbidden")
    actual = H2.findall(body)
    expected = [item["title"] for item in items]
    if actual != expected:
        raise ValueError(f"edited.md: H2 mismatch: expected {expected!r}, got {actual!r}")
    for item in items:
        if "subheadings" not in item:
            continue
        if not isinstance(item["subheadings"], list):
            raise ValueError("sections.json: subheadings must be a list")
        start = body.index(f"## {item['title']}")
        end = body.find("\n## ", start + 3)
        chunk = body[start:end] if end >= 0 else body[start:]
        found = [(len(level), title) for level, title in HEADING.findall(chunk) if len(level) > 2]
        expected_subs = [(sub.get("level"), sub.get("title")) for sub in item["subheadings"]]
        if found != expected_subs:
            raise ValueError(f"edited.md: subheading mismatch under {item['title']}")
    placeholder_body = re.sub(r"\[\[VISUAL:[a-z0-9-]+\]\]", "", body) if allow_visual_markers else body
    if re.search(r"\{\{.*?\}\}|\[\[.*?\]\]|\b(?:TODO|FIXME|lorem ipsum)\b", placeholder_body, re.I):
        raise ValueError("edited.md: unresolved placeholder")


def new_job(args: argparse.Namespace) -> None:
    if not SLUG.fullmatch(args.slug):
        raise ValueError("slug must be lowercase kebab-case")
    date.fromisoformat(args.date)
    writer_backend = args.writer_backend or read_json(MODEL_ROUTING)["default_writer_backend"]
    if writer_backend not in {"openrouter", "codex"}:
        raise ValueError("Invalid default glossary writer backend")
    job = ROOT / "jobs" / f"{args.date}-{args.slug}"
    job.mkdir(parents=False, exist_ok=False)
    (job / "sections").mkdir()
    (job / "review").mkdir()
    write_json(job / "request.json", {
        "term": args.term, "slug": args.slug, "locale": "en", "status": "brief-pending",
        "author": args.author, "editor": read_json(AUTHORS_FILE)["defaults"]["editor"], "workflow_version": 2,
        "humanization_required": True, "writer_backend": writer_backend,
    })
    print(job)


def assemble(args: argparse.Namespace) -> None:
    job = Path(args.job).resolve()
    parts = []
    for item in sections(job):
        path = job / "sections" / f"{item['id']}.md"
        value = path.read_text(encoding="utf-8").strip()
        if not value.startswith(f"## {item['title']}\n"):
            raise ValueError(f"{path}: wrong or missing H2")
        if len(H2.findall(value)) != 1:
            raise ValueError(f"{path}: expected exactly one H2")
        parts.append(value)
    output = "\n\n".join(parts) + "\n"
    validate_body(output, sections(job), allow_visual_markers=enriched(job))
    (job / "assembled.md").write_text(output, encoding="utf-8")
    draft = job / "out" / "draft.md"
    draft.parent.mkdir(exist_ok=True)
    draft.write_text(output, encoding="utf-8")
    print(job / "assembled.md")


def package(args: argparse.Namespace) -> None:
    job = Path(args.job).resolve()
    meta = read_json(job / "meta.json")
    validate_meta(meta)
    items = sections(job)
    report = (job / "qa_report.md").read_text(encoding="utf-8")
    if not report.startswith("Verdict: PASS\n"):
        raise ValueError("qa_report.md: QA PASS required before packaging")
    for name in ("edited.md", "meta.json"):
        expected = hashlib.sha256((job / name).read_bytes()).hexdigest()
        if f"{name} SHA256: {expected}" not in report:
            raise ValueError(f"qa_report.md: missing current {name} checksum; recheck after changes")
    if enriched(job):
        errors = validate_materials(job, for_qa=True)
        if errors:
            raise ValueError("materials: " + "; ".join(errors))
        names = ["research.md", "evidence.md", "sections.json", "visuals.json", "expert_quotes.json"]
        if read_json(job / "request.json").get("humanization_required"):
            names.append("humanization_report.md")
        if read_material(job / "expert_quotes.json")["quotes"]:
            names.append("raw/speaker-profiles.json")
        for name in names:
            expected = hashlib.sha256((job / name).read_bytes()).hexdigest()
            if f"{name} SHA256: {expected}" not in report:
                raise ValueError(f"qa_report.md: missing current {name} checksum")
    body = (job / "edited.md").read_text(encoding="utf-8").strip() + "\n"
    validate_body(body, items)

    try:
        import markdown
    except ImportError as exc:
        raise RuntimeError("Install Python dependencies: python3 -m pip install -r requirements.txt") from exc
    html = markdown.markdown(body, extensions=["tables", "sane_lists"]) + "\n"
    # Strapi removes image title, while the review Doc keeps it in its native-image receipt.
    html = re.sub(r'(<img\b[^>]*?)\s+title="[^"]*"', r'\1', html)
    if not (SANITIZER.parent / "node_modules" / "sanitize-html").exists():
        raise RuntimeError("Install sanitizer: cd tools/sanitize && npm ci")
    result = subprocess.run(["node", str(SANITIZER)], input=html, text=True, capture_output=True, check=True)
    if result.stdout != html:
        raise ValueError("HTML changes in the Strapi sanitizer; inspect markup before packaging")

    out = job / "out"
    out.mkdir(exist_ok=True)
    payload = {"data": {
        "term": meta["term"], "slug": meta["slug"], "locale": meta["locale"],
        "definition": meta["definition"], "metaTitle": meta["metaTitle"],
        "metaDescription": meta["metaDescription"], "indexable": meta.get("indexable", True),
        "contentHtml": html,
    }}
    write_json(out / "strapi-payload.json", payload)
    (out / "content.html").write_text(html, encoding="utf-8")
    note = ""
    if enriched(job):
        proposed = [q for q in read_material(job / "expert_quotes.json")["quotes"] if q["status"] == "proposed"]
        if proposed:
            note = ("> Editorial review: the expert comment(s) in this document are proposed wording. "
                    "They require explicit approval or removal before CMS submission.\n\n")
    (out / "review.md").write_text(
        f"# {meta['term']}\n\n{meta['definition']}\n\n{note}{body}", encoding="utf-8"
    )
    print(out)


def fingerprint(args: argparse.Namespace) -> None:
    job = Path(args.job).resolve()
    names = ["edited.md", "meta.json"]
    if enriched(job):
        names += ["research.md", "evidence.md", "sections.json", "visuals.json", "expert_quotes.json"]
        if read_json(job / "request.json").get("humanization_required"):
            names.append("humanization_report.md")
        if read_material(job / "expert_quotes.json")["quotes"]:
            names.append("raw/speaker-profiles.json")
    for name in names:
        print(f"{name} SHA256: {hashlib.sha256((job / name).read_bytes()).hexdigest()}")


def materials(args: argparse.Namespace) -> None:
    job = Path(args.job).resolve()
    errors = validate_materials(job, for_qa=args.stage == "qa", for_cms=args.stage == "cms")
    if errors:
        raise ValueError("\n- " + "\n- ".join(errors))
    print(f"PASS: materials {args.stage}")


def visual_action(args: argparse.Namespace) -> None:
    job = Path(args.job).resolve()
    if not enriched(job):
        raise ValueError("visual stages require workflow_version 2")
    if args.command == "render-visuals":
        run_blog_visual_script(job, "render_visuals.py")
    elif args.command == "upload-visuals":
        run_blog_visual_script(job, "upload_visuals.py", dry_run=args.dry_run)
    else:
        bind_visuals(job)


def approve_comment(args: argparse.Namespace) -> None:
    job = Path(args.job).resolve()
    if not args.by.strip() or not args.reference.strip():
        raise ValueError("human approver and approval reference required")
    path = job / "expert_quotes.json"
    data = read_material(path)
    matches = [q for q in data["quotes"] if q["id"] == args.id]
    if len(matches) != 1 or matches[0]["status"] != "proposed":
        raise ValueError("expected one proposed comment with this ID")
    q = matches[0]
    q["status"] = "approved"
    q["approval"] = {"by": args.by, "reference": args.reference,
                     "at": datetime.now(timezone.utc).isoformat(),
                     "text_sha256": digest(q["text"] + "\n" + q["attribution"])}
    write_json(path, data)
    print(f"approved {args.id}; rerun QA and package")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("new")
    start.add_argument("--term", required=True)
    start.add_argument("--slug", required=True)
    start.add_argument("--date", required=True)
    start.add_argument("--author", required=True, help="Strapi username, as in the blog job")
    start.add_argument("--writer-backend", choices=["openrouter", "codex"],
                       help="Override the configured writer for this new job")
    for name in ("assemble", "package", "fingerprint"):
        sub.add_parser(name).add_argument("--job", required=True)
    check = sub.add_parser("materials-check")
    check.add_argument("--job", required=True)
    check.add_argument("--stage", choices=["inputs", "qa", "cms"], default="inputs")
    for name in ("render-visuals", "upload-visuals", "bind-visuals"):
        action = sub.add_parser(name)
        action.add_argument("--job", required=True)
        if name == "upload-visuals":
            action.add_argument("--dry-run", action="store_true")
    approval = sub.add_parser("approve-comment")
    approval.add_argument("--job", required=True)
    approval.add_argument("--id", required=True)
    approval.add_argument("--by", required=True)
    approval.add_argument("--reference", required=True)
    args = parser.parse_args()
    try:
        {"new": new_job, "assemble": assemble, "package": package, "fingerprint": fingerprint,
         "materials-check": materials, "render-visuals": visual_action,
         "upload-visuals": visual_action, "bind-visuals": visual_action,
         "approve-comment": approve_comment}[args.command](args)
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
