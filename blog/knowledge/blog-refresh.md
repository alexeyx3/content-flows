# Published blog article refresh contract

Applies only to a job carrying `article_refresh_version: 1`. This is a versioned
update of one existing article, not selection or production of a new topic.
The original job and published record are read-only inputs. Each cycle owns a
new folder with its own metrics, evidence, article, review Doc and QA receipt.
House positioning, legal, voice, source, metadata and publication rules still
apply. This contract replaces new-topic research and whole-article drafting
requirements only for this explicit mode; it does not waive factual or QA gates.

## Publisher decisions

- Each scheduled cycle must produce a useful content improvement. Choose scope
  from evidence and reader value; no keyword density, length or section quota.
- Plan subsequent updates 15–30 days after an actual published update. Save the
  chosen date. Review readiness is not publication and must not advance the
  live last-updated date or start a post-publication effect window.
- Daily page totals, complete weekly query snapshots, and exact-window cycle
  comparisons are sufficient. Data errors and missing data are not zeroes.
- Query phrases, lemmas, unigrams, bigrams and embeddings are discovery aids.
  Decide coverage by meaning and intent. A literal missing phrase is not an
  instruction to insert it. Preserve entities, geography and negation.
- Related intent may justify a short useful addition in a relevant vendor card
  and an internal link to its main article. It need not become a new competing
  H2. Check other owned pages before assigning a query to this page.
- Protect working answers, primary intent and the existing ranking. Do not
  change the page URL, manufacture category fit or claim causal traffic gains.
- Record the cycle and review URL in the configured topic sheet, using dedicated
  refresh fields and history. Preserve original production/lifecycle fields.
- A refresh cycle ends with a checked full article in Google Docs.
  Publication remains a separate explicit action.

## Google indexing check before page selection

Publisher instruction: before taking any page into a new
refresh batch, run a fresh read-only URL Inspection API request for its exact
published URL. This precedes query collection and specialist dispatch:

```bash
python3 scripts/refresh_indexing.py --url https://example.com/blog/<slug>/ --cluster-id <id> --output <batch>/indexing-<slug>-<timestamp>.json --sync-temnik --apply
```

Save the dated response, verdict, coverage reason, Google/user canonical,
last crawl time, robots/indexing/fetch states where returned. Exit 0 requires
Google's PASS and the inspected URL as Google canonical. Exit 2/HOLD includes
exclusion, another canonical, missing/unknown data or API failure; do not treat
these as a normal query-driven refresh candidate. Rule: record the actual status and reason in the topic sheet, skip this
page, and continue downward until the requested number of indexed candidates is
selected. Do not start diagnosis, research or writing for the skipped page.
Unknown/API failure is recorded separately and skipped rather than called
non-indexed. A separately requested technical investigation is a different task.
The command's exit 2 applies to this candidate, not the entire batch; continue
the selection loop after the status sync succeeds. A failed sheet sync must be
resolved before claiming that the skipped status has been recorded.
Do not infer index membership from zero queries, HTTP 200, indexable=true,
sitemap presence or an IndexNow receipt. API failures are unknown, not exclusion.
This is Google's stored index status, not a live crawl test or indexing request.
The parent must inspect the receipt before selecting the page. Do not start
specialists merely because an old baseline contains an inspection response.
Keep existing cycle baselines, QA seals and review Docs unchanged.

The configured topic sheet is the user-visible tracker. Its original blog tab owns
the current refresh lifecycle and dedicated Google status/reason/check date,
canonical/crawl time/selection cells. `Blog refreshes` is a compact linked view
keyed by cluster ID: the current cycle, review URL, actual update and next review
dates reference the original tab, so ordinary lifecycle sync stays visible.
`Refresh history` retains one row per cycle. These are tabs of the same
spreadsheet, not a second independent queue. Inspection receipts/history are
also retained locally in SQLite, without replacing article analytics baselines.
Bing crawl metadata does not prove index membership; display it as unconfirmed
until an authoritative membership result is available. Inspection does not
overwrite the status of a previously completed review cycle.

## Inputs and provenance

Read `job.yaml`, `refresh.json`, `baseline/article.md`,
`baseline/cms-record.json`, `raw/analytics.json`, `semantics.csv`,
`raw/query-terms.json`, `raw/owned-pages.json`, and `raw/related-query-pages.json`.
Some optional APIs can fail; record their status and continue only with known
facts. Do not claim Bing inspection from a Google response or an IndexNow receipt.
The dated source report is historical context, not the current baseline.

