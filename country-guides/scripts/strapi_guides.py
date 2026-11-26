"""Write a country's three pages into Strapi (cms.example.com).

Every write needs explicit permission in the current conversation. Default is a dry run.

  --write            create or update the country and both subpages. Without --indexable the
                     records are published with indexable:false — a noindex preview.
  --draft            write as drafts (publishedAt:null) instead
  --indexable        set indexable:true. A normal publication uses --write --indexable and needs
                     the recorded review approval of every page.

  Caution: indexable is written on every --write. Updating a live guide without --indexable
  switches it to noindex; always pass --indexable when updating a published guide unless a
  noindex preview was explicitly requested.

Existing records are updated, never duplicated: ids come from out/strapi_record.json or from the
public country list. Before any write the blog's export
gate runs on each page (QA receipt, review approval, uploaded images). After the write the
public endpoints are read back and the sanitized body must equal what was sent.

Usage: python3 scripts/strapi_guides.py --job jobs/<job> [--write [--draft] [--indexable]]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from html import unescape
import urllib.error
import urllib.parse
from datetime import datetime, timezone

from common import EDITOR, PAGES, job_dir, load_job, page_dir, read_json, write_json
from article_materials import export_errors
from check_facts import HEADER, publication_header_errors, validate
from strapi_publish import SANITIZER, api, cms_image_html, read_meta, resolve_author_id, stop_brand_errors

KIND = {"eor": "eor", "contractors": "contractors"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def page_payload(job_path, page: str) -> tuple[dict, str]:
    d = page_dir(job_path, page)
    meta = read_meta(d)
    html = cms_image_html((d / "out" / "article.html").read_text(encoding="utf-8"))
    # The converter writes «'» in attributes as &#x27;, the sanitizer returns a plain «'».
    # Same markup: compare after unescaping, then send the sanitized form so read-back matches.
    cleaned = subprocess.run(["node", str(SANITIZER)], input=html, capture_output=True, text=True,
                             check=True).stdout
    if unescape(cleaned) != unescape(html):
        raise ValueError(f"{page}: body does not survive the Strapi sanitizer")
    html = cleaned
    data = {"contentHtml": html}
    for field in ("metaTitle", "metaDescription"):
        if meta.get(field):
            data[field] = meta[field]
    if page != "country":
        data["title"] = meta["title"]
    return data, html


def find_existing(slug: str, record: dict) -> dict:
    if record.get("country_id"):
        return record
    listing = api("/country-guides?pagination[pageSize]=100")
    for item in listing.get("data", []):
        attrs = item.get("attributes", item)
        if attrs.get("slug") == slug:
            subs = {s["kind"]: s["id"] for s in attrs.get("subpages", []) if s.get("id")}
            return {"country_id": item["id"], "subpages": subs}
    return {"subpages": {}}


def norm(html: str) -> str:
    return re.sub(r"\s+", " ", html).strip()


def readback(slug: str, sent: dict[str, str], pages: list[str]) -> list[str]:
    problems = []
    try:
        country = api(f"/country-guides/{urllib.parse.quote(slug)}/findBySlug")
        body = (country.get("data") or country).get("content") or ""
        if norm(body) != norm(sent["country"]):
            problems.append("country: body read back differs from what was sent")
        for page in [p for p in ("eor", "contractors") if p in pages]:
            sub = api(f"/country-guides/{urllib.parse.quote(slug)}/subpages/{KIND[page]}")
            body = (sub.get("data") or sub).get("content") or ""
            if norm(body) != norm(sent[page]):
                problems.append(f"{page}: body read back differs from what was sent")
    except urllib.error.HTTPError as e:
        problems.append(f"read-back failed: HTTP {e.code} (drafts are not served — expected with --draft)")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--indexable", action="store_true")
    ap.add_argument("--pages", default="country,eor,contractors",
                    help="which pages to write; the country page is always included (subpages need it)")
    args = ap.parse_args()
    job_path = job_dir(args.job)
    job = load_job(job_path)
    facts = read_json(job_path / "facts.json")
    header_errors = publication_header_errors(facts)
    if header_errors:
        sys.exit("not ready for Strapi:\n- " + "\n- ".join(header_errors))
    problems = validate(facts)
    # Preview write (indexable:false, seen on a preview site right after Google Docs) needs the
    # same gate as the Docs push: QA PASS sealed, real images.
    # Making pages indexable is the release step and also needs the recorded review approval.
    target = "strapi" if args.indexable else "review"
    pages = [p for p in PAGES if p == "country" or p in args.pages.split(",")]
    for page in pages:
        problems += [f"{page}: {p}" for p in export_errors(page_dir(job_path, page), target, remote=args.write)]
        body = page_dir(job_path, page) / "out" / "article.html"
        if body.exists():
            problems += [f"{page}: {p}" for p in stop_brand_errors(read_meta(page_dir(job_path, page)),
                                                                    body.read_text(encoding="utf-8"))]
    if problems:
        sys.exit("not ready for Strapi:\n- " + "\n- ".join(problems))
    payloads, sent = {}, {}
    for page in pages:
        payloads[page], sent[page] = page_payload(job_path, page)
    header = {k: facts["header"][k]["value"] for k in HEADER}
    author, editor = resolve_author_id(job["author"]), resolve_author_id(EDITOR)
    common = {"author": author, "editors": [editor], "indexable": bool(args.indexable),
              "publishedAt": None if args.draft else now()}
    country = {"name": job["country"], "slug": job["slug"], "code": job["iso"], **header,
               **payloads["country"], **common}
    record_path = job_path / "out" / "strapi_record.json"
    record = read_json(record_path) if record_path.exists() else {}
    existing = find_existing(job["slug"], record)
    plan = [f"country {job['slug']}: {'update id ' + str(existing['country_id']) if existing.get('country_id') else 'create'}"]
    plan += [f"{p}: {'update id ' + str(existing['subpages'][KIND[p]]) if KIND[p] in existing['subpages'] else 'create'}"
             for p in ("eor", "contractors") if p in pages]
    print("\n".join(plan) + f"\nindexable={common['indexable']} published={not args.draft}")
    print("\n".join(f"{p}: {len(sent[p])} chars of HTML" for p in pages))
    if not args.write:
        print("dry run — nothing written")
        return
    if existing.get("country_id"):
        cid = existing["country_id"]
        api(f"/country-guides/{cid}", "PUT", {"data": country})
    else:
        cid = api("/country-guides", "POST", {"data": country})["data"]["id"]
    out = {"country_id": cid, "subpages": dict(existing.get("subpages", {}))}
    write_json(record_path, out)
    for page in [p for p in ("eor", "contractors") if p in pages]:
        data = {"country": cid, "kind": KIND[page], **payloads[page], **common}
        sid = out["subpages"].get(KIND[page])
        if sid:
            api(f"/guide-subpages/{sid}", "PUT", {"data": data})
        else:
            out["subpages"][KIND[page]] = api("/guide-subpages", "POST", {"data": data})["data"]["id"]
        write_json(record_path, out)
    out["written_at"] = now()
    write_json(record_path, out)
    issues = [] if args.draft else readback(job["slug"], sent, pages)
    if issues:
        sys.exit("written, but:\n- " + "\n- ".join(issues))
    print(f"written: country {cid}, subpages {out['subpages']}")


if __name__ == "__main__":
    main()
