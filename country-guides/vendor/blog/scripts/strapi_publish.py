"""Article to production Strapi: a draft by default, straight to publication with --publish.

By default the script creates the record with publishedAt: null, i.e. a draft: publication was
a step the publisher took in the admin panel. The blog's standing permission to publish does
not extend to the guides. Publishing needs the EXPLICIT --publish flag, so an accidental
publication is impossible.

Three things are checked before sending, and each of them has broken the work before:
- field limits (metaTitle 70 / metaDescription 200 / summary 400);
- slug uniqueness: the public API does not return drafts, and Strapi rejects a duplicate only
  at write time, which wastes time;
- the body survives the sanitizer unchanged, otherwise part of the markup disappears on the site.

Usage:
  python3 scripts/strapi_publish.py --job jobs/<job-dir> --dry-run
  python3 scripts/strapi_publish.py --job jobs/<job-dir>
  python3 scripts/strapi_publish.py --job jobs/<job-dir> --update 152
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from article_materials import export_errors, is_v2, write_json
from lint_article import STOP_BRANDS

ROOT = Path(__file__).resolve().parents[1]
API = "https://cms.example.com/api"
TOKEN_FILE = ROOT / "config" / "strapi-api-token"
AUTHORS = ROOT / "config" / "blog-authors.json"
SANITIZER = ROOT / "tools" / "sanitize" / "check.js"
EDITOR_USERNAME = json.loads(AUTHORS.read_text(encoding="utf-8"))["defaults"]["editor"]  # editor of all pipeline articles
LIMITS = {"metaTitle": 70, "metaDescription": 200, "summary": 400}
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
YEAR_IN_SLUG = re.compile(r"(?:^|-)(?:19|20)\d\d(?:-|$)")
META_LINE = re.compile(r"^-?\s*(title|slug|metaTitle|metaDescription|summary)\s*:\s*(.+)$")


def token() -> str:
    return TOKEN_FILE.read_text(encoding="utf-8").strip()


def api(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def stop_brand_errors(meta: dict, html: str) -> list[str]:
    """Brands from config/stop-brands.json found in any metadata field or in the body.

    The list is loaded once by lint_article.py; an empty list blocks nothing.
    """
    text = " ".join(str(v) for v in meta.values()) + " " + html
    found = sorted({m.group(0) for m in STOP_BRANDS.finditer(text)}, key=str.lower)
    return [f"a stop-listed brand (config/stop-brands.json) is never mentioned on the site: {', '.join(found)}"] if found else []


def validate_meta(meta: dict) -> list[str]:
    errors: list[str] = []
    for field in ("title", "slug"):
        if not str(meta.get(field, "")).strip():
            errors.append(f"{field}: required field is empty")
    for field, cap in LIMITS.items():
        value = str(meta.get(field, ""))
        if len(value) > cap:
            errors.append(f"{field}: {len(value)} characters, maximum {cap}")
    slug = str(meta.get("slug", ""))
    if slug and not SLUG.match(slug):
        errors.append(f"slug: '{slug}' — only lowercase Latin letters, digits and hyphens")
    if slug and YEAR_IN_SLUG.search(slug):
        # Five articles once went out with a slug like "...-alternatives-2026".
        # Published articles are written without a year, and a year in the address is a commitment
        # to rewrite the address every January, with a redirect and lost signals.
        errors.append(f"slug: '{slug}' contains a year — addresses are written without a year")
    return errors


def html_survives_sanitizer(html: str) -> bool:
    r = subprocess.run(["node", str(SANITIZER)], input=html,
                       capture_output=True, text=True, check=True)
    return r.stdout == html


def cms_image_html(html: str) -> str:
    """Current CMS strips image title; retain it in source/manifests, omit on export."""
    return re.sub(r"<img\b[^>]*>",
                  lambda match: re.sub(r'\s+title="[^"]*"', '', match.group(0)), html)


def slug_is_free(slug: str) -> bool:
    """Whether the slug is taken, COUNTING drafts.

    The usual `/articles?filters[slug][$eq]=...` does not work for this: the controller
    hard-codes publicationState = 'live' and ignores the query parameter, so it does not see
    drafts at all (checked on production). The findBySlug route goes to the database directly
    and returns 404 if the article does not exist in any state.
    """
    try:
        r = api(f"/articles/{urllib.parse.quote(slug)}/findBySlug")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return True
        raise
    return not (r.get("data") or {})


def resolve_author_id(username: str) -> int:
    mapping = json.loads(AUTHORS.read_text(encoding="utf-8"))
    if username not in mapping:
        sys.exit(f"author '{username}' is not described in config/blog-authors.json")
    value = mapping[username]
    if not value:
        sys.exit(f"author '{username}' has no id set in config/blog-authors.json")
    return int(value)


def build_payload(meta: dict, html: str, author_id: int, editor_id: int,
                  publish: bool = False) -> dict:
    data = {
        "title": meta["title"],
        "slug": meta["slug"],
        "contentHtml": html,
        "author": author_id,
        "editors": [editor_id],
        # An EXPLICIT value is required both ways. Checked on production: if the field is
        # simply not sent, Strapi sets the date itself — the record comes out published and
        # gets into the public API and the sitemap. A draft is obtained only through an
        # explicit null, a publication through an explicit date.
        "publishedAt": (datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                        .replace("+00:00", "Z") if publish else None),
    }
    for field in ("metaTitle", "metaDescription", "summary"):
        if meta.get(field):
            data[field] = meta[field]
    return {"data": data}


def read_meta(job: Path) -> dict:
    """out/meta.md is written at the packaging step: lines of the form 'key: value'."""
    meta: dict = {}
    for line in (job / "out" / "meta.md").read_text(encoding="utf-8").splitlines():
        if m := META_LINE.match(line.strip()):
            meta[m.group(1)] = m.group(2).strip()
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--update", type=int, help="id of the existing record")
    ap.add_argument("--publish", action="store_true",
                    help="publish right away; without the flag — a draft")
    args = ap.parse_args()

    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    ready_errors = export_errors(job, "strapi")
    if ready_errors:
        sys.exit("not sent to Strapi:\n- " + "\n- ".join(ready_errors))
    meta = read_meta(job)
    html = (job / "out" / "article.html").read_text(encoding="utf-8")
    if is_v2(job):
        html = cms_image_html(html)
    author = re.search(r"^author:\s*(\S+)", (job / "job.yaml").read_text(encoding="utf-8"), re.M)
    if not author:
        sys.exit("job.yaml has no author field")

    problems = validate_meta(meta)
    problems += stop_brand_errors(meta, html)
    if not html_survives_sanitizer(html):
        problems.append("body: the Strapi sanitizer changes the markup — part of the text will be lost on the site")
    if not args.update and meta.get("slug") and not slug_is_free(meta["slug"]):
        problems.append(f"slug: '{meta['slug']}' is already taken on the blog")
    if problems:
        sys.exit("not sent:\n- " + "\n- ".join(problems))

    payload = build_payload(meta, html,
                            resolve_author_id(author.group(1)),
                            resolve_author_id(EDITOR_USERNAME),
                            publish=args.publish)
    if args.dry_run:
        preview = json.loads(json.dumps(payload))
        preview["data"]["contentHtml"] = preview["data"]["contentHtml"][:300] + " …"
        print(json.dumps(preview, ensure_ascii=False, indent=1))
        return

    # V2 first writes a draft and verifies the supported HTML before publishing.
    # Image title is omitted intentionally; any other change still blocks export.
    if is_v2(job):
        payload["data"]["publishedAt"] = None
    if args.update:
        r = api(f"/articles/{args.update}", "PUT", payload)
    else:
        r = api("/articles", "POST", payload)
    record = r.get("data") or {}
    if is_v2(job):
        record_id = record.get("id")
        write_json(job / "out" / "strapi_record.json", {"id": record_id, "slug": meta["slug"], "published": False})
        stored = (api(f"/articles/{urllib.parse.quote(meta['slug'])}/findBySlug").get("data") or {})
        stored = stored.get("attributes", stored)
        if stored.get("content") != html:
            sys.exit(f"record id={record_id} is left as a draft: the CMS changed the HTML. "
                     "Check the supported markup and repeat with --update of this id.")
        if args.publish:
            api(f"/articles/{record_id}", "PUT", {"data": {"publishedAt": build_payload(meta, html, 0, 0, True)["data"]["publishedAt"]}})
            write_json(job / "out" / "strapi_record.json", {"id": record_id, "slug": meta["slug"], "published": True})
    if args.publish:
        print(f"published: id={record.get('id')}")
        print(f"https://example.com/blog/{meta['slug']}/")
    else:
        print(f"draft is ready: id={record.get('id')}, slug={meta['slug']}")
        print("publication — with the --publish flag or by hand in the admin panel")


if __name__ == "__main__":
    main()
