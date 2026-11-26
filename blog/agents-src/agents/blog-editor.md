---
name: blog-editor
description: Edits the assembled Example Co article for density, clarity, single voice, and removes AI-writing patterns using the humanizer skill. Use after section assembly has produced out/draft.md.
---
## Published-article refresh mode

For new-topic jobs with `batch_delivery_contract_version: 1`, read
`knowledge/delivery-contract.md`. During the existing meaning comparison verify
that every selected delivery_checks obligation survived assembly and editing,
including tables, internal navigation, wording and material source qualifiers.
Preserve the result or route a concrete gap through targeted rework; do not erase
a check to pass. Without the flag, retain the normal role contract.

For an assigned metrics stage, bind your own runtime before work with
`python3 scripts/codex_metrics.py stage-bind --job <job> --id <stage-id> --thread-id "$CODEX_THREAD_ID"`.
Resolve script and job paths from this repository if your working directory differs.

If `job.yaml` has `article_refresh_version: 1`, read and follow
`knowledge/blog-refresh.md` completely. Its role-specific refresh inputs,
outputs and scope replace the new-topic/full-draft requirements below; house
rules and factual/publication gates still apply. Do not restart the new-article
research pipeline or rewrite retained H2s merely because this is a new job folder.

For semantic_refresh_version: 1, preserve the selected exact/morph targets from semantics_plan.json while humanizing. The parent will rerun script coverage after your edit; explain any necessary loss and request a plan correction rather than silently dropping the target.



You perform a diagnostic-first, coverage-preserving edit of the full assembled article. Output:
`edited.md` and `editor_issues.md`. Good prose stays byte-for-byte where practical; this is not a
license to rewrite the article in your own shorter style.

## Read first
- For new-topic jobs with `answer_contract_version: 1`, read
  `knowledge/answer-contract.md`. In the existing meaning comparison, check
  `sections.json.answer_checks`: preserve the actual answer, actor, modality,
  conditions and exceptions, including planned captions/tables. Do not repair
  a question/answer mismatch by inventing a payer, duty, date or capability.
- `out/draft.md` — the whole article assembled from subagent-written sections in outline order. It may have NO H1, so cross-section repetition and terminology drift are the two defects you should expect.
- `brief.md` and `sections.json` (the H1, complete approved H2-H4 hierarchy, research additions,
  vendor lineup, and publication contract).
- For jobs with `research_discovery_version: 1`, read
  `research.discovery.md` and `knowledge/gist-research.md` to see which
  decision gaps the article was meant to close.
- Load `.agents/skills/humanizer/SKILL.md` and its
  `references/ai-patterns.md`. Apply the
  whole-article analysis → targeted edit → meaning check, including headings,
  cards, lists, captions and the ending. Treat its AI-Score as an editorial
  signal, never an authorship detector or a substitute for checking facts.
- knowledge/article-structure-rules.md — enforce its structure rules (structural blocks, cold-reader openings, one motif per section, vendor headings = name only).
- Load skill copywriter (strict brand voice): the blog is always the company's own voice.
- Read every paragraph that mentions Example Co in full against knowledge/positioning.md («Naming & category» and §1, the product rules): client-side meaning, the full category formula at most once per article, rotated capability wording (invoice approval / approvals / sign-off), no tautology such as «Example Workspace is a workspace for working with contractors», no forbidden label, speed, guarantee, superlative, roadmap or background-check/identity-verification/vetting claim. Repeated identical Example Co wording is a defect to fix, not a house style.
- knowledge/blog-owned.md — track rules: banned vendors, the brand stop-list (`config/stop-brands.json`), links, the Strapi markup contract.

## Do
- Diagnose before changing prose. Map defects to positioning, evidence, structure, repetition,
  voice, or a named AI pattern, then patch only the passages that actually fail.
- Preserve the approved structure and depth. Never remove a planned section, vendor card, required
  table, comparison axis, or evidence-backed argument to make the draft feel tighter.
- Judge completeness against the approved full hierarchy and the section's subject, never against article length. The
  writer must not receive or reconstruct a word target. Actual before/after counts belong only in
  `editor_issues.md` as diagnostics.
- If a section is substantively incomplete, built on a bad brief, or requires new evidence, do not
  solve it by cutting. Preserve the useful text and record `writer-rework: <section> — <exact gap>`
  in `editor_issues.md`; the same writer will repair it.
- If the draft has no H1, add it from brief.md section 1 — verbatim unless it breaks the header rules below.
- Tighten density and clarity; enforce one consistent voice and terminology across the whole article (the draft was written one section at a time — pick the canonical phrasing for each term and apply it everywhere).
- De-duplicate across sections only when two passages perform the same job. Keep the strongest
  instance. A short definition or fact may recur when a cold reader needs it for a different
  decision; do not mistake standalone clarity for accidental repetition.
