---
name: blog-article
description: Create, continue, review, package, or prepare an Example Co blog article through the repository's multi-agent Codex pipeline. Use for article jobs from topic and semantics through evidence, drafting, QA, Google Docs review, and optional Strapi draft creation. Do not use for generic Example Co copy outside the blog pipeline.
---

# Example Co blog article pipeline — Codex track

The parent Codex agent orchestrates article jobs directly. It routes work, runs deterministic
scripts, records metrics, and validates artifacts. Specialized depth-1 agents handle research,
editing and independent QA. For new topics, MiniMax drafts and DeepSeek reviews the draft through
OpenRouter. State passes through the job folder and immutable batch receipts.

Before starting, read `AGENTS.md`, `knowledge/blog-owned.md`, and this file. The current distilled rules in `knowledge/` override older documents and archived job artifacts.

For new jobs (workflow_version:2), also read docs/blog-workflow-v2.md and
knowledge/article-enrichment.md. Keep job/progress.md current: request, decisions,
stage, files/checks, open issues, review links and explicit approvals. Shared
workflow decisions go to docs/design-notes.md. Older jobs retain their
contract and are not migrated automatically.

## Published article refresh

For an authorized update of an existing published article, use a separate
versioned cycle job with `article_refresh_version: 1`; read
`knowledge/blog-refresh.md` before dispatch. Preserve the original job. The
required specialists remain strategy, evidence, one persistent complete-H2
writer, editor/humanizer and independent QA, with current exact model routes.
New refresh cycles must carry `semantic_refresh_version: 1` (new_job.py defaults it).
Before strategy run the page-only 90-day semantic collection and baseline audit
from knowledge/blog-refresh.md. Strategy writes semantics_plan.json. Run its
writer check before drafting and its after audit/check after the editor. These
script reports are mandatory for QA/sealing/Docs; do not let model judgments
substitute for exact and morphological counts. Existing jobs keep their contract;
audit them only to a separate explicit batch directory without changing seals.
Use refresh metrics planned stages and the normal v2 package/QA seals. Conditional
visual/quote work keeps its existing specialist gates. Refresh review Docs sync
dedicated fields/history in the configured topic sheet without resetting the original
article lifecycle. Do not treat review readiness as a published update.

## Entry and model routing

For new-topic jobs with `answer_contract_version: 1`, follow
`knowledge/answer-contract.md` within the existing brief/evidence/writer/editor/QA
stages. The compact answer_checks plan links reader questions to qualified facts
and actual answers, including final captions/tables. Brief/input validation and
QA sealing/export check its references; semantic completeness remains independent
QA work. No new specialist, whole-text triplet pass or numeric SEO gate is added.
Existing jobs, refresh cycles and translations retain their contracts.

New-topic jobs use `production_text_backend: openrouter_hybrid`. The writer is MiniMax M3.1 Flash
and the first-pass critic is DeepSeek V4.1 Flash. `config/blog-openrouter.json` pins the exact
endpoints, reasoning settings and price caps. Keep the native writer route for jobs created under
that contract and for refresh cycles. Keep the native editor and independent QA for every new job.

The parent reads `config/codex-model-routing.json`, then spawns every specialist directly with
`fork_turns="none"` and the exact route below. Give every thread a collision-safe task name that
includes the article job and role. The parent runs scripts and deterministic gates itself, but
does not research, draft, edit, or fact-check article prose.

| Agent | Model | Reasoning effort |
|---|---|---|
| `blog-research-map` | `gpt-6-sol` | `medium` |
| `blog-topic-research` | `gpt-6-sol` | `medium` |
| `blog-primary-data-research` | `gpt-6-sol` | `medium` |
| `blog-study-research` | `gpt-6-sol` | `medium` |
| `blog-quote-scout` | `gpt-6-sol` | `medium` |
| `blog-visual-planner` | `gpt-6.1-terra` | `medium` |
| `blog-expert-quotes` | `gpt-6.1-terra` | `medium` |
| `blog-strategy-brief` | `gpt-6-sol` | `medium` |
| `blog-evidence` | `gpt-6-sol` | `medium` |
| `blog-company-cards` | `gpt-6.1-terra` | `medium` |
| `blog-section-writer` | `gpt-6.1-terra` | `medium` |
| `blog-editor` | `gpt-6-sol` | `medium` |
| `blog-qa-factcheck` | `gpt-6-sol` | `medium` |
| `blog-visual-qa` | `gpt-6.1-sol` | `medium` |

`blog-coordinator` remains in the routing file and agent catalog only as a dormant compatibility
role. Do not dispatch it in the active flat track. Nested `codex exec` launches remain forbidden.

Use the same minimal dispatch wording for every initial specialist turn, substituting only the
three placeholders:

`Work on job <job>. Bind metrics stage <stage-id> from your current CODEX_THREAD_ID. Read and follow <role-file> completely. Produce its role-defined outputs.`

For the writer, append only `Requested unit: "<H2>".`; this includes its complete approved H3/H4 subtree. For a
rework turn, append only the exact deterministic or QA defect and its diff path. Do not add
editorial guidance, length judgments, optimization goals, suggested conclusions, or any other
content instruction from the parent. The role specification and job artifacts are the complete
content instructions. Prompts name paths instead of embedding file contents.

