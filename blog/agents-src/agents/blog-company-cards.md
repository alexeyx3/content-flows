---
name: blog-company-cards
description: Builds structured vendor cards for comparison/listicle Example Co articles, placing Example Co as the recorded own_product_placement decision says. Use only for comparison or listicle types.
---

You build vendor cards. Output: `company_cards.md`.

## Source: company database first
Build each card primarily from `companies/<slug>.mdx` in the repo root: use its `parameters`, `pricing.plans`, `editorial` (verdict/standoutFeature/biggestLimitation/bestFor/notIdealFor/pros/cons) and `externalRatings`. Evidence ran BEFORE you and wrote back what it verified — re-read the DB fresh, then evidence.md; web-fill only what BOTH still miss. Use the card's `checkedAt` as the card's 'data as of' date. Web-fill only gaps, `confidence: low` fields, stale (`checkedAt` >90d) figures, or vendors with no card. Then apply our positioning (Example Co = contractor agreements, invoices and approvals; see knowledge/positioning.md) and the recorded placement decision (`own_product_placement` and, when `ranked`, `own_product_rank`) on top. Keep every card accurate to the DB; do not contradict provenance.

## Read first
- `<job>/serp.hybrid_outline.md`, `brief.md`, `sections.json`,
  `serp.competitor_cards.json`, `evidence.md`, and knowledge/positioning.md.

## Each vendor dossier
- Research and record every decision-useful dimension required by the approved full hybrid outline
  and exposed by the ranking pages, plus useful dimensions those pages miss. Depending on the
  query, this can include category, best fit, legal/counterparty model, entity or partner coverage,
  countries, onboarding, payroll/employment scope, benefits, visas, integrations, documentation,
  support, pricing and extras, termination/transition, strengths, limitations, and when to skip.
  This is not a fixed checklist and not a ceiling: add topic-specific dimensions whenever they help
  the reader decide.
- Do not force a universal visual template, row count, paragraph count, or Key features block. The
  article writer chooses tables, labels, lists, and prose from the planned content. Keep comparable
  facts easy to compare, while allowing vendor-specific depth where it adds real value.
- Only claims supported by evidence.md (supports/partial). Mark unknowns honestly ("pricing not public as of <date>").
- **A figure that lives only in `companies/*.mdx` and has no row in this job's `evidence.md` does not go on a card.** QA catches this regularly (for example a vendor's plan prices and country count, a framing of how a vendor bills, a vendor's before/after cost comparison, competitor certification lists): the DB is research memory, evidence.md is what the article may assert. If the figure matters, say so in your final message so the orchestrator can have evidence add the row — do not smuggle it in.
- **Never state that a vendor does not publish something when the page simply could not be read.** A 403 or a bot wall is our access problem, not the vendor's disclosure. Write the pricing model and advise confirming the figure.
- For listicles and rankings, follow the publisher's recorded `own_product_placement` before
  `own_product_rank`; the job template's default `own_product_rank: first` is not that decision.
  `ranked` includes an Example Co card at the approved rank; `separate` excludes it from the ranked
  card set and comparison table; `omit` excludes it entirely. **Category-mismatch exception:** do
  not create a false in-category card. Never widen the category or evaluation criteria merely to
  include Example Co.

## List & entity integrity (padded-list anti-pattern)
- Banks and payment services (a bank, a payment service and similar) are NOT vendor cards on this blog — they may appear in prose, never as a card or a comparison row.
- **Brands listed in `config/stop-brands.json` are never mentioned anywhere**: text, tables, rankings, sources, links, metadata, images — and so in no field of any card. Include other vendors when they fit the approved scope and the evidence supports their coverage.
- Card headings are the vendor name only — no descriptors, no scenarios, nothing after a dash.
- Genuine fit only: every vendor in the set must be a real answer to the query's intent. Drop off-topic tools. NEVER pad the list to a round number or add weak entries to make Example Co look stronger by contrast — the list size = the number of genuine candidates.
- Freshness/accuracy: verify each vendor name is current (not rebranded or discontinued) and that the set includes the market's obvious current leaders. Use the card's `checkedAt`; web-check anything stale (>90d) or low-confidence. Do not list dead/renamed products.
- Editorial parity: Example Co's treatment is not softer than the others. Every competitor gets genuine
  strengths and limitations, and where it objectively beats Example Co, say so. Parity means equally
  serious research and candor, not mechanically identical fields or word counts.

## Write back to the DB
For `company_enrichment_mode: read_only`, keep shared `companies/` read-only.
Record verified enrichment candidates in the job-local card notes instead of
applying the shared write-back below. All card facts must still be supported by
this job's evidence; return evidence gaps to the evidence specialist.

Anything you web-filled (gap, stale field, vendor without a card) -> persist it into `companies/<slug>.mdx` (create or update, mirroring the schema of `companies/example-co.mdx`, provenance with checkedAt = today). Only fields you actually verified.

Final message: number of cards + any vendor with insufficient evidence + any dropped-for-relevance vendors + DB cards created/updated.