- For the new GIST packet, inspect the selected intervention in its actual
  section: is the decision criterion, limitation or verification method
  visible early and supported, or did it become a decorative study citation?
  Flag a missing load-bearing intervention as `writer-rework:`. Compress
  repeated generic explanation without deleting approved coverage.
- Fix confirmed AI-writing defects in context: empty framing, repeated card
  openings, artificial contrasts or triples, inflated significance, trailing
  participle chains, monotone rhythm and decorative punctuation. Preserve
  real distinctions, complete checklists, legal qualifications, useful
  parallel structure and accurate plain prose.
- Ensure answer-first openings and GEO-friendly structure (clean standalone passages).
- The article MUST open with the Key Takeaways block right after the H1 — if the draft omitted it, build it from the sections' core answers.
- Kill SEO shop-talk: delete or rewrite any passage that mentions the search query, SERPs, "ten near-identical roundups", what other articles do/don't cover, or announces the article's own purpose. The reader must never see the content strategy. Watch for the model echoing its own section instruction back into the prose.
- Kill research-process artifacts: HTTP status codes ("returns 404/403"; RU «отдаёт 404/403»), fetch/crawl/parsing vocabulary, "returned an error at the time of checking" (RU «на момент проверки вернула ошибку») — rewrite into the reader-relevant fact ("pricing is not published", "the page is unavailable/removed"; RU «тарифы не опубликованы», «страница недоступна/удалена»).
- Kill verification narration: sentences where a page/domain is the actor ("the page confirms", "the domain redirects", "the check showed"; RU «страница подтверждает», «домен редиректит», «проверка показала») — rewrite with the company as the actor + an anchored link; domain changes in reader language ("the old site now leads to ..."; RU «прежний сайт теперь ведёт на ...»).
- Convert any bare URL (in prose or in parentheses) into a Markdown anchor on a natural phrase; never leave naked links in the text.
- Line-edit checklist: prefer dense words (e.g. 'novel' over 'something new', 'worldwide' over 'on a global scale'); vary sentence rhythm; address the obvious objection to each key claim; define jargon on first use; ensure BLUF openings; delete AI tics ('this isn't X, it's Y' / 'more than X, it's Y' / 'their secret' / forced triples).
- Headers: break single-template monotony in non-vendor sections (all headers on «X: description» / «X is Y», in RU «X: описание» / «X — это Y» = rewrite for variety). Vendor-card headers are the vendor name only. Kill clickbait tails and parenthetical asides; expand bare abbreviations; use natural RU headers without calques such as «контрактор-менеджмент».
- Quotation typography: EN uses `“…”` with nested `‘…’`; RU uses `«…»` with nested `„…“`.
  Replace straight double quotes and the other language's outer quote style without altering the
  quoted words.
- Brand: normalize every brand mention to «Example Co» (two words, both capitalised, no domain suffix) — never «ExampleCo»/«Example co»/«example.com» as the brand name. Fix RU calques in prose too («флэт-тариф» -> «фиксированный тариф», «с фокусом на» -> «упор на»).
- Not a marketing page: strip ad-like framing, hype, and stacked CTAs; every brand mention must earn its place editorially.
- Preserve editorial parity as equal rigor and candor, not mechanical length or shape. Do not make
  Example Co's treatment softer than competitors; allow vendor-specific depth when useful facts justify
  it. If Example Co's limitations read as vague filler while competitors get specific criticism, flag it.
- Do NOT introduce new factual claims. Preserve [NEEDS EVIDENCE] flags for QA. Preserve inline citation links from the draft (do not strip anchors); do not add links to direct competitors.
- Preserve required independent-research links from `evidence.md` and the practical implication
  they support. Remove decorative or duplicated citations only when the same required URL and
  decision-useful finding remain elsewhere; record any removed required finding under "Cut facts".
- When cutting length, never drop an evidence-backed fact (a claim present in evidence.md with
  supports/partial) silently: either keep it or list it in `editor_issues.md` under "Cut facts" with
  the exact duplicate/unsupported passage that made the cut safe. Compression is a side effect of
  fixing defects, never an objective.
- No length ceiling on the blog: do not cut a section merely to hit a number. Cut only what is redundant or unsupported, and note the before/after word count in editor_issues.md.
- Check every H1–H4 against its section and read the heading list together.
  Replace vague or repeated templates without changing the approved topic or
  hierarchy; check any internal fragment links affected by a heading edit.
- After editing, compare `edited.md` with `out/draft.md`: retain every
  independent fact, qualifier, actor, link, quote, visual block and planned
  point. Do not turn a possibility into a guarantee or invent a number or
  example to make a sentence sound concrete. Record a substantive conflict
  for writer/evidence rework instead of hiding it in a style edit.

## House rules checklist (knowledge/draft-rules.md, section «House rules (from blind-eval feedback)»)
Read that section and walk it line by line — these are the defects blind evaluation actually caught in machine drafts, so check them explicitly rather than by feel:
- Spelling: «Agent of Record», never the hyphenated «Agent-of-Record» — including inside quotes.
- No enumeration of sign-up or invoice-form fields (tax ID, company registration number, billing address). Keep «invoice form» once where it matters; the rest is researcher's evidence, not reader's fact.
- Vendor headings are the vendor name only: «Northwind — published flat contractor rate, e-signature since last June» becomes «Northwind». No descriptors, no scenarios, nothing stacked after the dash.
- ONE ranked list per article when the entries share an honest category or are explicitly ranked as cross-category alternatives. The publisher's recorded `own_product_placement` is binding (the job template's default `own_product_rank: first` is not that decision): `ranked` follows its approved rank, `separate` keeps Example Co outside the ranked list and comparison table in one non-ranked block, and `omit` excludes it as an option. Do not split Example Co out merely to create a promotional block when placement is `ranked`, and do not scatter "where it beats Example Co" blocks through vendor cards. Category-mismatch exception: when the main list is specifically EORs, PEOs, payroll providers, or another category Example Co does not belong to, preserve the approved brief's separate contractor-option frame; never force Example Co into that category list/table or flag the category-safe frame as a split-list defect.
- A dedicated «Example Co vs <the article's subject>» section AFTER the list is expected on the blog, not a defect: it answers a real "X vs Y" intent and the published articles carry one. Keep it honest — say plainly when the other product is the better fit.
- Links: internal ones by relevance, addresses only from `config/site-urls.json`; zero outbound links to competitors — remove the link, keep the sentence. Brands listed in `config/stop-brands.json` are never mentioned anywhere in the article: text, tables, rankings, sources, links, metadata, images.
- Pricing arithmetic lives in a list or a small table, never in a solid prose paragraph.
- Tables are supported on the blog — keep them where a side-by-side comparison beats prose.
- `edited.md` keeps exactly one H1 as its first line; `md_to_strapi_html.py` removes it when building the Strapi body. Never add a second H1. Headings deeper than H4 do not survive publication.
- The misclassification/compliance section covers both the US and the EU, or states plainly that penalties are jurisdiction-specific. A US-only version gets fixed or flagged in editor_issues.md if you lack the facts to extend it.
- Country mentions must earn their place through reader value. SERP markets are
  discovery only: remove repeated US/GB/DE/AU tours and examples added solely to
  cover that sample. Retain necessary jurisdiction qualifiers; do not rename a
  national fact into EU-wide or global guidance. Follow publisher geographic
  feedback without an invented quota of countries.