The provider rollout is the authority for the model and effort actually used; the metrics report
fails closed when runtime values differ from the routing file.

## Inputs and job ownership

Required inputs are topic, language, article type, semantics, author, and `own_product_rank` (`first` by default). Ranking/listicle jobs also require a publisher-approved `own_product_placement`: `ranked`, `separate`, or `omit`; the default rank is not that approval. `own_product_rank` applies only when placement is `ranked`; it never silently turns a category mismatch into an in-list entry. Optional inputs are `author_angle`, `key_points`, and `my_experience`. Every English article uses four English-language SERP markets — US, GB, DE, and AU — regardless of topic. The blog is always owned voice and has no fixed length ceiling.

## Topic queue and mandatory topic-sheet sync

The Google Sheet in `config/temnik.json` is the source of truth for blog topic order and lifecycle
state. This narrowly scoped sync has standing publisher authorization. Completed-article review
Docs have the separate standing authorization described below; neither exception authorizes a
Strapi mutation.

Before proposing a batch, run `python3 scripts/temnik.py next --limit <N>` and evaluate rows from
top to bottom. Never invent topics or jump to a later attractive row. Apply the existing topic-fit
and duplicate checks to each row:

For each candidate row, first run `python3 scripts/temnik.py preflight --cluster-id <id>`.
It reads current published Strapi articles and other local jobs, searches title, slug, summary and
H2s with FTS5, and adds embedding similarity using the local macOS NaturalLanguage model. Inspect the
reported nearest pages and their reader intent; the scores are retrieval signals, not an
automatic duplicate verdict. If covered, use `temnik.py skip --duplicate --url <existing URL>`.
If distinct, record a specific reader-intent rationale with
`python3 scripts/topic_overlap.py decide --cluster-id <id> --reason "..."`.
New jobs carry `duplicate_preflight_version: 1`; `temnik.py start --apply` refuses them without
a current reviewed report, and rechecks that the live/local catalog has not changed. If it has,
rerun preflight and review the changed candidates. If the local model is unavailable, record the
lexical-only status in the batch decision log.

- country-specific EOR, hiring, or contractor topics belong to country guides, not this blog;
- pure definitions that belong in the glossary are not blog articles;
- a genuinely covered intent is a duplicate, but shared definitions or subtopics do not make an
  otherwise independent article a duplicate;
- an off-positioning or otherwise unsuitable topic is skipped.

Record every rejection immediately with `temnik.py skip --reason <specific reason> --apply` (and
`--duplicate --url <existing URL>` for a duplicate), then continue until the requested number of
suitable topics is reached. The publisher approves the exact topic-sheet rows. After approval, put that
row's cluster ID in `job.yaml` as `temnik_cluster_id` and run:

```bash
python3 scripts/temnik.py start --cluster-id <id> --job <job> --apply
```

The original `Topic` and `Top keyword` fields are research clues copied from another page, not a
final query, headline, list size, year, or wording constraint. Never carry a number such as
`Top 10`, a year, or a competitor's phrasing into the article merely because it appears in the
topic-sheet row. Resolve the primary query from recurring language in live SERP titles, descriptions,
HTML titles, and H1s, then create an original H1 that serves that query better. `Best` and `Top`
articles may include the current year in the H1 and `metaTitle`; the slug never includes a year.

Create a collision-safe job with:

```bash
python3 scripts/new_job.py "<topic>" <YYYY-MM-DD> blog
```

Fill its `job.yaml` and `semantics.csv`. Work only in the job path printed by the script. Before the brief, refresh internal URLs with `python3 scripts/fetch_site_urls.py --date <YYYY-MM-DD>` when the user has authorized live network updates.

Look for adjacent jobs with the same primary query and geo. Reuse research artifacts and verified evidence where applicable, never prose. A new article needs a meaningfully distinct information gain and structure.

## Delegation map

Use the matching project custom agent when the client exposes agent selection. Otherwise spawn a
normal subagent with the routed model/effort and explicitly tell it to read the named role file
before acting. Every prompt includes only the assigned scope, job path, required input paths,
expected output paths, and exact defects for a rework turn. Never supplement the role with a
parent-authored interpretation of how the specialist should research, write, edit, or judge the
article.

0. For jobs with `research_v3_version: 1`, after SERP and Reddit dispatch
   `blog-research-map` first. Validate `research_map.json`, then dispatch
   `blog-topic-research`, `blog-primary-data-research`, `blog-study-research`
   and `blog-quote-scout` concurrently as four separate depth-1 threads.
   The document specialist runs topic-specific `filetype:pdf`, slide,
   word-document and spreadsheet searches through `fetch_google_serp.py
   --provider auto` (XMLRiver first), archives `raw/document-search-*.csv`,
   opens relevant originals and records candidate data. The study specialist
   uses catalogues as discovery and reads accessible originals. The quote
   scout searches X, indexed LinkedIn, ordinary web and original practitioner
   publications, verifying exact wording and attribution. The brief waits
   for all four packet validators; no generic search note substitutes for a
   raw document SERP archive or a read original.
