---
name: blog-evidence
description: Gathers tiered, entailment-verified sources for the claims in an Example Co brief. Use after the brief, before writing, for claim-heavy articles.
---
## Published-article refresh mode

For new-topic jobs with `batch_delivery_contract_version: 1`, read
`knowledge/delivery-contract.md` and the selected delivery_checks. Map factual
and numerical obligations through the appended delivery_check_ids evidence
column; preserve actual sources, supporting quotations and all material scope
qualifications. Resolve unsupported obligations before writing; a filled ID is
not entailment. Without the flag, retain the normal role contract.

For an assigned metrics stage, bind your own runtime before work with
`python3 scripts/codex_metrics.py stage-bind --job <job> --id <stage-id> --thread-id "$CODEX_THREAD_ID"`.
Resolve script and job paths from this repository if your working directory differs.

If `job.yaml` has `article_refresh_version: 1`, read and follow
`knowledge/blog-refresh.md` completely. Its role-specific refresh inputs,
outputs and scope replace the new-topic/full-draft requirements below; house
rules and factual/publication gates still apply. Do not restart the new-article
research pipeline or rewrite retained H2s merely because this is a new job folder.

For semantic_refresh_version: 1, semantics_plan.json selects wording targets, not verified factual claims. Verify the facts required for the additions, preserving scope and qualifiers even when an assigned phrase needs revision.



You collect evidence for the claims that need proof. Output: `evidence.md` in the job folder — section-writing subagents load it as the article's evidence pack, so it is the ONLY set of facts the article can contain.

## Company database — read FIRST (before any web fetch)

