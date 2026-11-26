# Example input files

Fictional, minimal files that show the exact shape the blog scripts and roles expect. Copy them,
then replace every value with your own.

| File | Where it goes | Read by |
|---|---|---|
| [`publisher-proposal.json`](publisher-proposal.json) | `docs/workflow-v2/batches/<batch>/publisher-proposal.json` | `scripts/blog_openrouter.py` (`approved_jobs`), `scripts/openrouter_blog_experiment.py` |
| [`brief-approval.json`](brief-approval.json) | `docs/workflow-v2/batches/<batch>/brief-approval.json` | the same two scripts |
| [`semantics.csv`](semantics.csv) | `jobs/<job>/semantics.csv` | research and brief roles |

`<batch>` is any ID made of letters, digits, `_` and `-`, starting with a letter or digit. The
same ID is passed as `--batch` to `blog_openrouter.py`, and the writer's run files go to
`runs/<batch>/`.

## publisher-proposal.json

The ordered list of articles in one hybrid batch, written by the orchestrator at the publisher
checkpoint after the briefs validate. It is a JSON array; each item is one article:

| Field | Required | What it must contain |
|---|---|---|
| `cluster_id` | yes | The topic-sheet `Cluster ID`, exactly `b-` plus four digits (`b-0123`). It must equal `temnik_cluster_id` in the job's `job.yaml`, and it must be unique in the batch |
| `job` | yes | Repository-relative path of the job folder, directly under `jobs/` |
| `heading` | yes | The approved H1. It must equal `title` in the job's `sections.json` |
| `sections` | yes | The `sections` array of the job's `sections.json`, copied verbatim (every field of every section) |
| `sha256` | yes | SHA-256 hex digests of the job's `brief.md`, `sections.json` and `serp.hybrid_outline.md`, keyed by file name |
| `article_type` | no | The job's article type. Used only when a title amendment is checked (`blog_openrouter.py amend-title`) |

The hashes in the example are placeholders. Compute the real ones from the files the publisher
approved, for example `shasum -a 256 jobs/<job>/brief.md`. If any of the three files, the H1 or
the outline changes after approval, `prepare` stops with "approved H1, outline or brief inputs
changed", and the batch needs a new proposal and approval.

## brief-approval.json

The publisher's approval of that exact proposal, plus the API budget of the batch:

| Field | Required | What it must contain |
|---|---|---|
| `status` | yes | Exactly `approved` |
| `publisher` | yes | Non-empty identity of the person who approved |
| `api_budget_usd` | yes | A number greater than zero: the most the batch may spend on OpenRouter calls. Every prepared phase must fit within it |
| `publisher_proposal_sha256` | yes | SHA-256 of the bytes of `publisher-proposal.json` as saved (`shasum -a 256 docs/workflow-v2/batches/<batch>/publisher-proposal.json`). Re-saving the proposal, even with different whitespace, invalidates the approval |
| `items` | yes | The same array as in `publisher-proposal.json`, value for value |
| `response` | no | The publisher's reply, kept as the record of the decision. The skill asks for it; the scripts do not check it |

The example's `publisher_proposal_sha256` is the real digest of the example proposal file, so the
pair is consistent as shipped.

A later change of an approved H1 and `metaTitle` goes through
`publisher-amendments.json` in the same folder, written by `blog_openrouter.py amend-title`
from a separate approval receipt passed with `--amendment`; the fields it checks are in
`amend_title()` of that script.

## semantics.csv

The query list for one article: the queries the article should answer, with whatever demand data
you have. You fill it in by hand when the job is created, or export it from your keyword tool or
from Search Console and trim it to the topic.

No script parses its columns. The research-map, topic, document, study and quote roles and the
brief role read it as text next to the search results. The brief role treats the first row as a
hypothesis for the primary query and then resolves the real primary query from the search results,
so put the main query first. Keep a header row and one query per row; extra columns are fine.
In a refresh job, `collect_refresh_baseline.py` writes a `semantics.csv` with the columns
`query,clicks,impressions,ctr,position` from the last 28 days of Search Console data for the
page.

The volumes in the example are invented.