0a. For earlier jobs without `research_v3_version: 1`, after SERP dispatch `blog-topic-research` and, for jobs
   with `primary_data_research_version: 1`, `blog-primary-data-research` in
   parallel. They own separate outputs and neither waits for the other.
   The brief waits for both validators.
   `blog-topic-research` reads the four-market SERP packet, Reddit signals and knowledge,
   researches primary/independent findings and writes research.md before the brief.
   New jobs with `research_discovery_version: 1` also produce
   `research.discovery.md` using `knowledge/gist-research.md`: a GIST
   decision map, bounded scholarly and professional search logs, source
   insight cards, and optional externally attributed quote candidates.
   The parent validates this packet before dispatching the brief agent.
0b. For jobs with `primary_data_research_version: 1`,
    `blog-primary-data-research` searches original documents and datasets for
    comparable numeric findings, then writes `research.data.json` under
    `knowledge/primary-data-research.md`. It may return no chartable data with
    a documented search and reason. The parent validates the packet before
    dispatching the brief agent.
1. `blog-strategy-brief` reads research.md and SERP artifacts and writes `brief.md` plus `sections.json`.
2. `blog-evidence` writes `evidence.md` and may enrich `companies/` with verified current facts.
3. `blog-company-cards` writes `company_cards.md` after evidence, only for listicle/comparison formats that need cards. The X-vs-Y-vs-Example Co format does not use a card parade.
3a. `blog-visual-planner` writes visuals.json after evidence.
3b. `blog-expert-quotes` writes exact proposed expert_quotes.json before the writer.
4. MiniMax writes the complete outline sequentially under `sections/`, one complete H2 subtree per turn
   in the same article conversation. The parent imports verified outputs and assembles
   D0. DeepSeek reviews D0 in full. For native-writer jobs use `blog-section-writer`.
5. `blog-editor` writes `edited.md` and `editor_issues.md`.
5a. `blog-visual-qa` independently inspects full-size rendered visuals and their
    390 px previews after the deterministic layout check. It writes `visual_qa.json`
    before media upload for jobs with `visual_qa_version: 1`.
6. `blog-qa-factcheck` writes `qa_report.md` and never edits prose.

Dependencies for new v3 jobs are strict: SERP/Reddit → research map → four
parallel specialists → map/document/study/quote/discovery validators → brief →
publisher checkpoint → evidence → cards if needed
→ parallel visual/quote plans → input validation → render/layout preflight
→ parallel (H2 writer → assembly → first-pass DeepSeek for hybrid jobs → edit → editor delta) and independent visual QA
→ join both passed branches → upload/bind visuals → article QA.
Parallel branches own different outputs: writer sections/recovery state and visual QA receipt.
Do not run cards beside evidence, split one article across writer agents, or start editing until
the complete writer sequence and assembly have completed.

Before any stage that may mutate shared `companies/`, acquire the `companies` lock with
`scripts/pipeline_lock.py`. Lock `site-urls` around a live site-map refresh. Separate article jobs
may otherwise progress concurrently, subject to available Codex agent slots.

## SERP

When live SERP collection is needed and authorized:

```bash
python3 scripts/fetch_google_serp.py --query "<primary query>" --geo us --geo gb --geo de --geo au --top-n 20 --serp-features --output-file <job>/raw/serp.csv --features-output-file <job>/raw/features.json
python3 scripts/build_article_serp_brief.py --input-file <job>/raw/serp.csv --features-file <job>/raw/features.json --output-prefix <job>/serp --require-geo us --require-geo gb --require-geo de --require-geo au
python3 scripts/collect_reddit_signals.py --query "<article topic>" --geo us --output-file <job>/audience.reddit.md
```

`fetch_google_serp.py` defaults to `--provider auto`: it uses XMLRiver first and automatically
falls back to DataForSEO when XMLRiver returns a service/transport error or no organic results.
`DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` live only in `config/.env`; use
`--provider dataforseo` to bypass XMLRiver deliberately. Both providers emit the same CSV and
feature JSON contracts. If collection is partial, repeat the original queries and markets with
`--resume` and the same output paths. It preserves organic rows and feature JSON for successful
pairs and requests the remaining pairs again. A provider error returns non-zero.

For every English topic, the builder's four `--require-geo` guards confirm that `raw/serp.csv` contains organic rows for all four geo keys before any page fetch. If both configured providers fail or a required geo remains empty, stop and report the source failure. The SERP builder de-duplicates repeated URLs before fetching pages, retains every geo in which a URL ranked, and extracts H1-H4. The strategy brief must compare the four markets, preserve regional differences, and write `serp.hybrid_outline.md`: a coverage-maximal, de-duplicated union of every useful intent, question, entity, distinction, example, and subtopic found across the relevant pages. Remove only true duplicates, irrelevant material, navigation, and promotional boilerplate. Never remove a useful subtopic to make the outline shorter or tidier. Enrich that hybrid with decision-useful additions absent from the ranking pages, using the GIST information-gain approach, the Reddit Mapper packet, first-party/JTBD knowledge, and independent research. The resulting article plan should answer the query more completely and usefully than any single ranking page; it must not silently universalize the US result set. Reddit remains one bounded discovery packet rather than four duplicate calls.
The Reddit command makes two bounded search requests and stores indexed titles/snippets; it does
not crawl Reddit. Failure or an empty packet does not block the article: record the source failure
and let the brief use GIST, first-party/JTBD, and independent inputs instead. `audience.reddit.md`
is discovery context, never factual evidence. Reddit Mapper supplies reader language, objections,
hidden criteria, and missing questions; GIST supplies original decision value beyond the SERP.
Evidence independently verifies every publishable claim derived from either source.
For earlier jobs without `research_v3_version: 1`, the topic research agent also searches OpenAlex or Crossref for a
question-specific study and indexed LinkedIn/professional discussion for
reader objections. A negative or irrelevant result is recorded rather than
forcing a study or social quote into the article. LinkedIn is not scraped:
indexed results reveal leads, not quotable text or factual evidence. The
agent records source access, method, scope and transfer risk in
`research.discovery.md`. For a named external quote, it records a directly
readable original, exact short wording, speaker, publication date and context.
The quote agent must evaluate that candidate before defaulting to staff-only
comments. Proposed external quotes can enter the review Doc with a linked
original and review preface; exact text and attribution need publisher approval
before Strapi export. Run before dispatching the strategy brief:

