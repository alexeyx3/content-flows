"""Deterministic calculations from facts.json -> derived.json (IDs C-001…).

Arithmetic is done here, not by a model: the employer's cost of a salary is the figure most
often wrong on competitor pages and the base of the cost charts.

For every cost scenario: each employer contribution =
max(0, min(gross, cap_monthly) - floor_monthly) × employer_pct (floor defaults to zero);
all employer contributions are included (also in_header:false ones), so the effective rate can
differ from the header rate — the methodology says so. A sourced rounding rule can truncate
to the output precision ("down") or round up to a whole currency unit ("whole_up").

Country-specific calculations go into <job>/calc_spec.json, written by the orchestrator:

  {"scenarios": [{"label": "Full-time minimum wage", "gross_monthly": 2409.33, "facts": ["F-001"]}],
   "vars": {"min_wage": {"value": 13.90, "facts": ["F-001"]}, "hours": {"value": 173.33, "facts": []}},
   "items": [{"claim": "Full-time minimum-wage pay is €{value:,.2f} a month.",
              "expr": "min_wage * hours", "methodology": "€13.90 × 173.33 h (40 h × 52 / 12)"}]}

Extra scenarios run through the same contribution logic; items are arithmetic over vars only
(evaluated without builtins), each becoming a C- row whose facts are the union of its vars' facts.
Use calc_spec.monthly_only: true when ordinary-month wage scenarios do not establish annual cost.
Optional calc_spec.calculation_decimals (0–6, default2) preserves source monetary precision;
component rounding is a budget convention, not a statutory remittance rule.

Usage: python3 scripts/calc.py --job jobs/<job>
"""
from __future__ import annotations

import argparse
from math import ceil
import re
import sys
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN

from common import job_dir, read_json, write_json


def currency_prefix(data: dict) -> str:
    """€ and ֏ attach to the number; a letter code (AED) needs a space."""
    sym = data.get("currency_symbol") or data["currency"]
    return sym + " " if sym[-1].isalpha() else sym


def calculation_decimals(data: dict) -> int:
    decimals = data.get("calculation_decimals", 2)
    if isinstance(decimals, bool) or not isinstance(decimals, int) or not 0 <= decimals <= 6:
        raise ValueError("calculation_decimals must be an integer from 0 to 6")
    return decimals


def money(x: float, decimals: int = 2) -> float:
    return round(x + 1e-9, decimals)


def contribution_amount(base: float, contribution: dict, decimals: int = 2) -> float:
    rounding = contribution.get("rounding", "nearest")
    if rounding == "nearest":
        return money(base * float(contribution["employer_pct"]) / 100, decimals)
    amount = Decimal(str(base)) * Decimal(str(contribution["employer_pct"])) / Decimal("100")
    if rounding == "down":
        return float(amount.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_DOWN))
    if rounding == "whole_up":
        return float(amount.quantize(Decimal(1), rounding=ROUND_CEILING))
    raise ValueError(f"Unknown contribution rounding: {rounding!r}")


