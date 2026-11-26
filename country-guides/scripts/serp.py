"""Fetch the search results for the three pages of a country and measure what each geo adds.

Runs the blog's fetch_google_serp.py (XMLRiver) and build_article_serp_brief.py per page with
this project's geos, then writes:
  serp/<page>.csv, serp/<page>.features.json, serp/<page>.serp_synthesis.md, …competitor_structures.csv
  serp/geo-overlap.md     — URLs of the top 10 per geo and what GB/AU add beyond US + the country
  serp/rankings.md        — result pages that look like vendor rankings (best/top/providers)

Usage: python3 scripts/serp.py --job jobs/<job> [--page country|eor|contractors] [--skip-fetch]
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import defaultdict

from common import BLOG_SCRIPTS, PAGES, ROOT, job_dir, load_job

RANKING = re.compile(r"\b(best|top \d+|top|providers|companies|platforms|services)\b", re.I)


def queries(job: dict, page: str) -> list[str]:
    n = job["query_name"]
    if page == "country":
        return [f"hiring in {n}", f"{n} minimum wage", f"average salary in {n}", f"{n} labor law"]
    if page == "eor":
        base = job["eor_query"]
        extra = f"employer of record in {n}"
        return [base, f"best employer of record {n}"] + ([extra] if extra != base else [])
    return [f"hire contractors in {n}", f"independent contractor {n}", f"how to pay contractors in {n}"]


def fetch(job_path, job: dict, page: str) -> None:
    out = job_path / "serp"
    cmd = [sys.executable, str(BLOG_SCRIPTS / "fetch_google_serp.py"),
           "--geos-file", str(ROOT / "config" / "geos.json"), "--top-n", "10",
           "--serp-features", "--ai-overview",
           "--output-file", str(out / f"{page}.csv"),
           "--features-output-file", str(out / f"{page}.features.json")]
    for g in job["geos"]:
        cmd += ["--geo", g]
    for q in queries(job, page):
        cmd += ["--query", q]
    subprocess.run(cmd, check=True)
    rows = list(csv.DictReader((out / f"{page}.csv").open(encoding="utf-8")))
    if not any(r["block"] == "organic" for r in rows):
        sys.exit(f"{page}: empty SERP — retry once before building anything")
    refill(out, job, page)
    subprocess.run([sys.executable, str(BLOG_SCRIPTS / "build_article_serp_brief.py"),
                    "--input-file", str(out / f"{page}.csv"),
                    "--features-file", str(out / f"{page}.features.json"),
                    "--workers", "4",
                    "--output-prefix", str(out / page)], check=True)


def empty_pairs(path, job: dict, page: str) -> list[tuple[str, str]]:
    have = {(r["query"], r["geo_key"]) for r in csv.DictReader(path.open(encoding="utf-8"))
            if r["block"] == "organic"}
    return [(q, g) for q in queries(job, page) for g in job["geos"] if (q, g) not in have]


def refill(out, job: dict, page: str) -> None:
    """XMLRiver sometimes returns an empty page for one query×geo; retry those once and append."""
    path = out / f"{page}.csv"
    for q, g in empty_pairs(path, job, page):
        tmp = out / f"{page}.retry.csv"
        subprocess.run([sys.executable, str(BLOG_SCRIPTS / "fetch_google_serp.py"),
                        "--geos-file", str(ROOT / "config" / "geos.json"), "--top-n", "10",
                        "--geo", g, "--query", q, "--output-file", str(tmp)], check=True)
        extra = [r for r in csv.DictReader(tmp.open(encoding="utf-8")) if r["block"] == "organic"]
        tmp.unlink()
        if extra:
            with path.open("a", encoding="utf-8", newline="") as f:
                csv.DictWriter(f, fieldnames=list(extra[0].keys())).writerows(extra)
        print(f"refill {page} «{q}» {g}: {len(extra)} rows")


def overlap_report(job_path, job: dict) -> str:
    country_geo = job["geos"][-1]
    lines = ["# What each geo adds", "",
             f"Base = US + {country_geo.upper()}. Extra geos are worth keeping only if they bring useful pages the base does not have.", ""]
    totals = defaultdict(lambda: [0, 0])
    for page in PAGES:
        path = job_path / "serp" / f"{page}.csv"
        if not path.exists():
            continue
        by = defaultdict(lambda: defaultdict(set))
        for r in csv.DictReader(path.open(encoding="utf-8")):
            if r["block"] == "organic" and int(r["position"] or 99) <= 10:
                by[r["query"]][r["geo_key"]].add(r["url"].split("#")[0].rstrip("/"))
        lines += [f"## {page}", "", "| query | " + " | ".join(job["geos"]) + " | new from gb | new from au |",
                  "|---|" + "---|" * (len(job["geos"]) + 2)]
        for q, geos in by.items():
            if any(not geos.get(g) for g in job["geos"]):
                lines.append(f"| {q} | " + " | ".join(str(len(geos.get(g, set()))) for g in job["geos"]) +
                             " | — | — | (a geo returned nothing — excluded from totals)")
                continue
            base = geos.get("us", set()) | geos.get(country_geo, set())
            new = {g: sorted(geos.get(g, set()) - base) for g in ("gb", "au")}
            for g in ("gb", "au"):
                totals[g][0] += len(new[g])
                totals[g][1] += len(geos.get(g, set()))
            lines.append(f"| {q} | " + " | ".join(str(len(geos.get(g, set()))) for g in job["geos"]) +
                         f" | {len(new['gb'])} | {len(new['au'])} |")
            for g in ("gb", "au"):
                for url in new[g]:
                    lines.append(f"|  ↳ {g} only | {url} |" + " |" * (len(job["geos"]) + 1))
        lines.append("")
    lines += ["## Totals", ""] + [f"- {g}: {a} of {b} top-10 URLs are not in US + {country_geo.upper()}"
                                  for g, (a, b) in totals.items()]
    return "\n".join(lines) + "\n"


def rankings_report(job_path) -> str:
    seen, lines = set(), ["# Ranking-like results (open them; count entries and criteria)", ""]
    for page in PAGES:
        path = job_path / "serp" / f"{page}.csv"
        if not path.exists():
            continue
        for r in csv.DictReader(path.open(encoding="utf-8")):
            if r["block"] == "organic" and RANKING.search(r["title"]) and r["url"] not in seen:
                seen.add(r["url"])
                lines.append(f"- [{page}] {r['title']} — {r['url']} ({r['geo_key']}, #{r['position']}, «{r['query']}»)")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--page", choices=PAGES)
    ap.add_argument("--skip-fetch", action="store_true", help="only rebuild the reports")
    ap.add_argument("--refill", action="store_true", help="retry empty query×geo pairs, rebuild structures")
    args = ap.parse_args()
    job_path = job_dir(args.job)
    job = load_job(job_path)
    for page in ([args.page] if args.page else PAGES):
        if args.refill:
            refill(job_path / "serp", job, page)
            subprocess.run([sys.executable, str(BLOG_SCRIPTS / "build_article_serp_brief.py"),
                            "--input-file", str(job_path / "serp" / f"{page}.csv"),
                            "--features-file", str(job_path / "serp" / f"{page}.features.json"),
                            "--workers", "4",
                            "--output-prefix", str(job_path / "serp" / page)], check=True)
        elif not args.skip_fetch:
            fetch(job_path, job, page)
    (job_path / "serp" / "geo-overlap.md").write_text(overlap_report(job_path, job), encoding="utf-8")
    (job_path / "serp" / "rankings.md").write_text(rankings_report(job_path), encoding="utf-8")
    print("serp/geo-overlap.md, serp/rankings.md written")


if __name__ == "__main__":
    main()
