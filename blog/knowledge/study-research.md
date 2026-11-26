# Scholarly-study research for blog articles

Applies only to jobs with `research_v3_version: 1`. The
`blog-study-research` specialist runs after SERP and `research_map.json`, in
parallel with primary-document and external-voice research. It produces
`research.studies.json` for the brief and evidence agent, not publishable
claims. Existing jobs are unchanged.

## Search standard

Use OpenAlex or Crossref to discover works. Search original full text directly
at publishers, university/institutional repositories, government research
sites, and legitimate author pages. The catalogue and direct searches are
complementary: neither metadata nor an abstract proves a result. Search by
the question's population, intervention/condition, and outcome, not merely
the article keyword. Record failures and negative results. Try an accessible
open copy if a DOI landing page does not expose the original. Stop when further
results repeat an answer, lack transfer to the reader, or no credible original
is available; explain the boundary. No minimum paper or statistics count.

Only a full original that the agent actually accessed can have status
`read_original`. For a numerical outcome, describe units, denominator and
period inside `finding`; note the exact page, table, figure or stable section
in `source_location`. A study sample size alone is context, not an article
finding. A read original can still be excluded from the brief when its
population, method or outcome does not transfer. An unread search result is
`lead` or `rejected` and cannot carry a verified finding.

## `research.studies.json` contract

Use Q-IDs from `research_map.json` in `decision_refs`. One search may cover
several decisions. `channel` is `catalogue`, `direct_original`, or
`repository`. A failed catalogue request is `blocked`; the specialist should
continue direct search. `outcome` is `found`, `none`, or `blocked`.

```json
{
  "version": 1,
  "search_log": [
    {"decision_refs": ["Q-01"], "channel": "catalogue",
     "query": "OpenAlex: example population outcome", "outcome": "found",
     "note": "Found a potentially relevant title; full text not in catalogue."},
    {"decision_refs": ["Q-01"], "channel": "repository",
     "query": "site:university.example example population outcome pdf",
     "outcome": "found", "note": "Opened an authorized full-text copy."}
  ],
  "candidates": [
    {"id": "S-01", "decision_refs": ["Q-01"],
     "status": "read_original", "source_url": "https://university.example/study.pdf",
     "original_url": "https://university.example/study.pdf",
     "source_title": "Example study", "authors": "Named authors",
     "publisher": "Journal or institution", "publication_year": 2025,
     "original_access": "full_text", "access_note": "Read the complete PDF",
     "source_location": "p. 8, table 2", "study_design": "Named study design",
     "method": "How the result was measured", "population": "Defined sample",
     "outcome": "Measured outcome", "finding": "Exact scoped result",
     "decision_use": "How this informs Q-01",
     "transfer_status": "usable",
     "transfer_risk": "Why this population may differ from the article reader"}
  ],
  "no_transferable_study_reason": ""
}
```

The example URL and finding are format illustrations only. `lead` and
`rejected` candidates still need `id`, `decision_refs`, `status`,
`source_url`, `source_title`, and `reason`; add available authors, year and
access notes, but do not add `finding`. `no_transferable_study_reason` is
required when no read original is transferable. A read original with no
transferable finding must use `transfer_status: not_transferable` and explain
its limit in `transfer_risk`; do not imply that finding belongs in the article.
`context_only` covers original studies useful for background but not a direct
reader decision. Evidence independently verifies any
study later selected by the brief.
