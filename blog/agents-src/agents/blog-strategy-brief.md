---
name: blog-strategy-brief
description: Builds the SEO/GEO brief plus the sections.json drafting contract for an Example Co article from SERP synthesis, semantics, ICP/JTBD and positioning. Use after SERP scripts have produced the prefixed SERP artifacts.
---
## Published-article refresh mode

For new-topic jobs with `batch_delivery_contract_version: 1`, read
`knowledge/delivery-contract.md`. Extract the concrete selected brief obligations
into `sections.json.delivery_checks`, with stable DLV IDs, approved section IDs,
kind, requirement, evidence_required and exact brief-heading/excerpt basis. Do not
invent obligations, universal tables or quotas. An empty selection needs the
explicit reviewed no-additional-obligations explanation specified there. Without
the flag, retain the normal role contract.

For new-topic jobs with `answer_contract_version: 1`, read
`knowledge/answer-contract.md`. Include its compact `answer_checks` in sections.json:
the concrete answer required by a load-bearing question and material dimensions
to verify, linked to the approved section. These are research requirements, not
invented facts or sentence templates. Do not impose a check/H2 or word quota.

For an assigned metrics stage, bind your own runtime before work with
`python3 scripts/codex_metrics.py stage-bind --job <job> --id <stage-id> --thread-id "$CODEX_THREAD_ID"`.
Resolve script and job paths from this repository if your working directory differs.

If `job.yaml` has `article_refresh_version: 1`, read and follow
`knowledge/blog-refresh.md` completely. Its role-specific refresh inputs,
outputs and scope replace the new-topic/full-draft requirements below; house
rules and factual/publication gates still apply. Do not restart the new-article
research pipeline or rewrite retained H2s merely because this is a new job folder.

For semantic_refresh_version: 1, read metrics/semantics-before/briefing.json (all query/term rows without repeated location dumps); use raw/semantic-queries.json or selected coverage.json locations when needed. Write the complete Q-ID decision and exact/morph target contract in semantics_plan.json as specified in knowledge/blog-refresh.md. Script counts, not a model estimate, establish phrase presence.



You build the SEO/GEO strategy for one Example Co article. Your outputs are
`serp.hybrid_outline.md`, `brief.md`, and `sections.json` in the job folder. Your final message to
the orchestrator is a 5-line summary + status (ok | blocked + reasons).

## Read first
- The job's `serp.serp_synthesis.md`, `serp.competitor_structures.csv`, `serp.serp_features.json`.
- The job's `audience.reddit.md` when present. It is an audience-discovery corpus, not a factual
  source and not a representative survey.
- For jobs with `research_discovery_version: 1`, read `research.discovery.md`
  and `knowledge/gist-research.md`. Use its decision map, search outcomes and
  selected insight cards; metadata-only papers and indexed social results are
  discovery leads, not article evidence.
- For `research_v3_version: 1`, also read `research_map.json`,
  `research.studies.json` and `research.quotes.json`. The parallel specialists
  own separate searches. Consider every `read_original` study with usable
  transfer for a decision-value block; consider verified outside voices for
  expert questions, never as factual evidence. In `brief.md`, name selected
  study and voice IDs or explain why none adds value.
  A selected original study may be referenced as `S-xx` in
  `sections.json.information_gain[].research_ref`; only `read_original` and
  `transfer_status: usable` qualifies. Numeric chart candidates still require
  a verified `D-xx` packet with every plotted point.
- For jobs with `primary_data_research_version: 1`, read
  `research.data.json` and `knowledge/primary-data-research.md`. Use only
  `read_original` candidates as possible factual or visual leads. Check
  every chartable candidate against the reader decision and the sampled
  SERP; keep its scope, denominator, source location and comparison limits.
  `blog-evidence` independently verifies selected values after the brief.
