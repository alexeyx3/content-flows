# Example Co article flow — Codex v2

Active instruction:
[blog-article](../.agents/skills/blog-article/SKILL.md). Execution history:
[design notes](design-notes.md).

## Standing rules

- Topics come only from config/temnik.json: the «Topic sheet - blog» tab, in row order.
  Any other shared SEO/GEO spreadsheet is not a source of topics for this flow.
- For EN — the US, GB, DE, AU search results and the full useful H2–H4 hybrid with no heading quota.
- Before evidence/writer — the existing approval of the brief and of own_product_placement;
  first does not replace the decision on category fit.
- The main Codex agent starts the specialists directly: fork_turns=none, the route from
  config/codex-model-routing.json. One persistent writer, one complete H2 with
  all its H3/H4 per turn. Metrics lock write transactions and check the stage plan.
- Google Docs for finished articles and the topic-sheet sync are allowed within the existing
  boundaries of AGENTS.md. Strapi/media changes and publication require explicit permission
  in the current conversation. Deploys and CMS modifications are not part of this flow.

## Order of v2

Topic sheet → SERP of four markets and Reddit Mapper → **a shared map of reader questions Q-xx** → **in parallel: topical research, the search for primary documents, scholarly originals and outside voices** → every research gate → the brief and
the full hybrid → the existing approval by the publisher → evidence → cards, if
needed → **parallel visual and quote plans** → the inputs check → **early render and layout** →
in parallel **MiniMax over complete H2s → assembly → first-pass review by DeepSeek → editor → delta** and **independent visual QA** →
both branches PASS → real visuals and packaging → QA of the whole
material → QA receipt → Google Docs and approval → affected QA after edits →
an approved Strapi draft/publication only on an explicit request.

| New role | Result | Route |
|---|---|---|
| blog-research-map | research_map.json: shared decisions and affected parties for the four parallel specialists | gpt-6-sol, medium |
| blog-topic-research | research.md + research.discovery.md in new jobs: sources, the GIST decision map and a verifiable search | gpt-6-sol, medium |
| blog-primary-data-research | research.data.json: original documents, verifiable numbers, series and reasons for declining a chart | gpt-6-sol, medium |
| blog-study-research | research.studies.json: catalogues as leads, originals that were read, method and transferability | gpt-6-sol, medium |
| blog-quote-scout | research.quotes.json: X, indexed LinkedIn, the web and experts' own publications; verified verbatim candidates | gpt-6-sol, medium |
| blog-visual-planner | visuals.json: data, place, task, captions | gpt-6.1-terra, medium |
| blog-visual-qa | visual_qa.json: an independent check of the original and the 390 px version before upload | gpt-6.1-sol, medium |
| blog-expert-quotes | expert_quotes.json: exact wordings for approval | gpt-6.1-terra, medium |

Strategy follows the `blog-strategy-brief` route with `gpt-6-sol/medium`. New topics use
the routes from `config/blog-openrouter.json`. Earlier jobs with the native writer and refresh
use `blog-section-writer` with `gpt-6.1-terra/medium`.

For new jobs `research_coverage_version: 1` makes the researcher, before searching,
break the topic down into several major reader decisions and the affected parties.
One query may cover several decisions; the log links them through
`decision_refs`, and the validator checks the coverage. On a material gap
the researcher continues the same
stage before handing over to the brief. This lowers the risk of an omission but does not
guarantee that the search results will show every existing study.

For new jobs `research_v3_version: 1` first creates a short
`research_map.json`, then four agents work at the same time. The document
search runs through `fetch_google_serp.py --provider auto`:
XMLRiver is the first to receive real `filetype:pdf`, `filetype:ppt/pptx`,
`filetype:doc/docx`, `filetype:xls/xlsx` queries on the topic and the audience;
the results are saved in `raw/document-search-*.csv`. The validator compares
the query log with the archive and requires at least one original that was read before
the brief. A useful original may be qualitative: a number and a chart are not
mandatory, but an empty research packet does not pass. A provider
error is recorded in the archive; the researcher continues the search in
open originals. The search is not repeated as a separate run after the article.

