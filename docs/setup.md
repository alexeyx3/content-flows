# Set-up

## Requirements

- Codex with subagents enabled. Open a session in the folder of the flow you want to run: Codex
  then loads that flow's `AGENTS.md`, `.codex/agents/` and `.agents/skills/`.
- Python. The flows are tested on Python 3.14 (`python3.14`). The optional semantics tool of the
  blog creates its own virtual environment with Python 3.12.
- Node.js for the reference HTML sanitizer, the chart and diagram renderer and the cover
  generator.
- Optional runtime capabilities, used when present and skipped otherwise:
  - a Semrush connection (MCP) in the Codex session: keyword ideas for the blog and the per-page
    semantics of the guides;
  - macOS: the blog's duplicate check adds embedding similarity through a local system model
    (`scripts/topic_overlap_embedding.swift`); elsewhere the check is lexical only and records
    that.

## Install

```sh
# blog
cd blog
pip install -r requirements.txt
npm ci --prefix tools/sanitize
npm ci --prefix tools/covers
sh tools/semantics/setup.sh          # optional: morphology checks for refreshes of published articles

# glossary (uses ../blog for rendering, review documents and credentials)
cd ../glossary
pip install -r requirements.txt
npm ci --prefix tools/sanitize
npm ci --prefix tools/covers

# country guides (self-contained: its copy of the blog scripts is under vendor/)
cd ../country-guides
pip install -r requirements.txt
npm ci --prefix vendor/blog/tools/sanitize
npm ci --prefix vendor/brand
```

## Keys

No key is stored in the repository. Each flow lists what it reads in an example file; copy it,
fill it in, and keep the real file out of git (the `.gitignore` files already exclude them).

| What | Where it goes | Needed for |
|---|---|---|
| SERP provider login | `blog/config/.env`, `country-guides/vendor/blog/config/.env` | Search analysis. The glossary reads the blog's file |
| Google service account (JSON key) | `blog/config/google-service-account.json`, `country-guides/vendor/blog/config/google-service-account.json` | Topic sheet, review documents, Drive uploads. Share the sheet and the review folder with the service account |
| CMS API token | `blog/config/strapi-api-token`, `country-guides/vendor/blog/config/strapi-api-token` | Drafts, media, publication. The country guides also read the CMS schema with it before a job can be created |
| OpenRouter key | `blog/config/openrouter.env`, `glossary/config/.env`, `country-guides/vendor/blog/config/.env` | Hybrid writer. Required in the country guides; in the blog and the glossary required by default, avoidable per job (see `docs/how-it-works.md`) |
| IndexNow key | A text file at your site root; its URL in `<flow>/config/indexnow.json` | Indexing ping after publication |

Each OpenRouter script takes only a key labelled for its own flow and refuses a generic one, so
that spend can be tracked per flow. Use a separate key per flow, each with its own limit.

## Check the installation

```sh
cd blog            && PYTHONDONTWRITEBYTECODE=1 python3.14 -m pytest -q -p no:cacheprovider
cd ../glossary      && PYTHONDONTWRITEBYTECODE=1 python3.14 -m pytest -q -p no:cacheprovider tests
cd ../country-guides && PYTHONDONTWRITEBYTECODE=1 python3.14 -m pytest -q -p no:cacheprovider tests
```

The tests run offline and need no keys. They cover the scripts and also the texts of roles and
rule cards: when you rewrite a card for your product, a test that asserted a phrase of the
fictional company will fail and show you which rule it was guarding.

Flow-specific checks:

- `blog`: `python3.14 scripts/validate_codex_setup.py` — agent profiles, skills and search markets.
- `country-guides`: `python3.14 scripts/preflight.py` — configuration and keys before a run.

## First run

1. Fill in the product rules: [adapting.md](adapting.md), sections 1–4.
2. Create the topic sheet from the flow's `config/topic-sheet-template.csv` (blog, glossary) or
   edit `country-guides/config/queue.json`.
3. Open Codex in the flow's folder and ask for one article, term or country. The orchestrator
   follows the skill, reports each stage, and stops at the review document.
4. Read the review document. Publish only by asking for it explicitly.