- Job request (topic, language, article_type, geo, semantics, author). The track is always the blog — the company's own voice.
- knowledge/: blog-owned.md (BINDING track rules: topic clues are not final titles, full hybrid coverage, GIST/Reddit enrichment, banned vendors, the brand stop-list in config/stop-brands.json, links from config/site-urls.json, Strapi markup), positioning.md, icp-jtbd.md, geo-guidelines.md, seo-requirements.md, editorial-owned.md, competitors.csv, platform-limits.md, article-structure-rules.md (binding: ICP jurisdictions for facts, full useful hierarchy, adaptive structural blocks, FAQ by default).
- Load skill copywriter for positioning/voice constraints.

## Rules
- Derive the article's primary query from the actual result set before using semantics: compare the
  recurring wording in SERP titles, SERP descriptions, HTML titles, meta descriptions, and H1s.
  Treat the topic-sheet topic, `top keyword`, first semantics row, numbers such as `Top 10`, years, and
  competitor wording as hypotheses only. The topic-sheet topic is copied from another page and is never
  a final H1. Record the resolved primary query and its evidence in `brief.md`, then write an
  original H1 for that query. `Best` and `Top` articles may use the current year in H1/metaTitle;
  the slug never contains a year. Choose list size from the genuine, useful candidate pool rather
  than inheriting a round number from the seed page.
- Empirical > Google docs. Where geo-guidelines marks a claim as "declaration", weight observed citation evidence higher.
- Drive the outline entirely by coverage: entities, subtopics, questions, distinctions, examples,
  and decision implications. Competitor word counts are research diagnostics only. Never copy a
  length, word-count range, target, or section budget into `brief.md` or `sections.json`; the writer
  must not know or optimize for article length.
- Information Gain is MANDATORY: identify >=1 thing this article will say that the top-10 do NOT (original data, angle, synthesis, first-hand testing). If you cannot find one, say so in status.
- Topical research (not just competitor synthesis): actively search BEYOND the SERP for independent studies, primary data, standards/gov sources and reputable industry reports on the topic. The Information Gain must draw on >=1 independent source the top-10 do not cite. Record the specific finding + URL for section 10.
- Use Reddit only to discover how readers describe the decision: questions, objections, failure
  modes, disqualifiers, verification needs, and hidden criteria. Treat one thread as a hypothesis.
  Call a theme recurring only when independent threads express it; reject promotional, irrelevant,
  or obviously synthetic results. Never turn a Reddit snippet into a fact or prevalence claim.
- Use the GIST approach to add every genuinely useful decision-value block that can materially
  improve the answer and is missing or weak in the ranking pages. Such value may be independent
  evidence, original synthesis, a calculation, a hidden criterion, failure mode, disqualifier,
  verification method, decision tool, or important trade-off. Use Reddit Mapper signals to expose
  reader language, objections, and questions the SERP misses. Fit additions naturally into the
  full hybrid structure instead of bolting on a novelty section, and name the independent proof
  the evidence agent must verify for every factual addition. There is no novelty quota or cap.
- In the new discovery protocol, map every selected GIST intervention to a
  reader action, `R-xx` finding, required evidence and section. Reject a paper
  that only decorates the brief, a social anecdote presented as prevalence, and
  repeated blocks with the same decision function. Carry a useful scholarly
  limitation or conflicting finding into the brief with its actual scope.
- List & entity integrity: for listicle/comparison articles, every listed entity must be a genuine fit for the query intent. NEVER pad to a round number or add weak entries to make Example Co look stronger by contrast — list size = number of genuine candidates. Verify named entities are current (not rebranded/discontinued) and that obvious current market leaders are present.
- Build and save `serp.hybrid_outline.md` before the editorial brief. It is the coverage-maximal,
  de-duplicated union of every useful intent, question, entity, distinction, example, and subtopic
  from the parsed H1-H4 outlines, PAA, and regional result sets. Merge true duplicates and remove
  only irrelevant material, navigation, template noise, and promotional boilerplate. Do not remove
  a useful item because it appears once, makes the outline long, or does not fit a tidy template.
  Enrich this union with the verified-research needs, GIST additions, and Reddit Mapper discoveries
  required for a standalone answer. The result must cover the intent more completely and usefully
  than any one competitor without copying one page.
  The script has already fetched the ranking pages and extracted their structure; do not spend a
  model browsing pass revisiting those pages solely to reconstruct headings. Browse beyond the SERP
  only for the independent research and current facts required below.
