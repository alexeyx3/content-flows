# Blog flow

Produces one blog article per job: a topic taken from the topic sheet, search results from four
English-language markets, four parallel research packets, a brief approved by the publisher,
verified evidence, vendor cards for comparisons and rankings, code-rendered charts and diagrams,
expert comments, section-by-section writing, editing, independent QA, a review document in Google
Docs, and on request a CMS draft, cover, publication and an IndexNow ping.

The same folder runs two more routes: a refresh of an article that is already published, and a
translation of a published article.

Example Co in this folder is a fictional company. Before the first run, replace it with your own:
see [Adapting](#adapting).

## Stages

### New article

| # | Stage | Who | Output in `jobs/<job>/` |
|---|---|---|---|
| 1 | Topic rows in sheet order, duplicate preflight, skip reasons, publisher approval of the rows | orchestrator, `temnik.py next`, `temnik.py preflight`, `topic_overlap.py decide`, `temnik.py skip` | `reports/topic-overlap/<cluster-id>.seed.json` (outside the job) |
| 2 | Create the job, mark the row in progress | `new_job.py`, `temnik.py start` | `job.yaml`, `progress.md`; `semantics.csv` is filled in by hand ([format](#job-files)) |
| 3 | SERP in US, GB, DE, AU; competitor structures; Reddit signals | `fetch_google_serp.py`, `build_article_serp_brief.py`, `collect_reddit_signals.py` | `raw/serp.csv`, `raw/features.json`, `serp.serp_synthesis.md`, `serp.competitor_structures.csv`, `serp.competitor_cards.json`, `serp.serp_features.json`, `audience.reddit.md` |
| 4 | Map of reader decisions | `blog-research-map` | `research_map.json` |
| 5 | Four research packets in parallel: topic, primary documents, studies, outside quotes | `blog-topic-research`, `blog-primary-data-research`, `blog-study-research`, `blog-quote-scout`; five `validate_*.py` scripts | `research.md`, `research.discovery.md`, `research.data.json`, `raw/document-search-*.csv`, `research.studies.json`, `research.quotes.json` |
| 6 | Hybrid outline and brief; overlap re-check on the resolved query | `blog-strategy-brief`, `validate_article_brief.py`, `topic_overlap.py check --stage resolved` | `serp.hybrid_outline.md`, `brief.md`, `sections.json` |
| 7 | Publisher checkpoint: H1, angle, full H2–H4 outline, placement of the own product in a ranking, API budget for a hybrid batch | publisher | `own_product_placement` in `job.yaml`; for hybrid jobs `docs/workflow-v2/batches/<batch>/publisher-proposal.json` and `brief-approval.json` ([examples](docs/examples/README.md)) |
| 8 | Evidence | `blog-evidence` | `evidence.md`; verified facts written back to `companies/` |
| 9 | Vendor cards (listicles and comparisons only) | `blog-company-cards` | `company_cards.md` |
| 10 | Visual plan and expert comments, in parallel | `blog-visual-planner`, `fetch_blog_profiles.py`, `blog-expert-quotes` | `visuals.json`, `raw/speaker-profiles.json`, `expert_quotes.json` |
| 11 | Input gate, render, geometry check | `workflow_gate.py check --target inputs`, `render_visuals.py`, `check_visual_layout.py`, `workflow_gate.py check --target writer` | `assets/<id>.png`, `out/visual-layout-check.json` |
| 12a | Writing, one complete H2 with its H3/H4 per turn | hybrid: `blog_openrouter.py … writer`; native: `blog-section-writer` with `writer_dispatch.py` | `sections/section_<N>.md`; `running_state.md` for the native writer |
| 12b | Independent visual QA, alongside 12a | `blog-visual-qa` | `visual_qa.json` |
| 13 | Assembly; first-pass review of the draft (hybrid jobs) | hybrid: `blog_openrouter.py import writer`, then `blog_openrouter.py … critic`; native: `assemble_sections.py` | `out/draft.md`; for hybrid jobs `raw/openrouter-draft-check.json`, `raw/openrouter-critic.json` |
| 14 | Editing and humanization; coverage delta | `blog-editor`, `article_delta.py editor-report` | `edited.md`, `editor_issues.md`, `metrics/editor-delta.md` |
| 15 | Join both branches; upload images for review; bind them into the text | `workflow_gate.py check --target visual`, `upload_review_visuals.py`, `package_article.py --bind-visuals`, `workflow_gate.py check --target qa` | `edited.md` with real images, `out/` |
| 16 | Deterministic checks | `check_research_links.py`, `wordcount.py`, `lint_article.py` | `metrics/research-links.md` |
| 17 | Independent QA | `blog-qa-factcheck` | `qa_report.md` ending with `overall: PASS` or `overall: BLOCK` |
| 18 | Orchestrator review packet, QA seal | `build_orchestrator_review.py`, `workflow_gate.py seal-qa` | `out/orchestrator_review.md`, `qa_receipt.json` |
| 19 | Package, review document | `package_article.py`, `temnik.py ready`, `gdoc_review.py push` | `out/meta.md`, `out/article.md`, `out/article.html`, `out/internal_package.md`, `review/01-doc-url.txt` |
| 20 | Human approvals recorded | `gdoc_review.py pull`, `workflow_gate.py approve-quotes`, `workflow_gate.py approve-review` | `review_approval.json`, quote statuses in `expert_quotes.json` |
| 21 | On request: CMS images, draft, cover, publish, verify, IndexNow | `upload_visuals.py`, `strapi_publish.py`, `tools/covers/article-covers.mjs`, `temnik.py publish`, `indexnow_blog.py` | `out/strapi_record.json`, `publication/`, `docs/indexnow/` (outside the job) |

The orchestrator is the parent Codex session. It runs the scripts and starts each specialist as a
flat depth-1 agent; it never researches, writes, edits or fact-checks article prose. The full
procedure is in [.agents/skills/blog-article/SKILL.md](.agents/skills/blog-article/SKILL.md), the
file contracts (`sections.json`, `visuals.json`, `expert_quotes.json`) are in
[docs/blog-workflow-v2.md](docs/blog-workflow-v2.md), and the reasons behind the rules are in
[docs/design-notes.md](docs/design-notes.md). The design shared by all three flows is described in
[../docs/how-it-works.md](../docs/how-it-works.md).

Rework after a QA block goes back to the thread that produced the defect (writer, editor, visual
planner), and the recheck goes to the original QA thread with a generated diff
(`article_delta.py snapshot` and `report`). The normal budget is one full edit, one full QA and one
targeted correction.

### Refresh of a published article

A refresh is a separate job with `article_refresh_version: 1` in `job.yaml`. The original job and
the published record are read-only inputs. The contract is
[knowledge/blog-refresh.md](knowledge/blog-refresh.md).

| # | Stage | Who | Output |
|---|---|---|---|
| 1 | Google URL Inspection of the exact URL before the page is selected; a page that is not indexed is recorded and skipped | `refresh_indexing.py` (with `--sync-temnik --apply` to record the status) | dated receipt in the batch directory, `Google: …` and `Refresh: selection` cells of the topic sheet |
| 2 | Cycle job, published baseline, page analytics | orchestrator, `collect_refresh_baseline.py`, `blog_refresh.py register` | `refresh.json`, `baseline/article.md`, `baseline/cms-record.json`, `raw/analytics.json` |
| 3 | Page-only query collection and coverage audit before any change | `refresh_semantics.py collect`, `refresh_semantics.py analyze --stage before`, `semantic_briefing.py` | `raw/semantic-queries.json`, `metrics/semantics-before/` |
| 4 | Refresh plan | `blog-strategy-brief`, then `refresh_semantics.py check --stage writer` | `refresh_plan.json`, `semantics_plan.json`, `brief.md`, `sections.json`, `research.md` |
| 5 | Evidence for new and changed claims | `blog-evidence` | `evidence.md`, `refresh_evidence.md` |
| 6 | Writing of `update` and `new` H2 units only; retained units are copied mechanically | `blog-section-writer` (native writer) | `sections/section_<N>.md` |
| 7 | Editing; coverage audit after the change | `blog-editor`, `refresh_semantics.py analyze --stage after`, `refresh_semantics.py check --stage after` | `edited.md`, `editor_issues.md`, `metrics/semantics-after/` |
| 8 | Independent QA, seal, package | `blog-qa-factcheck`, `workflow_gate.py seal-qa`, `package_article.py` | `qa_report.md`, `qa_receipt.json`, `out/` |
| 9 | Review document with changed words highlighted against the published baseline | `gdoc_review.py push --highlight-mode words --baseline …`, `verify_refresh_review.py`, `blog_refresh.py sync --status "in review"` | `review/`, `Refresh: …` cells and the `Refresh history` tab |
| 10 | On request: update the existing CMS record in place, sync, IndexNow | `strapi_publish.py --update <existing-id> --publish`, `blog_refresh.py sync --status published`, `indexnow_blog.py` | `out/refresh-publication.json` |

Two scripts keep the topic sheet in step with Google's index status. `refresh_indexing.py` runs a
read-only URL Inspection of one page and writes a dated receipt (`--url`, `--output`, optionally
`--cluster-id`); with `--sync-temnik` it hands the receipt to `blog_monitor.py` (a preview; add
`--apply` to write). `blog_monitor.py --input <receipt> [--apply]` takes a saved receipt: it writes the
`Google: …` and `Refresh: selection` cells of the evaluated rows, maintains the `Blog refreshes`
tab, refuses an inspection older than the one already in the sheet, and keeps every inspection in
`var/blog-monitor.sqlite3`. Without `--apply` it only prints the planned decisions. See
[docs/topic-sheet.md](docs/topic-sheet.md) for the columns.

### Translation of a published article

A translation is a separate job with `article_translation_version: 1`. Version 1 supports English
to Russian only. No topic selection, SERP, research or ranking decision is run; the current
published record is the source. The contract is
[knowledge/blog-translation.md](knowledge/blog-translation.md).

| # | Stage | Who | Output |
|---|---|---|---|
| 1 | Immutable snapshot of the published source | `blog_translation.py bootstrap` | `source/`, `translation.json`, `job.yaml`, `progress.md` |
| 2 | Translation, whole document or one complete H2 per turn | `blog-translator`; for units `translation_dispatch.py --prepare`, `--complete <unit>`, `--check`, `--assemble` | `translated.md`, `translated.meta.json`, `translation.links.json`, `translation.visuals.json`, `translation.issues.md`, `translation.glossary.json` |
| 3 | Editing against the source | `blog-translation-editor` | `edited.md`, `translation.meta.json`, `translation.editor.md` |
| 4 | Structure, numbers, links and leaked-marker check | `blog_translation.py check` | — |
| 5 | Independent QA: native-language readability first, then fidelity | `blog-translation-qa` | `translation.qa.json`, `translation.qa.md` |
| 6 | Source drift check, package, seal | `blog_translation.py drift`, `package`, `seal` | `out/translation-source-drift.json`, `out/article.md`, `out/article.html`, `out/meta.md`, `out/translation-package.json`, `translation.qa_receipt.json` |
| 7 | Review document with a preface listing source and QA limitations | `gdoc_review.py push`, `blog_translation.py verify-review` | `review/translation-review.json` |
| 8 | On request: linked draft in the CMS, then publication | `strapi_translation_draft.py authorize` and `export`, `strapi_translation_publish.py authorize` and `publish` | `out/strapi-translation-draft/`, `publication/` |

A fidelity PASS means the translation is complete and accurate against the source. It is not a
fresh fact check of the source and not approval to publish. `strapi_publish.py` refuses
translation jobs; they use the two dedicated scripts in row 8. Each runs only on an explicit
publisher request and previews by default: the draft script creates a linked draft, and the
publication script publishes that existing draft after a scoped publication-readiness QA and an
independently checked cover (details in
[docs/blog-workflow-v2.md](docs/blog-workflow-v2.md#translations-of-the-published-blog)).

## Layout

| Path | What it holds |
|---|---|
| `AGENTS.md` | Standing instructions to the orchestrator |
| `.agents/skills/blog-article/` | The skill: stages and the conditions for moving between them |
| `.agents/skills/copywriter/`, `.agents/skills/humanizer/` | Brand voice rules; editing method and the catalogue of AI-writing patterns |
| `agents-src/agents/` | Eighteen role specifications: seventeen active specialists and the dormant `blog-coordinator` |
| `agents-src/skills/` | Archived instructions of two earlier tracks (script-only and all-agent), kept for reference; not used by the active flow. The rule-consistency and fork-integrity tests read `blog-article/SKILL.md` |
| `.codex/agents/`, `.codex/config.toml` | Codex agent profiles that point to the role files; the limit on concurrent agent threads |
| `config/codex-model-routing.json` | Model and reasoning effort per role |
| `config/blog-openrouter.json` | Pinned OpenRouter routes of the hybrid writer and first critic: model, provider, price caps, output ceiling |
| `config/` | Topic sheet (`temnik.json`, `topic-sheet-template.csv`), search markets (`geos.json`), authors (`blog-authors.json`), brand rules and stop-list, site URL map, brand colours, IndexNow key location, refresh settings |
| `knowledge/` | Rule cards read by the roles: positioning, audience, legal, blog track rules, writing and structure rules, research contracts, refresh and translation contracts |
| `companies/` | Vendor cards with provenance: research memory shared by all jobs |
| `prompts/` | Rule files of the older script track (`generate_brief.py`, `edit_draft.py`) |
| `scripts/` | Topic sheet, SERP, validators, gates, writer runner, renderer, packaging, review document, CMS, IndexNow, metrics |
| `tools/covers/`, `tools/sanitize/`, `tools/semantics/` | Cover generator and fonts used by the visual renderer; reference HTML sanitizer of the CMS; pinned local spaCy runtime for refresh coverage counts |
| `docs/` | Design notes, v2 contracts, Codex notes, topic sheet |
| `tests/` | Offline tests; none of them calls an external service |

Folders created at run time: `jobs/` (one folder per article), `runs/<batch>/` (hybrid writer
manifests, attempts and receipts), `docs/workflow-v2/batches/<batch>/` (publisher proposal and
approval of a hybrid batch), `reports/topic-overlap/`, `docs/indexnow/`, `var/` (locks and caches).

The glossary flow in `../glossary` reuses this folder's visual renderer, Google Docs exporter,
author mapping, writer-style card and credentials. Keep the folders side by side.

## Set-up

```sh
pip install -r requirements.txt
npm ci --prefix tools/sanitize
npm ci --prefix tools/covers
sh tools/semantics/setup.sh              # refreshes only
```

- Python: the tested runtime is Python 3.14. If `python3` on your machine is another version,
  call `python3.14` in every command below.
- `tools/sanitize` holds the sanitizer that packaging checks the article HTML against;
  `tools/covers` holds the cover generator and the `sharp` library and fonts that
  `scripts/render_visuals.py` uses.
- `tools/semantics/setup.sh` is needed only for refreshes. It builds `.venv-semantics` with
  `python3.12` and the pinned spaCy models from `tools/semantics/runtime-lock.txt`.
- Credentials: copy `config/.env.example` to `config/.env` and fill in the SERP provider keys
  (XMLRiver first, DataForSEO as the second provider) and the Google settings. Key files sit next
  to it and are git-ignored: `config/google-service-account.json`, `config/strapi-api-token`,
  optionally `config/bing-webmaster-api-key.txt`.
- OpenRouter: copy `config/openrouter.env.example` to `config/openrouter.env`. The hybrid writer
  uses the environment variable `OPENROUTER_BLOG_API_KEY`, or the one key in that file labelled
  `blog`. Not needed when every job uses the native writer.
- Topic sheet: [docs/topic-sheet.md](docs/topic-sheet.md), `config/topic-sheet-template.csv`,
  then the sheet ID, tab `gid` and tab title in `config/temnik.json` and
  `python3 scripts/temnik.py setup --apply`.
- IndexNow: put the URL of your key file into `config/indexnow.json`.
- Duplicate preflight adds embedding similarity through a local macOS model
  (`scripts/topic_overlap_embedding.swift`). Where the model is unavailable the check is
  lexical only, and that status is recorded in the batch decision log.
- Open the Codex session from this folder so that `AGENTS.md`, the skill and the agent profiles
  are discovered at session start.

Checks:

```sh
python3 scripts/validate_codex_setup.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

## Commands

The orchestrator runs these in order. `<job>` is the path printed by `new_job.py`.

```sh
# Topic
python3 scripts/temnik.py next --limit 10
python3 scripts/temnik.py preflight --cluster-id <id>
python3 scripts/topic_overlap.py decide --cluster-id <id> --reason "<why the reader intent is distinct>"
python3 scripts/temnik.py skip --cluster-id <id> --reason "<why>" --apply          # add --duplicate --url <page> for a duplicate
python3 scripts/new_job.py "<topic>" <YYYY-MM-DD> blog
python3 scripts/temnik.py start --cluster-id <id> --job <job> --apply

# SERP and research
python3 scripts/fetch_site_urls.py --date <YYYY-MM-DD>
python3 scripts/fetch_google_serp.py --query "<primary query>" --geo us --geo gb --geo de --geo au --top-n 20 --serp-features --output-file <job>/raw/serp.csv --features-output-file <job>/raw/features.json
python3 scripts/build_article_serp_brief.py --input-file <job>/raw/serp.csv --features-file <job>/raw/features.json --output-prefix <job>/serp --require-geo us --require-geo gb --require-geo de --require-geo au
python3 scripts/collect_reddit_signals.py --query "<article topic>" --geo us --output-file <job>/audience.reddit.md
python3 scripts/validate_research_map.py --job <job>
python3 scripts/validate_research_discovery.py --job <job>
python3 scripts/validate_primary_data_research.py --job <job>
python3 scripts/validate_study_research.py --job <job>
python3 scripts/validate_quote_research.py --job <job>

# Brief and publisher checkpoint
python3 scripts/validate_article_brief.py --job <job>
python3 scripts/topic_overlap.py check --stage resolved --cluster-id <id> --topic "<job topic>" --keyword "<brief primary query>" --exclude-job <job>
python3 scripts/topic_overlap.py decide --stage resolved --cluster-id <id> --reason "<decision>"

# Plans, render, writing
python3 scripts/fetch_blog_profiles.py --job <job>
python3 scripts/workflow_gate.py check --job <job> --target inputs --offline
python3 scripts/render_visuals.py --job <job>
python3 scripts/check_visual_layout.py --job <job>
python3 scripts/workflow_gate.py check --job <job> --target writer --offline
python3 scripts/blog_openrouter.py prepare writer --batch <batch> --revision writer-1    # hybrid; then execute, import
python3 scripts/blog_openrouter.py prepare critic --batch <batch> --revision critic-1    # hybrid; then execute, import
python3 scripts/writer_dispatch.py --job <job>                                           # native writer; then --check
python3 scripts/assemble_sections.py --job <job>                                         # native writer; the hybrid import assembles by itself
python3 scripts/article_delta.py editor-report --job <job>

# Images into the text, checks, QA seal
python3 scripts/workflow_gate.py check --job <job> --target visual --offline
python3 scripts/upload_review_visuals.py --job <job>                                     # --dry-run previews
python3 scripts/package_article.py --job <job> --bind-visuals
python3 scripts/workflow_gate.py check --job <job> --target qa
python3 scripts/check_research_links.py --job <job>
python3 scripts/wordcount.py --job <job>
python3 scripts/lint_article.py --job <job>
python3 scripts/build_orchestrator_review.py --job <job>
python3 scripts/workflow_gate.py seal-qa --job <job>

# Package and review
python3 scripts/package_article.py --job <job>
python3 scripts/temnik.py ready --job <job> --apply
python3 scripts/gdoc_review.py push --job <job> --round 1
python3 scripts/gdoc_review.py pull --job <job> --round 1 --doc <url>
python3 scripts/workflow_gate.py approve-quotes --job <job> --ids <id> --by <person> --reference <decision-source>
python3 scripts/workflow_gate.py approve-review --job <job> --by <person> --reference <decision-source>

# CMS, only on an explicit request
python3 scripts/upload_visuals.py --job <job>                                            # then package --bind-visuals and the qa gate again
python3 scripts/strapi_publish.py --job <job> --dry-run
python3 scripts/strapi_publish.py --job <job>                                            # creates a draft
(cd tools/covers && node article-covers.mjs --slug=<slug>)                              # cover; token from STRAPI_TOKEN or config/strapi-api-token
python3 scripts/strapi_publish.py --job <job> --update <id> --publish
python3 scripts/temnik.py publish --job <job> --apply
python3 scripts/indexnow_blog.py --job <job> --apply
```

What writes by default differs by script. Topic-sheet commands (`temnik.py`), `blog_refresh.py`,
`indexnow_blog.py` and the translation exporters preview and write only with `--apply`.
`upload_review_visuals.py`, `upload_visuals.py` and `strapi_publish.py` write unless `--dry-run` is
given; `strapi_publish.py` without `--publish` creates a draft. `gdoc_review.py push` creates the
document. `scripts/check_article.py` assembles, splits paragraphs and writes packaged files, so
treat it as mutating.

Two actions have standing permission in `AGENTS.md`: keeping the topic sheet current, and creating
the review document once an article has passed QA and packaged. Uploading images to the CMS,
creating a draft and publishing run only after an explicit request in the current conversation.

Per-article time and token accounting is kept with `scripts/codex_metrics.py` (`start`,
`stage-start`, `stage-bind`, `stage-stop`, `finish`, `report`); the report is
`<job>/metrics/report.md`. See [docs/CODEX.md](docs/CODEX.md).

## Job files

`scripts/new_job.py` takes positional arguments only (it has no `--help`):

```sh
python3 scripts/new_job.py "<topic>" <YYYY-MM-DD> [<label>]
```

| Argument | Meaning |
|---|---|
| `<topic>` | Written to `topic` in `job.yaml` and to `progress.md`; its slug (Cyrillic transliterated, at most 60 characters) forms the folder name |
| `<YYYY-MM-DD>` | The first part of the folder name. Pass it explicitly; the script does not read the clock |
| `<label>` | Optional. Its slug is appended to the folder name, so that parallel runs of one topic get separate folders. The commands above pass `blog`, which gives `jobs/<date>-<topic-slug>-blog` |

If the folder exists, `-2`, `-3` and so on are appended. The script creates `raw/`, `sections/`,
`out/`, `assets/`, `progress.md` and `job.yaml`, and prints the job path. `semantics.csv` is not
created: add it by hand ([format and example](docs/examples/README.md#semanticscsv)).

Fields of the `job.yaml` it writes:

| Field | Default | Meaning |
|---|---|---|
| `workflow_version` | `2` | Turns on workflow v2 in the gates, metrics and refresh scripts |
| `answer_contract_version`, `semantic_refresh_version`, `duplicate_preflight_version`, `research_v3_version`, `research_discovery_version`, `primary_data_research_version`, `visual_qa_version`, `source_policy_version`, `visual_caption_sources_version`, `research_coverage_version`, `geographic_audit_version` | `1` | Protocol flags. Each switches on one contract in the scripts and roles; the comment next to each in the file says which. A job keeps the flags it was created with, so older jobs keep their older contracts |
| `production_text_backend` | `openrouter_hybrid` | Hybrid writer. Delete the line before metrics start to use the native writer ([below](#writer-subscription-or-openrouter)) |
| `topic` | from the argument | Working topic |
| `temnik_cluster_id` | empty | Required: the `Cluster ID` of the approved topic-sheet row, `b-` plus four digits. `temnik.py` finds the row by it and `blog_openrouter.py` matches batch files by it |
| `language` | `EN` | Article language; written to the sheet by `temnik.py ready` and checked by the linter against the page language in `config/site-urls.json` |
| `mode` | `owned` | The blog has one track, so `owned` is the only value. No script reads it |
| `article_type` | `comparison` | Set to the real type (guide, comparison, listicle and so on). The brief, packaging and the CMS script read it; `temnik.py ready` writes it to the sheet |
| `own_product_rank` | `first` | `first`, `top-3` or `neutral`; applies only when `own_product_placement` is `ranked`. The default is not approval |
| `own_product_placement` | `pending` | For rankings and listicles: `ranked`, `separate` or `omit`, recorded after the publisher decides |
| `author` | empty | Required: a username from `config/blog-authors.json` (`john.roe`, `jane.doe`). The CMS script maps it to a CMS user ID |
| `author_angle`, `key_points`, `my_experience` | empty | Optional author input. When filled, the brief role treats them as required inputs. `my_experience` is real, generic experience framing, never a fabricated checkable fact |
| `geo` | `[US, GB, DE, AU]` | The four English-language search markets used for every English topic |
| `semantics_file` | `semantics.csv` | Name of the query file; the roles read `semantics.csv` |
| `author_persona`, `include_competitors`, `exclude_competitors`, `must_cite`, `approved_claims` | `null` / `[]` | No script reads them and no role file names them; they reach the brief role only as part of `job.yaml`. Put a constraint that must bind into `author_angle` or `key_points` instead |

## Writer: subscription or OpenRouter

`scripts/new_job.py` writes `production_text_backend: openrouter_hybrid` into every new
`job.yaml`. With that line:

- the writer is a model called through OpenRouter. `scripts/blog_openrouter.py` sends one complete
  H2 with its approved H3/H4 per request, in one conversation per article that carries the earlier
  verified sections, and imports only a complete response from the pinned route;
- a second OpenRouter model reviews the assembled draft once, before the editor. Its findings
  (`raw/openrouter-critic.json`) are input for the native editor, who checks them against the
  evidence; they are not a verdict;
- substantive defects found later are repaired by the same writer model in a `repair` phase,
  limited to the H2 units listed in `raw/openrouter-rework-plan.json`;
- research, brief, evidence, vendor cards, visual planning, visual QA, comments, editing and
  independent QA stay native Codex agents on the subscription.

Where the settings live:

| What | File |
|---|---|
| Writer and critic routes: model, exact version, provider, price cap per token, reasoning setting, output ceiling | `config/blog-openrouter.json` |
| Budget of a batch (`api_budget_usd`), approved together with the briefs | `docs/workflow-v2/batches/<batch>/brief-approval.json`, bound by hash to `publisher-proposal.json`; field-by-field examples in [docs/examples/](docs/examples/README.md) |
| Models of the native roles | `config/codex-model-routing.json` |
| Models of the older script track, not used by the active flow | `config/openrouter.json` |

Before the first `prepare` of a batch, both approval files must exist in
`docs/workflow-v2/batches/<batch>/`: `publisher-proposal.json` lists the articles with the
hashes of their approved brief files, and `brief-approval.json` records the publisher's approval
of exactly that list and the budget. `prepare` refuses to run without them. Minimal examples,
with every field explained, are in [docs/examples/](docs/examples/README.md). Every article in a
batch is identified by its topic-sheet cluster ID in the form `b-` plus four digits, which must
match `temnik_cluster_id` in its `job.yaml`.

Each phase has three steps. `prepare` freezes the inputs and sends no paid request. `execute`
checks the provider, the token ceiling and the price cap, then calls the model within the approved
budget. `import` brings verified output into the job. Successful units resume from their receipts;
an attempt with an unknown charge blocks further calls until it is reconciled.

Receipts with the actual charge of every attempt are stored under
`runs/<batch>/variants/<revision>-<cluster-id>/attempts/`. Totals per article, including charged
retries and any unreconciled attempts:

```sh
python3 scripts/blog_openrouter.py cost --batch <batch>
```

To run with the native writer only, remove the `production_text_backend: openrouter_hybrid` line
from the job's `job.yaml` before metrics start. The orchestrator then keeps one persistent
`blog-section-writer` thread per article and feeds it one H2 per turn from
`scripts/writer_dispatch.py`; no OpenRouter key, batch approval file or `runs/` folder is needed.
To make that the default, change the template string in `scripts/new_job.py` and the sentence
about new-topic jobs in `AGENTS.md` and in the skill. Refresh and translation jobs always use
native agents.

## Adapting

1. `knowledge/positioning.md` — rewrite every section for your product: category formula, product
   name, capability wording, what the product is not, price wording, forbidden claims. The level
   of detail in the example is the level the editor and QA need.
2. `knowledge/blog-owned.md` — keep the craft rules (queue, SERP, links, tables, markup, length);
   rewrite the product parts: voice and frame, how the product is named, its card in comparisons,
   placement in rankings, the title templates of comparison formats.
3. `knowledge/icp-jtbd.md` — your segments, jobs, pains and customer language.
4. `knowledge/editorial-owned.md` — your editorial rules for the owned voice.
5. `knowledge/legal.md` — the conclusions of your own legal review of comparative content for
   the markets where you publish.
6. `companies/example-co.mdx` — replace with the card of your own product, with a source and a
   check date for every fact. Add cards for the vendors you compare with to `companies/`; the
   evidence role also creates and updates them as it verifies facts.
7. `knowledge/competitors.csv` — your competitor list.
8. `config/brand-rules.json` — brand and product names, site host, banned topics, wording that
   must not stand next to the brand. `scripts/lint_article.py` and
   `scripts/build_orchestrator_review.py` read it; update the linter tests with it.
9. `config/stop-brands.json` — brands that are never mentioned anywhere. Empty by default.
10. `config/site-urls.json` — the map of live URLs for internal links. Set your sitemap index in
    `scripts/fetch_site_urls.py` and rebuild with `python3 scripts/fetch_site_urls.py --date <YYYY-MM-DD>`.
11. `config/site-brand-tokens.json`, `tools/covers/assets/logo.svg` and the fonts in
    `tools/covers/assets/` — the colours, logo and typefaces of charts, diagrams and covers.
12. Authors: usernames, CMS user IDs and the `defaults` block (default author and editor) in
    `config/blog-authors.json`; the `author` comment in the
    `scripts/new_job.py` template; the editor named in `agents-src/agents/blog-expert-quotes.md`.
13. Replace `Example Co`, `Example Workspace`, `example.com` and `cms.example.com` across the
    folder (`grep -rn "Example Co\|example.com"`), including the roles in `agents-src/agents/`, the
    two editorial skills and the tests that assert on them.
14. `config/temnik.json`, `config/indexnow.json`, `config/geos.json` (search markets) and
    `config/codex-model-routing.json` (models available in your Codex account).
15. CMS. The scripts target a Strapi collection: `scripts/strapi_publish.py` (draft, publish,
    refresh update), `scripts/upload_visuals.py` (media), `scripts/fetch_blog_profiles.py` (author
    and editor names), `scripts/md_to_strapi_html.py` with `tools/sanitize/check.js` (HTML that
    survives the sanitizer), `scripts/strapi_translation_draft.py`,
    `scripts/strapi_translation_publish.py`, `tools/covers/article-covers.mjs` (cover upload), and
    the catalogue reads in `scripts/topic_overlap.py`, `scripts/temnik.py publish` and
    `scripts/blog_translation.py bootstrap`. For another CMS, replace these and keep the package
    format in `out/` and the receipts the gates read (`out/strapi_record.json`, the `asset` fields
    of `visuals.json`).
