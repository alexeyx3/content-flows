# Topic sheet

The flow takes its queue from one tab of a Google Sheet and writes each term's progress back to
the same row. `scripts/glossary_temnik.py` is the only script that touches the sheet; it previews
every change and writes only with `--apply`.

## Set-up

1. Create a Google Sheet and import `config/topic-sheet-template.csv` as a tab. Row 1 is the header.
   The four data rows in the template show a row at each stage; delete them and add your own terms.
2. Share the sheet with the service account from `../blog/config/google-service-account.json`
   (Editor access).
3. Put the sheet ID, the tab's `gid` and the exact tab title into `config/temnik.json`. The script
   refuses to run when the tab title differs from the configured one.

## Columns

The script finds columns by header text, so the order is free and extra columns are allowed.
The header names below are exact.

| Column | Who fills it | What it holds |
|---|---|---|
| `Cluster ID` | you | Stable row key, unique in the tab. Saved in the job as `temnik_cluster_id`; the script locates the row by it. |
| `Term` | you | The term as it will appear in H1. |
| `Primary query` | you | The exact search query for the SERP stage. Not read by the script; the orchestrator copies it into `request.json`. |
| `Search volume` | you | Optional, for your own prioritisation. Not read by the script. |
| `Slug` | you | Must equal the job's slug, otherwise the script stops. |
| `Language` | you | Must equal the job's locale (`en`). |
| `Action` | `start` | Set to `new` when the job starts. |
| `Status` | all commands | `in progress` → `in review` → `published`. Empty for a term nobody has taken. |
| `Start date` | `start` | Date the job was launched. |
| `Our Title`, `Our Description`, `Our H1` | `review` | Metadata of the packaged term. |
| `Google Doc` | `review` | URL of the review document. |
| `Ready date` | `review` | Date the text passed QA and went to review. |
| `Publication URL`, `Publication date` | `publish` | Filled after the live page is verified. |

## How rows move

| Command | Allowed current status | Writes |
|---|---|---|
| `glossary_temnik.py start --job <job> --date YYYY-MM-DD` | empty or `in progress` | `Action=new`, `Status=in progress`, `Start date` |
| `glossary_temnik.py review --job <job> --date YYYY-MM-DD` | `in progress` or `in review` | title, description, H1, Google Doc, `Ready date`, `Status=in review` |
| `glossary_temnik.py publish --job <job> --date YYYY-MM-DD` | `in review` or `published` | `Status=published`, `Publication URL`, `Publication date` |

Each command checks the cluster ID, slug and language first and refuses to overwrite a cell that
already holds a different value. Terms are taken top to bottom: skip rows that already have a
status and rows that duplicate a live page, and take the next free one.
