# How the flows work

Three flows share one design. This page describes that design; each flow's `README.md` lists its
own stages and commands, and its `docs/design-notes.md` gives the reason behind each rule.

## The shape of a flow

```
topic queue ──► job folder ──► research ──► brief ──► evidence ──► writing ──► editing ──► QA ──► review doc ──► CMS
 (sheet or        (one per       (SERP,      (outline,   (verified    (one       (defects,   (independent,  (human      (draft,
  queue file)      article)       sources)    contracts)  claims)      section    style)      PASS/BLOCK)    approval)   publish,
                                                                       per turn)                                          index)
```

Every arrow is a file contract. A stage reads named files from the job folder and writes named
files back; the next stage starts only when a script has validated them. Nothing is passed from
one agent to another through conversation.

## Orchestrator and specialists

- **The orchestrator** is the Codex session you talk to. It follows the flow's skill
  (`.agents/skills/<flow>/SKILL.md`) and the standing rules in `AGENTS.md`. It creates jobs, runs
  scripts, starts specialists, routes rework and reports. It does not write article prose and does
  not judge its own work.
- **Specialists** are flat, depth-1 agents. Each has a role file in `agents-src/agents/` that is its
  complete instruction: inputs to read, outputs to write, rules, and what to return. A specialist
  is started with no inherited conversation (`fork_turns="none"`) and a prompt that contains only
  the job path, the role file and the assigned unit. The orchestrator adds no editorial guidance of
  its own, so two runs of the same job get the same instructions.
- **Specialists never start other agents.** Fan-out happens only at the orchestrator, which keeps
  cost and context predictable.
- **Rework goes back to the same thread.** A QA block returns to the original writer or editor with
  the exact defect; the recheck goes to the original QA thread with a diff, not a full second pass.

| Role type | Does | Never does |
|---|---|---|
| Research / brief | SERP analysis, competitor structures, information gain, outline and per-section content contracts | Write prose |
| Evidence | Open primary sources, record claim, quote, URL, date and verdict | Accept a claim because the brief wants it |
| Company cards (comparisons, rankings) | Build each vendor's facts from its own pages on equal terms | Soften the treatment of your own product |
| Visual planner / visual QA | Plan data-backed charts and diagrams; inspect rendered images at full size and at phone width | Add a visual to meet a quota |
| Writer | One section per turn from the verified packet, keeping running state | Add facts that are not in evidence |
| Editor | Diagnose real defects, fix them, humanize the whole page, list every cut fact | Shorten to hide a gap |
| QA | Entailment of every claim, coverage against the brief, positioning rules, AI patterns; verdict PASS or BLOCK | Edit the text |

## Why the stages are separate

- **Brief before evidence, evidence before writing.** The writer receives only verified facts, so
  an unsupported claim is caught before it becomes a paragraph that reads well.
- **One section per writer turn.** A whole article in one request comes out thin. One H2 (or one
  H3 with its children) per turn keeps each section complete, and a persistent writer thread or a
  running-state file keeps sections from repeating each other.
- **Editing and QA are different agents.** The editor improves the text; QA only checks it. An
  agent that edits cannot give an independent verdict on the result.
- **Deterministic checks are scripts.** Forbidden wording, link targets, heading order, field
  lengths, HTML that survives the CMS sanitizer, image geometry: a script does not get tired and
  costs nothing. Agents handle what needs judgement.
- **Receipts bind a verdict to a version.** QA and humanization reports store a hash of the text
  they checked. Any later edit invalidates them and the package step refuses to continue.

## Models: where a strong one is needed

`config/codex-model-routing.json` in each flow assigns a model and reasoning effort to every role.
The pattern is the same everywhere:

| Stage | Model class | Reason |
|---|---|---|
| Research, brief, evidence | strong | Judgement about sources and what a reader needs; errors here propagate to everything after |
| Company cards, visual planning, writing | mid | Work from a verified packet under a tight contract |
| Editing, final humanization, QA | strong | Catching what the writer got subtly wrong |
| Translation drafts | light | Checked by a strong translation editor and QA afterwards |
| Orchestrator | strong, higher effort | Long context, routing decisions |

Reasoning effort is `medium` for every specialist, including on difficult legal or calculation
topics; only the orchestrator may run higher. The routes are explicit so that a specialist never
inherits the orchestrator's model by accident.

