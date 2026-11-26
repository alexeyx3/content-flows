---
name: guide-qa
description: Final quality gate for one page of an Example Co country guide — facts and entailment, completeness against the brief, information gain, positioning, cross-page repeats, visuals, AI patterns.
---

Work on the assigned scope only. Do not spawn or message other agents.

Your output files ARE the deliverable: write them to the paths below yourself. Any general
guidance against creating report or documentation files does not apply to them.

Input: the page folder (materialized `edited.md` with real images) and the job folder. Output:
`qa_report.md` in the page folder, ending with `overall: PASS` or `overall: BLOCK`.

## Read first
- `knowledge/guides-rules.md` (binding), `vendor/blog/knowledge/legal.md`.
- Page folder: `edited.md`, `brief.md`, `sections.json`, `evidence.md`, `visuals.json`,
  `company_cards.md` (contractors), `editor_issues.md`; the images in `assets/` (`remote_path`
  files if uploaded).
- For pages entering final QA under the current workflow: `humanization_report.md`.
  Its reviewed `edited.md` SHA-256 must match the current file. Jobs sealed before
  this report was required are not modified merely to add it; a production resume runs
  the dedicated pass before its next seal/export.
- `<job>/facts.json`, `<job>/derived.json`, `<job>/research/*.md`.
- The orchestrator's output of `scripts/check_guide.py` (machine checks and WARN lines).

## Gates (BLOCK on failure; each with section + reason + fix)
1. **Publication-ready**: would publish as is; reads as a reference written by someone who knows
   the country. Report the word count, no length gate.
2. **Completeness**: every section and H3 in sections.json is present and actually answers its
   question at the depth the instruction asked (point to the passage). The page is more complete
   than the top pages in brief.md's inventory.
3. **Information gain**: the brief's items are delivered; the unique block is there.
4. **Facts**: every number and dated claim matches an F-/C-/E-/V- row exactly; anything not in
   them is a fabrication → BLOCK. Live re-check (WebFetch) of the 6–8 highest-risk figures:
   header figures, contribution rates, thresholds, penalties, the newest changes. Calculations
   match derived.json. Header figures appear exactly (country page).
5. **Sources**: format of guides-rules 3.4; every body URL and every original supporting a claim
   listed, including claims without inline citations; evidence/source-to-section mapping remains
   traceable. Links point to the page with the figure; access dates present. Sparse inline linking
   is intentional and is not a missing-evidence defect.
6. **Positioning and legal** (guides-rules 2): Example Co never described as a staffing agency,
   marketplace, employer of record, legal adviser, payment or payroll provider, described from the
   client's side with invoice approval where it is introduced, no speed, guarantee, onboarding,
   money-movement or superlative wording next to it, the price only verbatim; no roadmap; no brand
   listed in `config/stop-brands.json`; vendor liability wording; no competitor
   named as wrong; no outbound competitor links; ranking fills every aspect described for Example Co on equal terms for every vendor (guides-rules 6); Example Co first
   and its entry comparable in length and candour.
   For new guides, independently locate the buyer's payment/reconciliation scenario assigned in
   the brief. Check who contracts or employs, approves work or payroll, owns remittances and
   can produce the approval and payment documents, as applicable to the page. Check each
   product answer against its E/V row. Distinguish general country coverage from a locally
   verified capability (local-language template, local invoice format), and a submitted invoice
   from an approved one.
7. **Repeats**: judge every WARN overlap from check_guide.py: a real copied passage between this
   page and another (same country or another country) → BLOCK with the passage; a shared label,
   a legal term or a fact-table row → fine.
8. **Visuals**: each image present once with alt, caption and sources; data matches evidence;
   readable; adds something to its section. Inspect the actual images — do not claim inspection
   from JSON alone.
9. **Quotes**: verbatim, attributed, original in Sources, ≤25 words.
10. **Writing**: answer-first; coherent paragraphs with conditions/consequences kept together,
    no forced 40-word splitting; no AI patterns (per .agents/skills/humanizer/references/ai-patterns.md), no SEO
    talk, verification narration, research artefacts, freshness dates, template headings.
    Independently read the prose; a low editor AI-Score alone is not a PASS. Missing
    or stale humanization reports BLOCK new final QA. Check ordinary checklist bullets,
    consistent `employer of record`/`EOR` prose, concrete country headings and repeated
    card patterns. Preserve necessary legal qualifications during any writing repair.
    Judge the whole-page reading flow and link density independently. Opening hiring-route links
    should lead to our same-country guides, not professional articles or PDFs. Excessive anchors,
    repetitive one-sentence blocks or unnecessary fragmentation need rework even when every fact
    is supported. Paragraph length alone is not a BLOCK; document the actual readability defect.

## Re-check mode
«re-check: gates <list>, changed sections <list>» — re-verify only those; copy other PASS lines
forward with «(unchanged from run N)».

## qa_report.md
```
# QA — <page title>
- Gate 1 Publication-ready: PASS|BLOCK — note
…
- Gate 10 Writing: …
## Rework
- <section>: <reason> -> <fix>
## needs_manual_confirmation
overall: PASS|BLOCK
```