def scenario_rows(data: dict, *, monthly_only: bool = False) -> list[dict]:
    decimals = calculation_decimals(data)

    def rounded(value):
        return money(value, decimals)

    facts = {f["id"]: f for f in data["facts"]}
    all_contributions = data.get("contributions", [])
    if not all_contributions:
        return []
    cur = currency_prefix(data)
    rows = []
    for s in data.get("cost_scenarios", []):
        contributions = all_contributions
        included = s.get("include_contributions")
        if included is not None:
            names = {c["name"] for c in all_contributions}
            if not isinstance(included, list) or not included or set(included) - names:
                raise ValueError("Scenario include_contributions must name known contributions")
            contributions = [c for c in all_contributions if c["name"] in included]
        gross = float(s["gross_monthly"])
        assessment_bases = s.get("contribution_bases", {})
        parts = []
        for c in contributions:
            assessment_base = float(assessment_bases.get(c["name"], gross))
            if assessment_base < 0:
                raise ValueError(f"Negative contribution assessment base: {c['name']}")
            floor = float(c.get("floor_monthly", 0))
            cap = float(c["cap_monthly"]) if c.get("cap_monthly") is not None else None
            if floor < 0 or (cap is not None and cap < floor):
                raise ValueError(f"Invalid contribution earnings band: {c['name']}")
            capped_gross = min(assessment_base, cap) if cap is not None else assessment_base
            base = max(0.0, capped_gross - floor)
            parts.append({"name": c["name"], "amount": contribution_amount(base, c, decimals),
                          "employer_pct": c["employer_pct"], "capped": capped_gross < assessment_base,
                          "contribution_base": base})
        total = rounded(sum(p["amount"] for p in parts))
        holiday_pct = float(s.get("holiday_allowance_pct", 0))
        rounded_up = [c["name"] for c in contributions if c.get("rounding") == "whole_up"]
        annual_extra = {} if monthly_only else {"total_annual_cost": rounded((gross + total) * 12)}
        if monthly_only and holiday_pct:
            raise ValueError("monthly_only cannot be combined with a holiday-inclusive annual scenario")
        if holiday_pct:
            if holiday_pct < 0 or assessment_bases:
                raise ValueError("Holiday allowance with custom assessment bases needs an explicit calc_spec model")
            if rounded_up:
                raise ValueError("Holiday allowance with whole-unit contribution rounding needs a monthly model")
            annual_salary = rounded(gross * 12)
            holiday_amount = rounded(annual_salary * holiday_pct / 100)
            annual_gross = rounded(annual_salary + holiday_amount)
            annual_parts = []
            for c in contributions:
                if c.get("cap_monthly") is not None and "cap_annual" not in c:
                    raise ValueError(f"Holiday-inclusive annual model needs cap_annual: {c['name']}")
                if c.get("floor_monthly", 0) and "floor_annual" not in c:
                    raise ValueError(f"Holiday-inclusive annual model needs floor_annual: {c['name']}")
                base = min(annual_gross, float(c["cap_annual"])) if "cap_annual" in c else annual_gross
                base = max(0.0, base - float(c.get("floor_annual", 0)))
                annual_parts.append(contribution_amount(base, c, decimals))
            annual_contributions = rounded(sum(annual_parts))
            annual_extra = {"total_annual_cost": rounded(annual_gross + annual_contributions),
                            "annual_gross_pay": annual_gross, "annual_holiday_allowance": holiday_amount,
                            "annual_employer_contributions": annual_contributions}
        used = sorted({fid for c in contributions for fid in c.get("facts", [])} | set(s.get("facts", [])))
        capped = [p["name"] for p in parts if p["capped"]]
        rounded_down = [c["name"] for c in contributions if c.get("rounding") == "down"]
        floors = [f"{c['name']} {cur}{float(c['floor_monthly']):,.{decimals}f}" for c in contributions
                  if c.get("floor_monthly", 0)]
        excluded = [c["name"] for c in all_contributions if c not in contributions]
        formula = "max(0, min(gross, monthly cap) − monthly floor)" if floors else "min(gross, monthly cap)"
        if assessment_bases:
            formula = formula.replace("gross", "assessment base")
        method = (f"Gross {cur}{gross:,.{decimals}f} per month; employer contributions = {formula} × "
                  f"employer rate for each of: " +
                  "; ".join(f'{p["name"]} {p["employer_pct"]}%' for p in parts) +
                  (f". Caps applied: {', '.join(capped)}" if capped else ". No cap reached") +
                  (f". Monthly earnings floors deducted: {'; '.join(floors)}" if floors else "") +
                  (". Specified assessment bases: " + "; ".join(
                      f"{name} {cur}{float(base):,.{decimals}f}" for name, base in assessment_bases.items())
                   if assessment_bases else "") +
                  (f". Each contribution rounded down to {'cents' if decimals == 2 else str(decimals) + ' decimal places'}: {', '.join(rounded_down)}" if rounded_down else "") +
                  (f". Each contribution rounded up to the next whole currency unit when fractional: {', '.join(rounded_up)}" if rounded_up else "") +
                  (f". Scenario exclusions: {'; '.join(excluded)}" if excluded else "") +
                  (f". Annual budget separately includes {holiday_pct}% holiday allowance on twelve "
                   "base salaries and contributions on combined annual wage, using explicit annual "
                   "caps/floors. Monthly figures describe an ordinary base month; annual budget "
                   "contributions are rounded at annual illustration level, not a payroll reconciliation"
                   if holiday_pct else "") +
                  ". Excludes voluntary benefits and provider fees." +
                  (f" Budget amounts round each component to {decimals} decimal places; this is not a statutory remittance rounding rule." if decimals != 2 else "") +
                  (f" Scenario assumptions: {s['note']}" if s.get("note") else ""))
        rows.append({
            "scenario": s["label"], "gross_monthly": rounded(gross),
            "parts": parts, "employer_contributions": total,
            "effective_rate_pct": round(total / gross * 100, 2),
            "total_monthly_cost": rounded(gross + total),
            **annual_extra,
            "facts": used, "methodology": method,
            "source_url": facts[contributions[0]["facts"][0]]["source"]["url"],
        })
    return rows