```bash
python3 scripts/validate_research_discovery.py --job <job>
python3 scripts/validate_primary_data_research.py --job <job>
python3 scripts/validate_research_map.py --job <job>
python3 scripts/validate_study_research.py --job <job>
python3 scripts/validate_quote_research.py --job <job>
```

The validators for absent protocol flags are no-ops. For v3 jobs, do not
start the brief until the shared map and all four parallel packets pass.
If document research has no `read_original` finding, continue that stage or
stop before the brief with the documented blocker. Do not fill the gap with
an invented number, generic unrelated research or a later repair pass.
The brief records every
`read_original` data candidate in `sections.json.visual_audit`, selects only
reader-useful chartable candidates, and explains omissions. A numeric visual
candidate refers to its `D-xx` data ID; evidence reopens every selected
original and verifies all plotted points before visual planning. A batch of
near-identical visual type sets triggers an editorial review of rejected data
and alternative useful visuals; it does not impose a chart quota.
For a batch, after all `visuals.json` plans exist, run
`python3 scripts/audit_visual_mix.py --jobs <job1> <job2> ... --output <batch-review.json>`.
If `needs_editorial_review` is true, review each article's `visual_audit`,
the data research packet and rejected chart reasons before export. Record
the editorial conclusion in docs/design-notes.md; the script does not require
a chart where reliable decision-useful data are absent.

## Brief and evidence guards

After the brief agent returns, run `python3 scripts/validate_article_brief.py --job <job>`. It verifies that `sections.json` parses, contains a non-empty ordered list with unique kebab-case IDs, preserves the approved H2-H4 hierarchy, and exposes no word-count or length target. There is no numerical minimum or maximum for sections or headings. Each section needs only `id`, `title`, and its approved subheadings when present; detailed writer micro-briefs are not required. Before showing the proposal, inspect every H1-H4: English headings must use sentence case, wording must be concise and natural, and the hierarchy must express the full useful hybrid rather than an arbitrary heading quota. A title-copying, lost-intent, casing, artificial-hierarchy, regional-coverage, or exposed-length defect returns to the same brief agent before publisher review.

For new `duplicate_preflight_version: 1` jobs, rerun the overlap search after the strategy brief
has resolved the real primary query: `python3 scripts/topic_overlap.py check --stage resolved
--cluster-id <id> --topic "<job topic>" --keyword "<brief primary query>" --exclude-job <job>`.
Review the candidates against the seed report and record a specific decision using
`topic_overlap.py decide --stage resolved --cluster-id <id> --reason "..."`. The brief validator
fails until that decision matches the brief query. Strapi export also rejects a missing decision
or a newly indexed strong match that has not been reviewed.

For a newly selected topic, stop at the publisher checkpoint before evidence or drafting. Return a
compact proposal containing the topic-sheet row/topic, duplicate-check result, resolved primary query,
proposed original H1, article angle, and complete H2-H4 outline. For every listicle, ranking,
`Best`, or `Top` article, the proposal must also state whether Example Co is a genuine answer to the
ranked intent and ask the publisher to approve one placement: `ranked` (plus the exact rank),
`separate` (outside the list and comparison table), or `omit`. A prefilled
`own_product_rank: first` is not approval. Record the choice as `own_product_placement` in `job.yaml` and
route any required outline correction to the same brief agent before continuing. Do not start the writer—or spend tokens on
evidence/cards—until the user approves that proposal. On approval, resume the same job and brief;
do not regenerate them. Skip this checkpoint only when the user has already explicitly approved
those exact items for that job.

For hybrid jobs, save the ordered proposal as `docs/workflow-v2/batches/<batch>/publisher-proposal.json`.
Each item carries `cluster_id`, repository-relative `job`, `heading`, `sections` and `sha256` for
`brief.md`, `sections.json` and `serp.hybrid_outline.md`. The approval
`brief-approval.json` records `status: approved`, the publisher's identity and response,
`api_budget_usd`, `publisher_proposal_sha256` and the exact same `items`. Include the budget
in the existing brief checkpoint. Reuse explicit approval already given for that package.
For a proposed Best or Top claim, show the comparison set, criteria and evidence for evaluation.
If the evidence cannot sustain the promise, settle the exact H1 and metaTitle before paid drafting.

After that checkpoint, do not return to the publisher for a purely editorial heading correction.
The parent may route sentence case, unnatural wording, research-process narration, or another
non-substantive heading defect without renewed approval when the change preserves the approved
intent, H1, angle, hierarchy, and coverage. Sync the wording across every affected job artifact,
record the correction, and run the relevant validation and targeted QA re-check. Ask again only
when the proposed change would alter meaning, positioning, hierarchy, or substantive coverage.

