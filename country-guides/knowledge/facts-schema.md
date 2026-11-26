# facts.json — the country fact pack

One file per country job: `jobs/<job>/facts.json`. It is the ONLY source of numbers for all three
pages. Written by the two `guide-facts` agents (scope `employment` and scope `contractors`), each
into its own part file (`facts.employment.json`, `facts.contractors.json`); the orchestrator
merges them with `scripts/check_facts.py --merge`. Validated by `scripts/check_facts.py`.

```json
{
  "country": "Germany", "slug": "germany", "iso": "DE",
  "currency": "EUR", "currency_symbol": "€",

  "header": {
    "minimumWage":    {"value": "€13.90 / hour", "facts": ["F-001"]},
    "averageSalary":  {"value": "€4,323 / month", "facts": ["F-010"]},
    "incomeTax":      {"value": "14–45%", "facts": ["F-030"]},
    "paidLeave":      {"value": "20 days", "facts": ["F-040"]},
    "publicHolidays": {"value": "9–13", "facts": ["F-045"]},
    "probation":      {"value": "up to 6 months", "facts": ["F-050"]},
    "noticePeriod":   {"value": "4 weeks – 7 months", "facts": ["F-051", "F-052"]},
    "employerContributions": {"value": 21.65, "facts": ["F-020", "F-021"]}
  },

  "facts": [
    {
      "id": "F-001",
      "topic": "minimum_wage",
      "pages": ["country", "contractors"],
      "claim": "The statutory minimum wage is €13.90 gross per hour from 1 January 2026.",
      "value": 13.90, "unit": "EUR/hour", "effective": "2026-01-01",
      "source": {"publisher": "BMAS", "title": "Mindestlohn steigt zum 1. Januar 2026",
                 "url": "https://www.bmas.de/...", "tier": "official"},
      "accessed": "2026-10-07",
      "quote": "exact supporting passage, original language allowed",
      "note": ""
    }
  ],

  "contributions": [
    {"name": "Pension insurance", "employer_pct": 9.3, "employee_pct": 9.3,
     "cap_monthly": 8450, "in_header": true, "facts": ["F-020"]}
  ],
  "minimum_wage_history": [{"date": "2022-10-01", "value": 12.00, "facts": ["F-003"]}],
  "notice_by_tenure": [{"tenure": "2 years", "months": 1, "facts": ["F-051"]}],
  "cost_scenarios": [{"label": "Average salary", "gross_monthly": 4323, "facts": ["F-010"]}],
  "unconfirmed": [{"topic": "regional holidays count", "reason": "no official consolidated list"}]
}
```

