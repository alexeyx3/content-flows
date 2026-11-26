> Design document. The run instructions are `AGENTS.md` and `.agents/skills/country-guide/SKILL.md` in the project root, and the binding rules are in `knowledge/guides-rules.md`. The skill and the rules are authoritative; this document explains them.

# Country guides: the content production flow

The main route: the draft is written by `gpt-6.1-terra` / medium through OpenRouter with the
OpenAI provider pinned. Editing, the separate style pass and independent QA run on
`gpt-6.2-sol` / medium in Codex. One section per request, the full packet, an explicit cache and
state deltas are kept. Actual charges are taken from the OpenRouter receipts. Commands and
recovery are in `docs/api-execution.md`, the profile is in `config/guide-execution.json`, the
model of every role in `config/codex-model-routing.json`.

The page template, the Strapi fields and the formatting rules are in
`country-guides-spec.md` and `country-guides-editor-guide.md`; the topic sheet and the queue are
described in `topic-sheet.md`; this document covers only how the pages are produced.

## Design decisions

| # | decision |
|---|---|
| 1 | The flow is a skill `country-guide`, its own agents `guide-*`, the project `.`. The blog's scripts (SERP, visual rendering, sanitizer, Google Docs) are reused from `vendor/blog/scripts`, not rewritten |
| 2 | The order of countries is the queue in `config/queue.json`, built by hand from the topic sheet (`docs/topic-sheet.md`): countries sorted by search demand for the query «employer of record <country>» in the US, plus the countries the publisher's audience hires in |
| 3 | SERP: every job collects four markets — US, GB, AU and the country itself (`new_guide_job.py` fixes the set). After the first three countries of a new setup we measure what GB and AU add beyond US and the country, and the set of markets is decided by that measurement; US and the country itself are always collected |
| 4 | Research has three lines beyond the fact pack and the SERP: `changes` (dated changes), `practitioners` (verbatim voices and real pains), `angle` (an internal audit of the top's figures, the country's unique blocks, proposed calculations). Primary sources are covered by the fact pack (`guide-facts`), own calculations by `calc.py` |
| 5 | The brief is a hybrid: the standard set + every useful unique block of the top + nodes nobody has. Larger than any page in the search results |
| 6 | Visuals: at least 2–3 per page where verified data exists for them. A visual may duplicate a table (minimum wage by year: a table and a chart). The table always stays |
| 7 | Overlaps between the three pages of a country and with neighbouring countries are acceptable. Only large verbatim repeats are caught |
| 8 | Structure: a mandatory core in a fixed order + additional sections, including new H2s, by the SERP and the research |
| 9 | The vendor ranking on the contractors page stays, Example Co first. **Equal terms**: whatever aspect the ranking describes for Example Co is filled for every vendor from its own pages or marked «not published»; no column or note exists only for Example Co. How money reaches a contractor is written on the page as a country reference, never as an Example Co service |
| 10 | The ranking is broader than anyone's in the search results: look at the rankings in the top and make more than a standard top-10 |
| 11 | The publisher reviews the pages before publication: local previews or Google Docs, and the rendered pages on the test site (a staging copy of the site that renders CMS records, so a page can be seen in its final layout before it is public) |

## The order of countries

Choose the next countries from the queue in `config/queue.json`. Every entry carries the order,
the slug, the ISO code, the country name, the EOR head query and its US cluster volume, the geo
key for the SERP, the name used in the SERP queries, the status and two flags (`icp`, `pilot`);
`docs/topic-sheet.md` describes every field and where it comes from.

Before a country is chosen, `scripts/check_cms_country.py --slug <slug>` reads the live CMS
schema and confirms that the country's ISO code is in the CMS enumeration and that the fields the
exporter writes are compatible. An unsupported code or an unavailable check means choosing another
country; the CMS and the site are not changed and no other code is substituted.

Before a country is queued, check its name for a homonym in search: «Georgia» returns the US
state, so keyword volumes from general exports cannot be used for the country, and the page
itself would compete with the intent about the state.

For the first run of a new setup, take three countries that test the template from different
ends: one with the densest facts and the heaviest SERP, one with a thin SERP, and one with an
unusual regime (free zones, a zero income tax) that shows whether the template bends. Mark them
with `pilot: true` in the queue.

## The unit of work