The scholarly agent searches not only OpenAlex/Crossref but also directly at
the publisher or in an open repository. Metadata, abstracts and snippets do not
become a study that was read. The outside-voices agent searches X,
indexed LinkedIn, ordinary search, interviews, associations and accessible
transcripts; only a directly read original with verified words,
name, role, date and context is passed to the quote agent. The number of outside
quotes is not fixed; their absence is explained by the search that was performed.

`geographic_audit_version: 1` requires an explicit geographic frame in the brief,
the reasoning for the jurisdictions needed and the risk of a source imbalance. The editor and QA
compare the frame with the text: a global heading must not hide what is mostly
one national system. The number of countries is not fixed; URL domains serve as
a diagnostic, not an automatic verdict.

`source_policy_version: 1` requires a final Sources/Источники section.
Every original that was used, every public source of a visual and of an outside quote
gets one clickable link there. The text keeps the name of the source,
the year and the necessary limits of applicability; there are no repeated URLs in sections and
captions. The gate checks the required URLs, the absence of duplicated links and
the final position of the section. Old articles are not repackaged automatically.

Quotes have no numeric minimum or maximum: the quote agent chooses different
verified perspectives by their value for the reader's decision and discards repeats.

Tables/lists remain part of writing and editing. Code-generated bar/line/process/
decision visuals use the original logo and the brand colours. Story and
concept illustrations are discussed separately for a specific section;
there is no automatic decorative generation.

## Contracts

For new topical articles `answer_contract_version: 1` adds a compact
chain "reader question → the necessary answer with its conditions → evidence → the place in
the finished text". The brief sets `sections.json.answer_checks`, evidence links
its rows through `answer_check_ids`, the editor preserves the meaning, and the existing
QA checks the answer, the tables and the already materialized captions. Contract and format:
[answer-contract.md](../knowledge/answer-contract.md). The scripts check the references
and the presence of exact QA quotes, but do not pass this off as a fact-check of meaning. There is no new agent,
no pass over every sentence, no quotas of keywords/length and no migration of old jobs.

### research.md and sections.json

The researcher numbers the findings R-01, R-02… and records links, supporting passages,
dates, jurisdictions, limitations, reader questions, visual and comment candidates.
New jobs get `research_discovery_version: 1` in `job.yaml`. Before the brief
the topical researcher prepares `research.discovery.md`: the GIST decision map,
the log of queries to primary sources and the finding cards. For jobs with
`research_v3_version: 1` the scholarly search and the search for outside voices are moved into
separate parallel packets; the topical researcher does not record someone else's
queries as its own. The `validate_research_discovery.py` script checks its
primary lane, and separate validators check the study and the voices. Earlier jobs
keep the three-channel discovery contract. An irrelevant study is not inserted
for the sake of a citation; LinkedIn results remain discovery if the original
is not available for permitted direct reading. An outside quote is not inserted
from a search snippet: the quote agent opens the original, checks the author,
the date, the exact words and the context. In the review Doc it may be `proposed` with
the original named in the final Sources and a note about its status; before Strapi the publisher
must approve the exact text and attribution.
Detailed contract: [gist-research.md](../knowledge/gist-research.md).
New jobs also get `primary_data_research_version: 1`. The independent
`blog-primary-data-research` runs in parallel with the topical researcher after
SERP, without waiting for its files. It searches open original PDF/PPT/DOC/XLS files and
web datasets for the reader's questions and saves numeric candidates and the exact
place in the source in `research.data.json`. Contract:
[primary-data-research.md](../knowledge/primary-data-research.md).
`validate_primary_data_research.py` and `validate_research_discovery.py`
must pass before the brief. Evidence reopens the selected originals and
confirms every point. There is no mandatory number of figures or charts.
For a batch, `audit_visual_mix.py --jobs ...` counts the types and flags
a repetition of one set of visuals across all articles. This requires an editorial
review of the data packets and of the reasons for declining charts, but not a quota of pictures.
In sections.json, besides the existing title/sections, the brief adds:

```json
{
  "information_gain": [
    {"id": "ig-1", "reader_value": "A concrete decision the reader will be able to make",
     "section_id": "selection-criteria", "research_ref": "R-01, R-03"}
  ],
  "visual_candidates": [
    {"section_id": "selection-criteria", "type": "decision", "purpose": "What to explain"}
  ],
  "visual_audit": {
    "considered_data_ids": ["D-01"], "selected_chart_ids": [],
    "decision": "The number describes the study sample, not a measured result for a chart."
  },
  "expert_questions": [
    {"section_id": "selection-criteria", "question": "Which disputed choice should be explained?"}
  ]
}
```

These are additional top-level fields; the existing section schema does not change.
`visual_audit` is mandatory only for new jobs with the primary-data protocol.
A numeric bar/line candidate refers to the selected `D-xx` through `data_ref`.
The same `data_ref` is kept in `visuals.json`; if evidence rejects
the selected data, `data_omissions[D-xx]` explains the absence of the chart.
All factual content goes through evidence.md; research.md does not bypass the fact-check.

### visuals.json

An example of the structure, not data for publication:

```json
{
  "version": 1,
  "visuals": [{
    "id": "annual-cost",
    "type": "bar",
    "section_id": "pricing",
    "purpose": "Show the difference in costs under comparable conditions",
    "title": "Annual costs",
    "alt": "A description of the comparison and the main result",
    "caption": "The period, the conditions and an explanation of the calculation in the article's language.",
    "sources": [{"label": "Name of the primary source", "url": "https://example.com/source", "public": true}],
    "data": {
      "unit": "USD / year", "period": "2026", "geography": "US",
      "categories": ["Scenario A", "Scenario B"],
      "series": [{"name": "Annual costs", "values": [1200, 2400],
                  "evidence_ids": [["PRICE-01"], ["PRICE-02"]]}],
      "methodology": "The formula, the input values and the assumptions for derived values"
    }
  }]
}
```

Charts: 2–8 categories, 1–3 series; every point has a non-empty list of
evidence_ids. Series must be comparable by unit/period/geography. Numbers are finite
and non-negative. `line` additionally requires `x_label`; for an uneven numeric
axis give `x_values` — numeric coordinates in the same order, strictly increasing.

For process/decision, instead of categories/series:

```json
{"nodes": [
  {"id": "start", "label": "First step", "evidence_ids": ["STEP-01"]},
  {"id": "next", "label": "Next step", "evidence_ids": ["STEP-02"]}
], "edges": [{"from": "start", "to": "next", "label": "Condition"}]}
```

An edge may carry `"style": "dashed"` when a dashed arrow
meaningfully distinguishes influence from control. By default the line is solid;
only `solid` and `dashed` are supported. The difference must also be named in
the short label of the line or block and in alt/caption, so that the meaning does not rest
on the stroke type alone.

2–8 nodes, one rooted tree, without cycles or merging paths; at most three leaf
branches. For a process in which two independent inputs give one decision,
`data.layout: two-input-merge` is allowed: seven nodes in the order context, baseline step,
two inputs, shared decision, next step, final step; edges 0→1, 1→2,
1→3, 2→4, 3→4, 4→5, 5→6 without arrow labels. Long labels/complex diagrams must be shortened or split: the renderer does not
clip text silently. An empty list of visuals requires omission_reason and an editorial
decision to change the plan. The illustration type is rejected explicitly in the first version.

Competitor URLs: `public:false`; the caption keeps the name of the source, the link is stored
only in the manifest. Every data source must be saved in the job's files.
title, alt and caption are at most 255 characters each: the corresponding fields
of Strapi media have the string type. The gate checks the limit before upload; text is not truncated.

The render adds asset: path, sha256, spec_sha256, width, height; the uploader adds url and
media_id, delivery_url, remote_path, remote_sha256 and pixels_identical. delivery_url is
the regular CMS address (usually WebP); url is the verified public source PNG for
the article and Docs. remote_path points to a copy of the PNG that was actually uploaded, for QA.
Agents do not make these fields up. The packager keeps inserted_markdown for
a repeated mechanical replacement of the picture when the file/caption is updated.