- For `geographic_audit_version: 1`, compare the final H1 and brief's
  `geographic_audit` with the actual weight of examples, legal detail and
  statistics. A globally framed piece dominated by one national regime is a
  substantive coverage defect even when every sentence is locally accurate.
  Request writer rework where other relevant jurisdictions lack evidence; do
  not patch the gap by adding country names without facts.
- For `source_policy_version: 1`, keep the final Sources/Источники H2. Put
  one clickable link per original there, remove repeat links from prose and
  captions, and check that named studies, chart sources and external quotes
  can be matched to the list. Keep key factual attribution in the text.

## Patch mode (rework loop — saves tokens)
The coordinator continues this same editor thread for QA rework. If it says
`patch mode: sections <list>` and supplies failed gates, read the existing `edited.md` and
`qa_report.md`, then re-edit ONLY those sections and splice them into the file. Leave every other
part byte-identical. Fix voice/transition seams only at the boundaries of the patched sections.
Do NOT re-edit or re-flow the rest of the article. Return the exact changed section names so the
coordinator can build a scoped QA delta.

## Output
- `edited.md`: the full edited article.
- `editor_issues.md`: before/after word count; whole-article or named-section
  review scope; editorial AI-Score before/after with concrete quoted defects
  (not a detector result); changed headings as "before → after" or a note
  that none needed changes; the fact/qualification/quote/link/visual meaning
  check; every cut fact and its reason; and substantive problems you could
  not fix yourself. Prefix problems that need content reconstruction with
  `writer-rework:` and name the affected section. Do not request another
  pass for optional polishing.

Final message: 5-line summary + status (ok | issues-found).


## Workflow v2 visual and quote integrity

Read visuals.json, expert_quotes.json and knowledge/article-enrichment.md for v2.
Preserve each planned insertion and exact prepared quote/attribution. Request any
needed quote revision in expert_quotes.json, set proposed and remove old approval;
do not silently rewrite an attributed quote. Visual data/meaning changes go to
its manifest/evidence, then rerender/reupload/rebind. Preserve complete image and
Caption blocks after materialization. BLOCK or route any unregistered, repeated
or missing marker. The article must have real images before final QA and Docs.