**One country — one job — three pages.** `jobs/<date>-<slug>/`. A country is done
as a whole, because the subpages rely on the root's fact pack, and a mismatch of figures between
the three pages is the main risk of the section.

## Stages

The overview below groups the skill's stages (numbers in brackets are the stage numbers of the
table in `.agents/skills/country-guide/SKILL.md`). The SERP capture is slow and runs as a
background session, so in practice it runs alongside the fact pack.

```
0. job and queue                 ← CMS compatibility check, job folder, queue status [0]
1. country fact pack             ← the only source of numbers for the three pages [2–3]
2. SERP: 3 clusters × markets    ← structure of the top, PAA, AI Overview, rankings in the top; semantics [1, 1b]
3. research: 3 lines             ← changes and practitioners after the fact pack, angle after the SERP; calculations [4, 4b]
4. brief ×3 + sections.json ×3   ← the hybrid, an assignment for every H2 [5]
5. evidence                      ← everything that goes into the text, visuals and quotes [6]
6. ranking (contractors only) + page inputs + visual plan [6–8]
7. visual rendering and independent visual QA [9–10]
8. writer by H2 ×3 → editor → checks → images → editorial pass → style pass [11–15a]
9. QA, packaging and the seal [16–17]
10. review previews / Google Docs → the publisher's edits → approval [18–19]
11. Strapi: dry run → write → read-back [20]
```

### 0. The job

`check_cms_country.py --slug <slug>` first (see «The order of countries»). Then
`new_guide_job.py --slug <slug> [--date YYYY-MM-DD]` repeats the live CMS check before touching
any folder or the queue, saves the sanitized result as `raw/cms-compatibility.json`, and creates
`job.json` with the country, slug, ISO code, `eor_query`, the SERP markets (`geos`), the author
(`john.roe`) and the editor (`jane.doe`), the creation date, `query_name`, the queue order and the
two queue flags (`icp`, `pilot`). It creates the three page folders with their `job.yaml`, copies
optional hint files (see below) into `raw/` and sets the queue status to `in_progress`.
`fetch_links.py` rebuilds `config/site-links.json` if it is older than a week.

### 1. The country fact pack — `facts.json`

Data first, text second: it is the only way to keep one figure in one place on three pages.

- **Two agents `guide-facts` in parallel**, scope `employment` and scope `contractors`, each
  writing its own part (`facts.employment.json`, IDs F-001…F-499; `facts.contractors.json`, IDs
  F-500…F-999). `check_facts.py --merge` merges them into `facts.json` and validates it; the
  orchestrator sends failures back to the agent until PASS. `calc.py` then writes `derived.json`
  (C- rows). The schema and the split of topics between the scopes are in
  `knowledge/facts-schema.md`.
- **Research memory.** If the project keeps an optional research memory (earlier verified facts
  for the country, copied by the job script into `<job>/raw/hint-facts.yaml`), it is an input
  as a **hint**, not as a source: the agent reopens every figure at the primary source.
- **Contents:** the eight header figures + all the fact tables of the root (minimum wage with
  5–10 years of history, contributions line by line as numbers with their caps, tax, working
  time, leave, termination by tenure, holidays, the 13th salary, visas) + the contractor status
  thresholds + the invoice requirements + the EOR specifics (legality of the model, licence and
  registry, maximum duration).
- **Every fact has:** `claim`, `source` (publisher, the document's actual title, the URL of the
  page with the figure, tier), `accessed`, the exact supporting `quote` taken from the raw page
  text, and optionally `value`, `unit`, `effective`, `note`. If a figure cannot be confirmed, it
  goes to `unconfirmed` with the reason and is never written.
- **Source priority:** the law and the authority → the central bank and statistics → Big Four
  and law firms → vendors only about themselves. Third-party rankings and fact aggregators are
  not a source.
- **Checked by a script:** the eight header fields are present and the seven strings fit into
  32 characters, `employerContributions` = the sum of the employer contributions marked
  `in_header` in the line-by-line table (or the evidenced fixed-levy model), every fact has a
  URL, a date and a quote, every referenced ID exists.

Prose from the research memory is never taken: hint files are leads, and their wording is not
copied.

### 2. SERP

`serp.py --job <job>` runs the blog's `fetch_google_serp.py` (XMLRiver) and
`build_article_serp_brief.py` for three clusters, 10 queries in total:

| page | queries (`<c>` is the queue's `query_name`) |
|---|---|
| country | `hiring in <c>`, `<c> minimum wage`, `average salary in <c>`, `<c> labor law` |
| EOR | the queue's `eor_query`, `best employer of record <c>`, `employer of record in <c>` (when it differs from `eor_query`) |
| contractors | `hire contractors in <c>`, `independent contractor <c>`, `how to pay contractors in <c>` |

Markets — the job's `geos`: US, GB, AU and the country's `geo_key`; country and domain IDs are in
`config/geos.json`. Top-10 organic, PAA, AI Overview. Empty query×market pairs are retried once;
`serp.py --refill` repeats that if `serp/geo-overlap.md` still shows an empty market.
`build_article_serp_brief.py` extracts the structures of the pages; the **vendor rankings in the
top** are written out separately to `serp/rankings.md`: who, how many positions, by which
criteria.

**Semantics (stage 1b, optional).** If a keyword tool is connected, the orchestrator collects
related and phrase-match keywords for the country page and the contractors page (US database plus
the country's own, if it exists) into `semantics/<page>.csv`. EOR semantics come from the topic
sheet tab «Semantics by page» (row ID `eor-<iso>`), if the sheet is available in the session. A
missing tool or sheet is recorded in `progress.md`; volumes are never invented.

**The measurement for the decision on markets** — after the first three countries: the share
of top-10 URLs from the additional markets that are absent from US and the country's own
results (`serp/geo-overlap.md` totals), and how many unique useful blocks they brought into the
hybrid. The result and the lessons are written into this document and the rules.

### 3. Research — three lines

`guide-research` runs one line per agent. `changes` and `practitioners` start right after the
fact pack, because they do not need the SERP; `angle` starts once the SERP is complete. Each
line writes `research/<line>.md` with the reader questions it addresses (`Q-xx`), numbered
findings (`R-C-xx`, `R-P-xx`, `R-A-xx`) with the exact supporting passage, URL, tier, date,
jurisdiction and the page and section each serves, and its gaps.

| line | what it looks for | output |
|---|---|---|
| changes | what changed recently and what is announced ahead, each with its effective date; anything effective within the next six months is flagged | the «Recent changes» section, an advisory note when a change is near |
| practitioners | verbatim quotes (at most 25 words) from local law firms, tax advisers, chambers of commerce, associations and officials, with name, role, organisation, date, URL and location in the source; pains from Reddit and forums as findings, not quotes | quote candidates and findings |
| angle | (1) the figures of 6–10 top results compared with `facts.json` in a section «Top audit (internal)»; (2) the country's unique blocks; (3) proposed interpretations and calculations by F- IDs; (4) visual candidates per page | an **internal** list of discrepancies, so that we do not make the mistake ourselves — publicly we do not name competitors, for an owned site that is close to disparagement; unique blocks; calculation proposals |

The angle line looks for the country's **unique blocks** — something neighbouring countries do
not have (a special regime, a threshold, a registry, a recent law). Every page carries at least
one (guides-rules 3.3), and the brief names it.

**Calculations (stage 4b).** The orchestrator reads the angle line's proposals, writes
`calc_spec.json` (extra salary scenarios, variables with F- IDs, formulas) and reruns
`calc.py`. It checks every formula by hand — caps, floors, which share applies — because the
script removes arithmetic slips, not modelling mistakes. The agents never calculate.

### 4. The brief — one per page

The agent `guide-brief`: the country page first, then the EOR and contractors pages in parallel
(the subpages read the country page's brief). Input — the fact pack, the calculations, the
SERP, the semantics if present, the research, the rules of the section.

- **The hybrid:** the mandatory core (guides-rules 3.1) + every useful unique block of the
  top across all markets + nodes nobody has. New H2s are allowed. A skipped top block needs a
  written reason.
- **`sections.json`:** for every H2 — the reader's question, what to explain (a mechanism, a
  difference, an example or a decision), which facts (`F-`), calculations (`C-`) and findings
  (`R-`) to use, the table format, the visual marker, the quote and the links. Plus
  `information_gain` tied to sections, `visual_candidates`, and `expert_questions` (empty).
  `out/meta.md` holds the H1, slug, metaTitle and metaDescription.
- **The subpage rule:** they take figures only from `facts.json` and `derived.json` and do not
  introduce their own.
- **Blocking:** no information gain beyond the top, or a core section the fact pack cannot
  support.

On a new setup the publisher may look at the briefs of the first countries before writing; the
skill has no mandatory pause, so agree on it in the conversation if you want one.

### 5. Evidence

`guide-evidence`: every research finding, quote and statement outside the fact pack that goes
into the text, a visual or a quote becomes an E- row in `evidence.md` — a verified link with the
exact supporting passage and the verdict «supports / partial / no», followed by a mapping R- → E-
and the bibliography metadata of every source. The facts of the pack are not re-verified; only
what the research added is checked.

### 6. The ranking, page inputs, visuals, quotes

**The ranking is on the contractors page only** (`guide-company-cards`, in parallel with
evidence). It writes `company_cards.md` in the contractors page folder and V- rows in
`evidence.vendors.md`.

- Broader than any ranking in this country's search results (`serp/rankings.md`); never a padded
  standard top-10.
- Example Co first, in the countries where it is available (the topic sheet's column
  «Example Co in country»; only such countries enter the queue).
- **Equal terms.** Whatever aspect is described for Example Co — who uses it, agreements and
  e-signature, invoice approval, exports, the published price — is filled for every vendor from
  its own pages or marked «not published». The seven columns are about what changes by
  country: Vendor, Model (contractor management software, agent of record, EOR, marketplace,
  invoicing tool), Presence in the country, Contracts under local law, IP assignment, Local
  documents, Classification support.
- A column that everyone has except us, or that only we have, would look odd: that is why the
  price and any other aspect follow the equal-terms rule, and the Example Co price is quoted
  only verbatim from its pricing page.
- A note about a vendor must be country-specific: if it can be moved to another country without
  editing, it is not good enough. The source of vendor facts is the vendor's own site, with a date.
- Liability wording: never state as fact that a vendor or an arrangement «takes on liability»
  or «guarantees» an outcome; say who the contracting party is, and that liability is
  determined by the clause of the contract.
- If the project keeps its own vendor cards under `companies/`, the notes do not copy their
  sentences.
- There is no ranking on the EOR page: Example Co is not an employer of record, and its own
  ranking of EOR providers without an EOR product would not be honest.

**Page inputs (stage 7).** If evidence added figures needed by the calculations (E- IDs), the
orchestrator extends `calc_spec.json` and reruns `calc.py`. Then `prepare_pages.py` lays the
inputs out per page: `evidence.md` with F-, C-, E- and V- rows, `research.md`, and an empty
`expert_quotes.json`.

**Visuals** (`guide-visual-planner`, `visuals.json` per page) — at least 2–3 per page where data
exists, no ceiling. The table always stays next to it. The renderer types are bar, line, process
and decision; the catalogue is in guides-rules section 7:

| page | candidates |
|---|---|
| country | minimum wage by year (line); employer cost at 2–3 salary levels (bar); notice period by tenure (bar); employer registration timeline (process); salaries by role (bar) |
| EOR | client–EOR–employee contracts (process); EOR hiring steps with timings (process); EOR cost vs own entity (bar); «do you need an EOR here» (decision) |
| contractors | classification test (decision); status thresholds (bar or process); from contract to paid invoice (process); who pays for a mistake (bar) |

Rendering — the blog's `render_visuals.py` and `visual_renderer.mjs`: brand colours, the brand
font and the logo from `vendor/brand/`, PNG. A chart type outside these four means extending the
renderer first.

**Quotes** — only verbatim external ones, with a verified original, a name, a role and a date,
carried as E- rows. `expert_quotes.json` stays empty by design. Comments on behalf of our own
staff — no, unless the publisher decides otherwise.

### 7. Rendering and the visual check

Before the writer, per page: `workflow_gate.py check --target inputs --offline` and
`render_visuals.py`. Then `guide-visual-qa` opens every PNG at full size and at 390 px and
writes `visual_qa.json` per page; it runs in parallel with writing.

### 8. The writer and the editor

- **Writer:** `guide_api.py --stage writer` on OpenRouter, one H2 (with its H3/H4) per request;
  the opening is its own request. The country page goes first; the subpages receive its text,
  and the type and hash of that context are recorded before the first subpage request. A
  subpage may cover the same topic as the root, but writes the section from scratch in its own
  words and for its own model — it does not copy. There are few such overlaps: the repeat
  scanner checks them.
- Numbers — only from `facts.json`, `derived.json` and the evidence. The visual marker
  `[[VISUAL:id]]` in its place.
- **Editor:** `guide-editor`, one per page — density, one voice, AI patterns (`humanizer`); the
  structure does not change. Then `check_guide.py` and `lint_article.py --walls`; confirmed fixes
  go through the same editor.
- **Images:** for local review the verified local images are bound; for Google Docs and for
  publication the images are uploaded to the CMS media library first (see stage 10), then bound
  with `package_article.py --bind-visuals`.
- **Editorial pass:** the orchestrator reads the three pages for positioning, repeats and
  whether each page beats the top, and notes the result in `progress.md`.
- **Style pass:** the same editor reads the whole page after the images are bound and saves
  `humanization_report.md` with the SHA-256 of the reviewed `edited.md`.

### 9. QA

`guide-qa`, one per page and in parallel, with the current `check_guide.py` output and the
style report:

- **Header = body:** the eight field figures match the root's tables and the routes table.
- **Facts:** every number in the text is in `facts.json`, `derived.json` or the evidence; the
  6–8 highest-risk figures are re-checked live; sources — as the «Sources» section, last, a link
  to the page with the figure, the access date.
- **Owned positioning:** the section is a reference, so the country's vocabulary («employee»,
  «payroll») is acceptable as a description of the country, but not as «Example Co does this».
  On the EOR page — no «we do this» and no Example Co plans. The ranking — on equal terms.
- **Repeats:** `check_guide.py` compares the three pages of the country, all finished countries
  and the project's vendor cards (n-gram matches, Sources excluded); the threshold catches only
  large verbatim pieces, and QA judges every warning.
- **Sanitizer:** the body passes `vendor/blog/tools/sanitize/check.js`, a copy of the CMS
  sanitizer, without losses.
- **Visuals:** inserted, alt and captions in place, the data matches the evidence, the actual
  images inspected.

Rework goes to the same editor, then the affected style pass, then the same QA — up to three
loops. A PASS freezes the text: `package_article.py` and `workflow_gate.py seal-qa` per page
write `qa_receipt.json`; any later change means repackaging, the affected QA and a new seal.

### 10. Review and Google Docs

Local review previews are delivered first. When Google Docs are requested, `gdoc_review.py push`
creates one document per page on the shared review drive, with the real pictures; the document
folder carries the page folder's name (`guide-<slug>`, `guide-<slug>-eor`,
`guide-<slug>-contractors`). The publisher's edits come back with `gdoc_review.py pull` → fixes
→ repeat QA of what was affected. After the publisher's explicit approval,
`workflow_gate.py approve-review --by --reference` records it in `review_approval.json`; the flow
never generates an approval.