The model IDs in the three routing files, by class. The suffix gives the class: `-sol` strong,
`-terra` mid, `-luna` light. The flows were tuned at different times, so the version numbers
differ between them; within a flow, keep the class of each role when you change versions.

| Class | `blog/config/…` | `glossary/config/…` | `country-guides/config/…` |
|---|---|---|---|
| strong (`-sol`) | `gpt-6-sol`: research map, topic, document, study and quote research, brief, evidence, editor, QA, translation editor and translation QA; `gpt-6.1-sol`: visual QA | `gpt-5.6-sol`: evidence, editor, QA | `gpt-6.2-sol`: facts, research, brief, evidence, editor, visual QA, QA; orchestrator at `high` |
| mid (`-terra`) | `gpt-6.1-terra`: company cards, visual planner, expert comments, section writer | `gpt-5.6-terra`: brief, section writer | `gpt-6.1-terra`: company cards, visual planner, section writer |
| light (`-luna`) | `gpt-6-luna`: translator; `gpt-5.6-luna`: the dormant `blog-coordinator` | — | — |

Two departures from the pattern above are in the files as shipped: the glossary brief runs on
the mid model, and the blog and glossary files have no orchestrator route (the
orchestrator is the session you open). The glossary file also has no routes for
`glossary-research`, `glossary-visual-planner` and `glossary-expert-comments`; until you add
them, those roles run on whatever model the session gives them (see `glossary/README.md`).

## Two ways to run the writer

Defaults differ by flow:

- **Glossary:** hybrid by default; `--writer-backend codex` when creating a job makes it
  subscription-only.
- **Blog:** new-topic jobs are created as hybrid (`production_text_backend: openrouter_hybrid` in
  `job.yaml`). Removing that line before the job starts switches it to the native writer; refreshes
  and translations always run native. `blog/README.md` explains how to change the default.
- **Country guides:** hybrid only. The native `guide-section-writer` role is kept but the skill
  does not dispatch it.

| | Subscription only | Hybrid |
|---|---|---|
| Writer | A native Codex specialist | A script calls a model through OpenRouter, one section per request |
| Everything else | Native Codex specialists | Native Codex specialists |
| Needs | A Codex subscription | A Codex subscription and an OpenRouter key |
| Spend | Counted against subscription limits | Subscription limits plus per-call charges |

Hybrid moves drafting, the stage that works from a verified packet under a tight contract, to an
API model and keeps every judgement stage native. The hybrid scripts carry the safeguards that
make API spend predictable:

- a pinned model version and provider, verified in each response; a mismatch stops the stage;
- a price cap per token and a budget per article, term or country, checked before every request;
- every paid response stored with a receipt in the job folder; a rerun reuses stored responses;
- no silent fallback to another model, provider or backend.

To see what a job cost, read the receipts under the job folder (`writer-api/` in the glossary,
the charge ledger in the blog and guides flows). Subscription usage is an account-wide
percentage; the guides flow records snapshots of it before and after each stage.

## Human checkpoints

| Checkpoint | What happens without it |
|---|---|
| Publisher decisions recorded in the job (for a ranking: whether and where the own product is placed) | Evidence and writing do not start |
| Review document in Google Docs after QA passes | Blog and glossary: created automatically and the article waits there. Guides: created when the guide task asks for it |
| Approval of an expert comment by the named person | The comment stays `proposed` and the CMS step refuses it |
| CMS draft, media upload, publication, indexing ping | Never run without an explicit request in the current conversation |

## Publication

After approval the flow builds the CMS payload from the reviewed version only, checks it against
the CMS sanitizer, uploads images, creates a draft, publishes on request, reads the public record
back to verify fields, cover, author and editor, updates the topic sheet with the live URL and
date, and sends the URL to IndexNow. Each step previews by default and writes with an explicit
flag. A brand listed in `config/stop-brands.json` blocks the payload before any API call.

## What is deliberately absent

- No word targets or minimum lengths. Length follows from the reader questions in the brief.
- No mandatory FAQ, key takeaways or call to action in the body.
- No unapproved place for the own product in a blog ranking. New jobs are created with
  `own_product_rank: first`, but for a ranking or listicle that value is not approval: the publisher
  records `own_product_placement` (ranked, separate or omit) and, when ranked, the rank, before
  evidence and writing start. The guides' vendor list puts the own product first by rule.
  Wherever the own product appears next to other vendors, every vendor is described on the same
  terms.
- No quota of visuals or related links.
