# Primary document and data research for blog articles

Applies to new jobs with `primary_data_research_version: 1`. The
`blog-primary-data-research` agent runs after the SERP packet and in parallel
with `blog-topic-research`. Its output is `research.data.json`. The brief may
select candidates only after both research packets pass their validators.

## Search and editorial standard

Start with a compact map of the reader's distinct high-value decisions and
affected perspectives; make each one a `reader_decisions` item before searching.
These are decision themes, not every article section or subheading. A single
search can cover several decisions when its population and outcome really fit;
record all covered decisions in that search_log row's `decision_refs`. Search original
government/institutional files, research papers, standards, open data and
first-party reports using combinations of the metric, population, jurisdiction,
file type and source domain. PDF, slides, documents and spreadsheets often
contain useful tables that ordinary article results omit. A file extension
alone does not make material authoritative. Record unsuccessful searches;
continue while a specific decision question remains unresolved, then stop
when more sources repeat the same answer or do not transfer to the audience.

For `research_v3_version: 1`, use the shared `research_map.json` Q-IDs as the
`reader_decisions` list and in every search row's `decision_refs`. Actually
search PDF, slide, word-document and spreadsheet families across the map,
with at least one institution-restricted query. Examples adapted from the
publisher's document: `filetype:pdf <question>`,
`site:gov.example filetype:ppt <outcome>`,
`site:edu filetype:doc <population>`, `filetype:xlsx <metric>`.
Adapt source domains and terms; do not repeat every format for every decision.
A found search row records `result_urls` with original URLs, while a `none`
row records what failed. Preserve the exact `filetype:` query so the gate can
distinguish actual document discovery from a generic promise.
Execute these queries with `scripts/fetch_google_serp.py --provider auto`,
which tries XMLRiver first; save CSV under `raw/document-search-*.csv`. The
validator cross-checks filetype queries against that raw SERP archive. If the
provider fails, retain its error row and continue direct source discovery.

If a direct statistic is absent, inspect a nearby decision-useful outcome:
scale, frequency, worker consequences, implementation friction, costs or a
documented process. Zero read originals blocks a v3 job before the brief;
explain a genuine access/source blocker instead of inventing a statistic.
A verified qualitative original may be `context_only` with its exact relevant
passage in `exact_value`. A chart still requires comparable numbers.

Before handing off the packet, audit coverage within this same research stage
across all `reader_decisions`. Reuse searches that already cover more than one
decision. For a material decision without a usable candidate or adequate
search, make a targeted original-source query using its actual population and
outcome terms, and record the result in `search_log`. Include
worker preferences or implementation effects when the topic asks an employer
to choose an arrangement that affects workers; an employer cost comparison
alone does not cover that decision. This is a completeness check, not a quota
of charts or countries. Explain a remaining gap specifically rather than
declaring the candidate pool exhausted after finding one good chart.

Original product data, tests and customer surveys are candidates only when
the actual dataset and its use are authorized and available. Do not manufacture
first-party evidence. Vendor surveys state their sponsor, population and
method; they are not independent market facts. Search snippets, catalogue
metadata and AI-generated summaries are leads only. The original document
must be opened before a candidate can be `read_original`.

An exact statistic needs source URL, publisher, publication date, page/table/
figure/sheet, exact value, definition, unit, period, geography, population,
base or denominator when applicable, method, and transfer risk. For a chart,
every plotted point needs a number, label and its source location. Derived
values need original inputs and formula; the evidence agent verifies both.
Do not add a chart merely because a number exists. A sample size alone is
generally context, not an outcome to graph. Prefer numbers that reveal a
comparison, trend or composition relevant to a decision.

## `research.data.json` contract

The packet is a research handoff, never article evidence. `status` is `lead`,
`read_original`, or `rejected`. `chart_status` is `chartable`, `context_only`,
or `unsuitable`. Only `read_original` candidates can enter the brief, and
`blog-evidence` must reopen them before the writer or visual planner uses them.
`candidates` may be empty when `no_data_reason` explains the search result.

```json
{
  "version": 1,
  "reader_decisions": ["What are the comparable cost components?"],
  "search_log": [
    {"question": "What are the comparable cost components?",
     "decision_refs": ["What are the comparable cost components?"],
     "channel": "official", "query": "site:gov.example filetype:pdf employer costs",
     "outcome": "found", "note": "Original annual schedule, table 2."}
  ],
  "candidates": [
    {"id": "D-01", "status": "read_original",
     "chart_status": "chartable", "question": "How do two comparable cost scenarios differ?",
     "decision_use": "Estimate the statutory layer separately from a provider's fee.",
     "proposed_section": "costs", "visual_type": "bar",
     "source_url": "https://gov.example/report.pdf", "source_title": "Annual costs",
     "publisher": "Official agency", "publication_date": "2026-01-01",
     "file_type": "pdf", "source_location": "p. 12, table 2",
     "unit": "local currency per year", "period": "2026",
     "geography": "named jurisdiction", "population": "defined employer group",
     "denominator": "not applicable", "method": "table values; no derived points",
     "transfer_risk": "Other employer types have different rates.",
     "points": [
       {"label": "Scenario A", "value": 100, "source_location": "p. 12, table 2, row A"},
       {"label": "Scenario B", "value": 150, "source_location": "p. 12, table 2, row B"}
     ]}
  ],
  "no_data_reason": ""
}
```

The example numbers and URL describe format only and must never enter a real
job. `lead` and `rejected` candidates require a `reason`; do not present
them as verified stats. When a read original supports a useful single claim
but not a graph, set `chart_status: context_only`, `visual_type: none`,
`exact_value` and `points: []`. A chartable candidate needs at least two
comparable points. Visual type is a suggestion for the brief, not a command.

The brief records selected and rejected data IDs and why a chart helps or
does not help. `blog-evidence` assigns evidence IDs to selected verified
values, and `blog-visual-planner` uses only those IDs. Article QA and visual
QA check all numbers and labels against the evidence and source, including
calculation, units, scale, date, geography, mobile readability and caption.

Adapted from a publicly shared information-gain method and its published prompt.
The document-mining method is useful; its quota of 20 statistics and DOCX
deliverable do not apply to this article pipeline.