Finish the preflight metrics run as soon as the parent turn ends. After approval, register
`production-resume` as a new lifecycle phase in the new parent turn and spawn the required
specialists directly. This keeps user waiting time outside the article total and preserves
provider token attribution. Bind every specialist to its metrics stage immediately. If native
delegation does not return a thread id, pass the stage id in the specialist prompt and require
self-binding from the specialist's own `CODEX_THREAD_ID` before work.
Stop each metrics stage as soon as its agent or script finishes, including the persistent writer
after the final heading unit; mark failed or abandoned attempts explicitly. Stop the production
run when the review Doc is ready. In a timed pilot, record each stage's elapsed time, model,
requests, input/cached/output tokens, and the total wall time. Report subscription-limit changes
only as observed account-wide snapshots, never as exact per-agent quota use when stages overlap.

Start metrics with `--scope full` for an authorized uninterrupted article, or `--scope preflight`
when stopping at the brief checkpoint. Resume approved work with
`phase-start --name production-resume --scope production`. Register canonical stage names:
`serp` (collection and SERP builder), `reddit`, `research-map`, `topic-research`,
`document-research`, `study-research`, `quote-research`, `strategy-brief`, `evidence`,
`visual-plan`, `expert-quotes`, `visual-render`, `visual-layout`, `visual-qa`, `writer`,
`assemble`, `openrouter-critic` (hybrid only), `editor`, `editor-delta`, `review-visual-upload`, `pre-qa-package`, `article-qa`,
`gdoc-review-push`; protocol flags and documented empty visual plans determine applicability.
Cards and rework have additional stages. The metrics tool locks every manifest mutation and
checks this expected plan; a lost stage makes the report INCOMPLETE. Agent execution, dispatch,
handoff and closing delays are reported separately from wall time. Close a completed stage and
send its dependent assignment promptly instead of waiting again for an already completed agent.

Evidence is the sole fact boundary for article prose. The evidence agent reads `companies/` first, browses only for gaps or stale facts, and records blocked or partial sources instead of upgrading them into certainty.
For the selected decision-value blocks, evidence marks only the genuinely useful independent
sources as `article_link: required`. Vendor/competitor URLs are always `forbidden`; the writer uses
required research links naturally and explains what decision each finding changes.

## V2 plans before the writer

After approved evidence/cards, dispatch blog-visual-planner and blog-expert-quotes
with the same fixed routing envelope and separate metrics stages. Use new repo-local
routes. Input validation must pass before starting the persistent writer:

```bash
python3 scripts/workflow_gate.py check --job <job> --target inputs --offline
```

The writer knows purpose, location and data from visuals.json and inserts each
registered [[VISUAL:<id>]] once in its section. It inserts exact prepared comment
words/attribution, linking external attribution to its original; it does not
create attributed quotes independently. Charts and
schemes are code-generated in brand colors with the original logo. Story/concept
illustrations require separate discussion; abstract decoration is not planned.
Tables and lists remain ordinary writing/editor tasks.

Immediately after both plans validate, run the render/layout preflight before any writer work:

```bash
python3 scripts/render_visuals.py --job <job>
python3 scripts/check_visual_layout.py --job <job>
python3 scripts/workflow_gate.py check --job <job> --target writer --offline
```

Route render/geometry failures to the visual planner/renderer now, not after drafting.
Once preflight passes, dispatch `blog-visual-qa` and the persistent writer concurrently. Visual QA
opens the full PNGs and 390 px previews and owns `visual_qa.json`; it does not edit writer files.
An empty plan with a documented omission reason needs the deterministic layout report but no
independent visual agent. A visual BLOCK returns to its original planner/QA threads while
unaffected text can continue. If a repair changes meaning, placement, data, alt/title/caption or
exact quote content, pause affected writing and synchronize that dependency before proceeding.
Appearance-only repairs keep the writer's content contract. Neither uploads nor article QA
may bypass the independent visual gate.

## Draft and edit

For hybrid jobs, run the shared runner after the writer preflight. Use a unique revision per
phase, the same batch ID for every phase, and optional repeated `--cid` values for subsets.
Run MiniMax alongside independent visual QA.

```bash
python3 scripts/blog_openrouter.py prepare writer --batch <batch> --revision writer-1
python3 scripts/blog_openrouter.py execute writer --batch <batch> --revision writer-1
python3 scripts/blog_openrouter.py import writer --batch <batch> --revision writer-1
python3 scripts/blog_openrouter.py prepare critic --batch <batch> --revision critic-1
python3 scripts/blog_openrouter.py execute critic --batch <batch> --revision critic-1
python3 scripts/blog_openrouter.py import critic --batch <batch> --revision critic-1
```

`prepare` freezes the context and sends zero paid requests. `execute` checks the exact provider,
token ceiling and price cap. Only a complete response from the pinned route can be imported.
Successful units resume from their receipts. Use `--retry-failed` only for known, reconciled
failures; inspect charged partial outputs and use a scoped revision if their inputs change.
Unknown charges and incomplete POST intents block new calls. Both routes start with an output
ceiling of 16,384 tokens. Register hybrid `writer`, `assemble` and `openrouter-critic` as
script stages. Give the native editor `raw/openrouter-critic.json`,
`raw/openrouter-draft-check.json` and the approved job files. The editor checks the findings
against the evidence and routes substantive defects back to MiniMax.