`baseline/article.md` is a deterministic reconstruction or verified equivalent
of the current published CMS body, with its current H1. All preserved prose is
from this same article. `baseline/source-*` contains original job artifacts for
reference only; an old QA verdict does not approve this refresh.

## Strategy — blog-strategy-brief

For new cycles, `semantic_refresh_version: 1` is mandatory. The new-job template
sets it; it is active only together with `article_refresh_version: 1`.
Existing cycles keep their original contract during an audit. An explicitly
requested content rework under the semantic protocol may opt in only after the
parent archives its previous artifacts and review receipts, records the user
authorization in refresh.json, and preserves the published baseline. Produce a
new review round and new QA; never silently migrate or reuse the old PASS.
Follow the deterministic semantic stage below.

Use baseline and actual queries as the starting point. Read compact source
artifacts when needed; use targeted current SERP/primary-source discovery for
questions that require it. Do not rerun the entire new-article research graph.
Write:

- `refresh_plan.json`: `version`, `cycle_id`, `primary_intent`,
  `protected_elements`, `query_decisions`, `changes`, `visual_decision`,
  `quote_decision`. Query decisions link actual query strings to the relevant
  section, coverage judgment and action (`expand`, `link`, `covered`,
  `separate_topic`, `irrelevant`). Changes explain the reader benefit and
  evidence needs; do not set length targets. Every available query must be
  considered, though several can share a single intent decision.
- `brief.md`: update rationale, complete final H2–H4 outline, inherited
  ranking/placement, metadata and unchanged slug, research needs and internal
  link decisions. End with the normal four metadata lines used by packaging.
- `sections.json`: normal complete ordered section map plus, per H2,
  `refresh_action` (`retain`, `update`, `new`) and `baseline_title` for existing
  sections. Record `information_gain` with `R-xx` references to `research.md`, plus
  `visual_candidates` and `expert_questions` arrays (empty with reasons when
  they add no value to this update).
- `research.md`: actual reader findings and candidate primary/independent
  sources read during planning. Query rows are audience evidence only, not
  proof of vendor capabilities or legal facts.

Preserve the existing H1 and major heading wording where feasible. Explain a
substantive heading/structure change; cosmetic editing must not obscure the
update's purpose. A full fresh outline is not permission to rewrite every H2.
No new quote or image is mandatory: record a reason tied to this update when
existing prose and ordinary tables adequately answer the selected questions.
If a visual or attributed quote is required, name the dependency so the parent
routes the existing specialist and its normal gates before affected writing.

## Evidence — blog-evidence

Read the plan and baseline. Produce `evidence.md` in the normal supported claim
table schema. Carry forward source rows from the same article only with clear
provenance; distinguish new verification from inherited checks. Verify every new
or changed factual assertion, current price used in an addition, and affected
load-bearing comparison. Check important retained facts for conflicts with the
new evidence. A stale source or blocked page never becomes fresh certainty.
Write `refresh_evidence.md` with changed/corrected/retained facts and exact
affected sections. May update verified company facts under the existing lock.
No requirement to invent new studies, comments, charts or case histories.

For a parallel refresh batch, `company_enrichment_mode: read_only` in job.yaml
keeps shared `companies/` read-only during that job. This explicitly replaces
the general create/update-card requirement: still verify all affected facts and
record original URLs, dates, quotes and qualifications in the job's evidence
files. A missing shared card never blocks gathering job-local evidence. Any
later shared enrichment needs a separate owner and the normal companies lock.
The mode prevents concurrent shared writes; it does not relax evidence checks.

## Persistent writer — blog-section-writer

Read the complete plan, baseline and verified evidence once. Each assignment
still names exactly one complete H2 and all approved H3/H4 descendants.
Write only assigned `update`/`new` units to their normal numbered section files.
For an explicitly opted-in rework of a pending cycle, refresh.json may name
`semantic_rework.working_article`, a job-relative archived reviewed candidate.
Use that candidate as the literal drafting/retained-unit starting text so earlier
verified corrections are not reverted. The published baseline remains immutable
and remains the source for semantic before counts, publication checks and the
published-to-review diff. Also retain a previous-review-to-final diff.

For an existing H2 use its baseline body (or that explicit working candidate) as the starting point, preserving
sound material and introducing the actual improvement. Initialize the unit from
the literal starting text and patch the necessary spans; returning an entire H2
is an output contract, not permission to rephrase all its paragraphs. Record the
reader-value addition, verified fact correction, link or concrete publication
blocker that justifies each changed baseline passage. Synonymous restatement
and generic style modernization alone do not justify changing published prose.
Retained H2 files are
copied mechanically by the parent; do not rewrite them. Never introduce a
second competing answer already owned by another page. Use exact verified
internal URLs and add phrases only where the text reads naturally.

