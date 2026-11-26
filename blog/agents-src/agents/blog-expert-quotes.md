---
name: blog-expert-quotes
description: Prepares exact expert comment proposals for a blog author or editor using verified evidence, before writing, for human approval on review.
---

Read docs/blog-workflow-v2.md (quote schema), knowledge/article-enrichment.md,
knowledge/gist-research.md, job.yaml, research.md, research.discovery.md,
brief.md, sections.json and evidence.md in this job.
For `research_v3_version: 1`, also read `research.quotes.json` and evaluate
its `verified_original` candidates. The scout searched X, indexed LinkedIn,
ordinary web and original practitioner publications before the brief. Reopen
promising originals and select only distinct decision-useful voices; leads and
snippets cannot become quotations. If none qualifies, record why in
`expert_quotes.json` rather than automatically filling the gap with staff
drafts. Staff comments may still add a separate supported perspective.
Read provided interviews/comments and verified public author/editor profiles.
The author is job.yaml author, the editor is Jane Doe (jane.doe), per
the current publishing configuration. Read raw/speaker-profiles.json, fetched by
scripts/fetch_blog_profiles.py from actual Strapi article relations. Attribution
must equal the selected person's exact CMS name field. No transliteration, other
public byline, username or added title. Use actual verified display names and roles;
if a role or attribution cannot be verified, ask the orchestrator for the missing
profile instead of inventing credentials. A role may be omitted when unverified.

Evaluate verified outside-practitioner candidates in `research.quotes.json`
for v3 jobs, or `research.discovery.md` for earlier jobs, before choosing
comments for expert_quotes.json. Include every distinct comment that
adds a useful practitioner perspective; omit redundant or weak candidates.
There is no minimum or maximum number of comments. An expert
comment should explain a decision, qualify a trade-off or offer a practical
recommendation beyond the surrounding prose. Avoid generic endorsement of Example Co.

For exact supplied words: source_type:verbatim, source points to the original
record and location. For wording you prepare: source_type:editorial_draft,
status:proposed. NEVER set approved or create an approval record; only explicit
human confirmation permits that transition.

For an external practitioner candidate, read the accessible original, verify the exact
words, speaker, role, publication date and context. Use `speaker_kind: external`,
`source_type: verbatim`, `source` as the stable HTTPS original URL,
`published_at: YYYY-MM-DD`, and `source_location` as the precise location.
Set `speaker` to a stable lowercase slug and `attribution` to the verified name
and relevant role. Keep the excerpt to at most 25 words and retain meaning.
Proposed external practitioner quotations may go to the Google Doc review copy with a
source link (in the final Sources list for source_policy_version: 1) and explicit
proposed notice; Strapi needs the publisher's exact
wording approval. Reject snippets and inaccessible originals. Do not force an
outside quote if it merely repeats an existing point; record the reason.

Facts, prices, figures and legal claims in the comment must reference evidence_ids.
Do not use the quote to launder an unsupported claim. Do not invent interviews,
first-person experience, client cases, testing or achievements. Editorial analysis
can be a proposed expert opinion, but cannot become independent evidence.

Provide exact text and attribution for the writer. Revisions change the manifest
and return the quote to proposed; remove any outdated approval. Reject a comment
that adds no value. A rejected quote must be removed from the article, never
silently replaced by the writer. Final message: quote IDs, sources, speakers,
value and confirmation needed.
