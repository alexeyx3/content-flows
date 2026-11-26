#!/usr/bin/env python3
"""Validate and apply reviewed glossary related-content manifests."""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://cms.example.com/api"
TOKEN_FILE = ROOT.parent / "blog" / "config" / "strapi-api-token"
TYPES = {"terms": {"prerequisite", "next_step", "distinction"},
         "articles": {"application", "workflow", "comparison"}}
CAPS = {"terms": 6, "articles": 3}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def indexes(inventory: dict) -> tuple[dict, dict]:
    return ({x["slug"]: x for x in inventory["terms"]},
            {x["slug"]: x for x in inventory["articles"]})


def validate(manifest: list, inventory: dict) -> None:
    terms, articles = indexes(inventory)
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("Manifest must be a nonempty JSON array")
    seen_sources: set[str] = set()
    for row in manifest:
        slug = row["sourceSlug"]
        if slug in seen_sources or slug not in terms or row.get("sourceId") != terms[slug]["id"]:
            raise ValueError(f"Unknown, repeated, or misidentified source: {slug}")
        seen_sources.add(slug)
        for field, catalog in (("terms", terms), ("articles", articles)):
            items = row.get(field)
            if not isinstance(items, list) or len(items) > CAPS[field]:
                raise ValueError(f"{slug}: {field} must be a list with at most {CAPS[field]} entries")
            if not items and not str(row.get("empty" + field.title() + "Reason", "")).strip():
                raise ValueError(f"{slug}: empty {field} needs a reason")
            seen_destinations: set[str] = set()
            for item in items:
                target = item["slug"]
                if (target in seen_destinations or target not in catalog
                        or item.get("id") != catalog[target]["id"] or target == slug):
                    raise ValueError(f"{slug}: duplicate, self, unknown, or wrong-ID {field} target {target}")
                seen_destinations.add(target)
                if item.get("type") not in TYPES[field] or not str(item.get("reason", "")).strip():
                    raise ValueError(f"{slug}: {target} needs a valid relationship type and reason")
                if catalog[target].get("indexable") is not True:
                    raise ValueError(f"{slug}: nonindexable {field} target {target}")


def public_term(session: requests.Session, slug: str) -> dict:
    response = session.get(f"{API}/glossary-terms/{slug}/findBySlug?locale=en", timeout=30)
    response.raise_for_status()
    data = response.json().get("data") or {}
    if not data.get("publishedAt") or data.get("indexable") is False:
        raise ValueError(f"{slug}: source is unpublished or nonindexable")
    return data


def relation_slugs(data: dict, field: str) -> list[str]:
    return [item["slug"] for item in data["relatedTerms" if field == "terms" else "relatedArticles"]]


def wanted(row: dict, field: str) -> list[str]:
    return [item["slug"] for item in row[field]]


def live_page(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    if response.url != url:
        raise ValueError(f"Redirected URL: {url} -> {response.url}")
    return response.content.decode("utf-8")


def preview(manifest: list, inventory: dict, session: requests.Session) -> list[dict]:
    terms, articles = indexes(inventory)
    checked_urls: set[str] = set()
    plan = []
    for row in manifest:
        slug = row["sourceSlug"]
        current = public_term(session, slug)
        if current["id"] != row["sourceId"]:
            raise ValueError(f"{slug}: live source ID changed")
        for field, catalog, prefix in (("terms", terms, "glossary"),
                                       ("articles", articles, "blog")):
            for item in row[field]:
                target = item["slug"]
                url = f"https://example.com/{prefix}/{target}/"
                if url not in checked_urls:
                    live_page(session, url)
                    checked_urls.add(url)
                if target not in catalog:
                    raise ValueError(f"{slug}: target vanished from inventory: {target}")
        before = {field: relation_slugs(current, field) for field in TYPES}
        initial = {"terms": terms[slug]["relatedTerms"],
                   "articles": terms[slug]["relatedArticles"]}
        after = {field: wanted(row, field) for field in TYPES}
        if before != after and before != initial:
            raise ValueError(f"{slug}: live relations changed since inventory; refresh review before writing")
        plan.append({"slug": slug, "id": row["sourceId"], "before": before,
                     "after": after, "change": before != after})
    return plan


def verify_one(session: requests.Session, row: dict) -> None:
    slug = row["sourceSlug"]
    expected = {field: wanted(row, field) for field in TYPES}
    for attempt in range(6):
        data = public_term(session, slug)
        actual = {field: relation_slugs(data, field) for field in TYPES}
        if actual == expected:
            html = live_page(session, f"https://example.com/glossary/{slug}/")
            rendered = {}
            for field, title, prefix in (("terms", "Related terms", "glossary"),
                                         ("articles", "Related articles", "blog")):
                match = re.search(
                    rf'<h2 class="text-block-title">{title}</h2>(.*?)</section>', html, re.DOTALL)
                rendered[field] = (re.findall(rf'href="(/{prefix}/[a-z0-9-]+/)', match.group(1))
                                   if match else [])
            if all(rendered[field] == [f'/{"glossary" if field == "terms" else "blog"}/{target}/'
                                       for target in expected[field]] for field in TYPES):
                return
        if attempt < 5:
            time.sleep(2)
    raise ValueError(f"{slug}: related content failed public API or page verification")


def apply(manifest: list, plan: list[dict], session: requests.Session, receipt_dir: Path) -> int:
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("Strapi API token is empty")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    by_slug = {row["sourceSlug"]: row for row in manifest}
    updated = 0
    for item in plan:
        slug = item["slug"]
        row = by_slug[slug]
        if not item["change"]:
            print(f"{slug}: already matches reviewed manifest", flush=True)
            continue
        payload = {"data": {"relatedTerms": [x["id"] for x in row["terms"]],
                            "relatedArticles": [x["id"] for x in row["articles"]]}}
        response = session.put(f"{API}/glossary-terms/{item['id']}",
                               headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=45)
        response.raise_for_status()
        verify_one(session, row)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        receipt = {"sourceSlug": slug, "sourceId": item["id"], "updatedAt": stamp,
                   "before": item["before"], "after": item["after"], "verified": True}
        (receipt_dir / f"{stamp}-{slug}.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        updated += 1
        print(f"{slug}: updated and verified", flush=True)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preview", "apply", "verify"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--receipt-dir", type=Path, default=ROOT / "docs/related-content/receipts")
    args = parser.parse_args()
    manifest, inventory = read_json(args.manifest), read_json(args.inventory)
    validate(manifest, inventory)
    with requests.Session() as session:
        if args.command == "verify":
            for row in manifest:
                verify_one(session, row)
            print(f"verified {len(manifest)} glossary related-content blocks")
            return
        plan = preview(manifest, inventory, session)
        print(json.dumps({"sources": len(plan), "changes": sum(x["change"] for x in plan),
                          "terms": sum(len(x["after"]["terms"]) for x in plan),
                          "articles": sum(len(x["after"]["articles"]) for x in plan)}, indent=2), flush=True)
        if args.command == "apply":
            print(f"updated {apply(manifest, plan, session, args.receipt_dir)} sources", flush=True)


if __name__ == "__main__":
    main()