Field notes: `id` is `F-` plus three digits, unique. `pages` — any of country / eor /
contractors. `value`, `unit`, `effective`, `note` optional. `tier` — law | official |
professional | vendor. `cap_monthly` — contribution ceiling per month in local currency,
optional. `in_header: false` excludes a contribution from `employerContributions` (e.g. a rate
that varies by industry). Optional `rounding: "down"` truncates each contribution to the output
precision. `rounding: "whole_up"` rounds a fractional contribution up to a whole local currency
unit. Both use decimal arithmetic and require a supporting legal rule in `facts`. The default
`nearest` preserves ordinary two-decimal rounding.
Optional `floor_monthly` is the evidenced lower earnings threshold deducted from capped
gross pay before applying a contribution rate: `max(0, min(gross, cap) - floor)`. It defaults
to zero. State the pay period and support both band endpoints with referenced facts; monthly
statutory thresholds must not be silently replaced by annual thresholds divided by twelve.
For statutory remuneration bands, a cost scenario may carry `contribution_bases`, a map
from exact contribution names to evidenced assessment bases. These replace gross pay only
for the named contributions, before caps and floors. Include the supporting band fact IDs
in the scenario's `facts`. Other contributions retain gross pay as their base. A scenario
`note` states plan, age and other assumptions and is carried into the derived methodology.
Optional scenario `include_contributions` explicitly lists applicable contribution names
when the pack also describes conditional sector schemes. The list must be non-empty and
contain only known names. Explain and evidence the scenario's eligibility and exclusions;
the header remains the independent sum of contributions marked `in_header: true`.
For an evidenced annual holiday allowance, scenario `holiday_allowance_pct` adds it to
twelve base salaries when computing `total_annual_cost`, with employer contributions
on that combined wage. The ordinary monthly result remains a base-month illustration.
Each applicable bounded contribution requires explicitly sourced `cap_annual` and, where
relevant, `floor_annual`; monthly thresholds are not silently multiplied by twelve.
Reference the allowance/base/cap facts in the scenario and explain the annual assumptions.
Combined holiday allowance and custom remuneration bands require a separate calc_spec model.
A job can set `calc_spec.monthly_only: true` to omit annual totals from monthly wage scenarios
when the evidence supports an ordinary-month calculation only. Any separately sourced annual
illustrations can still be modelled as `calc_spec.items` with their own assumptions.
A job's `calc_spec.json` may set `calculation_decimals` (integer 0–6; default 2).
Use 3 for a budget that must preserve a three-decimal source amount, such as a TND
wage in millimes. This controls scenario amounts, claims and calculated item values;
it does not establish a statutory remittance rounding rule. State the component-rounding
method and exclusions. Bar charts using those amounts set `data.value_decimals: 3` so
their labels preserve the same precision; other visuals retain their current defaults.
`minimum_wage_history` oldest first. `unconfirmed` lists what could not
be confirmed — never written on a page. A fact later found wrong or stale gets `"status": "superseded"`
and `"superseded_by": "E-0xx"`; it stays for the audit trail and reaches the writer with verdict `no`.
Quotes marked `[summary]` retain their provenance and reach page evidence with verdict
`partial`. They require an independently supported F-/E- row before publication; the
summary row itself is not silently promoted, including when another row corroborates it.
An explicitly unresolved fact may carry `"status": "restricted"` or `"status": "unconfirmed"`.
Its raw quote and provenance remain intact, but page evidence marks it partial and not for use.
Calculations depending on partial or superseded F rows inherit that restriction; arithmetic
does not establish an unverified input's legal applicability.

## Rules checked by the script

For a country whose employer levies have no truthful single wage percentage, use
`header.employerContributions: {"value": null, "model": "fixed", "display": "Fixed statutory levies", "facts": [...]}`.
The short display label replaces a percentage in review prose and the literal body check.
All supporting amounts and eligibility conditions still need F-/C-/E- evidence.
Do not substitute zero or invent a wage-equivalent rate. Any percentage contribution
in such a pack must be explicitly excluded from the headline with `in_header: false`.
The current CMS/frontend percentage field cannot display this model: Strapi export
is blocked before remote checks until that display support exists. Local drafting,
visuals, independent QA and review Docs may proceed with the truthful label.

- All eight header keys present; the seven strings are ≤ 32 characters and short (no commentary:
  «4 weeks – 7 months», not «4 weeks, grows with tenure»). A missing value is still a value:
  «None — set by collective agreements».
- For the ordinary percentage model, `employerContributions` equals the sum of `employer_pct` over contributions with
  `in_header: true`, rounded to two decimals.
- Fact IDs unique, every referenced ID exists; every fact has `claim`, https `source.url`,
  `source.publisher`, `source.tier`, `accessed` (ISO date) and a non-empty `quote`.
- `tier: vendor` facts may only describe that vendor.

## How the two scopes split

| scope | covers |
|---|---|
| employment | header, labour market and salaries by role, employer registration steps and timings, minimum wage and history, income tax, contributions with caps, working time, leave, sick pay, parental leave, probation, notice by tenure, severance, public holidays, 13th salary, visas, EOR legality, provider licence and registry, maximum EOR duration, permanent establishment, recent and announced changes, penalties for employers |
| contractors | employee-vs-contractor tests and their legal basis, status thresholds (turnover, VAT, single-client dependency, social insurance), contractor registration forms, contract requirements, invoice requirements and tax IDs, VAT and reverse charge, e-invoicing, local payment rails and currency rules as country reference, payment terms and statutory late-payment interest, reclassification penalties by party |