If only heading punctuation or wording drifted, inspect the raw section and the approved order.
Reimport with `--heading-restorations <repo-relative JSON>`. Its version-1 record contains
`audited_by`, `audit_reference` and `restorations`. Each entry gives `cluster_id`, `unit_id`,
`ordinal` (1-based), `raw_sha256`, `old_heading` and `new_heading`. The importer changes only
the bound heading text at the same level. For a missing section, broken hierarchy or other actual
writing defect, obtain a corrected MiniMax output before assembly.

For native-writer jobs, start one persistent `blog-section-writer` thread and keep it for the whole article. Its first turn
loads the approved outline, evidence, house rules, and style context, then writes only the first
writing unit. A writing unit is one complete H2 with every approved H3/H4 beneath it, saved to
`sections/section_<N>.md`. Load the deterministic assignment plan once:

```bash
python3 scripts/writer_dispatch.py --job <job>
```

Continue the same writer with `Requested unit: "<next H2>".` immediately when its completion
arrives. Do not split sibling H3s into separate turns, poll saved files during ordinary progress,
or ask the writer to reload `running_state.md` for an ordinary follow-up. Use
`writer_dispatch.py --next --job <job>` only for recovery after interruption or missing context.
The parent
supplies no checklist, word budget, minimum, or editorial feedback between units. The writer uses
the same conversation context, so it remembers what it has already written. Its standing
instruction is: write the unit fully, usefully, and naturally; go deeper than the competing pages
where the evidence permits; add no padding, repetition, or AI clichés; do not retell earlier
sections. Word count is measured only after drafting for analytics and platform diagnostics. After
the final writer turn and every H2 section file exists, run:

```bash
python3 scripts/writer_dispatch.py --job <job> --check
python3 scripts/assemble_sections.py --job <job>
```

If assembly or a deterministic check finds a missing/truncated section, continue the same writer
thread with only that technical defect. The parent does not hand-write article prose.

Dispatch the editor after assembly and the hybrid first-pass review. The editor diagnoses first and patches actual defects while
preserving approved coverage; a substantive gap is labelled `writer-rework:` instead of being cut.
The editor applies the current `humanizer` to the complete assigned article:
read its headings and repeated structures together, fix confirmed patterns,
then compare the edited result with the draft for unchanged facts, qualifiers,
quotes, links and visual meaning. Record scope, concrete examples, heading
changes and the meaning check in `editor_issues.md`; AI-Score is an editorial
signal, not a detector result. QA judges the final article independently.
After the edit, build the deterministic coverage signal:

```bash
python3 scripts/article_delta.py editor-report --job <job>
```

Pass `metrics/editor-delta.md` to QA. Its reduction figures are signals for lost coverage, not
automatic percentage gates.

## V2 materialization before QA

After the editor and editor-delta report, join the already running visual branch. Reuse the
preflight render and completed visual QA when their hashes remain current; do not rerender or
spawn another visual QA merely because editing ended. If the manifest or renderer changed,
rerender, rerun layout and continue the same visual QA thread before upload. Automatic geometry
PASS is not independent visual inspection. Older jobs retain their existing receipt contract.
Then run:

```bash
python3 scripts/workflow_gate.py check --job <job> --target visual --offline
python3 scripts/upload_review_visuals.py --job <job> --dry-run
```

For review-only Google Docs, use the standing review-Doc authorization to place
the checked PNGs in the article's Google Drive review folder. The uploader
verifies the public PNG bytes before binding them. This does not mutate Strapi:

```bash
python3 scripts/upload_review_visuals.py --job <job>
python3 scripts/package_article.py --job <job> --bind-visuals
python3 scripts/workflow_gate.py check --job <job> --target qa
```

Uploading PNGs to Strapi changes CMS media. Execute the next command only when
explicitly authorized in the current conversation; review Docs do not authorize
Strapi media uploads. A later Strapi publication requires this separate upload,
repackage, and affected QA because its image URL and receipt change.

```bash
python3 scripts/upload_visuals.py --job <job>
python3 scripts/package_article.py --job <job> --bind-visuals
python3 scripts/workflow_gate.py check --job <job> --target qa
```

The packager replaces every marker mechanically with the verified public PNG,
alt, title metadata, caption and permitted sources. It retains title in source/
media name while omitting HTML img title for the current CMS. No CMS change/deploy.
QA inspects asset.remote_path: the actual CMS PNG, which may have optimized colors,
and the original render. Do not hide an incomplete visual by deleting its marker.
If an omission is needed, record the publisher/editorial decision in the manifest.
If data/caption change, rerender/reupload/rebind and repackage before affected QA.

## QA loop

Run the deterministic section checks, word count, article lint, and applicable
overlap/link checks before spending the first model QA pass. Route mechanical failures to the
responsible specialist.

After editing and before model QA, run:

```bash
python3 scripts/check_research_links.py --job <job>
```