### 11. Strapi

`strapi_guides.py`, modelled on the blog's `strapi_publish.py`:

- previews by default; `--write` creates or updates the records, `--draft` writes drafts,
  `--indexable` sets `indexable: true` — a normal authorized publication uses
  `--write --indexable`, and a write without it is a noindex preview;
- runs the blog's export gate on each page first: QA receipt, review approval, uploaded images;
- finds the country record by its slug (or by the IDs saved in `out/strapi_record.json`) and a
  subpage by `country` + `kind` — updates instead of creating duplicates;
- writes the header fields from `facts.json` (seven strings and `employerContributions` as a
  number), `contentHtml`, the metadata, the author and the editor;
- pictures go into the production media library, on explicit permission;
- reads the record back through the public endpoints and compares the body after the
  sanitizer.

The schema the CMS must have is in `country-guides-spec.md`, «The specification of the types in
Strapi».

## Page structure

The core comes from `country-guides-editor-guide.md`; the binding order is guides-rules 3.1.
Additions follow the SERP and the research, including new H2s, in the places the brief sets. The
mandatory elements of the core:

- **country:** the direct answer; Three ways to hire; the labour market with salaries; employer
  registration; hiring and onboarding; minimum wage; taxes and contributions with the cost of an
  employee; working time; leave; termination; Recent changes; What a mistake costs; FAQ; Sources;