## Editor / humanizer — blog-editor

Read assembled `out/draft.md`, baseline and the plan. Produce the complete
`edited.md` and `editor_issues.md`. Apply current humanizer rules, reviewing
the whole article for repeated patterns and consistency; patch real issues,
including existing publication blockers. Preserve useful baseline material.
Check new text and seams particularly closely. Do not run a broad rewriting pass
over sound baseline paragraphs. If a whole section differs, distinguish real
updates from gratuitous rephrasing and restore the latter before QA.
Record changed section names,
meaning preservation, any heading edits and cut facts. Send substantive gaps
back to the writer/evidence; do not manufacture them as editorial polish.

## Independent QA — blog-qa-factcheck

This is a new first QA for this exact article version. Read the complete final
article, original-to-final diff, plan and evidence. Apply normal publication,
positioning, source, humanizer, metadata and integrity gates. Check protected
answers and intended scope across the whole page. Verify new/changed claims
and the most consequential retained facts; use documented evidence for the
rest, subject to the normal source freshness rules. Verify claimed additions
actually help readers, semantic insertions are natural, internal links belong
to the owned catalog, and related intent does not displace the main answer.
Report `overall: PASS` or `overall: BLOCK` in `qa_report.md`. Any rework continues
in the same writer/editor/QA threads with the precise defect and generated diff.

## Deterministic delivery

Use workflow v2 input validation and QA fingerprints. Empty visual/quote plans
require explicit update-specific omission reasons; do not fake visual or quote
stage completion. Materialize and independently inspect any added visual using
the normal specialist branch. Pre-fill retained section files from baseline or the explicit archived working candidate,
validate all final writing units, assemble, edit, build editor and baseline
diffs, package, QA, seal, and push the full review Doc with baseline highlighting.
For review export use `gdoc_review.py push --highlight-mode words --baseline`
with the published baseline, so edits are highlighted within paragraphs and
table cells. Preserve the converter’s local change/deletion report with the
review round. Block highlighting alone must not conceal a broad rewrite: inspect
the actual original-to-final diff for needless rephrasing first.
Sync refresh-specific topic sheet fields/history after successful Doc creation.
Keep a clear distinction between baseline metrics, review readiness and an
eventual published update; no post-update result exists before publication.

## Deterministic semantic stage — semantic_refresh_version: 1

Publisher approved: use one page-only query window, at most the
last 90 inclusive days and never earlier than original publication. Choose the
last returned final-data property date in GSC Pacific time, or record an explicit
known final-data end date. Preserve the exact raw query and stable Q-ID. Paginate
all returned rows. GSC omissions are unknown; never promise exhaustive access to
all real searches. Do not collect query-page pairs by a slug keyword. The older
28+28/six-week collector is retained for historical monitoring, not this stage.
Performance comparison before/after actual publication remains a separate task.

Parent commands, with script metrics stages `semantic-collect`, `semantic-before`,
`semantic-plan-check`, `semantic-after`:

```bash
python3 scripts/refresh_semantics.py collect --job <job>
python3 scripts/refresh_semantics.py analyze --job <job> --stage before
python3 scripts/semantic_briefing.py --report <job>/metrics/semantics-before/coverage.json
# strategy writes the normal refresh plan plus semantics_plan.json
python3 scripts/refresh_semantics.py check --job <job> --stage writer
# persistent writer -> editor/humanizer; then:
python3 scripts/refresh_semantics.py analyze --job <job> --stage after
python3 scripts/semantic_briefing.py --report <job>/metrics/semantics-after/coverage.json
python3 scripts/refresh_semantics.py check --job <job> --stage after
```

Collection creates immutable `raw/semantic-queries.json` with exact dates and raw
metrics. All roles use it instead of the old recent28 semantics.csv. Before/after
coverage.json, coverage.csv and report.md are under metrics/semantics-before and
metrics/semantics-after. The report contains every full query, lemma unigram and
adjacent lemma bigram, its original forms, originating Q-IDs, exact and morphology
counts, and match locations/sections/excerpts. No term quota or keyword density.
Before dispatch, create briefing.json with semantic_briefing.py inside the same
script stage. Agents normally read this complete compact view: all query/term
rows and counts remain, repeated location/excerpt arrays do not. Its coverage
SHA identifies the authoritative report. Load full match locations only for the
selected IDs; do not put multi-megabyte CSV location dumps into every role's
context. This view never replaces the authoritative report in gates or seals.

