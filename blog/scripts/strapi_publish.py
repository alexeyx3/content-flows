"""Article to production Strapi: a draft by default, straight to publication with --publish.

By default the script creates the record WITHOUT publishedAt, i.e. a draft: publication is
a step the publisher takes in the admin panel. Publishing from the pipeline is allowed, but
it needs the EXPLICIT --publish flag, so an accidental publication is impossible.

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
import ast
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.client import IncompleteRead
from pathlib import Path
if __package__:
    from .article_materials import cms_image_html, export_errors, is_v2, write_json
    from .lint_article import STOP_BRANDS
    from .topic_overlap import decision_errors, new_close_matches, resolved_query
else:
    from article_materials import cms_image_html, export_errors, is_v2, write_json
    from lint_article import STOP_BRANDS
    from topic_overlap import decision_errors, new_close_matches, resolved_query

ROOT = Path(__file__).resolve().parents[1]
API = "https://cms.example.com/api"
TOKEN_FILES = (
    ROOT / "config" / "strapi-api-token",
)
AUTHORS = ROOT / "config" / "blog-authors.json"
SANITIZER = ROOT / "tools" / "sanitize" / "check.js"
EDITOR_USERNAME = json.loads(AUTHORS.read_text(encoding="utf-8"))["defaults"]["editor"]  # editor of all pipeline articles
LIMITS = {"metaTitle": 70, "metaDescription": 200, "summary": 400}
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
YEAR_IN_SLUG = re.compile(r"(?:^|-)(?:19|20)\d\d(?:-|$)")
ALTERNATIVES_TITLE = re.compile(r"\balternatives\b", re.I)
ALTERNATIVES_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-alternatives$")
META_LINE = re.compile(r"^-?\s*(title|slug|metaTitle|metaDescription|summary)\s*:\s*(.+)$")


def token() -> str:
    for path in TOKEN_FILES:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    searched = "\n- ".join(str(path) for path in TOKEN_FILES)
    raise SystemExit(f"Strapi token not found. Checked:\n- {searched}")


def api(path: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
    )
    attempts = 3 if req.get_method() == "GET" else 1
    while True:
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except (ConnectionError, TimeoutError, IncompleteRead):
            attempts -= 1
            if not attempts:
                raise


def stop_brand_errors(meta: dict, html: str) -> list[str]:
    """Brands from config/stop-brands.json found in any metadata field or in the body.

    The list is loaded once by lint_article.py; an empty list blocks nothing.
    """
    text = " ".join(str(v) for v in meta.values()) + " " + html
    found = sorted({m.group(0) for m in STOP_BRANDS.finditer(text)}, key=str.lower)
    return [f"a stop-listed brand (config/stop-brands.json) is never mentioned on the site: {', '.join(found)}"] if found else []


def validate_meta(meta: dict, article_type: str | None = None) -> list[str]:
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
    title = str(meta.get("title", ""))
    if (article_type in (None, "listicle", "comparison")
            and title and ALTERNATIVES_TITLE.search(title)
            and not ALTERNATIVES_SLUG.fullmatch(slug)):
        errors.append(
            f"slug: '{slug}' — for a 'competitor + Alternatives' article the address must have "
            "the form '<competitor>-alternatives' with nothing after alternatives"
        )
    return errors


def html_survives_sanitizer(html: str) -> bool:
    r = subprocess.run(["node", str(SANITIZER)], input=html,
                       capture_output=True, text=True, check=True)
    return r.stdout == html


def slug_is_free(slug: str) -> bool:
    """Whether the slug is taken, COUNTING drafts.

    The usual `/articles?filters[slug][$eq]=...` does not work for this: the controller
    hard-codes publicationState = 'live' and ignores the query parameter, so it
    does not see drafts at all (verified on production). The findBySlug route
    goes to the database directly and returns 404 if the article does not exist in any state.
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