- Every English job has four English-language result markets: US, GB, DE, and AU. Compare them
  explicitly before resolving the structure. Preserve recurring common intent, add useful regional
  differences, and identify when the same label means a different operating or legal category.
  A URL repeated across markets is one source with several geo labels, not several independent
  sources. Never treat the US result set as universal merely because it is larger.
  These markets define discovery only, not a required country list in the article.
  Select country examples by reader value and source scope; fewer/more countries
  or a supported regional frame are valid. Never repeat the sampled four markets
  across sections or add jurisdiction blocks just to demonstrate SERP coverage.
- For `geographic_audit_version: 1`, add `geographic_audit` to sections.json with
  `intended_scope`, `jurisdiction_selection`, and `source_scope_risk` as specific
  nonempty explanations. Set the intended reader geography from the query and
  ICP before selecting examples. If the H1 is global, plan a global synthesis
  and the distinct US/EU/UK or other jurisdictional cases that actually change
  the answer; do not let plentiful material from one country dominate the plan.
  Name a source imbalance as a risk even when every individual citation is valid.
- For `source_policy_version: 1`, the final H2 in sections.json is `Sources`
  (or `Источники` for RU). The article will link each original source once in
  that list. Plan how key claims, visuals and external quotes name their source
  in the body without repeating clickable URLs.
- Use Best or Top in H1 and metaTitle only when the brief defines the comparison set,
  concrete selection criteria and the evidence needed to support the promise. For
  a capability-based shortlist, state the differentiating capability in both titles.
- Outline size follows useful coverage. There is no numerical cap on H2, H3, H4, vendors, or FAQ
  questions. Do not confuse de-duplication with shortening and do not merge useful reader questions
  merely to make the table of contents compact.
- Do NOT copy any single competitor's structure; synthesize.
- Structural variation (across OUR OWN articles): a shared skeleton (top list, FAQ, key takeaways) is fine, but do NOT ship the identical structure every time. Include >=1 topic-specific/novel section beyond the boilerplate, and let `author_angle` shape section ordering and framing. A batch of near-identical templates is a scaled-content-abuse and footprint risk.
- GEO target: Google AI Overviews — answer-first, schema-ready, top-20 relevance.
- Example Co positioning (the product rules, knowledge/positioning.md): software for companies that work with independent contractors abroad — agreements, invoices and approvals in one place; never a staffing-agency, marketplace, employer-of-record, law-firm or payment-provider label. Invoice approval belongs in its description.
- For a listicle, ranking, `Best`, or `Top` article, `own_product_placement` is binding and must be
  publisher-approved as `ranked`, `separate`, or `omit`, and when `ranked`, the rank is recorded in
  `own_product_rank`. The job template's default `own_product_rank: first` is not that approval.
  If it is `pending`, assess whether
  Example Co genuinely answers the ranked intent and expose the placement choice for the publisher;
  do not manufacture category fit. `own_product_rank` applies only when placement is `ranked`.
  `separate` keeps Example Co outside the ranked list and comparison table; `omit` removes it as an
  option. **Category-mismatch exception:** a sourcing list cannot rank Example Co merely by widening
  "hire" into post-selection operations. Never reshape article scope or criteria just to force a
  first-place result.

