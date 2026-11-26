# Country guides flow

Produces three English reference pages per country from one shared fact pack: search results in
four markets, research beyond the results, three briefs, verified evidence, a vendor ranking on
the contractors page, data-backed visuals, section-by-section drafting, editing, a separate style
pass, independent QA, review documents and, on request, three CMS records.

Example Co in this folder is a fictional company. The product card and rules in `knowledge/` and
the values in `config/` (brand rules, queue, vendors, site links) describe that fictional company
and its invented product. Before the first run, replace them with your own: see
[Adapting](#adapting).

The flow needs a CMS with a matching schema before the first job can be created: the job script
checks the country's ISO code and the exported fields against the live CMS schema and stops if the
CMS is missing, unreachable or different. The two content types it expects are described in
[docs/country-guides-spec.md](docs/country-guides-spec.md#the-specification-of-the-types-in-strapi).

## What a job produces

| Page | URL | H1 | Page folder in the job | CMS record |
|---|---|---|---|---|
| `country` — hiring overview | `/guides/<slug>/` | `Hiring in <Country>` (built by the site) | `pages/guide-<slug>/` | `country-guide`: name, slug, ISO `code`, the eight header figures, body, meta, `indexable`, author, editor |
| `eor` — employer of record | `/guides/<slug>/employer-of-record/` | `Employer of Record in <Country>` | `pages/guide-<slug>-eor/` | `guide-subpage` with `kind: eor`, linked to the country record |
| `contractors` — independent contractors | `/guides/<slug>/independent-contractors/` | `Hiring contractors in <Country>` | `pages/guide-<slug>-contractors/` | `guide-subpage` with `kind: contractors`, linked to the country record |

The site renders the header, the eight header figures (country page only), the disclaimer, the
table of contents and the banner itself; each page body starts after its H1. The country page
carries a routes table whose rate and notice period equal the header fields; the contractors page
carries the ranking «Who works with contractors in <Country>»; the EOR page has no ranking. The
fixed core of each page, the formats and the product rules are in
[knowledge/guides-rules.md](knowledge/guides-rules.md); the page template and the CMS types are
described in [docs/country-guides-spec.md](docs/country-guides-spec.md).

## Stages

One country is one job. Shared blog scripts are called from `vendor/blog/scripts/` with absolute
page-folder paths.

| # | Stage | Who | Output in `jobs/<date>-<slug>/` |
|---|---|---|---|
| 0 | Check the country's ISO code and field compatibility against the live CMS schema; create the job (repeats the check before touching folders or the queue); refresh internal links if `config/site-links.json` is older than a week | `check_cms_country.py`, `new_guide_job.py`, `fetch_links.py` | `job.json`, `progress.md`, `raw/cms-compatibility.json`, three page folders with `job.yaml`; queue status `in_progress` |
| 1 | Search results: 10 queries across three page clusters × markets (US, GB, AU and the country); structures, market overlap, rankings found in the results | `serp.py` (`--refill` retries empty query×market pairs) | `serp/<page>.csv`, `.features.json`, `.serp_synthesis.md`, `.competitor_structures.csv`; `serp/geo-overlap.md`, `serp/rankings.md` |
| 1b | Keyword semantics per page, if a keyword tool is connected; a missing tool is recorded, volumes are never invented | orchestrator | `semantics/<page>.csv` |
| 2 | Fact pack, two scopes in parallel | `guide-facts` ×2 (`employment`, `contractors`) | `facts.employment.json`, `facts.contractors.json` |
| 3 | Merge and validate until PASS; deterministic calculations | `check_facts.py --merge`, `calc.py` | `facts.json`, `derived.json` |
| 4 | Research lines: `changes` and `practitioners` right after stage 3, `angle` once the search results are complete | `guide-research` ×3 | `research/changes.md`, `research/practitioners.md`, `research/angle.md` |
| 4b | Country-specific calculations from the angle line's proposals; every formula checked by hand | orchestrator + `calc.py` | `calc_spec.json`, `derived.json` |
| 5 | Briefs: country first, then eor and contractors in parallel | `guide-brief` ×3 | per page `brief.md`, `sections.json`, `out/meta.md` |
| 6 | Evidence for research findings and quotes; the vendor ranking | `guide-evidence`, `guide-company-cards` in parallel | `evidence.md`, `evidence.vendors.md`, contractors page `company_cards.md` |
| 7 | Extend `calc_spec.json` if evidence added figures; lay the inputs out per page | `calc.py`, `prepare_pages.py` | per page `evidence.md` (F-, C-, E-, V- rows), `research.md`, `expert_quotes.json` (empty by design) |
| 8 | Visual plan for the three pages | `guide-visual-planner` | per page `visuals.json` |
| 9 | Input gate and rendering, per page | `workflow_gate.py check --target inputs --offline`, `render_visuals.py` | per page `assets/*.png` |
| 10 | Independent visual QA at full size and at 390 px, in parallel with writing | `guide-visual-qa` | per page `visual_qa.json`; 390-px copies in `work/` |
| 11 | Drafting, one section per request: country first, then eor and contractors | `guide_api.py --stage writer` (OpenRouter) | per page `sections/`, `running_state.md`, `out/draft.md`; receipts under `runs/guide-api/` |
| 12 | Substantive editing, one editor per page | `guide-editor` | `edited.md`, `editor_issues.md` |
| 13 | Machine checks and long-paragraph list; confirmed fixes through the same editor | `check_guide.py`, `lint_article.py --walls` | — |
| 14 | Bind images: verified local images for local review; for authorized publication upload to CMS media first | `upload_visuals.py` (`--dry-run` first), `package_article.py --bind-visuals` | images in `edited.md` |
| 15 | Editorial pass over the three pages: positioning, repeats, does each page beat the top | orchestrator | notes in `progress.md` |
| 15a | Separate whole-page style pass after images are bound | the same `guide-editor` | `humanization_report.md` with the SHA-256 of `edited.md` |
| 16 | Independent QA ×3 in parallel; rework → same editor + affected style pass → same QA, up to 3 loops | `guide-qa` | `qa_report.md` ending `overall: PASS` or `BLOCK` |
| 17 | Package and seal, per page | `package_article.py`, `workflow_gate.py seal-qa` | `out/`, `qa_receipt.json` |
| 18 | Local review previews; Google Docs when requested | `gdoc_review.py push` | `review/01-sent.md`, review documents |
| 19 | Pull the publisher's edits, fix, repeat affected QA; record the publisher's actual approval | `gdoc_review.py pull`, `workflow_gate.py approve-review` | `review_approval.json` |
| 20 | On an explicit request: the three CMS records | `strapi_guides.py` (dry run), then `--write --indexable` | `out/strapi_record.json` |

The orchestrator is the parent Codex session. It runs the scripts, starts each specialist as a
flat depth-1 agent with `fork_turns="none"` and the explicit model and `reasoning_effort` from
`config/codex-model-routing.json`, keeps `progress.md` and the queue status current, and never
marks its own work as QA. The full procedure is in
[.agents/skills/country-guide/SKILL.md](.agents/skills/country-guide/SKILL.md), the standing
rules in [AGENTS.md](AGENTS.md), the reasons behind the rules in
[docs/design-notes.md](docs/design-notes.md).

## Job folder

```
jobs/<date>-<slug>/
  job.json, progress.md
  raw/              cms-compatibility.json; hint-facts.yaml, hint-vendors.yaml (optional research memory)
  serp/             <page>.csv, .features.json, .serp_synthesis.md, .competitor_structures.csv,
                    geo-overlap.md, rankings.md
  semantics/        <page>.csv (optional)
  facts.employment.json, facts.contractors.json → facts.json
  calc_spec.json    country-specific calculations (written by the orchestrator)
  derived.json      C- rows from calc.py
  research/         changes.md, practitioners.md, angle.md
  evidence.md       E- rows; evidence.vendors.md — V- rows for the ranking
  work/             390-px copies made by visual QA
  out/              strapi_record.json after a CMS write
  pages/
    guide-<slug>/, guide-<slug>-eor/, guide-<slug>-contractors/
      job.yaml, brief.md, sections.json, out/meta.md
      evidence.md, research.md, expert_quotes.json      ← prepare_pages.py
      visuals.json, assets/, visual_qa.json
      sections/, running_state.md, out/draft.md        ← writer
      edited.md, editor_issues.md, humanization_report.md
      qa_report.md, qa_receipt.json, out/, review/, review_approval.json
      company_cards.md                                  ← contractors page only
```

Each page folder follows the blog's job format, which is why rendering, uploads, packaging, the
QA gate and review documents run from `vendor/blog/scripts/` unchanged. Two folders live outside
the job: `runs/guide-api/<job>/<revision>/` (API profile, requests, receipts, charges) and
`metrics/` (account-limit snapshots and model-route receipts).

## Layout

| Path | What it holds |
|---|---|
| `AGENTS.md` | Standing instructions to the orchestrator |
| `.agents/skills/country-guide/` | The skill: stages, dispatch rules, publication gates. Source in `agents-src/skills/country-guide/`, copied by `scripts/sync_agents.py` |
| `.agents/skills/copywriter/`, `.agents/skills/humanizer/` | Copywriting policy and checklist; editing method and the catalogue of AI-writing patterns |
| `agents-src/agents/` | Ten role specifications `guide-*.md` |
| `.codex/agents/` | Role profiles generated by `sync_agents.py` from the roles and the routes |
| `.codex/config.toml` | Session model and effort, agents enabled, 32 concurrent threads |
| `config/codex-model-routing.json` | Model and reasoning effort per role and for the orchestrator |
| `config/guide-execution.json` | The production hybrid: writer route, native stages, cache, budgets, no fallback |
| `config/` | Queue, search markets, internal links, product wording rules, brand stop-list, competitor hosts |
| `knowledge/guides-rules.md` | Binding rules for every role: pages, product positioning, structure, numbers, ranking, visuals, quotes, sources, writing |
| `knowledge/facts-schema.md` | The fact pack schema and the checks `check_facts.py` runs |
| `knowledge/product-positioning.md` | The full product card behind guides-rules sections 2 and 6 |
| `docs/` | Design notes, the flow design, the API runbook, the page specification with the CMS types, the editor guide, the topic sheet |
| `scripts/` | Job lifecycle, SERP, fact pack, calculator, page preparation, checks, API writer, CMS, route verification, experiments |
| `tests/` | Offline tests; none calls an external service |
| `vendor/blog/` | The copy of blog-flow parts this flow uses: SERP capture and brief builder, visual renderer and verifier, workflow gate, assembly, linter, text-overlap functions, packaging, Google Docs export and review, CMS upload and publish helpers (`scripts/`); the reference CMS sanitizer (`tools/sanitize/`); `config/.env.example`, author IDs, site URLs (`config/`); GEO, SEO and legal notes (`knowledge/`); the `visuals.json` schema (`docs/blog-workflow-v2.md`) |
| `vendor/brand/` | Logo, font files and the font loader used by the visual renderer |

The flow is self-contained: it does not read `../blog`.

## Set-up

```sh
pip install -r requirements.txt
npm ci --prefix vendor/blog/tools/sanitize
npm ci --prefix vendor/brand
```

- CMS: create the `country-guide` and `guide-subpage` content types described in
  [docs/country-guides-spec.md](docs/country-guides-spec.md#the-specification-of-the-types-in-strapi),
  with the ISO codes of your countries in the `code` enumeration, before the first job.
  `new_guide_job.py` refuses to create a job until `check_cms_country.py` passes against the live
  schema.
- Credentials live in `vendor/blog/config/`. Copy `.env.example` to `.env` and fill in
  `XMLRIVER_USER`, `XMLRIVER_KEY`, `GOOGLE_DRIVE_FOLDER_ID` and `OPENROUTER_GUIDES_API_KEY` (a key
  for this flow only; a generic key is refused). Put `google-service-account.json` and
  `strapi-api-token` next to it. The CMS token is needed from the first job, not only at
  publication: `check_cms_country.py` and `new_guide_job.py` read the live CMS schema with it.
  See [../docs/setup.md](../docs/setup.md).
- `python3.14 scripts/preflight.py` checks, offline, the required files, the ten roles and their
  `medium` routes, the match between `config/guide-execution.json` and the native routes, Python
  dependencies, Node assets and the presence of the three credential files. On a fresh copy it
  blocks on those three files until you add them.
- Queue: `config/queue.json`, built by hand from the topic sheet
  ([docs/topic-sheet.md](docs/topic-sheet.md)). Each country has `order`, `slug`, `iso`, `name`,
  `eor_query`, `eor_cluster_us`, `geo_key`, `status`, `query_name` and two flags: `icp` (a country
  of strategic interest to the business) and `pilot` (a country used for a trial run of a new
  setup). The flags are copied into `job.json` for the record; no script changes its behaviour
  because of them. Statuses go `planned` → `in_progress` (set by `new_guide_job.py`) → `review` →
  `published`.
- Internal links: `python3.14 scripts/fetch_links.py` rebuilds `config/site-links.json` from the
  sitemap index, English pages only. Writers may link only to addresses in that file.
- Checks: `PYTHONDONTWRITEBYTECODE=1 python3.14 -m pytest -q -p no:cacheprovider tests`.

## Commands

```sh
python3.14 scripts/check_cms_country.py --slug <slug>
python3.14 scripts/new_guide_job.py --slug <slug> --date YYYY-MM-DD                # --date defaults to today
python3.14 scripts/fetch_links.py                                                    # if site-links.json is older than a week
python3.14 scripts/serp.py --job jobs/<job>                                          # slow; --refill for empty pairs
python3.14 scripts/check_facts.py --job jobs/<job> --merge
python3.14 scripts/calc.py --job jobs/<job>                                          # again after calc_spec.json / new E- figures
python3.14 scripts/prepare_pages.py --job jobs/<job>

# per page folder; P is an absolute path such as $PWD/jobs/<job>/pages/guide-<slug>-eor
python3.14 vendor/blog/scripts/workflow_gate.py check --job $P --target inputs --offline
python3.14 vendor/blog/scripts/render_visuals.py --job $P

python3.14 scripts/guide_api.py --job jobs/<job> --stage writer --page country      # plan only: no key, no charge
python3.14 scripts/guide_api.py --job jobs/<job> --stage writer --page country --execute
python3.14 scripts/guide_api.py --job jobs/<job> --stage writer --page eor --page contractors --execute

python3.14 scripts/check_guide.py --job jobs/<job>
python3.14 vendor/blog/scripts/lint_article.py --input $P/edited.md --walls
python3.14 scripts/order_sources.py $P/edited.md                                     # after edits that move citations
python3.14 vendor/blog/scripts/upload_visuals.py --job $P --dry-run                  # publication only; real upload needs permission
python3.14 vendor/blog/scripts/package_article.py --job $P --bind-visuals
python3.14 vendor/blog/scripts/package_article.py --job $P
python3.14 vendor/blog/scripts/workflow_gate.py seal-qa --job $P
python3.14 vendor/blog/scripts/gdoc_review.py push --job $P --round 1               # later rounds: --round N --baseline $P/review/0<N-1>-sent.md
python3.14 vendor/blog/scripts/gdoc_review.py pull --job $P --round 1 --doc <id-or-url>
python3.14 vendor/blog/scripts/workflow_gate.py approve-review --job $P --by <publisher> --reference <link>

python3.14 scripts/strapi_guides.py --job jobs/<job>                                 # dry run
python3.14 scripts/strapi_guides.py --job jobs/<job> --write --indexable             # on an explicit request
```

Every command that writes to an external system previews by default. Media upload, CMS writes and
publication run only after an explicit request in the conversation; `approve-review` records only
an approval the publisher actually gave.

## Writer: subscription or OpenRouter

The production route is a hybrid, set in `config/guide-execution.json` and documented in
[docs/api-execution.md](docs/api-execution.md):

| Stage | Execution |
|---|---|
| Draft | `scripts/guide_api.py` → OpenRouter Responses, OpenAI provider pinned, `gpt-6.1-terra` / `medium` |
| Editing, repairs, separate style pass | native `guide-editor` in Codex, `gpt-6.2-sol` / `medium` |
| Final QA | native `guide-qa` in Codex, `gpt-6.2-sol` / `medium`, independent |
| Facts, research, briefs, evidence, ranking, visuals | native Codex roles on their routes in `config/codex-model-routing.json` |
| Coordination | `gpt-6.2-sol` / `high` |

Every writer request carries one section with its H3/H4 (the opening is its own request), the
full country packet (facts, calculations, all E/V rows, research), the page brief, visual data,
cards, all previous sections and the full merged state. An explicit 30-minute cache boundary sits
after the stable packet; the model returns the section plus append-only state additions, which
the code merges.

There is no writer-backend option at job creation: `new_guide_job.py --help` lists only `--slug`
and `--date`. The profile loader in `guide_api.py` accepts `openrouter` as the only
`default_backend` and requires `automatic_fallback: false`; `guide_api.py --backend` only asserts
the assigned transport, and `--stage editor`, `humanizer` or `repair` refuse to run because those
stages are native. A failed or mismatched API response stops the stage; it never falls back to
Codex. The native role `agents-src/agents/guide-section-writer.md` keeps the same
one-section-per-turn contract and has its route in `config/codex-model-routing.json`, but the
skill has no stage that dispatches it: a subscription-only run is not wired in. To add one, give
stage 11 an alternative that dispatches this role per page and produces `out/draft.md`, which the
editor reads.

- Key: `OPENROUTER_GUIDES_API_KEY` in `vendor/blog/config/.env` (or one line labelled
  `countries`); only `--execute` reads it.
- Budgets in `config/guide-execution.json`: `max_cost_usd` per revision (15, also the loader's
  ceiling), `max_call_cost_usd` reserve per call (8, checked before every request),
  `max_workers` (2), `timeout_seconds` (900), `max_repair_rounds` (3). A new `--revision` can
  set `--max-call-cost-usd` for a large packet or a lower `--max-cost-usd` that accounts for
  earlier spend; the revision's `profile.json` freezes the values.
- Recovery: a rerun with the same job, revision and inputs reuses successful receipts;
  `--retry-failed`, `--compact-packet`, `--resume-frozen-visuals` and
  `scripts/reconcile_openrouter_429.py --baseline <receipt>` cover the cases described in the
  runbook. A changed input packet needs a new revision.
- Charges: `runs/guide-api/<job>/<revision>/usage.writer-by-page.json` sums `usage.cost` per page
  over every writer attempt, retries included, and counts attempts without a known charge;
  `usage.latest.json` and the attempt receipts under `execution/variants/` keep tokens and
  provider data. Report actual charges per page and per country across all revisions; reserves
  are not charges.
- Subscription usage is an account-wide percentage. The orchestrator appends sanitized snapshots
  to `metrics/usage-snapshots.jsonl` at the checkpoints listed in `AGENTS.md`, and verifies the
  actual model of each native stage with `scripts/verify_model_route.py`.

## Adapting

1. Product rules: [knowledge/guides-rules.md](knowledge/guides-rules.md) section 2 (how the product
   is named and described, where it may appear, what it is never called) and section 6 (the
   ranking), and [knowledge/product-positioning.md](knowledge/product-positioning.md), the full
   card they follow. Keep the headings; rewrite the content at the same level of detail. The card
   is the source of truth: when it changes, update guides-rules and `scripts/check_guide.py` with
   it. The copywriting policy is in `.agents/skills/copywriter/`.
2. `config/brand-rules.json` — brand, product and site host; brand misspellings; banned topics
   (empty by default); site-wide wording; the industry term that is never your label; claims
   forbidden next to the brand; negation rules. Regular expressions read by `check_guide.py`,
   `order_sources.py` and `vendor/blog/scripts/lint_article.py`. Adjust the test fixtures that
   assert the fictional rules.
3. `config/stop-brands.json` — `brands` never mentioned anywhere; `subject_only_brands` named only
   inside their own ranking card and its Sources entries. Both empty by default.
4. `config/vendors.json` — `competitor_domains` a guide never links to (Sources give such pages
   as plain text) and `aliases` from a Sources publisher name to the ranking's vendor name.
5. `config/queue.json` — your countries, `topic_sheet` ID and EOR query volumes; the fields and the
   sheet behind them are in [docs/topic-sheet.md](docs/topic-sheet.md).
6. `config/geos.json` — search markets with your SERP provider's country and domain IDs. The set
   per job is fixed in `scripts/new_guide_job.py`: `us`, `gb`, `au` plus the country's `geo_key`.
7. `config/site-links.json` — `scripts/fetch_links.py` reads the sitemap index URL and the
   language-prefix pattern set at the top of that script.
8. Names and addresses: `Example Co`, `Example Workspace`, `example.com`, `cms.example.com`
   across the folder; author and editor usernames and their CMS IDs in
   `vendor/blog/config/blog-authors.json` (`scripts/common.py` reads `AUTHOR` and `EDITOR` from
   its `defaults` block); logo and fonts in `vendor/brand/`.
9. CMS: `scripts/strapi_guides.py` writes a Strapi `country-guide` record (name, slug, `code`,
   seven header strings, `employerContributions` as a number, body, meta, `indexable`, author,
   editors) and two `guide-subpage` records found by `country` + `kind`;
   `scripts/check_cms_country.py` reads both content-type schemas and expects `code` to be an
   enumeration (the schema is in
   [docs/country-guides-spec.md](docs/country-guides-spec.md#the-specification-of-the-types-in-strapi)).
   For another CMS replace both scripts, keep the "preview by default, write with a
   flag" behaviour, the read-back, and the package format in each page's `out/`; set the
   sanitizer allow-list in `vendor/blog/tools/sanitize/` to what your CMS keeps.
10. A subject other than hiring: `scripts/calc.py` models employer cost with contribution caps
    and floors, and [knowledge/facts-schema.md](knowledge/facts-schema.md) defines the header
    keys, contributions, scenarios and the two fact scopes. The header keys are also named in
    `scripts/check_facts.py` and `scripts/check_cms_country.py`, the core sections in
    `CORE` of `scripts/check_guide.py` and guides-rules 3.1, the page H1s in `h1()` of
    `scripts/common.py`, the visual catalogue in guides-rules section 7.
11. Models: `config/codex-model-routing.json` and `config/guide-execution.json`. The model names
    are also fixed in `load_profile()` of `scripts/guide_api.py` and in the pinned snapshots of
    `scripts/openai_guide_experiment.py`; `preflight.py` checks that the files agree.

Then follow [../docs/adapting.md](../docs/adapting.md), section 9 («Check»): tests pass, the
`grep` given there finds no fictional names outside the tests, one country runs end to end with
publication switched off. Section 8 of that file lists the copies under `vendor/blog/` that do
not follow changes in `../blog`.
