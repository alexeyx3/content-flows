# Glossary flow

Produces one English glossary term per job: research across three search markets, verified
sources, section-by-section writing, editing, independent QA, a review document, and on request a
CMS draft, publication and an IndexNow ping.

Example Co in this folder is a fictional company. Before the first run, replace it with your own:
see [Adapting](#adapting).

## Stages

| # | Stage | Who | Output in `jobs/<date>-<slug>/` |
|---|---|---|---|
| 1 | Create the job, mark the topic-sheet row | orchestrator, `glossary_job.py new`, `glossary_temnik.py start` | `request.json` |
| 2 | SERP in US, UK, DE; competitor structures; hybrid outline; research map; brief | `glossary-brief` (`glossary-research` for a complex term) | `serp.*.md`, `research.md`, `brief.md`, `sections.json`, `meta.json` |
| 3 | Source verification | `glossary-evidence` | `evidence.md` |
| 4 | Visual plan and optional expert comment | `glossary-visual-planner`, `glossary-expert-comments` | `visuals.json`, `expert_quotes.json` |
| 5 | Input gate | `glossary_job.py materials-check --stage inputs` | — |
| 6 | Writing, one H2 or H3 per turn | OpenRouter writer (`glossary_writer.py`) or `glossary-section-writer` | `sections/*.md` |
| 7 | Assembly, editing, visual binding, whole-page humanization | `glossary_job.py assemble`, `glossary-editor` | `edited.md`, `humanization_report.md` |
| 8 | Independent QA | `glossary-qa` | `qa_report.md` with `Verdict: PASS` or `BLOCK` |
| 9 | Package and review document | `glossary_job.py package`, `gdoc_review.py`, `glossary_temnik.py review` | `out/`, `review/` |
| 10 | On request: cover, CMS draft, publish, verify, IndexNow | `tools/covers`, `strapi_glossary.py`, `indexnow_glossary.py`, `glossary_temnik.py publish` | `publication.md`, `indexnow/` |

The orchestrator is the parent Codex session. It runs the scripts and starts each specialist as a
flat depth-1 agent; it never writes article prose and never marks its own work as QA. The full
procedure is in [.agents/skills/glossary-term/SKILL.md](.agents/skills/glossary-term/SKILL.md);
the reasons behind the rules are in [docs/design-notes.md](docs/design-notes.md).

## Layout

| Path | What it holds |
|---|---|
| `AGENTS.md` | Standing instructions to the orchestrator |
| `.agents/skills/glossary-term/` | The skill: stages and the conditions for moving between them |
| `.agents/skills/humanizer/` | Editing method and the catalogue of AI-writing patterns |
| `agents-src/agents/` | Eight role specifications |
| `config/codex-model-routing.json` | Model and reasoning effort per role; the OpenRouter writer route and per-term budget |
| `config/` | Search markets, topic sheet, review folder, IndexNow key, brand stop-list |
| `knowledge/positioning.md` | Rules for every statement about your own product |
| `scripts/` | Job lifecycle, writer, packaging, review document, CMS, IndexNow |
| `tools/covers/`, `tools/sanitize/` | Cover image generator; reference HTML sanitizer of the CMS |
| `docs/` | Design notes, artifact contract for research/visuals/comments, topic sheet, related-content policy |
| `tests/` | Offline tests; none of them calls an external service |

This flow reuses parts of the blog flow in `../blog`: the visual renderer and uploader, the Google
Docs exporter, the author ID mapping, the writer-style card and the credentials. Keep both folders
side by side.

## Set-up

```sh
pip install -r requirements.txt
npm ci --prefix tools/sanitize
npm ci --prefix tools/covers
```

- Credentials: copy `config/.env.example` to `config/.env` and add the OpenRouter key; Google and
  CMS credentials come from `../blog/config/`.
- Topic sheet: [docs/topic-sheet.md](docs/topic-sheet.md) and `config/topic-sheet-template.csv`.
- Review folder: put the shared-drive ID, folder ID and folder name into `config/google-drive.json`.
- IndexNow: put your key file URL into `config/indexnow.json`.

Checks: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests`.

## Commands

```sh
python3 scripts/glossary_job.py new --term "Example" --slug example --date YYYY-MM-DD --author john.roe
# by hand: add "temnik_cluster_id", "temnik_row" and the exact "primary_query" of the selected
# topic-sheet row to jobs/<job>/request.json (glossary_temnik.py finds the row by temnik_cluster_id)
python3 scripts/glossary_temnik.py start --job jobs/<job> --date YYYY-MM-DD            # preview; --apply writes
python3 scripts/glossary_job.py materials-check --job jobs/<job> --stage inputs
python3 scripts/glossary_writer.py write --job jobs/<job>                               # preview; --execute pays
python3 scripts/glossary_writer.py repair --job jobs/<job> --unit <id> --feedback "<exact defect>" --execute
python3 scripts/glossary_job.py assemble --job jobs/<job>
python3 scripts/glossary_job.py materials-check --job jobs/<job> --stage qa
python3 scripts/glossary_job.py package --job jobs/<job>
python3 scripts/gdoc_review.py --job jobs/<job> --round 1 --apply
python3 scripts/glossary_temnik.py review --job jobs/<job> --date YYYY-MM-DD --apply
node tools/covers/render-glossary-cover.mjs --term="Example" --out=jobs/<job>/out/cover.webp
python3 scripts/strapi_glossary.py dry-run --job jobs/<job>                             # then create-draft, attach-cover, publish, verify
python3 scripts/indexnow_glossary.py --job jobs/<job>                                   # preview; --apply sends
```

Every command that writes to an external system previews by default. CMS writes and publication
run only after an explicit request in the conversation.

## Writer: subscription or OpenRouter

New jobs record `writer_backend: openrouter`: a fast inexpensive model writes one heading unit per
request from the verified packet, and all research, evidence, editing and QA roles run as native
Codex agents on the subscription. `--writer-backend codex` at job creation keeps the writer
native as well, and then no OpenRouter key is needed. The route, the pinned provider and the
per-term budget are in `config/codex-model-routing.json`; paid responses and receipts are stored
under the job's `writer-api/`, so your actual charges can be read from there.

Model routes of the native roles: `config/codex-model-routing.json` routes `glossary-brief`,
`glossary-evidence`, `glossary-section-writer`, `glossary-editor` and `glossary-qa`. It has no
routes for `glossary-research`, `glossary-visual-planner` and `glossary-expert-comments`, so
those three run on whatever model the session gives them. Add explicit routes for them (strong for
research, mid for the visual plan and comments, `medium` effort, following the table in
[../docs/how-it-works.md](../docs/how-it-works.md#models-where-a-strong-one-is-needed)).

## Adapting

1. `knowledge/positioning.md` — rewrite every section for your product. The glossary card is short
   because glossary pages rarely mention the product: it holds only the rules a definition page
   can touch. For a fuller example of the same kind of card, with the level of detail a flow that
   describes the product often needs, see `../blog/knowledge/positioning.md`.
2. Replace `Example Co` with your brand and `example.com` / `cms.example.com` with your site and
   CMS API across the folder (`grep -rn "Example Co\|example.com"`).
3. `config/` — sheet and folder IDs, IndexNow key, search markets, `stop-brands.json`.
4. `scripts/strapi_glossary.py` targets a Strapi collection with the fields `term`, `slug`,
   `definition`, `contentHtml`, `metaTitle`, `metaDescription`, `author`, `editors`, a cover and two
   relation lists. For another CMS, replace this script and keep the package format in `out/`.
5. `tools/covers/assets/logo.svg` — your logo. The cover colours are read from the blog's
   palette, `../blog/config/site-brand-tokens.json` (`yellow.default` and `black`);
   `render-glossary-cover.mjs` falls back to its own values only when that file is missing.
6. Default author and editor usernames (`john.roe`, `jane.doe`) and their CMS IDs in
   `../blog/config/blog-authors.json`.