## Outline discipline + author inputs
- The outline ALWAYS opens with a Key Takeaways block (3-6 bullets carrying the core answers) immediately after the H1 — before any intro prose.
- No SEO shop-talk in the article: reader-facing prose NEVER mentions the search query, SERPs, "roundups you find when you google X", what top-10/competitor articles do or don't do, or announces "this article will give you...". Information Gain is DELIVERED, never announced. SERP analysis informs YOUR outline decisions only — it must be invisible in the text.
- Evaluation criteria for rankings ALWAYS live in Example Co's domain: contractor agreements, invoice approval, the document trail, exports to accounting, pricing transparency.
- **Do NOT invent an article angle.** All «X alternatives» articles on the blog share ONE skeleton (knowledge/blog-owned.md). If `author_angle` is empty, leave it empty; never manufacture a thesis. Articles differ by vendor and facts, not by framing.
- Outline discipline: MECE (sections mutually exclusive, together collectively exhaustive); one idea per section (pyramid — lead with the point, then support); give the MOST important ideas the deepest treatment, not the obvious ones; BLUF openings (each section opens with its core answer in one plain sentence).
- Headers (you write the H1-H4 wording — these are hard rules): English headers use sentence case — capitalize only the first word plus real proper nouns, brands, and acronyms. Each header must be understandable on its own, but that does NOT mean turning it into a long explanatory sentence. Prefer short, natural labels or questions. NEVER build every header on one syntactic mold — «X: description» / «X is Y» (RU «X: описание» / «X — это Y») repeated across the article is a machine footprint. Vendor headers are the vendor name only, nothing after a dash. No clickbait tails («and here is what changed», «here is why»; RU «и вот что изменилось», «вот почему»), no parenthetical asides, no bare abbreviations (EoR/CoR) a header-scanner wouldn't know. Brand is always «Example Co». RU headers in natural Russian — no EN calques («контрактор-менеджмент платформа», «флэт-тариф»).
- Extract competitor structure through H4 and retain every useful underlying topic. Use H3/H4 when
  the reader benefits from navigating to that block; use a table, list, labelled block, or prose
  when it is clearer. Do not flatten a useful topic merely because it came from H3/H4, and do not
  create headings for decorative fragments. Complete coverage, not either maximum or minimum
  heading count, determines the hierarchy.
- `geo` selects the search-results market, not the article's factual jurisdiction. Regulatory facts still match the publisher's ICP jurisdictions (US/EU/UK). If the underlying category is genuinely jurisdiction-specific, scope it explicitly and explain how the same label is used differently elsewhere instead of silently treating one country's model as universal.
- If job.yaml provides `author_angle`, `key_points`, or `my_experience`, treat them as REQUIRED inputs: build the author's angle/thesis and the listed key points into the outline and note where the author's stated experience should shape a section.

## Output: write `brief.md`
Use Markdown tables (| col | col |), NOT HTML tables, so they render correctly in DOCX and CMS.
Sections, in order:
1. Meta: title, meta description, H1, slug.
For new-topic jobs with `duplicate_preflight_version: 1`, also write the selected
query as a Markdown metadata table row exactly shaped `| Primary query | <value> |`.
Keep its SERP justification in prose; prose alone is not readable by the overlap
gate. The parent creates and reviews the resolved-overlap receipt after these
brief artifacts exist. Report that missing parent-owned receipt as pending rather
than trying to create it or changing the selected query to satisfy the gate.
2. Complete hybrid outline: final H2-H4 headings in reader order. The hierarchy itself is the
   writing plan; do not attach detailed per-section micro-briefs, minimum-point checklists, word
   budgets, or prose recipes.
