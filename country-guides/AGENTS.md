# Country guides — standing instructions

## Brand stop-list — mandatory

Brands listed in `config/stop-brands.json` are never mentioned anywhere: text, tables, rankings, sources, links, meta, images. The list is empty by default.

Project: this folder (`country-guides/`); every path below is relative to it.

- For creating, continuing, editing or reviewing an Example Co country guide, read
  `.agents/skills/country-guide/SKILL.md`. Ten specialist role specifications live in
  `agents-src/agents/`. The skill explicitly calls for specialist delegation when available.
- For maintenance of this pipeline, edit scripts/instructions directly; do not launch the
  content workflow or specialists merely because the project contains an agent workflow.
- Before selecting or starting another country, verify its actual ISO code and exporter field
  compatibility against the live Strapi schemas via `scripts/check_cms_country.py`.
  `new_guide_job.py` performs this check before creating any folders or changing the queue.
  Unsupported codes or unavailable schema verification block production; choose another
  country without changing CMS/frontend or substituting a code.
- Work inside this project folder. Treat everything outside it (other tools' home
  directories, sibling projects) as read-only sources. Never sync into them. Shared
  dependencies are under `vendor/`; the flow does not read or write `../blog`.
- Preserve existing jobs, their queue statuses, Google Docs URLs and Strapi IDs.
  Resuming an existing job requires a guide-production request; maintenance alone does not
  resume it.
- Rules: `knowledge/guides-rules.md`; facts: `knowledge/facts-schema.md`.
  Statements about Example Co follow the product rules: guides-rules sections 2 and 6 and
  `knowledge/product-positioning.md`. That card is the source of truth; when it changes,
  update guides-rules and `scripts/check_guide.py` with it.
  Design docs are under `docs/`. Current rules and skill override the implementation
  descriptions in those docs.
- One country owns one job folder. Use absolute page-folder paths for `vendor/blog/scripts/`.
  The parent orchestrates scripts and specialists; each specialist owns its assigned scope.
  Use the explicit model/effort routes in `config/codex-model-routing.json`; do not inherit
  the parent model. Verify actual provider rollout contexts against the route for each stage.
  Record a mismatch and stop that stage rather than silently substituting a model.
  Reasoning effort is `medium` at every guide stage, for specialist research, writing,
  editing, humanization and QA. Explicitly pass `reasoning_effort="medium"` when spawning
  specialists instead of inheriting a higher parent setting. Never escalate to `high` or
  above, including for difficult legal or calculation tasks, unless the publisher explicitly
  changes this rule.
  The coordinator is the one exception: it runs on `gpt-6.2-sol` at `high`, as set under
  `orchestrator` in `config/codex-model-routing.json`. This exception never applies to
  specialists.
  Start every independent, dependency-ready specialist scope promptly; do not impose a
  three-specialist workflow cap or pause writers merely because other scopes are active.
  The project runtime ceiling is 32 spawned threads. If the live session enforces a lower
  limit, record the actual rejection and report it; do not claim a config edit raised it.
  Preserve scope ownership and independent QA. Reuse writer/editor/QA agents for rework.
- Models: `config/codex-model-routing.json` assigns every role to one of two models.
  `gpt-6.2-sol` (the strong model) runs facts, research, briefs, evidence, editing, visual
  QA and final QA; `gpt-6.1-terra` (the mid model) runs the ranking, the visual plan and
  drafting, in Codex and through the production API alike. When a newer model of the same
  class becomes available, update the model name in that file, in
  `config/guide-execution.json` and in `load_profile()` of `scripts/guide_api.py` (README,
  «Adapting»), then run `scripts/preflight.py`; role assignments and specialist `medium` do not change
  with the model.
  Keep exactly one H2 section (with its H3/H4) per writer request, including API
  execution. This preserves each section's depth, completeness and necessary length; do
  not batch sections to reduce calls.
  Reduce routine coordinator work through deterministic dispatch and checks, without
  removing editorial or independent QA decisions.
  Do not split or filter the country fact and evidence packet by page: country, EOR and
  contractors retain the full shared packet.
  Research and brief roles stay on `gpt-6.2-sol`; moving them to `gpt-6.1-terra` needs the
  publisher's explicit approval.
  A measured experiment (`scripts/openai_guide_experiment.py`,
  `scripts/openrouter_experiment.py`) never changes production role routes and never
  authorizes publication. Compare frozen inputs before adopting a different execution in
  production, keep independent final QA in Codex, and report quality and all costs.
- The production hybrid for guides. Author: OpenRouter Responses, pinned OpenAI provider,
  `gpt-6.1-terra / medium`, via `scripts/guide_api.py` and `config/guide-execution.json`.
  Substantive editor, repairs and a separate whole-page style pass: native
  `guide-editor` in Codex, `gpt-6.2-sol / medium`. Final independent `guide-qa`,
  research, evidence, briefs and visual QA also run in Codex. API errors stop the
  stage. Do not switch provider, model or backend silently. Verify response
  model/effort/provider/usage and native rollouts. Older API revisions and receipts
  remain frozen; new writing follows the hybrid. Preserve the full factual and
  research packet, previous prose and full merged state, explicit cache at the
  end of the stable packet and one H2 per writer request.
- On every new country, report actual OpenRouter `usage.cost` by page and across
  all revisions, including retries, and identify any responses without a known charge.
  Keep these separate from reserves and Codex account-limit observations.
- Choose the next countries from the queue in `config/queue.json`; its fields and the topic
  sheet behind it are described in `docs/topic-sheet.md`.
- Keep job `progress.md` current. Numbers come from facts, derived calculations and evidence.
  Independent visual QA opens actual PNGs at full size and 390 px before uploads.
  Preserve all content and source checks; a technical pass is not an editorial QA verdict.
- After QA, changing text or visuals invalidates the relevant receipts. Repackage and repeat
  affected QA before sealing. Never generate user approval without the user's actual approval.
- Strapi media upload, guide writes and indexing require explicit conversational authorization
  for this flow. Existing authorization persists within the conversation; an authorization
  given for any other workflow does not cover these writes. Creating a requested review Doc
  is within that guide task.
- All published country-guide pages must be indexable.
  A normal authorized publication targets `indexable: true`; use a noindex preview only when
  explicitly requested. Never silently reset an existing guide to noindex during an update.
  This rule does not authorize publishing new content without a publication request.
- Local credentials for the integrations live in `vendor/blog/config/`. Do not print,
  commit or include their contents in reports. Having credentials grants no publication rights.
- Usage accounting is the parent's responsibility; specialists must not duplicate it.
  Append sanitized account-limit snapshots to `metrics/usage-snapshots.jsonl` before a batch,
  after research, drafting/humanization, final QA and delivery, and when resuming a batch.
  Take each snapshot from the Codex usage view of the account and record what it shows: UTC time,
  checkpoint and job scope, limit ID, window duration, reset timestamp and used percentage, with
  null for anything the view does not show. Missing values and unavailable token counts are null, never assumed zero.
  Never store account IDs, credentials or full account responses. Compare only matching limit
  IDs/windows/reset timestamps; percentage-point changes are account-wide observations and may
  include other chats. They are not exact per-job tokens or costs. Preserve elapsed-time and
  rework observations with their actual provenance; do not reconstruct missing historical usage.
- After changes to code or the skill, run
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests`,
  `python3 scripts/sync_agents.py`, and `python3 scripts/preflight.py`.
  Tests and maintenance must not call external APIs or rewrite existing job artifacts.