Exact means the same contiguous literal phrase, ignoring case and technical
whitespace, with word boundaries. Morphology means exact matches plus the same
ordered adjacent lemma sequence in one punctuation segment; each occurrence is
counted once. These inclusive counts must not be summed. Synonyms, reordering and
gaps never qualify as morphology. Do not bridge separate blocks/table cells or
delete stopwords to manufacture adjacent bigrams. Stopwords and negation remain
traceable. Source lists, link targets, code and image alt do not inflate body
counts. metaTitle/metaDescription/summary are audited separately.

The local pinned spaCy EN/RU models perform POS/lemma analysis; they are not an
LLM and make no network calls during annotation. Shared cached annotations are
keyed by exact text, language, model versions and semantic code/config hash.
Short-query POS ambiguity remains a documented NLP limitation. Brand names and
numbers are protected. Missing model/runtime fails closed; there is no stemming
fallback disguised as lemmatization. Setup: `sh tools/semantics/setup.sh`.

Strategy must read the before report, retain all raw Q-IDs, judge relevance and
intent, and write `semantics_plan.json`:

```json
{
  "version": 1,
  "queries": [{"query_id": "Q-...", "action": "expand", "section": "Exact H2 title", "reason": "Specific coverage/wording decision"}],
  "targets": [{"id": "Q-... or T-... from coverage.json", "match": "exact", "min_count": 1, "section": "Exact H2 title"}],
  "protect_ids": [],
  "loss_exceptions": [{"id": "Q-...", "match": "exact", "reason": "Evidence-backed reason this occurrence must disappear"}]
}
```

Each returned query needs exactly one reasoned `covered`, `expand`, `link`,
`separate_topic` or `irrelevant` decision. Groups can share reasoning but must
enumerate every Q-ID. An `expand` decision needs at least one linked exact or
morphological target. Targets can be useful shorter query-derived terms rather
than an unnatural entire prompt. A missing phrase is a measured signal, not an
automatic duty to insert it: exclusions and semantic-only coverage need reasons.
Use the catalog first for a nearby question; request other-page GSC data only for
a specific unresolved decision. Never infer a different URL's query is this
page's demand. Evidence verifies facts needed for the chosen additions.

Writer fulfils the selected targets naturally inside the assigned H2. Editor
preserves their wording/morphology while applying the humanizer. If a target
cannot be stated accurately or naturally, return the exact defect to strategy;
do not silently delete it or weaken facts. QA inspects the after report, additions,
intent, wording and reasoned exclusions. It never substitutes a model's impression
for script counts. All full-query presence losses and protected-term presence
losses require recorded reasons; frequency reductions and other term losses stay
visible advisories unless an explicit target says otherwise.

Writer gates require a current before report and a complete plan. QA, QA sealing,
Google Docs and Strapi gates require a current after report, fulfilled targets and
explained protected losses. Dataset, baseline, article, plan, metadata inputs and
engine-source hashes detect stale reports. QA receipts bind the registry, plan and
both coverage reports. Recompute after any editor/review change before affected
QA/sealing/export. Do not bypass this by reusing an older PASS.

Legacy audit example (no job flag or content migration): pass explicit --output
to collect and --output-dir to analyze, both in a dedicated batch audit directory.
Keep the old job's analytics, prose, QA receipts and review Doc unchanged.

## Authorized publication of an update

After explicit publisher approval, pull the latest review round and record
`workflow_gate.py approve-review` for its exact unchanged text. Run the Strapi
gate and `strapi_publish.py --job <job> --update <existing-id> --publish --dry-run`,
then the same command without `--dry-run`. Refresh jobs cannot create new CMS
records. The refresh branch checks the original/current record identity and
baseline, preserves the original `publishedAt`, author, editors, cover, tags,
indexability and URL, and applies the reviewed HTML directly to that live record.
It does not pass through an unpublished draft. It reads back exact HTML and
metadata; a content mismatch requests restoration of the preceding supported body.
Keep the pre-update snapshot and `out/refresh-publication.json` as receipts.

Save `next_review_date` in `refresh.json`, 15–30 days after the actual CMS update
date. Then run `blog_refresh.py sync --job <job> --status published --apply`.
This verifies current CMS hashes, live body and canonical before updating the
dedicated refresh summary/history and immutable local publication ledger. It
preserves original topic sheet lifecycle fields. The summary includes actual update
time and next review date. A planned review date is not a scheduled automation.
Finally submit the existing URL with `indexnow_blog.py --job <job> --apply` and
retain its receipt; acceptance does not prove indexing.
