# Example Co article pipeline for Codex

Brands listed in `config/stop-brands.json` are never mentioned anywhere: text, tables, rankings, sources, links, metadata, images.

This repository holds the Example Co blog article pipeline for Codex.

Statements about Example Co follow the product rules: `knowledge/positioning.md`, «Naming & category» and §1, with the blog rules in `knowledge/blog-owned.md`. The source of truth is the company's own source documents, distilled into `knowledge/`; when the product rules change, update these cards and `scripts/lint_article.py`.

## Boundaries

- Work only inside this repository unless the user explicitly asks otherwise.
- The sibling flows `../glossary` and `../country-guides` are separate. Never edit, delete, sync into, or commit there.
- Never publish an article or mutate Strapi or another external system unless the user explicitly asks for that action in the current conversation. The narrowly scoped review-Doc exception is below.
- Standing project exception: the blog pipeline must keep the exact
  Google Sheet configured in `config/temnik.json` (the topic sheet) current. It may update only rows it evaluates or
  links to jobs, and only the topic-decision and lifecycle fields defined by `scripts/temnik.py`.
  This exception does not authorize publishing to Strapi.
- Standing project exception: immediately after an article
  passes QA and packages successfully, create its Google Docs review copy with
  `scripts/gdoc_review.py push`, store the URL in the job, and sync the linked topic-sheet row to
  `in review`. This authorizes only review-document creation/update for completed
  blog articles; it does not authorize Strapi drafts or publication.
- Preserve existing and unrelated working-tree changes.

## Article workflow

- Before selecting a published page for a refresh, run a fresh Google URL Inspection
  with `scripts/refresh_indexing.py` and inspect its dated receipt under the batch
  directory and sync its status to the configured topic sheet. Follow the preselection
  rule in `knowledge/blog-refresh.md`: record a non-indexed page and skip to the
  next page, without starting diagnosis or article specialists for the skipped URL.
  An unavailable check is recorded as unknown and skipped, not as non-indexed.
  An old inspection snapshot or absence of GSC query rows does not satisfy this step.
- For requests to create, continue, review, or package an Example Co blog article, use the repo skill at `.agents/skills/blog-article/SKILL.md`.
- The parent Codex agent is the article orchestrator. It runs deterministic checks and starts the
  required specialist agents directly as depth-1 children, using a job-specific task name for
  every specialist thread. Do not insert an intermediate `blog-coordinator`: current local Codex
  runtimes may provision depth-1 agents without native delegation tools. The repo-local
  `blog-coordinator` profile is retained only as a dormant compatibility role for a future runtime
  that reliably supports nested delegation.
- Every article agent is spawned with `fork_turns="none"` and the exact model/effort in `config/codex-model-routing.json`. Do not pass the parent conversation or paste large job artifacts into agent prompts.
- Specialist prompts are fixed routing envelopes, not a place for the parent to interpret the
  content task. Apart from the job path, metrics stage ID, role-file path, and the requested writer
  heading or exact rework defect, the parent must not add editorial guidance, length judgments,
  optimization goals, or other content instructions. The role specification and job artifacts are
  the complete instructions for the specialist.
- Use the platform-neutral role specifications in `agents-src/agents/blog-*.md`. Codex agent configuration lives in `.codex/agents/*.toml`.
- New-topic jobs set production_text_backend: openrouter_hybrid. Use config/blog-openrouter.json
  and scripts/blog_openrouter.py for MiniMax drafting and targeted substantive repairs and
  DeepSeek's first review. The batch uses one approved budget and charge ledger, one complete
  H2 with its approved H3/H4 subtree per MiniMax turn, and one complete draft per DeepSeek review.
  The editor and independent publication QA remain Codex specialists.
- For jobs using the native writer, load scripts/writer_dispatch.py --job <job> once
  and dispatch the next complete H2 when the previous turn finishes.
