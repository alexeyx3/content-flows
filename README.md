# Content flows for Codex

Three working flows that produce long-form site content with an orchestrator and specialist
agents in Codex: blog articles, country guides and glossary terms. Each flow goes from a topic
queue to a published page: search analysis, research, verified sources, section-by-section
writing, editing, independent QA, a review document for a human, and on request a CMS draft,
publication and an indexing ping.

The flows were extracted from a production setup and anonymised. **Example Co, its product, its
rules, its vendors and its people are fictional.** They are there so that every rule file shows
how detailed it has to be. Replace them with your own before the first run.

## What is inside

| Folder | Produces | Roles | Start here |
|---|---|---|---|
| [`blog/`](blog/) | Blog articles: guides, comparisons, rankings, refreshes of published pages, translations | 18 | [`blog/README.md`](blog/README.md) |
| [`country-guides/`](country-guides/) | Three pages per country: hiring overview, employer of record, independent contractors | 10 | [`country-guides/README.md`](country-guides/README.md) |
| [`glossary/`](glossary/) | One glossary term per job | 8 | [`glossary/README.md`](glossary/README.md) |
| [`docs/`](docs/) | How the flows work, set-up, adapting to your product | — | [`docs/how-it-works.md`](docs/how-it-works.md) |

Every flow has the same layout:

| Path | What it holds |
|---|---|
| `AGENTS.md` | Standing instructions to the orchestrator |
| `.agents/skills/` | The flow's skill (stages and gates) and a humanizer skill; the blog and the guides also carry a copywriter skill |
| `agents-src/agents/` | One role specification per specialist |
| `.codex/` | Thread limits; agent profiles in the blog and the guides (the glossary passes role files directly) |
| `config/` | Model routing, search markets, topic queue, review folder, CMS and indexing settings |
| `knowledge/` | Rule cards the roles read: product positioning, structure, style, legal, SEO |
| `scripts/`, `tools/` | Job lifecycle, SERP capture, linters, renderers, packaging, review documents, CMS, indexing |
| `tests/` | Offline tests of scripts, rule texts and role texts |
| `docs/` | Flow description and design notes: each rule with the reason behind it |

`glossary/` reuses the visual renderer, Google Docs exporter and credentials of `blog/`; keep the
folders side by side. `country-guides/` carries its own copy of the blog scripts it needs under
`vendor/`.

## Reading order

1. [`docs/how-it-works.md`](docs/how-it-works.md) — the design shared by all three flows:
   orchestrator and specialists, file contracts, where a strong model is needed, subscription and
   OpenRouter writers, human checkpoints, publication.
2. One flow's `README.md`, then its skill in `.agents/skills/` and a few role files.
3. [`docs/adapting.md`](docs/adapting.md) — what to fill in for your product.
4. [`docs/setup.md`](docs/setup.md) — dependencies, keys, checks.

## What you need

- Codex with subagents enabled. Role files are plain Markdown and can be ported to another agent
  runtime; the profiles in `.codex/` are Codex-specific.
- Python (tested on 3.14) and Node.js.
- A SERP API key (the scripts use XMLRiver), a Google service account for Sheets, Docs and Drive,
  and a CMS API token (the publishing scripts target Strapi).
- An OpenRouter key for the hybrid writer. The blog and the glossary create jobs as hybrid by
  default and can be switched per job to run every role on the Codex subscription; the country
  guides need the key.

Nothing in this repository calls an external service until you add your own keys, and every
script that writes to an external system previews by default.