### expert_quotes.json

```json
{
  "version": 1,
  "quotes": [{
    "id": "selection-comment", "section_id": "selection-criteria",
    "speaker": "john.roe", "attribution": "John Roe",
    "text": "A proposed expert comment.",
    "source_type": "editorial_draft", "source": "",
    "evidence_ids": [], "status": "proposed"
  }]
}
```

Before preparing comments run `python3 scripts/fetch_blog_profiles.py --job <job>`.
For staff quotes the attribution must match exactly the name field of the author/editor in Strapi; the snapshot
raw/speaker-profiles.json is part of the QA receipt. A username, a transliteration and a name from
another public article do not replace this field. A mismatch blocks export.

For an outside verbatim quote add `speaker_kind: external`, `source_type:
verbatim`, `source` with the HTTPS URL of the readable original, `published_at` and
`source_location`; the attribution is the verified name and role, and in the text it links
to the original. The excerpt is at most 25 words. The quote agent evaluates outside
candidates from `research.discovery.md` before choosing staff comments.

source_type: editorial_draft/verbatim. verbatim needs the source of the real words.
status: proposed/approved/rejected. Roles are verified; an unconfirmed role is not
added. The quote agent has no right to set approved. Real quotes are also
confirmed for use in the article. Verifiable statements refer to
evidence_ids; an expert opinion does not serve as a source of factual statements.

The writer inserts the exact blockquote and attribution from the manifest. Proposed quotes
are visible at review; their status is stated in a separate note before the article. The note
does not get into the HTML and is excluded from the diff of edits to the document body.

## Early render and parallel check

```bash
python3 scripts/workflow_gate.py check --job <job> --target inputs --offline
python3 scripts/render_visuals.py --job <job>
python3 scripts/check_visual_layout.py --job <job>
python3 scripts/workflow_gate.py check --job <job> --target writer --offline
```

These commands run after the visual and quote plans are ready, before the writer.
Caption-length and geometry errors are fixed straight away. After PASS the independent
visual QA and the writing start at the same time. `scripts/blog_openrouter.py` takes the assignments
from the approved `sections.json`, keeps the full sequence of MiniMax turns and assembles
the verified H2/H3/H4. DeepSeek checks the assembled D0 before the editor. For the native writer
use `python3 scripts/writer_dispatch.py --job <job>`; `--next` is needed for recovery.

New jobs with `visual_qa_version: 1` go through a separate `blog-visual-qa` stage:
first `python3 scripts/check_visual_layout.py --job <job>`, then
the specialist opens every full PNG and the 390 px preview, checks overlaps,
arrows, the title, captions, the logo and readability, then writes `visual_qa.json`
with PASS/BLOCK and the hashes of the files viewed. The automatic check re-renders
the current assignment and blocks geometric intersections. BLOCK leads
to a fix and a repeated check before media upload. After the editor, join
the branches; do not recreate current PNGs and visual QA. After both PASS:

```bash
python3 scripts/workflow_gate.py check --job <job> --target visual --offline
python3 scripts/upload_review_visuals.py --job <job> --dry-run
```

For Google Docs with real pictures we use the article's folder on the shared Google
Drive — within the standing permission for review Docs. The PNG file is available at
a verifiable HTTPS URL; the script downloads it back and compares the hash with the rendered
diagram. Strapi media is not changed by this:

```bash
python3 scripts/upload_review_visuals.py --job <job>
python3 scripts/package_article.py --job <job> --bind-visuals
python3 scripts/workflow_gate.py check --job <job> --target qa
```

Perform a separate upload to the Strapi media library only with explicit permission for
that action in the current conversation. The publication gate rejects Drive-only IDs;
after the upload to the CMS the article must be repackaged and the affected QA repeated.

```bash
python3 scripts/upload_visuals.py --job <job>
python3 scripts/package_article.py --job <job> --bind-visuals
python3 scripts/workflow_gate.py check --job <job> --target qa
```

