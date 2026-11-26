#!/usr/bin/env python3
"""Submit verified, published Example Co blog articles to IndexNow."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "indexnow.json"
ENDPOINT = "https://api.indexnow.org/indexnow"
HOST = "example.com"
PREFIX = f"https://{HOST}/blog/"
RU_PREFIX = f"https://{HOST}/ru/blog/"


class PublicPageHTML(HTMLParser):
    """Read public page SEO controls without depending on HTML attribute order."""
    def __init__(self, value: str):
        super().__init__(convert_charrefs=True)
        self.canonicals: list[str] = []
        self.language = ""
        self.robots: list[str] = []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.language = attrs.get("lang") or ""
        if tag == "link" and "canonical" in (attrs.get("rel") or "").lower().split():
            self.canonicals.append(attrs.get("href", ""))
        if tag == "meta" and (attrs.get("name") or "").lower() in {"robots", "googlebot", "bingbot"}:
            self.robots.append(attrs.get("content") or "")


def public_translation_page(url: str, session: requests.Session) -> None:
    response = session.get(url, timeout=30, allow_redirects=False)
    response.raise_for_status()
    if response.status_code != 200 or response.url != url or getattr(response, "history", []):
        raise ValueError(f"Public translation URL redirects or is unavailable: {url}")
    page = PublicPageHTML(response.text)
    if page.canonicals != [url]:
        raise ValueError(f"Public canonical URL mismatch: {url}")
    if page.language.lower().split("-")[0] != "ru":
        raise ValueError(f"Public translation language is not Russian: {url}")
    headers = getattr(response, "headers", {})
    robots = page.robots + [value for key, value in headers.items() if key.lower() == "x-robots-tag"]
    if any(re.search(r"\b(?:noindex|none)\b", directive, re.I) for directive in robots):
        raise ValueError(f"Public translation is noindex: {url}")


def translation_article_url(job: Path, session: requests.Session) -> str:
    """Translation publication has its own receipt; never infer it from the draft."""
    record = json.loads((job / "publication" / "record.json").read_text(encoding="utf-8"))
    manifest = json.loads((job / "translation.json").read_text(encoding="utf-8"))
    if (record.get("published") is not True or not record.get("publishedAt")
            or record.get("indexable") is not True or record.get("readback_status") != "PASS"):
        raise ValueError(f"Translation is not published and indexable: {job}")
    if (record.get("locale") != "ru" or manifest.get("target_locale") != "ru"
            or manifest.get("source_locale") != "en"):
        raise ValueError(f"Translation publication locale mismatch: {job}")
    target_id = record.get("id")
    source_id = record.get("source_id")
    if (type(target_id) is not int or type(source_id) is not int or target_id <= 0
            or source_id <= 0 or target_id == source_id or source_id != manifest.get("source_id")):
        raise ValueError(f"Translation publication identity mismatch: {job}")
    slug = record.get("slug", "")
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9-]+", slug) or slug != manifest.get("slug"):
        raise ValueError(f"Invalid translation article slug: {slug!r}")
    cover = record.get("cover")
    if (not isinstance(cover, dict) or type(cover.get("id")) is not int
            or cover["id"] <= 0 or not isinstance(cover.get("url"), str) or not cover["url"].strip()):
        raise ValueError(f"Published translation cover is missing: {job}")
    # RU route independently verified against live pages, canonicals and sitemap.
    url = f"{RU_PREFIX}{slug}/"
    if "public_url" in record and record["public_url"] != url:
        raise ValueError(f"Translation public URL mismatch: {job}")
    public_translation_page(url, session)
    return url


def article_url(job: Path, session: requests.Session) -> str:
    config = job / "job.yaml"
    if config.exists() and re.search(r"^article_translation_version:\s*1\b", config.read_text(encoding="utf-8"), re.M):
        return translation_article_url(job, session)
    record = json.loads((job / "out" / "strapi_record.json").read_text(encoding="utf-8"))
    if record.get("published") is not True:
        raise ValueError(f"Article is not published: {job}")
    slug = record.get("slug", "")
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError(f"Invalid article slug: {slug!r}")
    url = f"{PREFIX}{slug}/"
    response = session.get(url, timeout=30)
    response.raise_for_status()
    if response.url != url or f'<link rel="canonical" href="{url}"' not in response.text:
        raise ValueError(f"Public canonical URL mismatch: {url}")
    return url


def verified_key(session: requests.Session) -> tuple[str, str]:
    location = json.loads(CONFIG.read_text(encoding="utf-8"))["keyLocation"]
    parsed = urlparse(location)
    if (parsed.scheme != "https" or parsed.netloc != HOST or parsed.query or parsed.fragment
            or not re.fullmatch(r"/[A-Za-z0-9-]{8,128}\.txt", parsed.path)):
        raise ValueError("IndexNow key file must be at the root of Example Co")
    key = parsed.path[1:-4]
    response = session.get(location, timeout=30)
    response.raise_for_status()
    if response.text.strip() != key:
        raise ValueError("Public IndexNow key file does not match its filename")
    return key, location


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, action="append", required=True,
                        help="Published article job; repeat for a batch")
    parser.add_argument("--apply", action="store_true", help="Send the IndexNow POST")
    args = parser.parse_args()
    with requests.Session() as session:
        urls = [article_url(job, session) for job in args.job]
        if len(urls) != len(set(urls)) or len(urls) > 10_000:
            raise ValueError("IndexNow submission needs unique URLs, at most 10,000")
        key, location = verified_key(session)
        if not args.apply:
            print(json.dumps({"ready": True, "count": len(urls), "urls": urls}, indent=2))
            return
        response = session.post(ENDPOINT, json={"host": HOST, "key": key,
                                                "keyLocation": location, "urlList": urls}, timeout=45)
    receipt = {"submittedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "endpoint": ENDPOINT, "keyLocation": location, "count": len(urls),
               "urls": urls, "httpStatus": response.status_code,
               "accepted": response.status_code in (200, 202), "response": response.text[:500]}
    directory = ROOT / "docs" / "indexnow"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now(timezone.utc):%Y-%m-%dT%H%M%SZ}.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(urls), "httpStatus": response.status_code,
                      "accepted": receipt["accepted"], "receipt": str(path)}))
    if not receipt["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
