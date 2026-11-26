---
name: blog-article-agents
description: Same Example Co blog pipeline, but brief, draft and edit run as native subagents instead of the OpenRouter scripts. Use when OpenRouter is unavailable or when the whole article must be produced without API calls.
---

> Archived: an older all-agent variant of the script track, kept for reference; the active skill is `.agents/skills/blog-article/SKILL.md`.


# Example Co blog article pipeline — all-agent track (orchestrator)

Same pipeline as `blog-article`, same repo, same job folders, same knowledge and the same vendor
database. One difference: the three stages that the other track pays OpenRouter for — brief, draft,
edit — here run as subagents. Everything else is identical, and both tracks share
`knowledge/`, `companies/`, `config/` and every script, so a rule fixed in one is fixed in both.

Use this track when OpenRouter is unavailable, or when an article must be produced entirely by
native subagents. Both tracks may run on different articles at the same time.

| Stage | script track (`blog-article`) | this track |
|---|---|---|
| SERP | scripts | same scripts |
| Brief | `scripts/generate_brief.py` | **`blog-strategy-brief` subagent** |
| Evidence | `blog-evidence` | same |
| Cards | `blog-company-cards` | same |
| Draft | `scripts/generate_draft.py` | **`blog-section-writer` subagent, one persistent thread and one complete H2 subtree per turn** |
| Edit | `scripts/edit_draft.py` | **`blog-editor` subagent** |
| QA | `blog-qa-factcheck` | same |
| Lint, packaging, Strapi, covers | scripts | same scripts |

## Cost discipline
- The three replaced stages cost subagent tokens instead of dollars. A subagent reads the knowledge
  base itself, so a batch is far from free: group the outline into 3-4 drafting calls, not ten.
- NEVER Read large artifacts into your own context: `out/draft.md`, `edited.md`, `evidence.md`,
  `company_cards.md`, `serp.*` belong to the subagents. You read job.yaml, subagent final messages,
  script stdout, `qa_report.md`, `editor_issues.md` and the lint output.
- After QA PASS the text is FROZEN. Packaging is mechanical only.

## 0. Inputs
Ask for or read: topic, language, article_type, geo (SERP geography only — facts always follow ICP jurisdictions), semantics, `author` (`john.roe` | `jane.doe` | `ann.poe`, a username with a CMS user ID in `config/blog-authors.json`), and `own_product_rank` (`first` | `top-3` | `neutral`). For every ranking/listicle, also require publisher-approved `own_product_placement` (`ranked` | `separate` | `omit`); rank applies only to `ranked`, and the job template's default `own_product_rank: first` is not that approval. Also read optional `author_angle`, `key_points`, `my_experience`. There is no length ceiling and no mode to choose: the blog is always the company's own voice.
Create the job: `python3 scripts/new_job.py "<topic>" <today-date> blog` (prints the job path). Fill `<job>/job.yaml`. Put semantics in `<job>/semantics.csv`.
Before the brief, refresh the site map so internal links point at pages that exist: `python3 scripts/fetch_site_urls.py --date <today>`.

## Parallel sessions (several articles at once)
- Work ONLY inside the job folder new_job.py printed for THIS session. Never write into, "fix", or reuse another job folder.
- Shared files (`companies/*.mdx`, `config/`) may be touched by sibling sessions concurrently. That is expected — last write wins and both are fresh; do NOT stop to ask the user to arbitrate.

## Adjacent articles in the same cluster — reuse the research, not the prose
Before step 1, look for earlier jobs on an adjacent topic: `ls jobs/ | grep <topic-slug>`. If one exists with the same primary query + geo:
- SERP: copy its `raw/serp.csv`, `raw/features.json` AND all `serp.*` artifacts into this job; SKIP step 1 (0 API calls, the brief-builder output is deterministic).
- Evidence: pass its `evidence.md` path to `blog-evidence` as `sibling_evidence` — it reuses verified rows and skips known dead ends.
- Brief: pass its outline to `blog-strategy-brief` as `sibling_briefs`. The new article MUST carry 2-3 sections the neighbour does not have — two near-identical outlines on one blog compete with each other in search and in AI answers.
Never reuse a neighbour's draft or edited text: the prose is written fresh every time.

