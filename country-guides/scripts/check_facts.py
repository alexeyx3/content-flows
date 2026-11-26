"""Merge and validate the country fact pack (facts.json). Schema: knowledge/facts-schema.md.

Usage:
  python3 scripts/check_facts.py --job jobs/<job> --merge   # facts.employment.json + facts.contractors.json -> facts.json
  python3 scripts/check_facts.py --job jobs/<job>           # validate facts.json
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date

from common import header_display, job_dir, read_json, write_json

HEADER_TEXT = ("minimumWage", "averageSalary", "incomeTax", "paidLeave", "publicHolidays",
               "probation", "noticePeriod")
HEADER = HEADER_TEXT + ("employerContributions",)
FACT_ID = re.compile(r"^F-\d{3}$")
TIERS = {"law", "official", "professional", "vendor"}
PAGES = {"country", "eor", "contractors"}
LISTS = ("facts", "contributions", "minimum_wage_history", "notice_by_tenure", "cost_scenarios",
         "unconfirmed")


def header_rate(contributions: list[dict]) -> float:
    return round(sum(float(c["employer_pct"]) for c in contributions if c.get("in_header", True)), 2)


def publication_header_errors(data: dict) -> list[str]:
    """The current CMS/frontend only support a percentage in this field."""
    if data.get("header", {}).get("employerContributions", {}).get("model") == "fixed":
        return ["Fixed employer levies require CMS/frontend display support before publication; "
                "never export a zero-percentage placeholder."]
    return []


def merge(parts: list[dict]) -> dict:
    """Combine scope files. Scalars must agree; lists are concatenated; header keys may come from either."""
    out: dict = {"header": {}}
    for part in parts:
        for key, value in part.items():
            if key == "header":
                for hk, hv in value.items():
                    if hk in out["header"] and out["header"][hk] != hv:
                        raise ValueError(f"header.{hk}: the two scopes disagree")
                    out["header"][hk] = hv
            elif key in LISTS:
                out.setdefault(key, []).extend(value)
            elif key in out and out[key] != value:
                raise ValueError(f"{key}: the two scopes disagree ({out[key]!r} vs {value!r})")
            else:
                out[key] = value
    return out


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    for key in ("country", "slug", "iso", "currency"):
        if not data.get(key):
            errors.append(f"{key}: missing")
    facts = data.get("facts", [])
    ids = [f.get("id") for f in facts]
    known = set(ids)
    for fid in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"{fid}: duplicate id")
    for f in facts:
        fid = f.get("id") or "?"
        if not FACT_ID.match(str(fid)):
            errors.append(f"{fid}: id must look like F-001")
        if not str(f.get("claim", "")).strip():
            errors.append(f"{fid}: no claim")
        src = f.get("source") or {}
        if not str(src.get("url", "")).startswith("https://"):
            errors.append(f"{fid}: source.url must be https")
        if not src.get("publisher"):
            errors.append(f"{fid}: source.publisher missing")
        if src.get("tier") not in TIERS:
            errors.append(f"{fid}: source.tier must be one of {sorted(TIERS)}")
        try:
            date.fromisoformat(str(f.get("accessed")))
        except ValueError:
            errors.append(f"{fid}: accessed must be an ISO date")
        if not str(f.get("quote", "")).strip():
            errors.append(f"{fid}: no supporting quote")
        if set(f.get("pages", [])) - PAGES or not f.get("pages"):
            errors.append(f"{fid}: pages must be a non-empty subset of {sorted(PAGES)}")

    def refs(where: str, items) -> None:
        for r in items or []:
            if r not in known:
                errors.append(f"{where}: unknown fact {r}")

    header = data.get("header", {})
    for key in HEADER:
        entry = header.get(key)
        fixed = (key == "employerContributions" and isinstance(entry, dict)
                 and entry.get("model") == "fixed")
        if not isinstance(entry, dict) or (entry.get("value") in (None, "") and not fixed):
            errors.append(f"header.{key}: missing")
            continue
        if not entry.get("facts"):
            errors.append(f"header.{key}: no supporting facts")
        refs(f"header.{key}", entry.get("facts"))
        if key in HEADER_TEXT:
            value = str(entry["value"])
            if len(value) > 32:
                errors.append(f"header.{key}: {len(value)} chars, max 32")
            if "," in value and not re.search(r"\d,\d{3}", value):
                errors.append(f"header.{key}: looks like commentary, keep the bare figure: {value!r}")
    contributions = data.get("contributions", [])
    for c in contributions:
        if not isinstance(c.get("employer_pct"), (int, float)):
            errors.append(f"contribution {c.get('name')!r}: employer_pct must be a number")
        if c.get("rounding", "nearest") not in {"nearest", "down", "whole_up"}:
            errors.append(f"contribution {c.get('name')!r}: rounding must be nearest, down or whole_up")
        floor = c.get("floor_monthly", 0)
        cap = c.get("cap_monthly")
        if not isinstance(floor, (int, float)) or floor < 0:
            errors.append(f"contribution {c.get('name')!r}: floor_monthly must be non-negative")
        elif cap is not None and (not isinstance(cap, (int, float)) or cap < floor):
            errors.append(f"contribution {c.get('name')!r}: cap_monthly must be at least floor_monthly")
        for period_key in ("cap_annual", "floor_annual"):
            if period_key in c and (not isinstance(c[period_key], (int, float)) or c[period_key] < 0):
                errors.append(f"contribution {c.get('name')!r}: {period_key} must be non-negative")
        refs(f"contribution {c.get('name')!r}", c.get("facts"))
    rate = (header.get("employerContributions") or {}).get("value")
    entry = header.get("employerContributions") or {}
    if entry.get("model") == "fixed":
        display = entry.get("display")
        if rate is not None:
            errors.append("fixed employerContributions must use value:null, never a percentage placeholder")
        if not isinstance(display, str) or not display.strip() or len(display) > 32 or "%" in display:
            errors.append("fixed employerContributions requires a short non-percentage display label")
        if any(c.get("in_header", True) for c in contributions):
            errors.append("fixed employerContributions must not hide in_header percentage contributions")
    elif entry.get("model", "percentage") != "percentage":
        errors.append("unknown employerContributions model")
    elif contributions and isinstance(rate, (int, float)) and not errors:
        if round(float(rate), 2) != header_rate(contributions):
            errors.append(f"header.employerContributions {rate} != sum of in_header employer_pct "
                          f"{header_rate(contributions)}")
    elif rate is not None and not isinstance(rate, (int, float)):
        errors.append("header.employerContributions must be a number")
    for key in ("minimum_wage_history", "notice_by_tenure", "cost_scenarios"):
        for item in data.get(key, []):
            refs(key, item.get("facts"))
            if key == "cost_scenarios":
                names = {c["name"] for c in contributions}
                included = item.get("include_contributions")
                if included is not None and (not isinstance(included, list) or not included or
                                              any(name not in names for name in included)):
                    errors.append("cost_scenarios: include_contributions must name known contributions")
                holiday = item.get("holiday_allowance_pct", 0)
                if not isinstance(holiday, (int, float)) or holiday < 0:
                    errors.append("cost_scenarios: holiday_allowance_pct must be non-negative")
                elif holiday:
                    for c in contributions:
                        if included is not None and c["name"] not in included:
                            continue
                        for monthly, annual in (("cap_monthly", "cap_annual"), ("floor_monthly", "floor_annual")):
                            if c.get(monthly) and annual not in c:
                                errors.append(f"cost_scenarios: holiday-inclusive annual model needs {annual} for {c['name']}")
                for name, base in item.get("contribution_bases", {}).items():
                    if name not in names or not isinstance(base, (int, float)) or base < 0:
                        errors.append(f"cost_scenarios: invalid assessment base for {name!r}")
    history = [h.get("date") for h in data.get("minimum_wage_history", [])]
    if history != sorted(history):
        errors.append("minimum_wage_history must be oldest first")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--merge", action="store_true")
    args = ap.parse_args()
    job = job_dir(args.job)
    if args.merge:
        parts = [read_json(job / f"facts.{scope}.json") for scope in ("employment", "contractors")]
        write_json(job / "facts.json", merge(parts))
        print("merged -> facts.json")
    data = read_json(job / "facts.json")
    errors = validate(data)
    if errors:
        sys.exit("BLOCK facts.json:\n- " + "\n- ".join(errors))
    print(f"PASS facts.json: {len(data['facts'])} facts, header complete, "
          f"employerContributions {header_display(data['header']['employerContributions'])}")


if __name__ == "__main__":
    main()