def read_author(job: Path) -> str:
    """Read a YAML scalar without making quote style part of the username.

    Jobs are intentionally simple YAML, but both `author: john.roe` and
    `author: "john.roe"` are valid. The old regex returned the quote as
    part of the value and made a valid job impossible to publish.
    """
    match = re.search(
        r"^author:\s*(.*?)\s*(?:#.*)?$",
        (job / "job.yaml").read_text(encoding="utf-8"),
        re.M,
    )
    if not match or not match.group(1).strip():
        raise SystemExit("job.yaml has no author field")
    raw = match.group(1).strip()
    if raw[:1] in {"\"", "'"}:
        try:
            value = ast.literal_eval(raw)
        except (SyntaxError, ValueError) as exc:
            raise SystemExit(f"invalid author value in job.yaml: {raw}") from exc
        if not isinstance(value, str):
            raise SystemExit("author in job.yaml must be a string")
        return value.strip()
    return raw


def build_payload(meta: dict, html: str, author_id: int, editor_id: int,
                  publish: bool = False) -> dict:
    data = {
        "title": meta["title"],
        "slug": meta["slug"],
        "contentHtml": html,
        "author": author_id,
        "editors": [editor_id],
        # An EXPLICIT value is required in both directions. Verified on production: if the
        # field is simply not sent, Strapi sets the date itself and the record comes out
        # published, reaching the public API and the site map. A draft is obtained
        # only through an explicit null, publication through an explicit date.
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


def stored_article(meta: dict, html: str, record_id: int, cover: dict | None = None) -> dict:
    record = api(f"/articles/{urllib.parse.quote(meta['slug'])}/findBySlug").get("data") or {}
    article = record.get("attributes", record)
    expected = {key: meta[key] for key in ("slug", "title", "metaTitle") if meta.get(key)}
    expected["content"] = html
    mismatches = [key for key, value in expected.items() if article.get(key) != value]
    if record.get("id") != record_id:
        mismatches.append("id")
    if cover is not None:
        media = article.get("cover") or {}
        media = media.get("data", media) or {}
        if (cover.get("status") != "complete" or cover.get("target_id") != record_id
                or cover.get("slug") != meta["slug"] or cover.get("title") != " ".join(meta["title"].split())
                or cover.get("locale") != article.get("locale")
                or not cover.get("media_id") or cover["media_id"] != media.get("id")):
            mismatches.append("cover")
    if mismatches:
        raise SystemExit(f"CMS readback differs for id={record_id}: {', '.join(mismatches)}")
    return article


def refresh_existing(job: Path, meta: dict, html: str, record_id: int | None,
                     publish: bool, dry_run: bool) -> None:
    """Update a reviewed live article without a draft interval or a new publish date."""
    if not record_id or not publish:
        raise SystemExit("refresh requires --update <existing id> --publish")
    baseline = json.loads((job / "baseline/cms-record.json").read_text(encoding="utf-8"))
    baseline = baseline.get("data", baseline)
    baseline = baseline.get("attributes", baseline)
    current = api(f"/articles/{urllib.parse.quote(meta['slug'])}/findBySlug").get("data") or {}
    current_id = current.get("id")
    current = current.get("attributes", current)
    if current_id != record_id or baseline.get("id", record_id) != record_id:
        raise SystemExit("refresh record id differs from published baseline/current slug")
    if (current.get("slug") != meta["slug"] or baseline.get("slug") != meta["slug"]
            or not current.get("publishedAt")
            or current.get("publishedAt") != baseline.get("publishedAt")):
        raise SystemExit("refresh requires the same live URL and original publication date")
    if current.get("content") not in (baseline.get("content"), html):
        raise SystemExit("live article changed since refresh baseline; refusing to overwrite")
    data = {"title": meta["title"], "contentHtml": html,
            "publishedAt": current["publishedAt"]}
    data.update({key: meta[key] for key in LIMITS if key in meta})
    if dry_run:
        print(json.dumps({"refresh": True, "id": record_id, "slug": meta["slug"],
                          "publishedAt": data["publishedAt"],
                          "content_sha256": hashlib.sha256(html.encode()).hexdigest(),
                          "preserved": ["URL", "publishedAt", "cover", "author", "editors", "tags", "indexable"]}, indent=2))
        return
    before_path = job / "out/refresh-before.json"
    if not before_path.exists():
        write_json(before_path, {"id": record_id, **current})
    api(f"/articles/{record_id}", "PUT", {"data": data})
    stored = api(f"/articles/{urllib.parse.quote(meta['slug'])}/findBySlug").get("data") or {}
    stored_id = stored.get("id")
    stored = stored.get("attributes", stored)
    preserved = ("slug", "publishedAt", "cover", "author", "editors", "tags", "indexable", "locale", "createdAt")
    mismatch = [key for key in preserved if stored.get(key) != current.get(key)]
    mismatch += [key for key in ("title", *LIMITS) if key in data and stored.get(key) != data[key]]
    if stored_id != record_id or stored.get("content") != html or mismatch:
        # The old supported HTML/metadata are reversible; never create a second record.
        rollback = {key: current.get(key) for key in ("title", *LIMITS, "publishedAt")}
        rollback["contentHtml"] = current["content"]
        api(f"/articles/{record_id}", "PUT", {"data": rollback})
        write_json(job / "out/refresh-failed.json", {"id": record_id, "mismatched_fields": mismatch,
                                                    "rollback_requested": True})
        raise SystemExit("refresh CMS readback mismatch; prior body restored; inspect before retry")
    stamp = stored.get("updatedAt")
    if not stamp:
        raise SystemExit("refresh readback has no updatedAt")
    write_json(job / "out/strapi_record.json", {"id": record_id, "slug": meta["slug"], "published": True})
    write_json(job / "out/refresh-publication.json", {
        "id": record_id, "slug": meta["slug"], "url": f"https://example.com/blog/{meta['slug']}/",
        "publishedAt": stored["publishedAt"], "updatedAt": stamp,
        "article_sha256": hashlib.sha256((job / "edited.md").read_bytes()).hexdigest(),
        "content_sha256": hashlib.sha256(html.encode()).hexdigest(), "preserved_fields": list(preserved)})
    print(f"updated: id={record_id}; the original publication date is preserved\nhttps://example.com/blog/{meta['slug']}/")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--update", type=int, help="id of an existing record")
    ap.add_argument("--cover-receipt", type=Path, help="Exact cover upload receipt for publishing a checked draft")
    ap.add_argument("--publish", action="store_true",
                    help="publish immediately; without the flag the record is a draft")
    args = ap.parse_args()
    if args.cover_receipt is not None and not (args.publish and args.update):
        ap.error("--cover-receipt requires --update <draft id> and --publish")

    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    if re.search(r"^article_translation_version:\s*1\b", (job / "job.yaml").read_text(), re.M):
        sys.exit("translation CMS export unsupported: linked localization, locale-aware identity and explicit authorization required")
    if ready_errors := export_errors(job, "strapi"):
        sys.exit("not sent to Strapi:\n- " + "\n- ".join(ready_errors))
    meta = read_meta(job)
    job_config = (job / "job.yaml").read_text(encoding="utf-8")
    if re.search(r"^duplicate_preflight_version:\s*1\b", job_config, re.M):
        cluster = re.search(r'^temnik_cluster_id:\s*["\']?([^\s"\']+)', job_config, re.M)
        topic = re.search(r'^topic:\s*["\']?(.*?)["\']?\s*(?:#.*)?$', job_config, re.M)
        brief_path = job / "brief.md"
        query = resolved_query(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else ""
        if not cluster or not topic or not query:
            sys.exit("not sent: overlap gate needs temnik cluster, topic and brief primary query")
        cluster_id, topic_text = cluster.group(1), topic.group(1).strip().strip('"\'')
        if overlap_errors := decision_errors(cluster_id, "resolved", topic_text, query):
            sys.exit("not sent: " + "; ".join(overlap_errors))
        if fresh_hits := new_close_matches(cluster_id, topic_text, query, job, meta.get("slug", "")):
            urls = ", ".join(hit["url"] for hit in fresh_hits)
            sys.exit(f"not sent: new close owned-content matches since overlap review: {urls}; rerun resolved preflight")
    html = (job / "out" / "article.html").read_text(encoding="utf-8")
    if is_v2(job):
        html = cms_image_html(html)
    author = read_author(job)

    article_type_match = re.search(r"^article_type:\s*([^\s#]+)", job_config, re.M)
    article_type = article_type_match.group(1).strip("\"'").lower() if article_type_match else None
    problems = validate_meta(meta, article_type)
    problems += stop_brand_errors(meta, html)
    if not html_survives_sanitizer(html):
        problems.append("body: the Strapi sanitizer changes the markup, so part of the text will be lost on the site")
    if not args.update and meta.get("slug") and not slug_is_free(meta["slug"]):
        problems.append(f"slug: '{meta['slug']}' is already taken on the blog")
    if problems:
        sys.exit("not sent:\n- " + "\n- ".join(problems))

    if re.search(r"^article_refresh_version:\s*1\b", job_config, re.M):
        refresh_existing(job, meta, html, args.update, args.publish, args.dry_run)
        return

    payload = build_payload(meta, html,
                            resolve_author_id(author),
                            resolve_author_id(EDITOR_USERNAME),
                            publish=args.publish)
    v2 = is_v2(job)
    cover = None
    if args.cover_receipt:
        if not v2:
            sys.exit("--cover-receipt requires a v2 job")
        cover = json.loads(args.cover_receipt.read_text(encoding="utf-8"))
        if not isinstance(cover, dict):
            sys.exit("Cover upload receipt must be a JSON object")
        stored = stored_article(meta, html, args.update, cover)
    if args.dry_run:
        preview = json.loads(json.dumps(payload))
        preview["data"]["contentHtml"] = preview["data"]["contentHtml"][:300] + " …"
        print(json.dumps(preview, ensure_ascii=False, indent=1))
        return

    receipt_path = job / "out/strapi_record.json"
    if cover is not None:
        # A matching checked draft is already stored. A retry after an ambiguous publish PUT
        # reads back the existing publication instead of making it a draft again.
        if not stored.get("publishedAt"):
            api(f"/articles/{args.update}", "PUT", {"data": {"publishedAt": payload["data"]["publishedAt"]}})
            stored = stored_article(meta, html, args.update, cover)
        if not stored.get("publishedAt"):
            sys.exit(f"CMS publication timestamp missing for id={args.update}")
        write_json(receipt_path, {"id": args.update, "slug": meta["slug"], "published": True})
        print(f"published: id={args.update}\nhttps://example.com/blog/{meta['slug']}/")
        return

    if v2:
        payload["data"]["publishedAt"] = None
    if args.update:
        r = api(f"/articles/{args.update}", "PUT", payload)
    else:
        r = api("/articles", "POST", payload)
    record = r.get("data") or {}
    if v2:
        record_id = record.get("id")
        write_json(receipt_path, {"id": record_id, "slug": meta["slug"], "published": False})
        stored = (api(f"/articles/{urllib.parse.quote(meta['slug'])}/findBySlug").get("data") or {})
        stored = stored.get("attributes", stored)
        if stored.get("content") != html:
            sys.exit(f"record id={record_id} left as a draft: the CMS changed the HTML. "
                     "Check the supported markup and retry with --update for this id.")
        if args.publish:
            api(f"/articles/{record_id}", "PUT", {"data": {"publishedAt": build_payload(meta, html, 0, 0, True)["data"]["publishedAt"]}})
            write_json(receipt_path, {"id": record_id, "slug": meta["slug"], "published": True})
    if args.publish:
        print(f"published: id={record.get('id')}")
        print(f"https://example.com/blog/{meta['slug']}/")
    else:
        print(f"draft ready: id={record.get('id')}, slug={meta['slug']}")
        print("to publish, use the --publish flag or do it by hand in the admin panel")


if __name__ == "__main__":
    main()