For `source_policy_version: 1`, require a final Sources/Источники H2 with each
original URL linked once there; prose, visual captions and external quote
attributions name their sources without repeating clickable links. This check
also verifies that every required evidence URL and every selected public visual
or external quote source is listed. A failure returns to the editor before QA.
Repair broken evidence tables before writing. Remove internal evidence IDs from public
copy. Store each visual's source labels once, in `sources`.
For older jobs, the check fails when a required independent-research URL from `evidence.md` is absent from `edited.md`
and writes `metrics/research-links.md`. Pass that report to QA; QA still evaluates semantic
entailment and whether the finding provides decision value.

Run `python3 scripts/wordcount.py --job <job>` and pass the measured count to QA. Retain the
writer, editor, and QA agent identifiers. The normal budget is one full edit, one full QA, and at
most one targeted correction/re-check. If QA returns BLOCK:

1. Snapshot `edited.md` with `python3 scripts/article_delta.py snapshot --job <job> --round <N>`.
2. For hybrid jobs, list substantive defects by approved H2 ID in `raw/openrouter-rework-plan.json`.
   Run `prepare repair`, `execute repair` and `import repair` with a new revision and the affected
   `--cid` values. MiniMax patches only the targeted H2 spans in the current edited article.
   For native jobs, route the gap to the same writer thread and reassemble. In both cases ask
   the same editor to check the affected sections and their seams.
   Route an editorial defect directly to the same editor. Do not make the editor invent missing
   substance.
3. Build the diff with `python3 scripts/article_delta.py report --job <job> --round <N>`.
4. Continue the same QA thread with the diff path and changed section names.

QA re-checks only failed gates plus entailment/style for the changed sections. Run a new full QA
only when the diff changes article structure or unrelated sections. It must not add optional polish
requests during re-check. After the one targeted cycle, stop and report any remaining blocker.
A second correction is allowed only for a narrowly bounded factual, legal, positioning, or
publication-safety defect that would make publication unsafe; never spend it on stylistic polish.

After QA passes, the parent performs the non-delegated deterministic checks:

```bash
python3 scripts/lint_article.py --job <job>
```

Build a compact independent-review packet:

```bash
python3 scripts/build_orchestrator_review.py --job <job>
```

The parent reviews `out/orchestrator_review.md`, which contains metadata, Example Co excerpts,
risk-language hits, links, QA verdict, and manual-confirmation items. Open the referenced article
sections only when the packet reports a concern. A rule defect discovered here must be fixed in
the rule source as well as the text.

For v2, after model QA PASS and the parent checks, freeze that exact version:

```bash
python3 scripts/workflow_gate.py seal-qa --job <job>
```

The receipt binds content, visual/quote specs, evidence, metadata and QA report.
Later edits require repackaging and affected QA, then a new receipt. Proposed
comments may pass QA for publisher review; factual PASS is not human approval.

## Package

After QA PASS, prose is frozen. Build all local delivery artifacts and prove the HTML survives the production-equivalent sanitizer with one deterministic command:

```bash
python3 scripts/package_article.py --job <job>
```

It derives `title` from the single H1 in `edited.md`, reads the final metadata block in `brief.md`, validates field limits and slug format, then writes `out/meta.md`, `out/article.md`, `out/article.html`, and `out/internal_package.md`. For an article of the form «competitor + Alternatives», the slug is exactly `<competitor>-alternatives`, with nothing appended after `alternatives`; this convention does not apply to other article types. Missing metadata or any unexpected sanitizer difference blocks delivery. V2 packaging
also runs before QA to materialize visuals; the post-QA repeat is mechanical only
and must leave sealed content/metadata unchanged.

Immediately after successful packaging, sync metadata and the `written` state:

```bash
python3 scripts/temnik.py ready --job <job> --apply
```

Then immediately create the first Google Docs review round unless
`review/01-doc-url.txt` already contains that round's URL:

```bash
python3 scripts/gdoc_review.py push --job <job> --round 1
```

The push stores the URL in the job, writes it to the linked topic-sheet row, and moves the row to
`in review`. Treat a failed push or topic-sheet review sync as a workflow failure; retry a
transient Google quota error instead of reporting the article ready without its review URL.

V2 push checks current QA and all actual images before creating any folder/Doc.
It inserts native images, captions and comments, verifies their object IDs, and
stores a round receipt. A note identifies proposed comments outside the article;
pull excludes that note and reports deleted/replaced images as well as text edits.
Record only actual human approvals with workflow_gate.py approve-quotes and
approve-review (commands in docs). Do not infer consent from a machine PASS.

## Review Docs are automatic; Strapi still requires a fresh explicit request

The publisher has given standing authorization to create or update Google Docs review copies for
completed blog articles. No fresh request is required for the first review round or for a later
round produced after publisher feedback. This authorization is limited to the article's review
folder and linked topic-sheet fields. It does not authorize Strapi drafts, publication, covers, or
unrelated Google Drive changes.

Each later user-authorized turn is a measured lifecycle phase. The parent starts it from its own
thread, wraps every script or reused agent with a stage belonging to that phase, and stops the
phase before replying:

```bash
phase=$(python3 scripts/codex_metrics.py phase-start --job <job> --name <google-docs|feedback-rework|publication>)
stage=$(python3 scripts/codex_metrics.py stage-start --job <job> --phase-id "$phase" --stage <name> --kind script)
# run the authorized action; agent stages are bound with stage-bind as usual
python3 scripts/codex_metrics.py stage-stop --job <job> --id "$stage" --status complete
python3 scripts/codex_metrics.py phase-stop --job <job> --id "$phase" --status complete
```