## The track
The blog is always the company's own voice: brand voice from copywriter, strict legal with the info-section exception, schema for AI Overviews, and the binding rules in knowledge/blog-owned.md (banned vendors, the brand stop-list in `config/stop-brands.json`, internal links, the Strapi markup contract).

## 1. SERP (Bash)
```
python scripts/fetch_google_serp.py --query "<primary query>" --geo <geo> --top-n 20 --serp-features --output-file <job>/raw/serp.csv --features-output-file <job>/raw/features.json
python scripts/build_article_serp_brief.py --input-file <job>/raw/serp.csv --features-file <job>/raw/features.json --output-prefix <job>/serp
```
GUARD: after the fetch, confirm `<job>/raw/serp.csv` has more than 1 line (i.e. organic rows beyond the header). The XMLRiver API occasionally returns an empty result on the first call — if empty, re-run the fetch once before proceeding. This yields `<job>/serp.serp_synthesis.md`, `.competitor_structures.csv`, `.competitor_cards.json`, `.serp_features.json`.

## 2. Brief (subagent)
Dispatch `blog-strategy-brief` with: topic, `job.yaml` (all binding fields including `own_product_placement` and, when applicable, `own_product_rank`),
`<job>/serp.serp_synthesis.md`, `semantics.csv`, and the paths of any `sibling_briefs`. Tell it to
read `knowledge/` itself — the brief must reflect the current knowledge base, not a digest.
Outputs: `<job>/brief.md` and `<job>/sections.json`.
GUARD before step 3: `sections.json` parses, has a non-empty ordered section list, ids are
latin-kebab, every section has id/title, approved H3-H4 entries are preserved in `subheadings`, and
the list matches the brief's full hybrid outline. There is no numerical section limit and no
detailed writer micro-brief requirement. Vendor-card form follows the researched content; no fixed
row count, paragraph count, or universal template limits useful substance.

## 2.5 Evidence
Dispatch `blog-evidence` -> `<job>/evidence.md`. The drafting script loads this file as the model's ONLY source of facts, so a gap here becomes a gap (or a hallucination) in the draft. Evidence reads the local company DB at `companies/` (repo root) FIRST; web only for gaps/stale — and writes verified findings BACK into `companies/` so future articles reuse them.

## 2.6 Company cards (only if article_type in {comparison, listicle})
Dispatch `blog-company-cards` -> `<job>/company_cards.md` STRICTLY AFTER 2.5 completes — NOT in parallel: cards consumes evidence.md plus the DB cards evidence just wrote back; running them in parallel duplicates web research and wastes tokens. Pass the approved `own_product_placement` and `own_product_rank` only when placement is `ranked`. The drafting script picks the file up automatically if it exists.

## 3. Draft (one persistent subagent, one complete H2 per turn)
Start `blog-section-writer` once. Load `scripts/writer_dispatch.py --job <job>` once; each assignment
is a complete H2 including every approved H3/H4 below it. Save the whole subtree to
`<job>/sections/section_<N>.md`. Continue the same thread with the next H2 promptly on completion;
`running_state.md` is for interruption recovery, not ordinary follow-ups.
For v2, follow the active `.agents/skills/blog-article/SKILL.md` preflight: render and check layout
before writing, then run independent visual QA alongside the writer. Join passed branches before
upload/package QA.
Then assemble:
```
python3 scripts/writer_dispatch.py --job jobs/<job-dir> --check
python3 scripts/assemble_sections.py --job jobs/<job-dir>
```
It orders sections by `sections.json` (not by filename), adds the H1 from the brief and writes
`<job>/out/draft.md`. It fails loudly on a missing section instead of silently shipping a hole.
GUARD: if a section is technically missing or truncated, continue the same thread for that section with the specific
defect named. Never patch the prose yourself — the orchestrator does not write article text.