- After visual/quote plans validate, render and check layout before starting the writer.
  Independent visual QA runs alongside drafting; both branches must pass before upload/package QA.
- Metrics mutations use a per-job transaction lock. Start with `--scope full`, or `--scope preflight`
  followed by a `phase-start --scope production` after brief approval. A missing planned stage
  makes the metrics report incomplete.
- `knowledge/` holds the current rules every role reads; a rule that changes is changed there.
- A job owns only its folder under `jobs/`. Do not reuse prose from another job.
- Blog topics come from the configured topic sheet in sheet order. Do not invent or cherry-pick a later
  topic while an earlier unprocessed row has not been evaluated. Record every skipped or duplicate
  row with a specific reason, then continue downward until the requested number of suitable topics
  has been found.
- For every listicle, ranking, `Best`, or `Top` article, publisher approval must explicitly resolve
  `own_product_placement` as `ranked`, `separate`, or `omit`. A default `own_product_rank: first` is not
  approval to put Example Co inside a category it does not genuinely answer. When placement is
  `ranked`, separately approve its rank; when it is `separate`, keep it outside the ranked list and
  comparison table. Record the decision in `job.yaml` before evidence or drafting.
- Subagents may update `companies/` only when their assigned evidence or company-card role requires verified enrichment.
- Rework continues in the original editor and QA threads. Pass QA failures plus a generated article diff; do not repeat a full QA pass unless the edit changes article structure or unrelated sections.
- New article jobs use an independent `blog-visual-qa` stage after rendering and before any media upload. It checks full-size and 390 px previews; the visual gate must pass before upload. Rework continues in the same visual QA thread.

## Verification

- Run `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider` after changing pipeline code or instructions.
- Run `python3 scripts/validate_codex_setup.py` after changing Codex agents or repo skills.
- Treat `scripts/check_article.py` as mutating: it assembles output, splits paragraphs, and writes packaged files.

## Workflow v2

The pipeline runs workflow v2. The entry point is `.agents/skills/blog-article/SKILL.md`; the
Codex configuration lives in this repository.

### Documents

- `docs/blog-workflow-v2.md`: the enrichment contracts.
- `docs/design-notes.md`: implementation decisions and checks. Record shared decisions there.
- Keep `progress.md` current in every new job.

### Research before the brief

- V2 adds topic research before the brief, and visual planning and expert comment proposals after
  approved evidence and before the persistent writer.
- New jobs with `primary_data_research_version: 1` dispatch the primary-document research
  specialist in parallel with topic research after SERP. Both packets must validate before the
  brief; chart numbers are reverified by evidence.
- New jobs with `research_v3_version: 1` dispatch `blog-research-map` after SERP/Reddit and
  validate its compact Q-ID decision map, then run topic, primary-document, scholarly-study and
  outside-quote research in parallel.
- The document agent uses the repo SERP collector with `filetype:` queries (XMLRiver first) and
  archives `raw/document-search-*.csv`. Its validator requires four format families, archived
  queries and at least one read original before the brief.
- Study metadata and social snippets are leads only. The study and quote packets have separate
  validators.

### Visuals and media

- Materialize the actual visuals before QA. The Docs and Strapi export gates fail closed on
  markers, missing images, stale QA or altered quotes.
- Uploading PNGs to Strapi changes CMS media and needs explicit authorization in the current
  conversation; the standing review-Doc exception does not cover it.
- For review-only Google Docs, checked PNGs may instead go to the article's Google Drive review
  folder with `scripts/upload_review_visuals.py`. This falls under the standing review-Doc
  exception and creates no Strapi media. Strapi export rejects Drive-only image IDs and still
  needs separate CMS-upload authorization.
- New jobs (`visual_qa_version: 1`) need current geometry and independent visual QA receipts
  before media upload; older jobs keep their existing contract.

### Existing jobs

- A job keeps the protocol flags it was created with.
- Do not silently migrate existing jobs or overwrite their artifacts.