QA receives the finished text with images and inspects asset.remote_path. After
PASS and the orchestrator's existing checks:

```bash
python3 scripts/workflow_gate.py seal-qa --job <job>
python3 scripts/package_article.py --job <job>
python3 scripts/temnik.py ready --job <job> --apply
python3 scripts/gdoc_review.py push --job <job> --round 1
```

Push itself checks the materials before creating the folder/document, confirms real
inline images, saves the receipt and syncs `in review` to the topic sheet.
Pull tracks text edits and the deletion/replacement of a picture; the service note about
proposed comments is not part of the article diff.

```bash
python3 scripts/gdoc_review.py pull --job <job> --round 1 --doc <url>
```

After a real human approval, record exactly that decision:

```bash
python3 scripts/workflow_gate.py approve-quotes --job <job> --ids <id> --by <person> --reference <decision-source>
python3 scripts/workflow_gate.py approve-review --job <job> --by <person> --reference <decision-source>
```

The scripts do not verify identity and do not replace the approval. A machine PASS does not
allow a quote from the author/editor to be approved automatically.

Strapi on a separate request: first --dry-run, then writing the draft; --publish
only on an explicit request to publish. The v2 gate checks QA/approvals before the API.
The draft is read back: an unexpected change in the HTML stops publication.
The ID is written to out/strapi_record.json for a repeated --update without a duplicate.

## Machine guarantees and limitations

- No VISUAL/QUOTE markers and no registered service placeholders.
- Every planned image is inserted exactly once with alt and captions.
- The data and the source file match the render; the real PNGs are saved for QA.
- Images are available over HTTPS; the CDN and the local copy match by hash.
- Title is prepared in the sources/media name but is not required in the HTML of the current CMS.
- The package matches edited.md; the QA receipt corresponds to the current materials.
- Quotes match the exact text/attribution; Strapi requires the approvals.

Meaning, accuracy and readability are assessed by the specialists and by visual inspection,
not only by hashes. Old jobs are not migrated automatically; the new contract is switched on
only with workflow_version:2. A technical run and a real article are counted
separately: a passing technical run does not by itself prove the flow on a real article.

## Design and integration limitations

The generator uses tools/covers (sharp, Exo 2 and the font helper)
and tools/covers/assets/logo.svg from this project. For another location
BLOG_BRAND_DIR and BLOG_LOGO_PATH are available. No additional Node dependencies are
installed into the blog repository. PNG suits Docs and the site; SVG is kept as the source.

The current CMS upload lifecycle replaces media.url with the lg_webp address, although the original
stays in S3. The uploader gets the address of the original by hash/ext from the AWS provider's response
and checks HTTPS, PNG/JPEG and the dimensions. The CMS may optimize the colours of a PNG: so
the uploader downloads assets/<id>.strapi.png, records remote_sha256 and sets
pixels_identical. QA and the editor look at remote_path, that is, the real file
on the site, together with the source render. Export checks the hash of that copy and of the public
file. The source render is kept for reproduction. Another provider
with an unconfirmed address of the original stops the upload; agents do not guess the URL.
When the CDN is unavailable, the ID of the media already created is kept: the repeated check
uses that ID and does not upload a duplicate.

Strapi media stores name, alternativeText and caption. The current CMS keeps img alt
and figcaption but removes img title; the flow works within that contract.
Title is prepared and stored in the manifest, the Markdown and the source HTML; it is passed to media
as name. This is the name of the media file, not the HTML title attribute on the site.
strapi_publish.py excludes only img title from the v2 HTML it sends, then
checks the remaining attributes and markup against the sanitizer in force and reads
the result back. The loss of alt, of an image or of a caption still blocks
publication. tools/sanitize/check.js corresponds to the unmodified CMS.