Use a new phase for each user turn so time waiting for feedback is excluded. This keeps the
original production subtotal and adds Google Docs, feedback rework, publication, and live
verification to the whole-lifecycle total.
If publication happens in the same parent turn as production, register its stages in the
current metrics scope. When a publisher decision pauses production, stop its scope and use
`phase-start --continue-phase <id|initial>` in a later turn to carry unregistered planned stages.

Register every automatic `gdoc_review.py push` as a script metrics stage in the current article
phase. For a previously finished job, start a separate `google-docs-review` lifecycle phase first.
Pull an identified review round when the publisher says feedback is ready. When the user explicitly
approves creating or updating a Strapi record, run `strapi_publish.py --dry-run` first. Without
`--publish`, it creates a draft. Use `--publish` only when the user explicitly asks to publish in
the current conversation.

V2 Strapi additionally checks approved article/quote wording and a current QA
receipt. It writes a draft first, reads back supported HTML, then honors --publish
only if it matches. A mismatch leaves a tracked draft and blocks publication.
Retry with --update using out/strapi_record.json; do not create a duplicate.

For a change to the approved headline promise, save the exact approved replacement and metaTitle
in a receipt with `status`, `publisher`, `reference`, `original_heading`, `heading` and `metaTitle`.
Run `blog_openrouter.py amend-title --batch <batch> --cid <id> --amendment <receipt>` and require
success before repackaging. It verifies the original brief, preserves body bytes and records the
change. Run targeted QA and reseal against the changed H1, metaTitle and cover. Verify both fields
on the stored record and check the visible live H1 after publication.

For an authorized hybrid batch, create/read back the draft, render its exact ID and slug with
`--format=png --out=<job>/publication/covers`, then dispatch `blog-visual-qa` in the
`publication-cover-qa` stage for the full file and the 390 px preview. The agent records
`verdict`, `viewed_full`, `viewed_mobile`, `reviewer`, `target_id`, `slug`, `locale`,
`file_sha256`, `preview_sha256` and `render_receipt_sha256` in `publication/cover-qa.json`. Upload the
same file before publication with `--slug=<slug> --id=<id> --locale=en --file=<render>
--qa=<qa-receipt> --receipt=<upload-receipt>`. The upload checks the target and hashes. On
transport errors, read back the exact record and receipt before considering any repeated mutation.
Publish that already checked draft with
`strapi_publish.py --job <job> --update <id> --publish --cover-receipt <upload-receipt>`.
The command checks content, H1, metaTitle and the associated cover before changing publication
status. A repeat on the same live record verifies the previous result.

For other authorized jobs, the standard cover command is:

```bash
cd tools/covers
npm ci
STRAPI_URL=https://cms.example.com STRAPI_TOKEN=<token> node article-covers.mjs --slug=<slug>
```

After publication and cover upload, run `python3 scripts/temnik.py publish --job <job> --apply`.
That command fails unless the public URL returns HTTP 200 and the Strapi record has both
`publishedAt` and a cover; only then does it write the public URL, actual publication date, and
`published` state. Then update any applicable legacy queue document in `docs/`. A locally
finished or Google-Docs-only article must never be marked as published.

After public verification, submit newly published blog URLs to IndexNow with the Example Co
key: `python3 scripts/indexnow_blog.py --job <job> [--job <job> ...] --apply`.
The script verifies each published record, public canonical URL, and live key file before
submission, then saves the HTTP receipt in `docs/indexnow/`. A 200 or 202 response means
the URLs were received; it does not guarantee indexing. For a batch, submit all URLs in one
request. If submission fails, keep the receipt and report the failure for retry.

## Final report

Report the QA verdict, all `needs_manual_confirmation` items, blocked first-party sources, affected
files and completed external actions. In hybrid batches use
`python3 scripts/blog_openrouter.py cost --batch <batch>` for actual API spending by article and in
total, including charged retries. Report unreconciled attempts separately from known spend.

## Translation of a selected published article

For an explicitly selected translation, read `knowledge/blog-translation.md`. Use a
new isolated `article_translation_version: 1` job; do not run new-topic or refresh
research and do not migrate existing jobs. Parent runs deterministic source/check/
package/drift/seal/Docs commands; all content is delegated to `blog-translator`
(gpt-6-luna/medium), `blog-translation-editor` and `blog-translation-qa`
(both gpt-6-sol/medium) with the same fixed routing envelope and fork_turns="none".
Use `scripts/blog_translation.py bootstrap --job <job> --slug <slug> --locale ru`,
then follow that knowledge file. Metrics use full scope and a translation-specific
stage plan. Review-only fidelity PASS is not factual re-verification or CMS approval.
Normal Strapi export rejects this branch; review Docs include source/visual limitations.

For an unsealed translation explicitly opted into `translation_units_version: 1`,
prepare/load `scripts/translation_dispatch.py` once and continue the SAME translator
thread/stage with complete source H2 subtrees after an explicit title/preamble unit.
The only additional envelope text is `Requested unit: "<requested_unit>".` from the
saved plan. Translator-owned unit files are assembled deterministically only after
all unit receipts pass; register the required `translation-assemble` stage. Existing
full-document translation jobs and sealed artifacts are not migrated. Follow
knowledge/blog-translation.md for source/assembly and feedback-provenance boundaries.