- **EOR:** the direct answer; what an EOR is (one sentence + the glossary); legality under
  local law; the licence and the registry; who signs what; hiring step by step with timings;
  the cost; where the model runs out; when an EOR is not needed; alternatives; how to choose a
  provider; FAQ; Sources;
- **contractors:** the direct answer; where the line runs; the status thresholds; the forms of
  registration; the contract; what a contractor produces to get paid; how the money arrives (as
  a reference, without Example Co); terms and late payment; what breaks; who pays for a mistake;
  models; one versus ten; the ranking; FAQ; Sources.

The editor guide lists no «Sources» section for the subpages — the flow adds it: every page has
its own list.

## What is built

| what | where |
|---|---|
| the skill `country-guide` | `agents-src/skills/country-guide/` → `.agents/skills/country-guide/` (copied by `scripts/sync_agents.py`) |
| the agents `guide-facts`, `guide-research`, `guide-brief`, `guide-evidence`, `guide-company-cards`, `guide-visual-planner`, `guide-visual-qa`, `guide-section-writer`, `guide-editor`, `guide-qa` | `agents-src/agents/` → role profiles in `.codex/agents/` (generated by `scripts/sync_agents.py` with the routes) |
| the rules of the section for the agents | `knowledge/guides-rules.md`: template, positioning, sources, ranking; `knowledge/facts-schema.md`; `knowledge/product-positioning.md` |
| scripts | `check_cms_country.py`, `new_guide_job.py`, `fetch_links.py`, `serp.py`, `check_facts.py`, `calc.py`, `prepare_pages.py`, `guide_api.py`, `check_guide.py` (header = body, sources, sanitizer, repeats across pages and countries), `order_sources.py`, `strapi_guides.py`, `verify_model_route.py`, `preflight.py` |
| from the blog, by path | `vendor/blog/scripts/` (`fetch_google_serp.py`, `build_article_serp_brief.py`, `render_visuals.py`, `visual_renderer.mjs`, `workflow_gate.py`, `package_article.py`, `upload_visuals.py`, `gdoc_review.py`, `lint_article.py`), `vendor/blog/tools/sanitize/check.js` |
| the queue | `config/queue.json` in the project; statuses `planned → in_progress → review → published` |