def spec_items(spec: dict, start: int, cur: str, decimals: int = 2) -> list[dict]:
    variables = spec.get("vars", {})
    names = {k: float(v["value"]) for k, v in variables.items()}
    rows, n = [], start
    for item in spec.get("items", []):
        value = eval(item["expr"], {"__builtins__": {}, "min": min, "max": max, "round": round, "ceil": ceil}, names)  # noqa: S307
        used = sorted({f for k in variables if re.search(rf"\b{re.escape(k)}\b", item["expr"]) for f in variables[k].get("facts", [])})
        n += 1
        rows.append({"id": f"C-{n:03d}", "value": round(float(value), decimals),
                     "claim": item["claim"].format(value=float(value), cur=cur),
                     "methodology": f'{item["methodology"]} [expr: {item["expr"]}]', "facts": used,
                     "source_url": item.get("source_url", "")})
    return rows


def evidence_urls(text: str) -> dict[str, str]:
    """E-/V- row id -> source_url from an evidence table."""
    urls = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*([EV]-\d+)\s*\|", line)
        if m:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[3].startswith("https://"):
                urls[m.group(1)] = cells[3]
    return urls


def build(data: dict, spec: dict | None = None, evidence: str = "") -> dict:
    spec = spec or {}
    if "calculation_decimals" in spec:
        data = dict(data, calculation_decimals=spec["calculation_decimals"])
    decimals = calculation_decimals(data)
    if spec.get("scenarios"):
        data = dict(data, cost_scenarios=list(data.get("cost_scenarios", [])) + spec["scenarios"])
    monthly_only = spec.get("monthly_only", False)
    if not isinstance(monthly_only, bool):
        raise ValueError("monthly_only must be a boolean")
    rows = scenario_rows(data, monthly_only=monthly_only)
    out, n = [], 0
    cur = currency_prefix(data)
    for r in rows:
        n += 1
        r["id"] = f"C-{n:03d}"
        annual = '' if monthly_only else f', annual {cur}{r["total_annual_cost"]:,.{decimals}f}'
        r["claim"] = (f'At {cur}{r["gross_monthly"]:,.{decimals}f} gross per month ({r["scenario"]}), employer '
                      f'contributions are {cur}{r["employer_contributions"]:,.{decimals}f} '
                      f'({r["effective_rate_pct"]}% of gross); total monthly cost {cur}{r["total_monthly_cost"]:,.{decimals}f}{annual}.')
        out.append(r)
    urls = {f["id"]: f["source"]["url"] for f in data["facts"]} | evidence_urls(evidence)
    for r in spec_items(spec, n, cur, decimals):
        unknown = [f for f in r["facts"] if f not in urls]
        if unknown:
            raise ValueError(f'{r["id"]}: unknown fact/evidence ids {unknown}')
        if not r["source_url"]:
            r["source_url"] = urls[r["facts"][0]] if r["facts"] else ""
        out.append(r)
    return {"currency": data["currency"], "rows": out}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    job = job_dir(args.job)
    data = read_json(job / "facts.json")
    spec = read_json(job / "calc_spec.json") if (job / "calc_spec.json").exists() else None
    try:
        evidence = "\n".join((job / n).read_text(encoding="utf-8")
                              for n in ("evidence.md", "evidence.vendors.md") if (job / n).exists())
        derived = build(data, spec, evidence)
    except (KeyError, ValueError, TypeError) as e:
        sys.exit(f"calc failed: {e}")
    write_json(job / "derived.json", derived)
    for r in derived["rows"]:
        print(f'{r["id"]}: {r["claim"]}')
    if not derived["rows"]:
        print("no cost scenarios or contributions — nothing derived")


if __name__ == "__main__":
    main()