For new-topic jobs with `answer_contract_version: 1`, read
`knowledge/answer-contract.md`. Link the selected `sections.json.answer_checks`
to existing atomic claims using the appended `answer_check_ids` evidence column.
Keep actor, relation/result and material conditions in claim/supporting_quote;
rejected or unverified rows cannot fulfil a required answer. Do not fabricate
facts to close the map; resolve an unsupported planned answer before writing.
Keep the evidence rows in one continuous Markdown table. For requirements, record the
actor, jurisdiction, obligation and exceptions. For a case study, record what was observed
and in which study population. Record promotional terms separately with end date and eligibility.
For each in-scope vendor, first read `companies/<slug>.mdx` in the repo root (slug = vendor name lowercased, spaces→hyphens; e.g. northwind.mdx, contoso-global.mdx, fabrikam.mdx, example-co.mdx). These cards are the PRIMARY source: their `provenance{sourceUrl,note,checkedAt,confidence}` already satisfies entailment + source-tiering. For a fact covered by a card, populate evidence.md from it: `source_url` = provenance.sourceUrl, `supporting_quote` = provenance.note (or the pricing/editorial text), `last_checked` = provenance.checkedAt, `entailment_verdict` = supports (use `partial` if the field's confidence is low/medium or the value is vendor-self-reported). Go to the WEB only for: vendors with NO card, facts absent from the card, fields with `confidence: low`, or `checkedAt` older than ~90 days (pricing especially). Do NOT re-fetch what a card already covers at high confidence. Keep 'verify-on-quote' on pricing.

## Read first
- `serp.hybrid_outline.md`, `brief.md`, and `sections.json`. Treat the approved H2-H4 hierarchy as
  the complete research surface: extract every claim, statistic, comparison, legal distinction,
  vendor attribute, and decision-value block that needs support. Do not research only the brief's
  headline examples while leaving later subheadings without usable evidence.
- For jobs with `research_discovery_version: 1`, read
  `research.discovery.md`. Reopen every selected scholarly source used by the
  brief; verify method, population, outcome, date and transfer limits against
  the original abstract or full text. A catalogue record or DOI is metadata,
  not support for an effect claim. Check social leads against primary or
  independent sources; a post alone cannot establish a general fact.
- For `research_v3_version: 1`, also read `research.studies.json` and
  `research.quotes.json`. Reopen each selected study at its original URL and
  verify the exact finding, population, method, year and transfer limit. A
  proposed outside quote is a voice, not evidence of a general fact; verify
  any factual, numerical or legal claim in it independently in `evidence.md`.
  Record selected candidates that fail verification and why.
- For jobs with `primary_data_research_version: 1`, read `research.data.json`
  and the brief's data/visual audit. Reopen every selected original document
  or dataset. Verify publisher, publication date, source page/table/sheet,
  definition, denominator, unit, period, geography, population and each
  proposed chart point. Give each publishable point a distinct evidence row
  with a stable ID and exact supporting location; verify formulas and inputs
  for derived values. Reject a candidate when the original is unavailable,
  a point cannot be found, or compared groups use incompatible definitions.
  Record the reason in `evidence.md`; do not pass an unverified number to the
  visual planner or writer.
- Read section 7a of `brief.md` as a research request, not as evidence. Reddit signal IDs may
  explain why a question matters, but they never substantiate the answer.
- knowledge/competitors.csv, knowledge/positioning.md.
- If the orchestrator passes a `sibling_evidence` path (an earlier job on an adjacent topic): read it FIRST. Copy its verified rows (supports/partial) for claims this brief also makes — do not re-research them. Treat its needs_manual_confirmation items as KNOWN DEAD ENDS: carry them over with a "(carried from sibling)" note. Research only claims new to THIS brief.

## Rules
- Source tiers, prefer high: gov/standards/primary > vendor docs/pricing pages > reputable industry. NEVER content farms / SEO listicles as a source of truth.
- Entailment: the quoted snippet must actually support the claim. Record the exact supporting quote.
- Every fact carries a source URL — no `source_url`, no row. The drafting model writes strictly from this file and cannot go look anything up: a fact you record without a live URL is a fact the article will state unsourced, and a fact you leave out is a fact the article simply will not have. Do not fold two facts into one row to save a URL; split them.
- Example Co pricing — one formulation only, verbatim: «from $25 per active contractor per month, charged only for months with an approved invoice; no setup fee», per the official Example Co pricing page. Never «cheap», never «free», never «low-cost». The volume-discount table that circulates in an outside review article ($22 / $19 / $16 by headcount) is FORBIDDEN: never record those numbers, never cite that review as the source of pricing tiers, not even capped at `partial`. If a claim needs a specific figure that the official page does not publish, mark it needs_manual_confirmation instead.
- Verify TOPICAL sources too, not only competitor/company facts. For the hybrid outline's GIST and
  Information-Gain items (independent studies, primary data, standards/government sources,
  industry reports), open each source, confirm the cited finding/stat is actually there, and
  confirm the source is genuinely independent and authoritative (assign a tier). These give the
  article new information; treat them as first-class claims. Reddit Mapper findings identify what
  readers want checked; they are prompts for research, never proof by themselves.
- For every selected decision-value block, find the strongest independent source that actually
  supports its load-bearing claim. Record what decision the finding changes and whether its exact
  URL should appear in the article. Prefer original research, government/standards sources, and
  primary datasets; do not add a decorative study that merely restates generic context.
- A Reddit post or indexed snippet can never be the sole source for a generalized claim. If an
  audience hypothesis cannot be independently verified, keep it as a question/checklist prompt or
  mark it `needs_manual_confirmation`; do not upgrade it into a market fact.
- Apply the same boundary to professional social posts. Preserve a
  verifiable author's words only as an external quote candidate with context
  and URL; do not turn a LinkedIn snippet into a quotation or evidence row.
- Freshness/accuracy of entities: confirm every named tool/vendor/product is current (not rebranded or discontinued).
- **NEVER infer the ABSENCE of a product from a vendor's marketing headline.** The typical case: a card such as `companies/globex.mdx` records `eorSupported: false` because the vendor's home page carries a slogan like «Contracts, not middlemen» — positioning, not a product statement. The vendor's own pricing page may still describe an EOR plan, and independent reviews may confirm a real EOR product. Had it reached the article it would have been a false comparative claim about a competitor, which `legal.md` forbids. A negative claim about a competitor needs the same proof as a positive one: the pricing page, the product page, or an independent review — never a tagline. Flag anything renamed or dead so writers don't cite it.
- Public-link policy: competitor URLs stay in this internal log — the published article carries ZERO outbound links to competitors.
- Blocked sources (403/paywall/bot-wall): do NOT retry more than once. Take the quote via search extraction, append ` [fetch:403]` to the supporting_quote, cap the verdict at `partial`, and add ONE corroborating live source for the same claim (its own row). This marker tells QA not to re-fetch the blocked URL.
- Record last_checked date.

## Output `evidence.md` (one row per claim)
| claim_id | claim | section | source_url | source_tier | supporting_quote | last_checked | entailment_verdict | article_link | decision_use |

entailment_verdict is one of {supports, partial, no}. Claims with no supporting source -> mark needs_manual_confirmation.
`article_link` is one of {required, optional, forbidden}. Use `required` for
every independent original source necessary to verify a selected decision-value
block; the final Sources list links each distinct URL once. Use `forbidden` for
competitor/vendor URLs and sources unsafe for publication. `decision_use` is one short phrase
stating what the reader can decide, verify, avoid, or calculate because of the finding. Do not mark
more links required just to increase citation count.

## Write back to the DB (research once, reuse forever)
For an explicitly configured `company_enrichment_mode: read_only` job, keep
`companies/` read-only. This replaces the create/update-card requirement below
for that job only; still verify every needed fact and retain its original URL,
quote, date and qualifications in job-local evidence. Missing shared cards do
not block evidence collection. Record any verified enrichment candidates in
the evidence notes for a later owner under the normal companies lock. This
scope permits independent jobs to collect evidence concurrently without shared
writes; it does not relax sourcing or entailment checks.

Whatever you web-verified must land in the DB so the NEXT article gets it for free:
- Vendor with NO card -> create `companies/<slug>.mdx` following the existing card schema (frontmatter: name, website, categories, parameters with `provenance{sourceUrl,note,checkedAt,confidence}`, pricing.plans). Fill only fields you actually verified; set checkedAt = today.
- Existing card, stale/low-confidence field you re-verified -> update that field + its provenance entry in place. Do not touch fields you did not verify.
- Never invent schema fields; mirror the structure of `companies/example-co.mdx`.

Final message: counts by verdict + list of needs_manual_confirmation claims + DB cards created/updated.


## Workflow v2 visual and comment evidence

For workflow_version:2 read research.md and knowledge/article-enrichment.md. Verify
publishable findings and prepare source-backed values/relations for planned
visuals: units, period, geography, evidence IDs and explicit formulas for derived
values. Record independent-source article_link policies as usual; competitor URLs
remain forbidden in public captions. Verify factual assertions needed for the
expert comment questions. Do not invent data merely to make a chart possible.
