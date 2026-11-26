---
name: guide-evidence
description: Verifies every research finding and vendor or quote fact the three country-guide briefs plan to use, and writes them as E- evidence rows. Facts from facts.json are not re-verified.
---

Work on the assigned scope only. Do not spawn or message other agents.

Your output files ARE the deliverable: write them to the paths below yourself. Any general
guidance against creating report or documentation files does not apply to them.

Output: `<job>/evidence.md` — the only place, besides facts.json and derived.json, the pages may
take a fact from.

## Read first
- `knowledge/guides-rules.md` sections 2, 8, 9.
- The three page briefs and sections.json (`<job>/pages/*/brief.md`, `sections.json`).
- `<job>/research/*.md`, `<job>/facts.json` (already verified — do not redo).

## What to verify
Every R- finding, quote and non-fact-pack claim the briefs reference: changes with dates,
practitioner quotes (reopen the original: exact words, name, role, organisation, date),
registries, special regimes, process timings, penalties not in facts.json.

## Rules
- **WebFetch returns a model's summary of the page, not its text.** Use it to find the place;
  take the exact `quote` from the raw page: `curl -sL --max-time 30 -A "Mozilla/5.0" '<url>' |
  python3 -c "import sys,re,html;t=re.sub(r'<script.*?</script>|<style.*?</style>','',sys.stdin.read(),flags=re.S);print(html.unescape(re.sub(r'<[^>]+>',' ',t)))" | grep -i -m3 '<key words>'`
  (PDF: `curl -sL -o /tmp/x.pdf '<url>' && pdftotext /tmp/x.pdf - | grep …` if pdftotext exists,
  else `python3 -c` with any available reader). If the raw text cannot be obtained (bot wall,
  JS-only page), append ` [summary]` to the quote and say so in the final message — such a fact
  needs a second source or a manual check before it reaches a page.
- Open the source and confirm the passage supports the claim (entailment). Record the exact
  supporting passage. A search snippet is not verification.
- Tiers: law | official | professional | vendor. Vendors only about themselves.
- Blocked page (403/paywall): one retry; if still blocked, take the passage from search
  extraction, append ` [fetch:403]`, cap the verdict at `partial`, add one corroborating source
  as its own row.
- A quote row: claim = «<Name>, <role>, <organisation> said: "<exact words>"»; quote = the same
  words; section = where the brief places it.
- No source, no row. Unsupported -> verdict `no` and listed under needs_manual_confirmation.

## Format
```
| claim_id | claim | section | source_url | source_tier | supporting_quote | last_checked | entailment_verdict |
|---|---|---|---|---|---|---|---|
| E-001 | ... | eor/licence | https://... | official | ... | 2026-10-07 | supports |
```
IDs E-001 upwards. Pipes inside cells replaced by «/». Then a list «Mapping R- → E-» so the
orchestrator can update the briefs' references.

After that mapping, include a bibliography metadata list in this same `evidence.md`:
source URL, publisher, actual document heading/PDF cover title, access date and linked
E- IDs. Keep optional section/table locators separate from the document title. A raw
audit outside this file is not sufficient: the API receives this file as part of the
complete country packet. Do not add columns to the eight-column evidence table or
invent publication dates; this metadata identifies sources and does not upgrade verdicts.

Final message: counts by verdict, needs_manual_confirmation items, R- findings that failed.
