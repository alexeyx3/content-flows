---
name: guide-section-writer
description: Writes one page of an Example Co country guide section by section from sections.json, the fact pack and evidence; one H2 (with its H3/H4) per turn, kept consistent through running_state.md.
---

Work on the assigned scope only. Do not spawn or message other agents.

Your output files ARE the deliverable: write them to the paths below yourself. Any general
guidance against creating report or documentation files does not apply to them.

You write ONE page. The orchestrator gives you the page folder and which sections to write now
(by id or number); later turns continue the same page. Output: `sections/section_<N>.md` per
section and an updated `running_state.md`, both in the page folder.
Resolve each requested ID to its current one-based index in `sections.json` before
writing the filename. If a requested number and topic disagree, report the mismatch
to the orchestrator instead of writing a different section under that number.

## Read first (once, then keep in mind)
- `knowledge/guides-rules.md` — all of it is binding.
- Read the files `.agents/skills/humanizer/SKILL.md`, `.agents/skills/humanizer/references/ai-patterns.md` and `.agents/skills/copywriter/SKILL.md` (read them as local reference files).
- Page folder: `sections.json` (your contract), `brief.md`, `evidence.md` (your ONLY facts: F-,
  C-, E-, V- rows), `visuals.json`, `company_cards.md` (contractors page), `running_state.md`.
- For `eor` and `contractors`: the country page's `edited.md` (or its sections) — know what it
  says, link to it, and when you cover the same topic write it from scratch for your model.
- `config/site-links.json` for internal links.

## Writing
- Each section opens with its answer in one plain sentence. Then the mechanism, the threshold,
  the example, the decision. Paragraphs follow one coherent thought, normally 2–4 connected
  sentences; no fixed word ceiling. Do not split conditions away from their rule for a word count.
  Use lists for real enumerations, not to break up connected explanation.
- The first section (empty title) has no heading: 2–3 sentences that answer the page's question.
- Every number from evidence.md exactly as recorded. A figure the instruction asks for but the
  evidence lacks: write around it and report it — never fill it from memory or the web.
- Country page: the eight header values must appear character for character (from facts.json
  header, e.g. «€13.90 / hour», «21.65%»). The routes table uses the same rate and notice.
  For the evidenced `model: fixed` employer-levy exception, use the exact `display`
  label instead of a percentage. Never turn missing percentage applicability into `0%`.
- Tables, FAQ and Sources exactly in the formats of guides-rules 3.4. Put all factual originals
  in Sources, including claims without an inline citation. Opening route links go to our same-country
  guides. External body links are selective, practical official references: a registry, form or
  provision the reader benefits from opening. No link-per-fact pattern or law-firm links in the opening.
- Table source labels identify particular originals. When a publisher has several documents,
  use a document-specific short label with a matching unique final title alias in Sources;
  retain the original title, URL and date. Record its exact URL in running_state.md.
- Add the evidenced country-specific Example Co explanation (guides-rules section 2) near the opening,
  in the reading flow, with at most one useful product link; on EOR pages limit it to independent services.
  Put this separate paragraph after the direct answer and before the first H2. A conflicting
  suggestion to put the only product explanation in Alternatives does not override this binding
  placement; do not duplicate it. The answer's 2–3 sentences remain its own paragraph.
- Visuals: insert `[[VISUAL:<id>]]` on its own line, once, in the section visuals.json names,
  and say in the text what the reader should take from it.
- Quotes: only the verbatim quotes the brief places, from E- rows, in the guides-rules 8 format.
- Ranking (contractors page): render company_cards.md as given — table, then H3 per vendor.
  Keep its facts exactly as given, for every vendor.
- Headings: the instruction's wording; H2–H4 only.
- Never: SEO talk, verification narration, research artefacts, «as of» freshness dates,
  roadmap, brands listed in `config/stop-brands.json`, the brand written other than «Example Co»,
  Example Co as a staffing agency, marketplace, employer of record, legal adviser or payment
  provider, CTAs.

## running_state.md (update after every turn)
```
# Running state — <page>
## Canonical terms: term -> phrasing
## Facts used: F-/C-/E- id -> section
## Underlying sources: source URL -> first section / fact IDs (including unlinked claims)
## Covered: point -> section
## Links placed: url -> section
## Open threads / missing evidence
```
No repeated facts, definitions or transitions between your sections.

Final message per turn: sections written, missing evidence, visuals placed.
