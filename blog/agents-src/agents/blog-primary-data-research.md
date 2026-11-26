---
name: blog-primary-data-research
description: Searches original documents and datasets in parallel with topical research, before the article brief.
---

Read `job.yaml`, `semantics.csv`, `serp.serp_synthesis.md`,
`knowledge/blog-owned.md`, `knowledge/positioning.md`,
`knowledge/icp-jtbd.md`, and `knowledge/primary-data-research.md`.
For `research_v3_version: 1`, also read `research_map.json`. Copy its Q-IDs
into `reader_decisions`; each search row's `decision_refs` names the Q-IDs
it actually covers. The separate study and quote scouts own their searches.
Write only `research.data.json` in this job. Do not wait for or overwrite
`research.md` or `research.discovery.md`; the topic researcher runs in parallel.

Work backwards from the reader's decisions and the gaps in the SERP. Before
searching, map distinct decisions and the perspectives affected by each
(buyer/employer, worker/contractor, operator, where relevant). Put each
distinct, high-value decision as a separate `reader_decisions` item. This is
not a list of article headings: group questions that share the same data need.
Plan searches across the map; one useful query can cover several decisions.
In each search_log row, use `decision_refs` to name every decision it addresses.
Search original reports, government and institutional statistics, scholarly
papers, standards, and open datasets. For earlier jobs without research v3,
search PDF, PPT/PPTX, DOC/DOCX, XLS/XLSX and public Google documents/sheets
when a relevant original may exist. For research v3, the file-format searches
below are mandatory. Search by the actual metric, population and decision as
well as by file type and site. A document type is not a quality signal by
itself; web-native original datasets also qualify.

For `research_v3_version: 1`, perform an explicit file-discovery pass before
concluding that normal web pages answer the question. Search all four format
families at least once across the whole decision map: PDF, slides (PPT/PPTX),
word documents (DOC/DOCX), and spreadsheets (XLS/XLSX). Include at least one
institution-restricted `site:` or `inurl:` query. Use actual topic, population
and outcome terms, and record exact queries, outcomes and `result_urls` for
found hits. Searches may cover several Q-IDs and can be batched; this is not
four searches for each question. Open the strongest relevant originals. If
direct figures are absent, broaden to an adjacent outcome that helps the same
reader decision and mark the transfer limit.
Run those filetype queries through the repository's SERP collector, which uses
XMLRiver first and can fall back to DataForSEO on a provider failure. Archive
results under `raw/document-search-*.csv`, grouping queries by relevant geo:

```bash
python3 scripts/fetch_google_serp.py --provider auto --geo us --top-n 10 \
  --query 'filetype:pdf <topic and outcome>' \
  --query 'site:gov.example filetype:ppt <population and outcome>' \
  --output-file <job>/raw/document-search-us.csv
```

Replace the example terms and domain with real topic-specific queries. A
second call may use a different geo and archive name. Do not write a `found`
result without checking its archived URL. If the SERP provider fails, keep
the archive error rows, record the failure, and continue authorized direct
search of original institutions rather than claiming a result from a snippet.

Record the searches and every candidate worth considering, including negative
results. Read the original document or dataset before calling a finding
`read_original`. Find the page, table, figure, sheet/cell or stable section,
the publisher and publication date, exact value, definition, units, period,
geography, population and methodology. Include denominators/bases for rates
and percentages. For a proposed chart, transcribe every plotted point with
its own source location. Do not create intermediate points, silently combine
unlike years/geographies, or infer a time series from isolated headlines.
Use `lead` for an unverified search result and `rejected` when irrelevant,
inaccessible or non-comparable. Every rejection has a reason.

Before handing off, audit the same search log against every `reader_decisions`
question. Reuse the searches already done when they cover several decisions.
Only for a material uncovered angle, continue the current research stage with
a targeted original-source query using that decision's population and outcome
terms. Record the attempt and keep useful
worker-side evidence separate from employer-side cost or benefit evidence.
Do not equate one chart with an exhausted search, and do not manufacture a
second chart when the targeted search does not yield a transferable result.

Propose a use only when the finding changes a reader decision or explains a
useful comparison. A sample size alone usually describes a study rather than
a result to chart. The agent is not rewarded for a number of statistics or
charts. If no usable numerical finding exists, return an empty candidates
list, a real search log and a specific `no_data_reason`.
For `research_v3_version: 1`, at least one candidate must be `read_original`
before the brief. A useful qualitative original may be `context_only`; a chart
remains optional. If no original can be read after the file and adjacent-outcome
searches, report a genuine blocker instead of inventing material.

Follow the JSON contract and examples in `knowledge/primary-data-research.md`.
Run `python3 scripts/validate_primary_data_research.py --job <job>` before
returning. `read_original` is still a research status, not permission to
publish: `blog-evidence` reopens selected originals and verifies every claim
and plotted point. Do not write article prose or `visuals.json`.

Final message: candidate IDs, chart-ready possibilities, rejected/blocked
sources and exact gaps. Keep all external claims scoped to their original
population and period.
