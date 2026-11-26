# Outside-practitioner quote research

This packet applies only when `job.yaml` has `research_v3_version: 1`. The
`blog-quote-scout` agent receives the shared `research_map.json` and searches
in parallel with other research specialists, before the brief and writer.
`research.quotes.json` is a handoff, not a verified article fact or permission
to publish anyone's words.

## Search and selection

Search by a reader decision, practitioner role and the likely disagreement or
practical choice, not only by the topic noun. Cover X, indexed LinkedIn and
ordinary web search. Use at least one original-first lane: named interviews,
signed practitioner articles, professional association material, conference
or webinar transcripts, podcast transcripts, or named comments in original
reports. Several decisions may share a query. Record a blocked channel and
the access limitation instead of fabricating a result. Do not scrape LinkedIn
or bypass access controls. An X result qualifies only when its original post
is directly readable or available through an authorized API. Search-result
text, AI summaries, reposts and catalogue metadata never supply exact words.

Read the original around the proposed excerpt. Check the author's name and
role, date, full wording, context, scope and exact source location. Preserve
qualifications. Limit each proposed excerpt to 25 words. Prefer a paraphrase
with a source when exact wording adds nothing; note why that candidate is not
a quote. Do not fill a quota. The agent may return zero verified candidates,
but must explain the actual search and what blocked useful leads. The quote
agent later decides whether a verified candidate belongs in the article;
`blog-evidence` independently verifies any factual claim around it.

## `research.quotes.json` contract

`decision_refs` use IDs from the shared map (`Q-01`, etc.). `channel` is `x`,
`linkedin`, `web_search`, or `original_source`. The `original_source` lane
specifies its `source_kind` such as `interview`, `signed_article`,
`association`, `conference_transcript`, `podcast_transcript`, or
`original_report`. The social channels may discover the author while a
separate original-source row verifies the words. Outcomes are `found`, `none`,
or `blocked`. Every search records a concrete query and note; `blocked`
records the access problem. Do not multiply near-identical queries merely to
fill the log.

```json
{
  "version": 1,
  "search_log": [
    {
      "channel": "web_search",
      "decision_refs": ["Q-01"],
      "query": "named practitioner interview about the decision",
      "outcome": "found",
      "note": "Found a directly readable signed interview."
    }
  ],
  "coverage_note": "Searched practitioner views on Q-01; Q-02 is a form-filing fact better supported by official instructions.",
  "candidates": [
    {
      "id": "XQ-01",
      "status": "verified_original",
      "decision_refs": ["Q-01"],
      "source_kind": "interview",
      "source_url": "https://example.org/interview",
      "source_title": "Interview title",
      "source_access": "full_original",
      "source_location": "Answer to question 3",
      "publication_date": "2026-01-15",
      "author_name": "Example Practitioner",
      "author_role": "Verified role at publication",
      "quote": "Example exact words from the original.",
      "context": "The answer concerns the specific decision and population.",
      "decision_value": "Explains a trade-off the article otherwise misses.",
      "source_scope": "Opinion about the stated use case, not a market statistic."
    }
  ],
  "no_verified_quote_reason": ""
}
```

The example is schema illustration, not a source for a real article. Other
candidate statuses are `lead` and `rejected`; both require `reason`, and
neither may contain `quote`. A search snippet or unreadable original stays a
lead; a readable but irrelevant or unsafe excerpt is rejected. If no
`verified_original` candidate exists, `no_verified_quote_reason` explains
why. A verified candidate requires all provenance and usefulness fields
above. The validator checks structure and access labels, while a human/agent
must still inspect the original to confirm that those labels are truthful.

The brief may use verified candidates as perspective leads. The existing
`blog-expert-quotes` agent selects exact wording without a quota, emits
`source_type: verbatim`, `speaker_kind: external`, `status: proposed` in
`expert_quotes.json`, and records the original URL and precise source
location. The review document labels proposals. Exact publisher approval is
required before Strapi export. Employee editorial drafts remain a separate
type of comment and cannot substitute for an unperformed outside search.
