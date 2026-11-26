# Topic sheet

The blog takes topics from one Google Sheet and writes every article's state back to its row.
The sheet is the source of truth for topic order and lifecycle. Reading is always safe; every
command that changes a cell previews by default and writes only with `--apply`.

## Set-up

1. Create a Google Sheet and import `config/topic-sheet-template.csv` as a tab. Row 1 is the
   header. The four data rows show a topic at each stage (not started, in progress, in review,
   published); delete them and add your own topics in the order you want them written.
2. Share the sheet with the service account whose key is `config/google-service-account.json`
   (Editor access).
3. Put the sheet ID, the tab's `gid` and the exact tab title into `config/temnik.json`. Scripts
   refuse to run when the tab title differs from the configured one.
4. Run `python3 scripts/temnik.py setup --apply` once: it adds the skip-reason column if missing.

Scripts find columns by header text, so column order is free and you may add columns of your own.
Header names below are exact.

## Columns of the main tab

| Column | Filled by | What it holds |
|---|---|---|
| `Cluster ID` | you | Stable row key, unique in the tab. Required format: `b-` plus exactly four digits (`b-0123`). Jobs store it as `temnik_cluster_id` and every command locates the row by it; the hybrid writer (`blog_openrouter.py`) accepts only this format, because it matches batch approval items, jobs and the cost receipts of each article by this ID. |
| `Topic` | you | Working title of the topic. |
| `Top keyword` | you | Primary search query. |
| `Article type` | `ready` | Type recorded in the job (guide, comparison, ranking and so on). |
| `Language` | `ready` | Language recorded in the job, lower case. |
| `Action` | `start`, `skip` | `new` when an article is started; `duplicate` or `skip` when a topic is rejected. |
| `own_product_rank` | `start` | Publisher's decision on the own product recorded in the job. |
| `Author` | `start` | Author recorded in the job (CMS username). |
| `Status` | all commands | empty → `in progress` → `written` → `in review` → `published`. |
| `Our Title`, `Our Description`, `Our H1` | `ready` | Final metadata of the article. |
| `Our URL` | `publish`, `skip --duplicate` | The live URL; for a duplicate, the existing page that already covers the topic. |
| `Google Doc` | `review` | URL of the review document. |
| `Start date`, `Ready date`, `Publication date` | `start`, `ready`, `publish` | Lifecycle dates. |
| `Publication URL` | `publish` | Live URL, written after the live page is verified. |
| `Skip reason` | `skip` | Why a topic was skipped or which page it duplicates. |
| `Google: indexing`, `Google: reason`, `Google: checked`, `Google: canonical`, `Google: last crawl` | `blog_monitor.py` | Result of the latest URL Inspection of the published page. |
| `Refresh: selection` | `blog_monitor.py` | Whether the page is eligible for a refresh (a page that is not indexed is skipped). |
| `Refresh: cycle`, `Refresh: version`, `Refresh: status`, `Refresh: Google Doc`, `Refresh: date`, `Refresh: note`, `Refresh: published`, `Refresh: next check` | `blog_refresh.py` | State of the current refresh of a published article. |

## How a row moves

| Command | Writes |
|---|---|
| `temnik.py next --limit 10` | nothing; lists unprocessed rows in sheet order |
| `temnik.py preflight …` | nothing; searches published pages and local jobs for the topic |
| `temnik.py skip --cluster-id <id> --reason "<why>"` (add `--duplicate --url <page>` for a duplicate) | `Action=skip` or `duplicate`, `Skip reason`, for a duplicate `Our URL` |
| `temnik.py start --cluster-id <id> --job jobs/<job>` | `Action=new`, `own_product_rank`, `Author`, `Status=in progress`, `Start date` |
| `temnik.py ready --job jobs/<job>` | title, description, H1, `Article type`, `Language`, `Ready date`, `Status=written` |
| `temnik.py review --job jobs/<job> --google-doc <url>` | `Google Doc`, `Status=in review` |
| `temnik.py publish --job jobs/<job>` | verifies the live page, then `Our URL`, `Publication URL`, `Publication date`, `Status=published` |

Topics are taken strictly in sheet order. A later row is not started while an earlier unprocessed
row has not been evaluated; every skipped or duplicate row gets a specific reason.

## Other tabs

`blog_monitor.py` and `blog_refresh.py` create and maintain two more tabs in the same sheet:

| Tab | Purpose |
|---|---|
| `Blog refreshes` | One row per published article: refresh status, review document, date updated on the site, next content check, Google and Bing indexing, cycle. |
| `Refresh history` | Append-only log of completed refresh cycles. |

Index status values written by the monitor: `Indexed`, `Not indexed`, `Different canonical`,
`Unknown`, `Check unavailable`. An unavailable check is recorded as unknown and the page is
skipped; it is never treated as "not indexed".
