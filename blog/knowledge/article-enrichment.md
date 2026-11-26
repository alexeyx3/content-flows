# Article enrichment — workflow v2

Binding for jobs with `workflow_version: 2`. Contract and commands:
`docs/blog-workflow-v2.md`.

## Research and reader value

Before the brief, blog-topic-research writes research.md using live primary and
independent sources beyond the SERP. New jobs also write
`research.discovery.md` under the bounded GIST contract in
`knowledge/gist-research.md`. The research agent searches scholarly
catalogues and indexed professional discussion for specific reader questions,
records useful and rejected leads, and checks evidence transfer. A paper
record, DOI, citation count, or LinkedIn snippet alone is not a publishable
claim or quotation. Direct LinkedIn scraping is outside this workflow.
For jobs with `research_v3_version: 1`, a shared `research_map.json` precedes
four parallel specialists. Scholarly search moves to `research.studies.json`,
and outside-practitioner sourcing to `research.quotes.json`; the topic agent
keeps primary qualitative discovery and Reddit context. The document specialist
runs archived `filetype:` searches through the repo SERP collector, which
tries XMLRiver first. Each selected study or quote still needs an accessible
original and independent evidence checks before prose.
New jobs with `primary_data_research_version: 1` also run
blog-primary-data-research in parallel after SERP collection. It searches
original documents and datasets for decision-useful statistics and comparable
chart values, writing `research.data.json` under
`knowledge/primary-data-research.md`. The brief waits for both research
packets, considers all originals in `visual_audit`, and records a concrete
reason when no numeric chart belongs in the article. No statistics quota
applies. A search result or AI summary is never a verified number.
The brief maps each Information Gain finding
to a concrete reader benefit and section. A new citation alone is not new value.
Do not claim original research, tests or personal experience that did not happen.
blog-evidence verifies the findings and records every fact used in text or visuals.
For numeric visuals it reopens the original and verifies each plotted point,
definition, denominator, period and calculation before visual planning.
SERP market selection is not a country quota. Use jurisdictions only where they
help a reader decision; preserve the scope of specific legal/statistical evidence.

## Writer

Read visuals.json and expert_quotes.json before writing. A visual has a section_id,
purpose, verified data, alt, title and caption. Write that section knowing what the
visual will explain; describe its useful conclusion in the text and keep important
information accessible outside the picture too.

Insert `[[VISUAL:<id>]]` on a line of its own, once, in the designated section.
Do not create an image URL, render a chart or invent its values. If the visual's
data does not support the planned conclusion, report the gap instead of inventing
it. This marker is allowed in the draft and initial edited text only.

For each non-rejected expert comment insert the EXACT quote and attribution:

```text
> <text from expert_quotes.json>
>
> — <attribution from expert_quotes.json>
```

For `speaker_kind: external`, link the attribution to the verified `source`
URL: `> — [<attribution>](<source>)`. For `source_policy_version: 1`, keep
the exact attribution as plain text and put the original URL once in the final
Sources/Источники list instead. The manifest must also record the
publication date and exact source location. The review Doc preface identifies
all `proposed` comments, including external ones; Strapi requires exact-text
publisher approval. External quotations are verbatim excerpts, never drafted
or paraphrased as if spoken by the named person.

Use the section_id and build the surrounding prose naturally. Do not compose an
attributed quote yourself, silently alter it, add a job title, experience or case.
`proposed` is an editorial formulation awaiting review, not a previously recorded
statement. Its status is kept outside the article, in a review preface. Approved
text must still match its approval hash. Rejected quotes must not remain in text.
For staff author/editor names use the exact Strapi profile `name`, including its
spelling and language, not a transliteration, username or another public byline.
Before quotes, run scripts/fetch_blog_profiles.py --job <job>; it reads public
article relations and saves raw/speaker-profiles.json. Direct /users endpoints
are deliberately empty in the current CMS. Missing/mismatched CMS names block
the input/export gate. Do not add a role to the name unless explicitly requested.

## Editor

Preserve the visual's designated location and purpose. Before materialization,
preserve each registered marker exactly once; flag unknown/repeated markers.
After materialization, preserve the complete image and Caption block. If data,
title or meaning changes, update the manifest and rerender before QA.

