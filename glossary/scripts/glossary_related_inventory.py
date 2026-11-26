#!/usr/bin/env python3
"""Snapshot live English glossary terms and blog articles for related-content review."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

import requests

API = "https://cms.example.com/api"
GLOSSARY_SITEMAP = "https://example.com/sitemap_glossary.xml"
BLOG_SITEMAP = "https://example.com/sitemap_blog.xml"


def sitemap_slugs(session: requests.Session, url: str, prefix: str) -> set[str]:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    return {value.rsplit("/", 2)[-2] for element in root.iter()
            if element.tag.endswith("loc") and (value := element.text)
            and value.startswith(prefix) and value != prefix and value.endswith("/")}


def list_collection(session: requests.Session, name: str, fields: tuple[str, ...] = ()) -> list[dict]:
    entries = []
    page = 1
    while True:
        params = {"pagination[pageSize]": 100, "pagination[page]": page}
        params.update({f"fields[{i}]": field for i, field in enumerate(fields)})
        response = session.get(f"{API}/{name}", params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        entries.extend(result["data"])
        if page >= result["meta"]["pagination"]["pageCount"]:
            return entries
        page += 1


def term_detail(slug: str) -> dict:
    response = requests.get(f"{API}/glossary-terms/{slug}/findBySlug?locale=en", timeout=30)
    response.raise_for_status()
    value = response.json()["data"]
    if value.get("indexable") is not True or not value.get("publishedAt") or value.get("locale") != "en":
        raise ValueError(f"Not a published, indexable English term: {slug}")
    return {"id": value["id"], "term": value["term"], "slug": slug,
            "definition": value.get("definition", ""), "indexable": True,
            "relatedTerms": [item["slug"] for item in value.get("relatedTerms") or []],
            "relatedArticles": [item["slug"] for item in value.get("relatedArticles") or []]}


def snapshot() -> dict:
    with requests.Session() as session:
        term_slugs = sitemap_slugs(session, GLOSSARY_SITEMAP, "https://example.com/glossary/")
        blog_slugs = sitemap_slugs(session, BLOG_SITEMAP, "https://example.com/blog/")
        listed_terms = list_collection(session, "glossary-terms")
        listed_term_slugs = {item["slug"] for item in listed_terms if item.get("locale") == "en"}
        if not term_slugs or term_slugs != listed_term_slugs:
            raise ValueError("English glossary sitemap and public Strapi list differ; investigate before snapshot")
        articles = list_collection(session, "articles", ("slug", "title", "locale", "publishedAt", "indexable"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        terms = sorted(pool.map(term_detail, term_slugs), key=lambda item: item["slug"])
    articles = sorted(({"id": item["id"], "title": item["title"], "slug": item["slug"],
                        "indexable": True} for item in articles
                       if item["slug"] in blog_slugs and item.get("locale") == "en"
                       and item.get("publishedAt") and item.get("indexable") is True),
                      key=lambda item: item["slug"])
    if not articles:
        raise ValueError("No published, indexable English blog articles found")
    return {"snapshotDate": datetime.now(timezone.utc).date().isoformat(),
            "sources": {"glossarySitemap": GLOSSARY_SITEMAP, "blogSitemap": BLOG_SITEMAP},
            "terms": terms, "articles": articles}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = snapshot()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.out}: {len(result['terms'])} terms, {len(result['articles'])} articles")


if __name__ == "__main__":
    main()
