#!/usr/bin/env python3
"""Submit verified, published Example Co glossary URLs to IndexNow."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "indexnow.json"
SITEMAP = "https://example.com/sitemap_glossary.xml"
HOST = "example.com"
PREFIX = "https://example.com/glossary/"
ENDPOINT = "https://api.indexnow.org/indexnow"
XML_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def glossary_url(url: str) -> str:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.netloc != HOST or parsed.query or parsed.fragment
            or not url.startswith(PREFIX) or url == PREFIX
            or not re.fullmatch(r"[a-z0-9-]+", url[len(PREFIX):].rstrip("/"))
            or not url.endswith("/")):
        raise ValueError(f"Not a canonical glossary article URL: {url}")
    return url


def published_urls_from_sitemap(session: requests.Session) -> list[str]:
    response = session.get(SITEMAP, timeout=30)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    urls = [element.text for element in root.findall(f"{XML_NS}url/{XML_NS}loc")]
    articles = sorted({glossary_url(url) for url in urls if url and url.startswith(PREFIX) and url != PREFIX})
    if not articles:
        raise ValueError("Glossary sitemap contains no article URLs")
    return articles


def published_url_from_job(job: Path, session: requests.Session) -> str:
    record = json.loads((job / "out" / "strapi-record.json").read_text(encoding="utf-8"))
    if record.get("status") != "published":
        raise ValueError(f"Job is not published: {job}")
    url = glossary_url(f"{PREFIX}{record['slug']}/")
    response = session.get(url, timeout=30)
    response.raise_for_status()
    if response.url != url:
        raise ValueError(f"Public URL redirected: {url} -> {response.url}")
    return url


def verified_key(session: requests.Session) -> tuple[str, str]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    location = config["keyLocation"]
    parsed = urlparse(location)
    if (parsed.scheme != "https" or parsed.netloc != HOST or parsed.query or parsed.fragment
            or not re.fullmatch(r"/[A-Za-z0-9-]{8,128}\.txt", parsed.path)):
        raise ValueError("IndexNow keyLocation must be a root-level key file on Example Co")
    key = parsed.path[1:-4]
    response = session.get(location, timeout=30)
    response.raise_for_status()
    if response.text.strip() != key:
        raise ValueError("Public IndexNow key file does not match its filename")
    return key, location


def submit(urls: list[str], session: requests.Session) -> dict:
    if not urls or len(urls) > 10_000 or len(urls) != len(set(urls)):
        raise ValueError("IndexNow submission needs 1–10,000 unique URLs")
    for url in urls:
        glossary_url(url)
    key, location = verified_key(session)
    response = session.post(ENDPOINT, json={"host": HOST, "key": key,
                                          "keyLocation": location, "urlList": urls}, timeout=45)
    receipt = {"submittedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "endpoint": ENDPOINT, "keyLocation": location, "count": len(urls),
               "urls": urls, "httpStatus": response.status_code,
               "accepted": response.status_code in (200, 202), "response": response.text[:500]}
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--all", action="store_true", help="all published article URLs from the live sitemap")
    source.add_argument("--job", type=Path, help="one published job, after public-page verification")
    parser.add_argument("--apply", action="store_true", help="send the IndexNow POST")
    args = parser.parse_args()
    with requests.Session() as session:
        urls = (published_urls_from_sitemap(session) if args.all
                else [published_url_from_job(args.job, session)])
        verified_key(session)
        if not args.apply:
            print(json.dumps({"ready": True, "count": len(urls), "urls": urls}, indent=2))
            return
        receipt = submit(urls, session)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    receipt_dir = ROOT / "docs" / "indexnow" if args.all else args.job / "indexnow"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{stamp}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"count": receipt["count"], "httpStatus": receipt["httpStatus"],
                      "accepted": receipt["accepted"], "receipt": str(receipt_path)}))
    if not receipt["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
