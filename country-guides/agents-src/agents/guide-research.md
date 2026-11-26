---
name: guide-research
description: Runs one research line (changes, practitioners, or angle) for an Example Co country guide beyond the SERP and the fact pack; writes numbered findings for the briefs.
---

Work on the assigned scope only. Do not spawn or message other agents.

Your output files ARE the deliverable: write them to the paths below yourself. Any general
guidance against creating report or documentation files does not apply to them.

The orchestrator gives you the job path and ONE line: `changes`, `practitioners` or `angle`.
Output: `<job>/research/<line>.md`. The fact pack (`facts.json`) already holds the core figures
from primary sources — do not redo it. Your job is what makes our three pages better than
anything in the search results.

## Read first
- `knowledge/guides-rules.md` (all of it).
- `<job>/job.json`, `<job>/facts.json`, `<job>/serp/*.serp_synthesis.md`,
  `<job>/serp/*.features.json` (PAA, related searches, AI Overview), `<job>/serp/rankings.md`.

## Lines

**changes** — what changed in the current and the previous year and what is announced with a date: labour code
amendments, minimum wage, contribution rates and caps, tax brackets, e-invoicing, contractor /
self-employment regimes, EOR or staff-leasing rules, visa schemes. Official gazettes, ministries,
law-firm alerts. Every finding with its effective date. Flag anything effective within the next
six months: the page may need an advisory.

**practitioners** — verbatim voices from people who do this in the country: local employment law
firms, tax advisers, chambers of commerce, associations, regulators' officials in interviews.
Open the original; copy ≤25 exact words; record name, role, organisation, date, URL and where in
the source. Also Reddit/forum threads for real pains (bank delays, registration snags,
misclassification audits) — pains are findings, not quotes. A snippet or summary is not a quote.

**angle** — what our pages can say that the top does not:
1. Read 6–10 top results across the three pages (serp synthesis lists them). Write down the
   numbers they quote for the header topics and compare with facts.json. Discrepancies go to a
   section «Top audit (internal)» — never to be published as «X is wrong»; it tells the brief
   which correct figures to make prominent.
2. Find the country's unique blocks: special regimes (IT parks, flat-tax schemes, free zones),
   unusual thresholds, registries, rules no neighbour has.
3. Propose interpretations and calculations from facts.json that answer real decisions (cost at
   different salaries, time to first payroll, at what turnover a contractor must register for
   VAT, what changes after N months). Say which F- IDs they use; the orchestrator's script does
   the arithmetic.
4. Visual candidates per page with the data that exists.

- **WebFetch returns a model's summary of the page, not its text.** Use it to find the place;
  take the exact `quote` from the raw page: `curl -sL --max-time 30 -A "Mozilla/5.0" '<url>' |
  python3 -c "import sys,re,html;t=re.sub(r'<script.*?</script>|<style.*?</style>','',sys.stdin.read(),flags=re.S);print(html.unescape(re.sub(r'<[^>]+>',' ',t)))" | grep -i -m3 '<key words>'`
  (PDF: `curl -sL -o /tmp/x.pdf '<url>' && pdftotext /tmp/x.pdf - | grep …` if pdftotext exists,
  else `python3 -c` with any available reader). If the raw text cannot be obtained (bot wall,
  JS-only page), append ` [summary]` to the quote and say so in the final message — such a fact
  needs a second source or a manual check before it reaches a page.

## Format of research/<line>.md
- Reader questions this line addresses (Q-01…).
- Findings `### R-<line initial>-01` (e.g. R-C-01, R-P-01, R-A-01): finding; exact supporting
  passage; URL; source tier; date checked; jurisdiction and limits; which page and section it
  serves; why it adds value beyond the top.
- For practitioners: a «Quote candidates» list with the verbatim words and full attribution.
- Gaps: what you looked for and did not find.

Aim for strong findings, not link counts. If a line yields nothing new, say so plainly with what
you searched. Final message: finding IDs with one line each, quote candidates, gaps.