Preserve quote wording and attribution. Propose quote edits in editor_issues.md
and have the quote agent update the manifest; invalidate any old approval. Never
rewrite an approved quote while polishing the article. Every numerical/factual
statement in a quote is still subject to evidence checks.

Tables and lists stay within writing and editing; no separate production stage.

## Visual production and export

bar/line/process/decision visuals are rendered with code, in the brand palette from
`config/site-brand-tokens.json`, Exo 2 and the ORIGINAL SVG logo. The renderer inserts the logo;
models must not redraw it. Sources, units, period and geography must be recorded.
For new charts, use the palette set in config/site-brand-tokens.json and the cover tools;
replace it with your own. Chart titles use Exo 2 SemiBold;
data labels, axes, legends and explanatory labels use Manrope Regular/SemiBold
(the font files in tools/covers/assets; replace them with your own). Use only site palette colors for
chart marks and supporting lines. This font rule does not retroactively alter
publisher-approved process diagrams or their uploaded image hashes.
Derived values carry their calculation in data.methodology and are checked by QA.
Source URLs remain in the internal manifest. Use sources[].public=false for
competitor URLs: public caption keeps the source's name without linking to it.
Put attribution labels in `sources`. The packager appends them to the visible
caption, so write the caption's interpretation and scope without a second source list.
Title, alt and caption each have a 255-character maximum: the current Strapi
media schema stores name, alternativeText and caption as string fields. Keep
descriptions useful within that limit; never truncate them silently on upload.

Illustrations are outside automatic v1 production. Discuss the concrete task with
the publisher first: what the picture explains and what it adds to the section. Decorative
abstraction and generic stock scenes are not a valid task. Do not put an unresolved
illustration into a deliverable or quietly substitute a generic generated image.

render_visuals.py → upload_visuals.py → package_article.py --bind-visuals replaces
the writer's markers with actual PNG images, alt, title, visible captions and
source attribution. This happens BEFORE final QA. Google Docs must contain real
inline images, never Markdown image syntax or service markers in place of them.

## QA and approval

QA reads the FULL materialized article, visuals and expert comments. Check data
entailment, units, comparisons, calculations, diagram connections, captions, alt,
title, brand assets, mobile readability, placement and the actual reader benefit.
Before a diagram is shown for publisher review or uploaded, its renderer must pass
the geometry check for node, title, footer, arrowhead and edge-label collisions.
Inspect the rendered PNG at its full size and at a 390 px article width as well:
automatic geometry catches box intersections but cannot judge every visual tangent,
text crowding or unclear connector. Any element covering another unintentionally
is a visual QA failure; revise and rerender before export.
No service markers may survive. The code gate also checks completeness and hashes.

For expert comments, verify speaker/attribution against the author's/editor's
profile; distinguish source quotes from proposed wording. Proposed comments may
pass technical QA and go to review, but cannot go into Strapi before approval.
Do not treat proposed wording as independent evidence for the article's claims.

End qa_report.md with `overall: PASS` or `overall: BLOCK`. On PASS, the orchestrator
runs workflow_gate.py seal-qa. Rewrites after this invalidate the receipt; rerun
the affected QA gates, repack and reseal. Approval records are created ONLY after
an explicit human decision, with the approving person's name and the source of
that decision. Writing a record is not itself approval.

Before Google Docs: complete images, no placeholders, current QA PASS. Before any
Strapi write: all the same checks plus approved quote texts and review approval
for the exact current article. --publish remains an explicit publication action;
creating a draft does not publish it. No agent may waive an export failure.

## Actual CMS image for QA

Strapi may optimize the PNG and returns a WebP delivery URL. upload_visuals.py
captures the public original PNG in asset.remote_path and records remote_sha256.
Inspect remote_path (the actual public image), alongside the original asset.path.
Different compression/colors alone are not a failure; unreadable labels, changed
meaning, lost logo or changed dimensions are. Export checks both local and public
hashes. Do not use delivery_url as the Docs image URL or invent asset metadata.

## Current CMS compatibility — publisher decision

Do not modify or deploy Strapi to add image title. The current CMS keeps img alt
and figcaption but strips img title. Prepare title in the manifest/source and use
it as media.name; do not claim this is an HTML title on the site. strapi_publish.py
omits only img title from the exported v2 body, validates all other markup and
checks the saved draft before publication. Source QA still requires title metadata.
