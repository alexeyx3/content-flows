"""Map of the site's live URLs -> config/site-urls.json.

Needed so that agents place internal links only to pages that exist, not to
invented ones. The source is the production sitemap index.

Every entry has `lang`: the page language. An English article links only to English pages.
Some sites keep articles in several languages on the same path pattern (for example
`/blog/<transliteration>/`), so the address does not tell them apart (otherwise an English
article could link to a page in another language). Localised versions are dropped
(the blog exists only in the default language) and so are legal pages: an article has no reason to
link to an offer or terms page.

Rebuild before every batch of articles: the site is alive, and sections appear and move.

Usage:
  python3 scripts/fetch_site_urls.py --date 2026-09-03
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = "https://example.com/sitemap-index.xml"
LOC = re.compile(r"<loc>([^<]+)</loc>")
LOCALIZED = re.compile(r"^/[a-z]{2}(-[a-z]{2})?/")
# The site's legal layer: terms, policies and agreement pages. Matched both by
# substrings anywhere in the path and by path prefixes (a legal section such as
# /legal/ and agreement pages such as /sla-standard/). A link from an article
# to an agreement is useless to the reader, so these do not enter the linking map.
# Adjust both lists to the legal pages of your own site.
LEGAL_SUBSTRINGS = (
    "terms-of-service", "terms-and-conditions", "privacy", "addendum", "cookie",
    "dpa", "acceptable-use", "sub-processors", "notice",
)
LEGAL_PREFIXES = ("/legal/", "/sla-")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "blog-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse_locs(xml: str) -> list[str]:
    return LOC.findall(xml)


HTML_LANG = re.compile(r"<html[^>]*\blang\s*=\s*[\"\']([a-zA-Z-]+)", re.I)


CYRILLIC = re.compile(r"[А-Яа-яЁё]")
TITLE = re.compile(r"<title[^>]*>(.*?)</title>|<h1[^>]*>(.*?)</h1>", re.I | re.S)


def page_lang(html: str) -> str:
    """Page language.

    Some sites set the same `<html lang>` on every page, whatever the language of the
    article. So the heading is checked first: Cyrillic in the title or h1 means a Russian
    page; otherwise the `<html lang>` attribute is used. The body cannot be used: Cyrillic
    can also appear in the footer and menu of English pages.
    """
    m = TITLE.search(html)
    heading = next((g for g in (m.groups() if m else ()) if g), "")
    if CYRILLIC.search(heading):
        return "ru"
    m = HTML_LANG.search(html)
    return m.group(1).split("-")[0].lower() if m else ""


def filter_urls(urls: list[str]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for url in urls:
        path = url.split("example.com", 1)[-1] or "/"
        if LOCALIZED.match(path):
            continue
        if any(k in path for k in LEGAL_SUBSTRINGS):
            continue
        if any(path.startswith(k) for k in LEGAL_PREFIXES):
            continue
        if url in seen:
            continue
        seen.add(url)
        slug = path.strip("/").split("/")[-1]
        rows.append({
            "url": url,
            "path": path,
            "label": slug.replace("-", " ") if slug else "home",
        })
    return sorted(rows, key=lambda r: r["path"])


def detect_language(row: dict) -> tuple[str, str]:
    try:
        return page_lang(fetch(row["url"])), ""
    except Exception as exc:
        return "", type(exc).__name__


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="build date, YYYY-MM-DD (passed explicitly)")
    ap.add_argument("--output", default=str(ROOT / "config" / "site-urls.json"))
    args = ap.parse_args()

    urls: list[str] = []
    for sitemap in parse_locs(fetch(INDEX)):
        urls.extend(parse_locs(fetch(sitemap)))
    rows = filter_urls(urls)

    # Take the language from the page: the address does not always distinguish the language of an article.
    with ThreadPoolExecutor(max_workers=6) as executor:
        for row, (lang, error) in zip(rows, executor.map(detect_language, rows)):
            row["lang"] = lang
            if error:
                print(f"  language not detected: {row['path']} ({error})")

    by_lang: dict[str, int] = {}
    for row in rows:
        by_lang[row["lang"] or "?"] = by_lang.get(row["lang"] or "?", 0) + 1
    print("languages:", ", ".join(f"{k}={v}" for k, v in sorted(by_lang.items())))

    Path(args.output).write_text(
        json.dumps({"generated": args.date, "count": len(rows), "urls": rows},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{args.output}: {len(rows)} addresses out of {len(urls)} in the site map")


if __name__ == "__main__":
    main()
