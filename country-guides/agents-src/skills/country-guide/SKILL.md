---
name: country-guide
description: Create, continue, edit or review the three Example Co country-guide pages through research, fact packs, visuals, writing, QA and requested Docs or Strapi delivery.
---

# Country guide — orchestration

Project: `.` (`AGENTS.md`, `knowledge/guides-rules.md`, `knowledge/facts-schema.md`).
Design: `docs/country-guides-flow.md`. You are the orchestrator (main session):
you run scripts, dispatch agents, read their final messages and short reports, keep
`<job>/progress.md` current and do your own editorial pass.

## Production hybrid

Read `config/guide-execution.json`. Run `scripts/guide_api.py` for drafting on
OpenRouter Responses, pinned to OpenAI `gpt-6.1-terra / medium`. Dispatch native
`guide-editor` in Codex for substantive editing, repairs and a separate whole-page
style pass, on `gpt-6.2-sol / medium`. Assign independent `guide-qa` on that same
model and effort with separate ownership. Research, facts, briefs, evidence and
visual QA stay with their existing Codex routes. The drafting stage stops on
provider/model/effort mismatch or material failure. Details: `docs/api-execution.md`.

Every author call writes one section with its H3/H4 (the opening has no H2).
Send all facts, calculations, E/V evidence and research on every call.
Explicit 30-minute caching ends after the complete stable packet. The author
returns the new section and append-only state additions. Send all previous prose
and the complete merged state to the next call.

Dry-run before `--execute`. An authorized guide job covers paid draft writing.
Report actual OpenRouter charges by page and country across all revisions and
retries from `usage.cost`. Track unknown charges, reserves and Codex account
limits separately. Receipts live in `runs/guide-api/<job>/<revision>/`.
Standard job outputs, QA and user publication gates still apply.

## Dispatching agents in Codex

Read the project's `AGENTS.md` first. Roles live in `agents-src/agents/guide-*.md`.
Use native collaboration tools to spawn each specialist directly as a child of the
orchestrator, with `fork_turns="none"`. Read `config/codex-model-routing.json` and pass
the assigned role's exact `model` and `reasoning_effort="medium"` explicitly on every
spawn; do not inherit the parent settings or escalate reasoning. If the built-in role pins
an older model, use an explicit route override with the same project's role file and scope.
Follow a later explicit
model choice from the user if given. Dispatch every independent, dependency-ready scope
promptly; there is no three-specialist workflow cap. The project config allows 32 spawned
threads. Keep writing active alongside card/source rework and visual QA whenever its inputs
are ready. Respect real dependencies and file ownership; never duplicate work to fill slots.
If the live runtime rejects a launch at a lower ceiling, save that rejection and report the
effective limit. A config edit alone does not prove the running session has adopted it.

For a measured batch, record the UTC preparation and production starts separately,
account-limit snapshots and per-stage dispatch/completion timestamps. After dispatch
and again at completion run `scripts/verify_model_route.py` against the actual provider
rollout for that agent. Save its receipt under the batch's `metrics/` directory. A
configuration file or an agent's self-reported model is not runtime proof. If a route
does not match, stop that stage and report the mismatch; never silently substitute.
Check the parent route too, respecting the explicit user-authorized coordination exception
in `config/codex-model-routing.json`. An already-open chat can retain its old model/effort after
a config edit; request the UI change and keep any preparation on the old route separate
from the compliant production measurement. Report missing measurements as unavailable.

Prompt: «Read <absolute role file> completely. Job: <absolute job path>.
Scope/page: <scope>. Produce the role-defined files. Work on the assigned scope only;
do not spawn or message other agents.» Pass paths and scope, not complete artifact contents.
Use a unique task name containing the country, page and role. Reuse the same native
QA/research specialist for its follow-ups. API drafting resumes from its job/revision/stage receipts. Reuse the same native editor
for the style pass and repairs, and the same independent QA for rechecks. Use
`send_message` for messages during active work. Agent state is not a replacement for files.
If collaboration tools are unavailable, follow the role files in order in the main chat,
record that the checks were not independent, and do not claim independent QA.

`python3 scripts/sync_agents.py` syncs the local skill and optional role profiles inside
this project only. It never writes into another tool's home directory. The installed user
skill routes to this project; explicit activation is `$country-guide`.

