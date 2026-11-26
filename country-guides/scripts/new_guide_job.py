"""Create a country job: three page folders compatible with the blog v2 scripts.

Usage: python3 scripts/new_guide_job.py --slug germany [--date 2026-10-07]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date

from common import HINTS, AUTHOR, EDITOR, PAGES, ROOT, h1, page_dir, queue, save_queue, write_json
from check_cms_country import check_country

PROGRESS = """# {name} — country guide job

## Request and decisions

## Stage

Job created {created}.

## Done and checked

## Open questions

## Review (Google Docs)

## Strapi
"""


def create(slug: str, created: str) -> str:
    q = queue()
    entry = next((c for c in q["countries"] if c["slug"] == slug), None)
    if not entry:
        sys.exit(f"{slug}: not in config/queue.json")
    job = ROOT / "jobs" / f"{created}-{slug}"
    if job.exists():
        sys.exit(f"{job} already exists")
    compatibility = check_country(entry["iso"], slug)
    if compatibility["status"] != "PASS":
        sys.exit("CMS compatibility BLOCK before job creation:\n- " +
                 "\n- ".join(compatibility["errors"]))
    for sub in ("raw", "serp", "research", "semantics"):
        (job / sub).mkdir(parents=True)
    write_json(job / "raw/cms-compatibility.json", compatibility)
    geos = ["us", "gb", "au", entry["geo_key"]] if entry["geo_key"] not in ("us", "gb", "au") else ["us", "gb", "au"]
    write_json(job / "job.json", {
        "country": entry["name"], "slug": slug, "iso": entry["iso"], "eor_query": entry["eor_query"],
        "geos": geos, "author": AUTHOR, "editor": EDITOR, "created": created,
        "query_name": entry["query_name"], "queue_order": entry["order"], "icp": entry["icp"], "pilot": entry["pilot"]})
    (job / "progress.md").write_text(PROGRESS.format(name=entry["name"], created=created), encoding="utf-8")
    for page in PAGES:
        d = page_dir(job, page)
        d.mkdir(parents=True)
        (d / "job.yaml").write_text(
            f"topic: {h1(entry['name'], page, entry['iso'])}\nlanguage: en\nworkflow_version: 2\n"
            f"author: {AUTHOR}\npage: {page}\ncountry_slug: {slug}\n", encoding="utf-8")
    # Optional research memory: earlier verified facts and vendor notes for the country are
    # copied into the job as hints (leads to reopen at the primary source, never a source).
    for name, target in ((f"{slug}.yaml", "hint-facts.yaml"), (f"{slug}--vendors.yaml", "hint-vendors.yaml")):
        if (HINTS / name).exists():
            shutil.copy2(HINTS / name, job / "raw" / target)
    entry["status"] = "in_progress"
    save_queue(q)
    return str(job.relative_to(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()
    print(create(args.slug, args.date))


if __name__ == "__main__":
    main()