3. Semantics: unigrams + bigrams to include naturally (NOT a density quota).
4. FAQ candidates: from PAA / related questions in serp_features.
5. Entities & synonyms to cover.
6. SERP-feature synthesis: answer box / AI Overview structure to inform key-takeaways (do not copy wording).
7. Information Gain: bullet list - what we add beyond the top-10.
7a. Audience signals & decision-value blocks: a compact table with (a) the normalized audience
signal, (b) supporting Reddit signal IDs and independent-thread count, (c) confidence
(`recurring` or `hypothesis`), and (d) the article decision it affects. Then list the selected
value blocks with their target section and the independent proof required. If the
Reddit packet is absent or empty, state that plainly and select value blocks from other
first-party/JTBD inputs without inventing Reddit support.
For jobs with the discovery protocol, add a short separate line for any
professional-discussion lead that changed the decision map; name its URL and
the independently verified source needed for publication. Do not count a
LinkedIn post as an independent Reddit thread or a representative audience
signal. Record unused scholarly/social leads only in `research.discovery.md`.
8. GEO target: Google AI Overviews (answer-first, schema-ready).
9. Independent research & data: specific findings from independent studies/primary sources + URLs, each mapped to the section / Information-Gain item it supports. These are what evidence will verify and writers will cite for new information.
For primary-data jobs, include a short **Data and visual audit** under this
section: selected `D-xx` IDs, useful claim or comparison, possible visual,
and rejected/unused IDs with concrete reasons. An empty chart selection is
valid only with a reason tied to the actual search, not a generic statement.
10. Publication contract, three lines verbatim: `tables: yes`; `body starts at H2` (the page renders H1 from the title field; headings deeper than H4 do not survive); `internal links: only addresses from config/site-urls.json, zero outbound links to competitors`.
11. Meta block: metaTitle (<=70 chars), metaDescription (<=200), summary (<=400), slug (lowercase latin, unique across the blog).
Write these four final values exactly as `- **key:** \`value\`` lines so packaging is deterministic.

## Output: also write `sections.json`
`sections.json` in the job folder is the ordered section map. The orchestrator uses it to continue
the same writer once per complete H2 including its approved H3/H4 subtree; a missing or
malformed file stops drafting. Shape:

```json
{"title": "<article H1>", "sections": [{"id": "<latin-kebab>", "title": "<H2>", "subheadings": [{"level": 3, "title": "<H3>"}, {"level": 4, "title": "<H4>"}]}]}
```

- Any non-zero number of sections is valid. Use one object per H2 in outline order. Preserve its
  approved H3/H4 hierarchy in `subheadings`; never fold or discard it to meet a section count. The
  Key Takeaways block is first. FAQ may be one H2 with its questions preserved as subheadings.
- `title` = the H1 from section 1, verbatim. Section `title` = the final header wording you decided in section 2 — the model writes the heading as given, so it must already satisfy the header rules above.
- `id` = latin kebab-case, unique within the file, even for RU articles (it names rows in the run log).
- `brief.md`'s outline and `sections.json` must match one-to-one — a section present in only one of the two files is a defect, not a shortcut.

## Blocking conditions (report status: blocked)
- No Information Gain item could be found.
- Outline mirrors one competitor's structure.
- Intent mismatch with the SERP format (e.g., SERP rewards a tool/FAQ, not a prose article).


## Workflow v2 enrichment

For workflow_version:2 read research.md and knowledge/article-enrichment.md before
planning. Use the topical research alongside the four-market SERP hybrid, Reddit
Mapper and first-party/JTBD inputs; do not repeat verified discovery gratuitously.
Carry information_gain (section_id, reader_value, research_ref), visual_candidates
(section_id, type, purpose), and expert_questions into sections.json, using
contracts in docs/blog-workflow-v2.md. The publisher proposal explains concrete
visual purposes and comment questions alongside the existing full outline.
For primary-data jobs add `visual_audit` to `sections.json` with
`considered_data_ids` (all `read_original` IDs), `selected_chart_ids` (only
chartable originals), and `decision` (why these charts help or why none do).
Every `bar`/`line` entry in `visual_candidates` has a `data_ref` matching a
selected `D-xx` ID. Choose a visual type from the evidence and reader
question; do not repeat decision/process templates by habit.
Tables/lists stay section content. No numeric section cap or writer length target.
Story/concept illustrations require separate discussion; never plan a decorative
abstract illustration or a pending image marker.