Google Docs REST inserts real images by a public URL:
[documentation](https://developers.google.com/workspace/docs/api/how-tos/images).
The current REST API has no method for setting alt/title on an inline image (also verified
against the installed discovery schema). So Docs has the image and a visible
caption, and the metadata is kept in the receipt. The site has alt and the caption; the name
is kept in media.name, and there is no HTML title on the site. Do not claim that Docs REST sets them.

## Documentation

In every new job keep progress.md: the request, the decisions taken, stages/commands,
finished files, checks, open questions, approvals, the Docs URL and the actual
state of Strapi. Shared changes / why / what was checked go to docs/design-notes.md.

## Translations of the published blog

Translation is a separate review-only EN→RU branch for one explicitly selected published article.
It is neither a refresh nor a new topic from the topic sheet. Contract:
[knowledge/blog-translation.md](../knowledge/blog-translation.md). A new isolated
job stores the immutable current CMS JSON/HTML, the auxiliary Markdown, the source
metadata/relations, the inventory and the hashes. The historical ranking is kept with provenance;
the translation is not declared a fresh check of the statements or a new approval of placement.

Three separate roles: blog-translator — gpt-6-luna/medium; blog-translation-editor
and blog-translation-qa — gpt-6-sol/medium. The parent starts them directly with the usual
fixed envelope/fork_turns=none and runs only deterministic commands.
The full metrics scope has its own list of stages. Structure/numbers/links/visuals,
live source drift, independent QA, package and seal are checked before Docs. New RU
summary/SEO fields for empty EN fields are explicitly marked derived_from_source, with the same
limits. This does not permit data from memory or new advertising.

The Google Doc contains a separate preface with the source/hash, the freshness limitations,
source-policy remarks, the cover status and the origin of the metadata. Native
readback: `python3 scripts/blog_translation.py verify-review --job <job> --round 1`.
The link/local status are saved in review/translation-review.json. There are no topic-sheet fields for
translations yet; the EN lifecycle and refresh fields are not overwritten. The ordinary Strapi
export (`strapi_publish.py`) blocks translation jobs; a linked localization is created and
published only through the two dedicated scripts below, each on an explicit publisher request.
Old jobs are not migrated; complex unsupported HTML forms of the source are blocked before the snapshot is written.

For an explicitly approved placement of a translation as a draft only, a separate
`scripts/strapi_translation_draft.py` is available: a local authorize with the hash of the approved
text → dry-run → parent `export --apply` → an independent readback. Full contract:
[knowledge/blog-translation.md](../knowledge/blog-translation.md), section «Explicitly authorized linked Strapi draft». The ordinary Strapi
export of a translation is still blocked; publication, media and new facts are not part
of the draft permission. The RU cover stays empty in the draft, and the QA limitations are
stored in tracking.

Publication of that linked draft is a separate step, run only when the publisher explicitly asks
for it: `scripts/strapi_translation_publish.py`. Its preconditions are checked in code: the
tracked draft with a passing readback, the publisher's request in `publication/request.json`, a
PASS of the scoped publication-readiness QA in `publication/readiness.json` (contract: section
«Scoped publication-readiness QA contract» of the translation card) bound to the current article,
metadata and QA seal, a verified review round, and a rendered RU cover with an independent
full-size and 390 px visual QA receipt (`publication/cover.json`, `publication/cover-plan.json`),
attached by the separately authorized cover workflow. Order: `authorize` (records the request,
bound to the article hash, review round and target ID) → default dry-run `publish` → parent
`publish --apply`, which changes only `publishedAt` and `indexable` on the tracked RU record and
then reads it back. The script never uploads media and never creates a record; the EN source must
still match its snapshot.

For new unsealed translations an explicit `translation_units_version: 1` is available:
the same persistent translator and one metrics stage perform the title/preamble, then
the complete source H2s with all their descendants. `scripts/translation_dispatch.py --prepare`
creates a deterministic plan and source slices, which the parent reads once.
`--complete` binds every complete RU unit to the source/output hashes; `--assemble`
writes translated.md only after the full set and does not overwrite an existing text.
Optional assembly/unit hashes are part of the QA seal; translation-assemble is required.
The full editor and independent QA remain the next mandatory stages. Old
jobs and finished full-document translations are not migrated; decisions from one job's
feedback are not carried over into a new batch as permissions for semantic changes.