## 4. Edit (subagent)
Dispatch `blog-editor` -> `<job>/edited.md` + `<job>/editor_issues.md`. It de-duplicates across
sections, enforces one voice, adds the H1 if missing and applies the house rules. In rework rounds
pass the QA report path in the same way the script track passes `--qa-report`.

## 5. QA + rework loop (<=3, incremental — saves tokens)
Run `python3 scripts/wordcount.py --job jobs/<job-dir>` first and quote the number from
`<job>/wordcount.txt` in the dispatch — QA has no shell, and the edit script's own word count
runs several hundred words higher (it counts tables and links, wordcount.py counts what a human reads).
Gate 7's contrast cap scales with length, so the wrong figure moves the cap.
Dispatch `blog-qa-factcheck` -> `<job>/qa_report.md`.
- If overall BLOCK: re-dispatch `blog-editor` with the QA report path plus your own findings, and name explicitly what must NOT come back (the families listed in `knowledge/blog-owned.md` and in the editor's own final checklist). Then re-dispatch `blog-qa-factcheck` with "re-check: gates <failed list>". Never re-run a full QA pass on unchanged gates. Repeat <=3 times total.
- Only if a section is broken beyond editing (missing entirely, or built on facts that are not in evidence.md): fix the input — patch `sections.json`/`evidence.md`, delete that section's file and re-dispatch `blog-section-writer` for it alone, re-assemble, then go through step 4 again.
- After 3 failed loops: ship best version, list unresolved blockers explicitly.

## 5.5 Orchestrator's own pass — do NOT skip, do NOT delegate
Start with the machine pass — it is free and it never gets tired:
```
python3 scripts/lint_article.py --job jobs/<job-dir>
```
It fails on the hard bans (stop-list brands from
`config/stop-brands.json`, «only product», mixed-case CoR/AoR, roadmap quarters, hard-coded freshness
dates, search-behaviour phrasing, an industry term such as «Agent of Record» used as our own label,
two H1s, headings below H4, an internal address
used more than twice or absent from `config/site-urls.json`), and it always prints the manner
numbers next to the reference values of the published articles (`reference_manner` in
`config/brand-rules.json`): bullets, «you / your», Example Co mentions.

Paragraph length has no numeric target. Paragraphs follow meaning
and vary naturally. Never create a density report or dispatch an editing pass merely to split
paragraphs by word count; use a list only when the content is genuinely an enumeration.

Then the part no script can do. QA is a checklist agent: it enforces the rules that were written
down. The orchestrator also sees the publisher's recent decisions, rules that are out of date and
the comments on the previous article. Run these yourself on `edited.md`:

- **Self-description beyond the string checks.** The linter catches the known phrasings; you judge the
  ones nobody has banned yet. Every sentence about Example Co: does it follow the current
  positioning card?
- **Internal information.** Future product names and anything that only exists in an internal doc never
  reach public text.
- **Legal substantiation** (knowledge/legal.md): every comparative claim traceable to evidence.md; no
  unsubstantiated superlative; no disparagement, including implied; competitor names nominative only;
  vendor images — alt text, source, no impression of endorsement.
- **Verbatim overlap with the neighbouring articles** — a signal, not a gate (uniqueness is not the
  priority: clear and accurate beats original at any cost). Run it,
  do not eyeball it: `python3 scripts/text_overlap.py <job>/edited.md jobs/<neighbour>/edited.md` for
  every adjacent article. A shared run past 40 words is worth rewriting; 20-40 words is fine when it
  is a category definition or a vendor card — those legitimately repeat across the queue; measure
  your own baseline on published neighbours. Facts and numbers stay identical either way.
- **The publisher's last review.** Re-read the newest `review/*-comments.md` in ANY job folder, not just
  this one. A comment given on the previous article is a rule for this one; if it is not yet in
  knowledge/, put it there before shipping, or it will be given again.

Anything you fix here is a defect in the rules, not in the text: fix the rule too, in the same session.

## 6. Package (mechanical only — text is frozen after QA PASS)
Write `<job>/out/meta.md` as `key: value` lines — `title`, `slug`, `metaTitle`, `metaDescription`, `summary`: take the FINAL title/H1 wording from `edited.md` headers (editing may have changed them), the rest from brief.md, respecting the caps (70 / 200 / 400). Copy `edited.md` -> `<job>/out/article.md`; build `<job>/out/internal_package.md` (source map from evidence.md + needs_manual_confirmation + serp_synthesis).
For an article of the form «competitor + Alternatives», the slug is exactly `<competitor>-alternatives`, with nothing appended after `alternatives`. This slug convention is specific to competitor-alternatives articles.
Then convert the body for Strapi and prove it survives the sanitizer:
```
python3 scripts/md_to_strapi_html.py --input <job>/edited.md --output <job>/out/article.html
node tools/sanitize/check.js < <job>/out/article.html | diff - <job>/out/article.html
```
An empty diff is the gate — any difference means markup would be lost on the site.

## 6.5 Review, then draft into Strapi
```
python3 scripts/gdoc_review.py push --job <job> --round 1
```
Give the publisher the document link. After the publisher comments or edits in place:
```
python3 scripts/gdoc_review.py pull --job <job> --round 1 --doc <link>
```
Apply the edits to `edited.md`, re-run QA on the affected gates only, repack, and send the next round with `--round 2 --baseline <job>/review/01-sent.md` (changed passages come highlighted). Repeat until the publisher says it is ready.
ONLY after that:
```
python3 scripts/strapi_publish.py --job <job> --dry-run
python3 scripts/strapi_publish.py --job <job>
```
This creates a DRAFT (`publishedAt: null` is sent explicitly — omitting the field makes Strapi publish the entry immediately).

Then draw the cover for that draft:
```
cd tools/covers && STRAPI_URL=https://cms.example.com \
  node article-covers.mjs --slug=<slug>
```
The generator lives in this repository under `tools/covers` (see its README); it reads the token from `STRAPI_TOKEN` or from the git-ignored `config/strapi-api-token`. Uploading a cover does not publish the draft.

Publishing is the publisher's own step in the admin panel — never publish from the pipeline.
If the repository is under version control, commit the job and the vendor-card enrichment together (`jobs/<job>` and `companies/`; `raw/` is ignored).

## 7. Final report to the user (pre-publication checklist)
End with: overall QA verdict; the full `needs_manual_confirmation` list; blocked-source items (`[fetch:403]`) that still want a first-party quote; no API cost line (this track spends no OpenRouter money — say so instead). Publishing/labeling decisions (disclosure etc.) are the publisher's own domain — do NOT add reminders or notes about sponsorship/affiliation anywhere in the report or the article.

## Translation of a selected published article

For an explicitly selected translation, read `knowledge/blog-translation.md`. Use a
new isolated `article_translation_version: 1` job; do not run new-topic or refresh
research and do not migrate existing jobs. Parent runs deterministic source/check/
package/drift/seal/Docs commands; all content is delegated to `blog-translator`
(gpt-6-luna/medium), `blog-translation-editor` and `blog-translation-qa`
(both gpt-6-sol/medium) with the same fixed routing envelope and fork_turns="none".
Use `scripts/blog_translation.py bootstrap --job <job> --slug <slug> --locale ru`,
then follow that knowledge file. Metrics use full scope and a translation-specific
stage plan. Review-only fidelity PASS is not factual re-verification or CMS approval.
Normal Strapi export rejects this branch; review Docs include source/visual limitations.

For an unsealed translation explicitly opted into `translation_units_version: 1`,
prepare/load `scripts/translation_dispatch.py` once and continue the SAME translator
thread/stage with complete source H2 subtrees after an explicit title/preamble unit.
The only additional envelope text is `Requested unit: "<requested_unit>".` from the
saved plan. Translator-owned unit files are assembled deterministically only after
all unit receipts pass; register the required `translation-assemble` stage. Existing
full-document translation jobs and sealed artifacts are not migrated. Follow
knowledge/blog-translation.md for source/assembly and feedback-provenance boundaries.
