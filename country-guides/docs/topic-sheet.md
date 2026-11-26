# Topic sheet

The topic sheet is the human-maintained list of candidate countries behind the queue. **No script
of this flow reads or writes the sheet.** The flow runs from `config/queue.json`, which you build
from the sheet by hand; the `topic_sheet` value in that file is only a pointer to the sheet for
people. The orchestrator may read one tab of the sheet during a job (EOR semantics, see below) if a
spreadsheet connection is available in the session; without it, the job records the missing
semantics and continues.

Three names are referenced by the instructions and should exist exactly as written: the column
«Example Co in country» (`knowledge/guides-rules.md` section 6), the tab «Semantics by page» and
its row IDs `eor-<iso>` (the skill's stage 1b). Everything else below is a suggested layout that
maps one-to-one onto the queue fields.

## Set-up

1. Create a Google Sheet with two tabs: a country tab (any title, one row per country) and a tab
   titled «Semantics by page». Row 1 of each tab is the header.
2. If you want the orchestrator to read the semantics tab, share the sheet with the service account
   from `vendor/blog/config/google-service-account.json` (Viewer access is enough) or connect a
   spreadsheet tool to the session.
3. Put the sheet ID into `topic_sheet` in `config/queue.json`.

## Country tab

| Column | Who fills it | What it holds | Queue field |
|---|---|---|---|
| `Country` | you | The country name in English as it appears in the H1 («Hiring in Germany»). | `name` |
| `Slug` | you | Lower-case kebab-case address segment (`united-kingdom`). | `slug` |
| `ISO` | you | The country's actual two-letter uppercase ISO code (`GB`, not `UK`). It must be in the CMS `code` enumeration; `check_cms_country.py` checks it. | `iso` |
| `Query name` | you | The country as people type it in search («uk», «germany»); the SERP queries are built from it. | `query_name` |
| `EOR query` | you | The head query of the EOR page, usually «employer of record <country>». | `eor_query` |
| `EOR volume (US)` | you | US search volume of the EOR query's cluster from your keyword export; it orders the queue. Never invented: leave empty if you have no export. | `eor_cluster_us` |
| `Geo key` | you | The SERP market key of the country in `config/geos.json`. | `geo_key` |
| `Example Co in country` | you, from the product's coverage | `yes` when Example Co is available for contractors in this country. Only `yes` countries enter the queue, because the contractors-page ranking puts Example Co first. | — (filter) |
| `ICP` | you | `yes` for a country of strategic interest to the business, for example one where your audience often engages contractors. | `icp` |
| `Pilot` | you | `yes` for a country chosen for a trial run of a new setup (see below). | `pilot` |
| `Order` | you | The position in the queue: by `EOR volume (US)`, with strategic countries moved up as you decide. | `order` |
| `Status` | you, mirrored from the queue | `planned` → `in_progress` → `review` → `published`. | `status` |
| `Notes` | you | Homonyms («Georgia» is also a US state), unusual regimes, anything the orchestrator should know. | — |

`icp` and `pilot` are recorded flags: `new_guide_job.py` copies both into the job's `job.json`,
and no script changes its behaviour because of them. They tell the orchestrator and the publisher
why a country is in the queue and which jobs belong to a trial run.

## Semantics by page

One row per keyword. The orchestrator reads the rows of one country's EOR page and saves them as
`<job>/semantics/eor.csv`; the brief agent reads that file if it exists.

| Column | What it holds |
|---|---|
| `ID` | The page key: `eor-<iso>` in lower case, for example `eor-de`. Rows for other pages may use `country-<iso>` and `contractors-<iso>`, but the skill reads only the EOR rows from the sheet; the country and contractors pages take their semantics from a keyword tool. |
| `Keyword` | The query as exported from your keyword tool. |
| `Volume` | Its search volume, with the market in the header if you keep several (`Volume (US)`). |
| `Notes` | Optional: intent, a homonym, a reason to skip. |

## How a country moves

| Step | Where | What changes |
|---|---|---|
| Candidate added | sheet | A row with `Example Co in country = yes`, the queries, the volume and the flags. |
| Queued | `config/queue.json` | You add the entry with `status: planned` and its `order`. |
| Job created | `new_guide_job.py` | Checks the ISO code against the live CMS schema first; on PASS sets `status: in_progress`. |
| Sent to review | orchestrator | Sets `status: review` once the three pages have passed QA and the review documents or previews are delivered. |
| Published | orchestrator | Sets `status: published` after the authorized CMS write and the read-back. |

Mirror the status in the sheet by hand if you use the sheet to track progress. For the first run
of a new setup, mark three countries `pilot: yes` that test the template from different ends: one
with the densest facts and the heaviest search results, one with thin results, and one with an
unusual regime (free zones, a zero income tax). Skip a country whose ISO code the CMS does not
accept rather than changing the CMS or substituting another code.
