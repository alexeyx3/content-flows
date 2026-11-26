---
name: guide-brief
description: Builds the brief and sections.json drafting contract for ONE page (country, eor or contractors) of an Example Co country guide — a hybrid larger than any page in the search results.
---

Work on the assigned scope only. Do not spawn or message other agents.

Your output files ARE the deliverable: write them to the paths below yourself. Any general
guidance against creating report or documentation files does not apply to them.

The orchestrator gives you the job path and the page: `country`, `eor` or `contractors`. You
write, in the page folder (`<job>/pages/guide-<slug>[-eor|-contractors]/`): `brief.md`,
`sections.json` and `out/meta.md`.

## Read first
- `knowledge/guides-rules.md` — binding; sections 3, 5, 6, 7 decide
  your outline.
- `vendor/blog/knowledge/geo-guidelines.md`, `vendor/blog/knowledge/seo-requirements.md`.
- `<job>/job.json`, `<job>/facts.json`, `<job>/derived.json`, `<job>/research/*.md`.
- `<job>/serp/<page>.serp_synthesis.md`, `<page>.competitor_structures.csv`, `<page>.features.json`,
  `serp/geo-overlap.md`, `serp/rankings.md`; `<job>/semantics/<page>.csv` if present.
- For `eor` and `contractors`: the country page's `brief.md` and `sections.json` — know what the
  country page covers so you can link to it and write your overlapping passages for your model.

## The hybrid
1. Inventory: list every distinct useful block the top pages carry for this page type across all
   geos (who has it). Use their H2/H3 structures, PAA, related searches and AI Overview.
2. Outline = the core of guides-rules 3.1 for this page, in its order + every useful block from the
   inventory + blocks nobody in the top has (from research: changes, angle, practitioners,
   derived calculations). New H2s are allowed. Name the page's unique block (3.3).
3. The result must be more complete than any single top page. If the top has a block we skip,
   write why in brief.md (e.g. it describes their product).
4. Do not mirror one competitor's structure. Do not let the outline read as a template with the
   country name swapped: headings answer this country's questions.

## brief.md
1. Meta: H1 (fixed per page — guides-rules table), metaTitle ≤70, metaDescription ≤200, the
   page's main queries.
2. Inventory table: block | who has it in the top | taken / skipped and why.
3. Outline H2–H4 with a 1–3 line micro-brief each.
4. Information gain: what this page says that the top does not, mapped to R-/F-/C- IDs.
5. FAQ candidates (PAA, related searches, AI Overview, Reddit), phrased as people ask.
6. Visual candidates (≥2–3 where data exists; guides-rules 7) with the IDs of their data.
7. Quote placements: which verbatim practitioner quotes from research go where (≤2–3 per page).
8. Facts that must appear: header figures (country page), key thresholds, dates.
9. For subpages: which country-page topics you revisit, for what reason, and where you link.
10. Gaps: questions we cannot answer with verified data.

## sections.json — the writer's contract
```json
{"title": "<H1>",
 "sections": [{"id": "answer", "title": "", "instruction": "..."},
              {"id": "three-ways-to-hire", "title": "Three ways to hire in Germany", "instruction": "..."}],
 "information_gain": [{"id": "ig-1", "reader_value": "...", "section_id": "...", "research_ref": "R-A-01, F-012"}],
 "visual_candidates": [{"section_id": "...", "type": "line", "purpose": "...", "data": "F-001, F-003"}],
 "expert_questions": []}
```
- One object per H2, in order; the first is the direct answer with an empty title; the last two
  are the FAQ and «Sources». H3/H4 are listed inside the parent's instruction with their wording.
- `id` latin kebab-case, unique. Every `section_id` in information_gain and visual_candidates is
  exactly ONE existing section id — never two joined by a comma or semicolon (the gate rejects it);
  a finding that serves two sections gets two entries.
- `instruction` (for the writer, never echoed into the text): the reader's question; what to
  explain (mechanism, difference, example, decision); which F-/C-/R- IDs to use; the table
  format if any (guides-rules 3.4); which visual marker goes here; which quote goes here; internal
  links to place. No word quota — depth follows the question, but say where depth matters most.
- Reconcile the outline and the section instructions before delivery: every required contract
  topic in brief.md must appear in its assigned instruction, including tax responsibilities,
  expense allocation and currency when those topics are requested. Do not leave a requirement
  only in a different outline or expect the writer to reconstruct it from a shorter instruction.
- Assign the single neutral product explanation near the opening, after the direct answer and
  before the first H2; on EOR pages restrict it to genuinely independent services. The direct
  answer's sentence count applies to that answer, not to the separate product paragraph.
  Do not reserve this explanation for Alternatives or create a conflicting late placement.
- In existing first-payroll and EOR cost sections, assign the steps the buyer needs to fund,
  check and reconcile the first pay run, including who owns payroll and remittances and what
  evidence Finance can obtain. Use the applicable local obligations and verified terms.
- In existing contractor payment and provider sections, assign one buyer scenario from signed
  terms and acceptance to invoice, approval, payment and reconciliation. Identify who signs, who approves
  or handles exceptions, what Finance can match, and which document shows that an invoice was
  approved and paid, where evidenced. Require E/V support for product claims. Distinguish the
  buyer's jurisdiction from the worker's location, and general product availability from a
  confirmed country-specific capability (a local-language agreement template, a local invoice
  format).
- Missing universal fines, lookbacks or prices are evidence constraints, not public copy.
  Ask for a reader-facing explanation of the applicable case-specific obligations; never ask
  the writer to announce what was or was not verified for the guide or to imply no penalty exists.
- The Sources section instruction: «List every source used on this page in order of first use,
  guides-rules 3.4 format».
- For the contractors ranking, preserve all seven company-card columns: Vendor, Model,
  Presence in the country, Contracts under local law, IP assignment, Local documents,
  Classification support. Do not merge contracts, IP and documents into one column.

## out/meta.md
```
title: <H1 exactly>
slug: <slug for country; <slug>-employer-of-record; <slug>-independent-contractors>
metaTitle: <≤70>
metaDescription: <≤200>
```

## Blocking (status: blocked)
- No information gain beyond the top.
- A core section of 3.1 cannot be supported by facts.json — name what is missing.

Final message: 5-line summary, the unique block, visual count, status ok | blocked.
