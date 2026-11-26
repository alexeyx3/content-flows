# GIST research for new blog articles

Adapted for this blog from an external content-logic methodology for
information gain. This is a small operational contract, not a copy of the
original skill. It applies when
`job.yaml` sets `research_discovery_version: 1`.

For jobs also setting `research_v3_version: 1`, a shared map and the parallel
study, document and quote packets replace this file's scholarly and
professional search lanes. The topic researcher keeps the four discovery
headings but logs only its own primary qualitative searches, referring to
the sibling packets for the other results without claiming to have done them.

## Work backwards from the reader's decision

Before collecting sources, state the reader's question, the decision or
verification they need to make, and what the current SERP leaves unclear.
Check for missing failure modes, hidden information, limitations,
disqualifiers and measurable properties. Turn a useful missing node into a
specific article intervention: a criterion, comparison, verification method,
checklist, decision tool or visual. Do not add a section just to display a
novel source.

Ask of each selected block: what uncertainty does it resolve, what action
does it improve, what evidence supports it, and what is lost if removed?
Select different decision functions instead of repeating one point through
multiple studies, quotes or headings. Put the most useful distinction early.

## Three bounded discovery lanes

1. **Primary and professional material.** Search official rules, standards,
   datasets, original reports and author-controlled publications for the
   exact question. Record the source's scope and competing definitions.
2. **Scholarly catalogues.** Run at least one question-specific search in
   [OpenAlex Works](https://help.openalex.org/api/searching/) and/or
   [Crossref Works](https://www.crossref.org/documentation/retrieve-metadata/rest-api/).
   Both expose public search endpoints. Record the query, DOI or stable work URL, title,
   authors, date and access level. Catalogue metadata, citation counts and
   search snippets are leads, not proof. Read the abstract or full original
   paper before extracting a finding. Check population, method, outcome and
   date. If no study transfers to the reader's decision, record that result
   and omit academic citations from the article.
3. **Public professional discussion.** Run a bounded indexed-web search for
   relevant LinkedIn posts and, where useful, author-controlled blogs or
   conference material. Capture URLs, author names and the question or
   objection worth investigating. Indexed snippets are discovery only.
   Do not crawl LinkedIn, bypass access controls, copy posts from search
   results, or treat a post as evidence of prevalence or a legal/market fact.
   Verify the substantive claim in an accessible primary or independent
   source before it enters `evidence.md`.

LinkedIn's [User Agreement](https://www.linkedin.com/legal/user-agreement)
restricts unauthorized automated access and copying. An indexed hit can
therefore point to a question or an author-controlled publication; it is not
an invitation to fetch the LinkedIn post automatically.

Search the lanes for the reader question, not just the topic noun. One
bounded query per applicable lane is a starting point. Broaden only for a
specific unresolved question; stop when another source would repeat an
existing decision function.

## Research insight card

For each candidate worth considering, record in `research.discovery.md`:

- question and missing node;
- source URL, author/organization, date, access level;
- research role: discovery, validation, constraint or measurement;
- finding and mechanism in the source's own context;
- evidence level: direct, strong adjacent, indirect, hypothesis or speculation;
- transfer risk to this audience and decision;
- practical intervention, required data and verification step;
- reason to select or reject it, and the corresponding `R-xx` finding if selected.

An insight card is not permission to publish a claim. The evidence agent
reopens selected sources and records exact entailment. A DOI alone, an
abstract about a different audience, or a LinkedIn opinion cannot become a
general fact. Conflicting findings stay visible with their differing scopes.

## External quotations

The research agent may propose a short externally attributed quotation only
when the exact words, author, date and stable original URL can be verified
through an authorized, directly readable source. Record it as a candidate,
not as article prose. A LinkedIn search snippet never qualifies. Direct
LinkedIn automation is not part of this workflow; a repost on an author's own
site can qualify if read directly. The evidence agent checks meaning and
context; the editor decides whether the words add value. A verified external
quotation may appear as `proposed` in a Google Doc review copy with its
original source linked and the review preface identifying it as unapproved.
The publisher approves its exact text and attribution before Strapi export.
Keep quotations at most 25 words from one source and prefer a linked
paraphrase when the exact wording is not necessary. Pass candidates to the
quote agent. A selected verbatim third-party quote belongs in
`expert_quotes.json` with `speaker_kind: external`, original URL, publication
date and exact source location. A search snippet never qualifies.

The existing John Roe/Jane Doe quote workflow remains separate:
its editorial drafts are not recordings of their own words.

## Packet contract

`research.discovery.md` contains these headings:

1. `## Decision map` — question, reader action and missing nodes.
2. `## Search log` — query, channel (`primary`, `scholarly`, `social`),
   outcome and the reason a lane was unhelpful or inapplicable.
3. `## Insight cards` — selected and rejected candidates with the fields
   above, or a clear explanation that no transferable candidate was found.
4. `## External quote candidates` — verified candidates with provenance or
   `None` and the reason.

The strategy brief uses selected cards only where they improve a reader
decision. `research.md` retains the concise `R-xx` findings; neither packet
bypasses `evidence.md`, publisher approval or QA.

Use this table in `## Search log`; add rows when a second question needs a
different search. Outcomes are `found`, `none`, `blocked`, or
`not_applicable`. A non-result needs an explicit reason.

| channel | query | outcome | note |
|---|---|---|---|
| primary | source and decision terms | found | R-01, narrow scope. |
| scholarly | mechanism and audience terms | none | No transferable paper found. |
| social | indexed professional question terms | found | Question lead only; no post text copied. |