## Stages (one country = one job)

Before committing to a country, run `python3 scripts/check_cms_country.py --slug <slug>`.
It reads the live Strapi country/subpage schemas without creating a probe record. Unsupported
ISO codes, incompatible fields, or unavailable verification stop selection before research
or paid writing; choose another topic. Do not change CMS/frontend or substitute another
country code. `new_guide_job.py` repeats the live check before any job/queue mutation and
saves a sanitized receipt at `raw/cms-compatibility.json`. This is schema compatibility,
not a replacement for content validation, QA or publication authorization. Existing jobs
and any explicit unpublished hold are preserved; do not resume them for this check.

| # | stage | who | output |
|---|---|---|---|
| 0 | `python3 scripts/new_guide_job.py --slug <slug>`; `python3 scripts/fetch_links.py` if site-links.json is older than a week | script | `jobs/<date>-<slug>/` |
| 1 | `python3 scripts/serp.py --job <job>` as a non-blocking command session (10 queries × geos, slow: 20–40 min; empty query×geo pairs are retried once). If geo-overlap.md still shows a geo with nothing: `serp.py --job <job> --refill` | script | `serp/` |
| 1b | Semrush (MCP, database us + the country's own if it exists): related/phrase-match keywords for `<country> minimum wage`, `average salary <country>`, `hiring in <country>`, `<country> labor law`, `independent contractor <country>`; EOR semantics from the topic sheet tab «Semantics by page» (ID `eor-<iso>`) | you | `semantics/<page>.csv` |
| 2 | guide-facts ×2 in parallel: scope `employment`, scope `contractors` | specialist | `facts.employment.json`, `facts.contractors.json` |
| 3 | `python3 scripts/check_facts.py --job <job> --merge` → fix with the agent until PASS; `python3 scripts/calc.py --job <job>` | script | `facts.json`, `derived.json` |
| 4 | guide-research `changes` and `practitioners` right after stage 3 (they do not need the SERP); `angle` once the SERP is complete | specialist | `research/*.md` |
| 4b | read angle.md's calculation proposals; write `<job>/calc_spec.json` (extra salary scenarios, vars with F- IDs, formulas — see calc.py docstring); `calc.py`. Check every formula yourself (caps, which share applies) — the script only removes arithmetic slips, not modelling mistakes | you + script | `derived.json` |
| 5 | guide-brief `country`; then guide-brief `eor` and `contractors` in parallel | specialist | page `brief.md`, `sections.json`, `out/meta.md` |
| 6 | guide-evidence and guide-company-cards in parallel | specialist | `evidence.md`, `evidence.vendors.md`, contractors `company_cards.md` |
| 7 | if evidence added figures needed by calculations (E- IDs), extend calc_spec.json and rerun `calc.py`; then `python3 scripts/prepare_pages.py --job <job>` | script | page `evidence.md`, `research.md`, `expert_quotes.json` |
| 8 | guide-visual-planner | specialist | page `visuals.json` |
| 9 | per page: `workflow_gate.py check --job <page> --target inputs --offline`; `render_visuals.py --job <page>` | script | `assets/*.png` |
| 10 | guide-visual-qa in parallel with writing | specialist | page `visual_qa.json` |
| 11 | `guide_api.py --job <job> --stage writer --page country --execute`; then `--stage writer --page eor --page contractors --execute`. Each page stays one section per request; sections, full state and draft are materialized mechanically. | OpenRouter `gpt-6.1-terra` / medium | page `sections/`, `running_state.md`, `out/draft.md` |
| 12 | Dispatch `guide-editor` for each assembled page with the full packet. | Codex `gpt-6.2-sol` / medium | page `edited.md`, `editor_issues.md` |
| 13 | `python3 scripts/check_guide.py --job <job>`; `lint_article.py --input <page>/edited.md --walls`; confirmed fixes through the assigned editor | script + Codex editor | — |
| 14 | For local review bind the verified local images. For authorized publication: `upload_visuals.py --job <page> --dry-run`, then (Strapi media — needs permission) `upload_visuals.py --job <page>`, `package_article.py --job <page> --bind-visuals` | script | real images in edited.md |
| 15 | your editorial pass: read the three pages; positioning; repeats; does each page beat the top | you | notes in progress.md |
| 15a | Assigned editor runs a separate whole-page style review after binding images. Repeat affected style review after repairs. | Codex `gpt-6.2-sol` / medium | `edited.md`, hash-bound `humanization_report.md` |
| 16 | native guide-qa ×3 in parallel (give it current check_guide output and signed style report); rework → assigned Codex editor + affected style review → SAME native QA; up to 3 loops | independent Codex QA | `qa_report.md` |
| 17 | per page: `package_article.py --job <page>`; `workflow_gate.py seal-qa --job <page>` | script | `qa_receipt.json` |
| 18 | Deliver validated local review previews. If Docs delivery is requested, per page: `gdoc_review.py push --job <page> --round 1` → links to the publisher; a later round after text changes: `--round N --baseline <page>/review/0{N-1}-sent.md` (a file path, not a number) | script | Google Docs |
| 19 | `gdoc_review.py pull …` → fixes → affected QA → after the publisher's explicit approval `workflow_gate.py approve-review --job <page> --by <publisher's name> --reference <link>` | you | `review_approval.json` |
| 20 | `python3 scripts/strapi_guides.py --job <job>` (dry run) → authorized publication `--write --indexable` (indexable:true unless the publisher explicitly requests a noindex preview) | script | `out/strapi_record.json` |

Shared blog scripts are copied into `vendor/blog/scripts/`; always pass ABSOLUTE page paths to them.

## Rules for the orchestrator
- Numbers only from facts.json / derived.json / evidence. A gap is reported, never filled.
- Humanization is a separate Codex pass before independent final QA, even when the first edit
  already used humanizer rules. Read the whole final page, including headings and
  repeated card patterns. Save concrete before/after examples and the SHA-256 of the
  reviewed `edited.md` in `humanization_report.md`. An editorial AI-Score is not a
  detector result or proof of quality. QA independently checks the prose and report.
  Preserve legal qualifications, facts, source links, quotes and visual blocks. After
  subsequent text changes, repeat the affected humanization review and update its
  report before affected QA. A stale report does not cover the new text.
- Before exports, inspect the rendered lists and headings. Use ordinary Markdown
  bullets for checklists; task-list tokens such as `- [ ]` render as literal brackets
  in the current CMS path. Keep `employer of record` or `EOR` consistent in prose;
  hyphens in URL slugs remain unchanged. Replace vague country-template headings
  such as `in Portuguese terms` with the actual question the section answers.
  FAQ labels are editable under guides-rules 3.4; align the section title and its
  instruction after renaming, while preserving the required questions and answer format.
- After a QA PASS the text is frozen: any change → repackage → affected QA → seal again.
- Strapi writes (media upload, records) only with explicit permission in the conversation.
  Authorized publication defaults to indexable:true under the standing rule;
  use noindex only when requested. Existing authorization persists; do not ask again.
- Keep `<job>/progress.md`: decisions, stage, checks, open questions, Doc links, Strapi state.
  Update `config/queue.json` status: in_progress → review → published.
- After the first three countries of a new setup, write the geo measurement
  (serp/geo-overlap.md totals) and lessons into `docs/country-guides-flow.md` and the rules.
- Report honestly: what passed, what is blocked, what the publisher must look at.

## Existing jobs and external tools

Existing jobs and their review/Strapi identifiers are preserved. Maintenance of the
pipeline does not resume them, rerun publishing, reset their queue status, or grant
external-write authorization. On an explicit continuation, inspect progress.md and validate
current artifacts before proceeding. Do not overwrite reviewed text just to refresh a path.

Semrush and the topic-sheet connection are optional runtime capabilities: inspect available
tools rather than assuming particular MCP tool names exist. If a tool is unavailable, record the
missing semantics/source and continue independent work; never invent keyword volumes.
Research uses available web search and page-reading tools, with the original source
actually opened. A local archive is research memory, not verification of a current law.
Google Docs uses the vendored service-account scripts and shared review folder. Creating
review Docs is covered when requested as part of the guide task; an authorization given for
another workflow does not cover this one. Stage 19 requires the publisher's actual approval, not an
automatic receipt. Production-media uploads remain separate external writes.

Run `python3 scripts/preflight.py` before a fresh run; it lists the dependency locations
it checks.
