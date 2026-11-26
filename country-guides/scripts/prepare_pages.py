"""Lay the country-level inputs out into each page folder in the blog v2 format.

Writes per page: evidence.md (F- facts + C- calculations + E- rows of evidence.md + V- rows of
evidence.vendors.md),
research.md (all research/*.md of the country), expert_quotes.json (empty by design: guides
carry only verbatim external quotes from evidence). Run after evidence, before the visual plan;
rerun whenever facts.json, derived.json or evidence.md change.

Usage: python3 scripts/prepare_pages.py --job jobs/<job>
"""
from __future__ import annotations

import argparse
import re
import sys

from check_facts import validate
from common import PAGES, job_dir, page_dir, read_json, write_json

HEAD = ("| claim_id | claim | section | source_url | source_tier | supporting_quote | last_checked | "
        "entailment_verdict |\n|---|---|---|---|---|---|---|---|\n")
NO_QUOTES = {"version": 1, "quotes": [],
             "omission_reason": "Country guides carry only verbatim external quotes recorded as E- rows "
                                "in evidence.md and inserted by the writer; no staff comments."}


def cell(value) -> str:
    return re.sub(r"\s+", " ", str(value)).replace("|", "/").strip()


def fact_rows(facts: dict, derived: dict) -> list[str]:
    rows = []
    fact_verdicts = {}
    for f in facts["facts"]:
        s = f["source"]
        verdict = "supports"
        claim = cell(f["claim"])
        if "[summary]" in f["quote"].lower():
            # An opened page summary is not an exact source passage. Retain the
            # lead, but do not grant publication support without corroboration.
            verdict = "partial"
        if f.get("status") in {"restricted", "unconfirmed"}:
            verdict = "partial"
            claim = f"RESTRICTED — do not use: {claim}"
        if f.get("status") == "superseded":
            # Kept for the audit trail; the writer must use the row named in superseded_by.
            verdict = "no"
            claim = f'SUPERSEDED by {f.get("superseded_by", "?")} — do not use: {claim}'
        fact_verdicts[f["id"]] = verdict
        rows.append(f'| {f["id"]} | {claim} | {cell(f.get("topic", ""))} | {s["url"]} | '
                    f'{s["tier"]} | {cell(f["quote"])} | {f["accessed"]} | {verdict} |')
    for r in derived.get("rows", []):
        inputs = [fact_verdicts.get(fid, "supports") for fid in r["facts"]]
        verdict = "no" if "no" in inputs else "partial" if "partial" in inputs else "supports"
        claim = cell(r["claim"])
        if verdict != "supports":
            claim = f"RESTRICTED INPUTS — do not use: {claim}"
        rows.append(f'| {r["id"]} | {claim} | calculation | {r["source_url"]} | derived | '
                    f'{cell(r["methodology"])} (facts: {", ".join(r["facts"])}) | — | {verdict} |')
    return rows


def evidence_rows(text: str) -> list[str]:
    return [l for l in text.splitlines() if re.match(r"^\|\s*[EV]-\d+\s*\|", l)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    job = job_dir(args.job)
    facts = read_json(job / "facts.json")
    errors = validate(facts)
    if errors:
        sys.exit("facts.json is not valid — run check_facts.py")
    derived = read_json(job / "derived.json") if (job / "derived.json").exists() else {"rows": []}
    ev = "\n".join((job / name).read_text(encoding="utf-8")
                   for name in ("evidence.md", "evidence.vendors.md") if (job / name).exists())
    rows = fact_rows(facts, derived) + evidence_rows(ev)
    research = "\n\n".join(f"<!-- {p.name} -->\n" + p.read_text(encoding="utf-8")
                           for p in sorted((job / "research").glob("*.md")))
    if not research.strip():
        sys.exit("research/ is empty — run the research stage first")
    for page in PAGES:
        d = page_dir(job, page)
        (d / "evidence.md").write_text(f"# Evidence — {facts['country']} ({page})\n\n" + HEAD + "\n".join(rows) + "\n",
                                       encoding="utf-8")
        (d / "research.md").write_text(research, encoding="utf-8")
        if not (d / "expert_quotes.json").exists():
            write_json(d / "expert_quotes.json", NO_QUOTES)
    print(f"{len(rows)} evidence rows ({sum(r.startswith('| E-') for r in rows)} E-) laid out into {len(PAGES)} pages")


if __name__ == "__main__":
    main()