The readiness check of the flow on a new setup is a run on three countries: nine pages have
passed QA, are in Google Docs and are loaded to the test site; the measurement by market is
done; the lessons are written into the rules.

## Open

1. Whether countries go live one by one or as a batch is a release decision outside this
   flow; the indexing flag (`indexable`) in Strapi is set by this flow.

## How it is built

The project `.`, the skill `country-guide`, ten roles `guide-*`
(facts, research, brief, evidence, ranking, visual plan, writer, editor, visual check,
QA). Implementation notes behind the description above:

- **The fact pack is JSON** (`facts.json`): PyYAML is not among the flow's dependencies
  (`requirements.txt`), and the blog manages without it too. The two parts (`facts.employment.json`,
  `facts.contractors.json`) are merged by `check_facts.py`. Optional hint files in `raw/` stay
  YAML, because they are read by agents, not by scripts.
- **Every page is a folder in the blog's v2 job format** (`pages/guide-<slug>`,
  `guide-<slug>-eor`, `guide-<slug>-contractors`). That is why rendering, picture upload,
  packaging, the QA gate and Google Docs are taken from `vendor/blog/scripts` without changes.
  The folder name is also the name of the document folder on the shared review drive.
- **Practitioners' quotes go through the evidence** (E- rows), not through `expert_quotes.json`:
  the blog's validator lets only the article's author and editor into the quote manifest.
- **Calculations are done by a script**, `calc.py` (the cost of an employee with contribution
  caps and floors); the agents do not calculate them.
- **Repeats** are caught by `check_guide.py` using the functions of the blog's `text_overlap.py`:
  a match of 20 words or more is a warning for QA, of 45 or more a block. The three pages of the
  country, all finished countries and the project's vendor cards are compared; the Sources
  section is excluded.
- **Pictures in Google Docs require an upload to the Strapi media library**: the blog's export
  gate lets only uploaded images into Docs. The upload is a write to production Strapi and needs
  permission.
- **Roles are launched with an explicit model and the path to the role file**: the prompt names
  the absolute role file, so a general-purpose agent can run any role; agent types added to
  `.codex/agents/` are picked up only in a new session.
- **Semantics**: EOR — from the tab «Semantics by page» of the topic sheet; the root and the
  contractors page — from a keyword tool (US). Keyword data shows demand for news about a
  country's labour law (for example «germany labor law news») — hence the block of recent
  changes; on the contractors page there is demand from freelancers themselves (visa, taxes,
  registration).
