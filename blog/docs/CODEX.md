# Codex adaptation

This document describes how the Example Co blog pipeline runs in Codex.

## Active integration

- `AGENTS.md` defines repository boundaries and persistent project rules.
- `.agents/skills/blog-article/SKILL.md` is the active end-to-end orchestrator skill.
- `.codex/agents/*.toml` defines 18 role profiles: specialized project agents for research, brief, evidence, cards, visuals, quotes, writing, editing, QA and translation, plus a dormant thin coordinator kept for compatibility.
- `config/codex-model-routing.json` pins the model and medium reasoning effort for every article role.
- `.agents/skills/copywriter` and `.agents/skills/humanizer` provide repo-local editorial behavior.
- `agents-src/agents/blog-*.md` remains the detailed role source read by each custom agent.
- `config/temnik.json` identifies the ordered blog topic queue; `scripts/temnik.py` owns its
  conflict-safe lifecycle updates.

Open a new Codex session from this repository so project instructions, repo skills, and custom agents are discovered at session start. Ask Codex to use `$blog-article` or request an Example Co blog article normally.

Install the two local Node toolchains once after cloning:

```bash
(cd tools/sanitize && npm ci)
(cd tools/covers && npm ci)
```

Validate the integration with:

```bash
python3 scripts/validate_codex_setup.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider
```

Use a Python interpreter with the packages from `requirements.txt` and `pytest` installed.
The tested runtime is Python 3.14, called as `python3.14`.

New-topic production uses MiniMax M3.1 Flash for complete H2 units and DeepSeek V4.1 Flash
for the first review pass on the assembled first draft (D0). `scripts/blog_openrouter.py` uses the pinned routes in
`config/blog-openrouter.json` and the exact brief and budget approvals for each batch.
The native editor, independent article and visual QA, and existing publication gates remain
part of the active flow. Refresh and translation jobs follow their own routes.

## Topic queue

The blog topic sheet is not a loose idea list. Read it from the first unprocessed row downward, apply
the topic-fit and duplicate checks to every row, and record `duplicate` or `skip` plus a specific
reason instead of silently jumping over it. Continue until the requested batch contains enough
suitable rows. Only after the publisher approves those rows are jobs created and marked `in progress`.

The same row is updated automatically at four boundaries: job start, successful packaging,
Google Docs handoff, and verified live publication. See `python3 scripts/temnik.py --help`.
`AGENTS.md` authorizes these topic-sheet updates and review Docs for QA-passed, packaged articles.
Strapi actions require an explicit request in the current conversation.

Article agents start without inherited parent history. The job folder is the handoff boundary:
prompts name the files to read instead of copying their contents. Editor and QA rework continues
in the original threads and uses a generated diff so a small correction does not trigger a second
full review.

The writer uses one persistent conversation per article. Every turn covers one complete H2 and
its approved H3/H4 descendants. For native jobs the parent loads
`scripts/writer_dispatch.py --job <job>` and dispatches each unit to the same thread; in hybrid
jobs the writer runner verifies prior outputs and carries them into the next request. The approved full
H2-H4 hierarchy and research context replace detailed section micro-briefs. They contain no total
length, competitor word range, minimum, or section word budget. Word count is measured after
drafting only.
For v2, render and check layout after both visual/quote plans validate, before writing.
`workflow_gate.py check --target writer --offline` requires current render/layout without waiting
for independent visual QA. That QA runs alongside writing/editing; uploads and final article QA
still require both branches to pass. Reuse unchanged render/QA receipts after editing.
Every English topic uses four English-language SERPs — US, GB, DE, and AU — which are de-duplicated
by URL while preserving regional presence and positions. `fetch_google_serp.py` uses XMLRiver and
falls back automatically to DataForSEO when `config/.env` contains `DATAFORSEO_LOGIN` and
`DATAFORSEO_PASSWORD`; pass `--provider dataforseo` to bypass XMLRiver. Both providers preserve
the same downstream CSV/feature contract, and a provider outage produces a non-zero exit rather
than a header-only success. The
editor preserves approved coverage and records substantive gaps as `writer-rework:` instead of
cutting around them. After editing, `article_delta.py editor-report` gives QA section-level word
deltas and heading changes as a signal. The normal budget is one full edit, one full QA, and one
targeted correction/re-check; only an unresolved factual, legal, positioning, or publication-safety
blocker may justify one final bounded correction.

## Per-article metrics

The coordinator starts provider-backed measurement from its own thread:

```bash
python3 scripts/codex_metrics.py start --job jobs/<job> --scope full --weekly-remaining <percent>
```

`--weekly-remaining` may be omitted when the user has not supplied a snapshot. Wrap every local
script or agent in `stage-start` / `stage-stop`, and bind agent stages to the returned thread id
with `stage-bind`. Reused editor/QA threads are attributed by non-overlapping stage time windows;
an optional `--root-turn-id` gives even narrower attribution when the runtime exposes it.
Every manifest mutation holds a per-job lock across read/modify/atomic replace. Start freezes the
expected stage list; omitted stages make the report INCOMPLETE. Use `--scope preflight` when the
run ends at brief approval, then `phase-start --name production-resume --scope production` for
the approved continuation. Feedback/publication phases use their default manual scope.
The report separates observed completed-turn execution from dispatch, between-turn and closing
delays. Missing task events are unknown, not zero; the cause of a delay is not inferred.

The parent orchestrator finishes measurement promptly when the review Doc is ready:

```bash
python3 scripts/codex_metrics.py finish --job jobs/<job> --weekly-remaining <percent>
```

If the user reports the post-run weekly percentage later, attach it without changing the finish
timestamp:

```bash
python3 scripts/codex_metrics.py weekly-after --job jobs/<job> --remaining <percent>
```

The report separates input, cached input, derived uncached input, output, and reasoning output.
It validates the actual provider-recorded model/effort against `config/codex-model-routing.json`.
Ambiguous attribution or a routing mismatch produces an `INCOMPLETE` report instead of an
estimate. The weekly subscription percentage remains a coarse user observation and is never
derived from token counts. The article-total boundary is the parent orchestrator turn plus all
bound specialist stages. The dormant compatibility coordinator is not dispatched.

Google Docs review, feedback rework, Strapi draft creation, cover upload, publication, and live
verification are later lifecycle phases. Register them in the same job metrics before reporting a
whole-lifecycle total; keep the production subtotal separate so waiting for user feedback is not
presented as model work. After a verified publication, update the relevant queue document in
`docs/`.

Start and stop one phase per user turn. Register same-turn publication in the current production
scope. Resume work deferred for a publisher decision with `phase-start --continue-phase <id|initial>`.
Hybrid run costs come from `python3 scripts/blog_openrouter.py cost --batch <batch>`.

```bash
phase=$(python3 scripts/codex_metrics.py phase-start --job jobs/<job> --name google-docs)
stage=$(python3 scripts/codex_metrics.py stage-start --job jobs/<job> --phase-id "$phase" --stage gdoc-push --kind script)
# run the action
python3 scripts/codex_metrics.py stage-stop --job jobs/<job> --id "$stage"
python3 scripts/codex_metrics.py phase-stop --job jobs/<job> --id "$phase"
```

Use the same pattern for `feedback-rework` and `publication`; agent stages are bound to their
provider thread exactly as in production. The report shows production and whole-lifecycle totals.
