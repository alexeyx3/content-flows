# OpenRouter and Codex hybrid for country guides

The main production route. Settings are in `config/guide-execution.json`.

| Stage | Execution |
|---|---|
| Draft | OpenRouter Responses, OpenAI provider, `gpt-6.1-terra`, medium |
| Substantive editing, repairs and the separate style pass | `guide-editor` in Codex, `gpt-6.2-sol`, medium |
| Independent final QA | `guide-qa` in Codex, `gpt-6.2-sol`, medium |
| Facts, research, source verification, briefs, visuals | The existing Codex roles |
| Coordination | `gpt-6.2-sol`, high |

## Running the author

Finish the fact pack, the calculations, source verification, the briefs and the contracts. Call
`prepare_pages.py`, check the inputs and render the assigned images.
Independent visual QA can run at the same time as writing.

```sh
# Check the plan without a key and without paid requests.
python3 scripts/guide_api.py --job jobs/2026-11-20-example --stage writer --page country
python3 scripts/guide_api.py --job jobs/2026-11-20-example --stage writer --page country --execute
python3 scripts/guide_api.py --job jobs/2026-11-20-example --stage writer --page eor --page contractors --execute
```

Every call is responsible for one section with all its H3/H4. The opening goes as a separate
request. Every request receives the full country packet with the facts, the calculations, all
E/V rows and the research, the full page brief, the visual data and the cards, all previous
sections and the full memory. The code saves new memory entries through append-only
deltas. The explicit boundary of the 30-minute cache sits after the complete stable packet.
The provider receipts keep the real cache data. Image addresses and source numbering in
their export-dependent form are not part of the stable packet.

The country draft serves as context for the subpages if the editor has not yet prepared
`edited.md`. The type and SHA-256 of the context are recorded before the first subpage request is
sent. Repeats are compared against the current final country page.

The API author saves `sections/`, `running_state.md` and `out/draft.md`. The OpenRouter key
`countries` is read by the existing runner only for the call.
The transport pins OpenAI Standard. Before a result is applied, the model
version, the effort, the provider and the reliability of `usage.cost` are checked. A mismatch
stops the stage.

## Editing and release

Assign a separate editor to each page. The editor saves `edited.md` and
`editor_issues.md`. After the `check_guide.py` checks, lint and the materialization of
the verified images, the same editor reads the whole page in a separate pass
and saves `humanization_report.md` with the SHA-256 of the current text. The report needs
specific edits or the reason why no edits were required.

Independent QA receives the original brief, the verified facts, the current packet,
the exact SHA and the result of the style pass. After a confirmed defect the same
editor makes a point edit, then updates the style check. The re-check
is done by the same independent QA. The usual packaging,
QA seal and the publisher's actual approval follow. For publication
the country requirements, the Strapi authorization and a separate check
of the published pages apply. For local review use the verified local
visuals.

## Recovery and actual charges

- A run with the same job, revision and inputs picks up the successful receipts.
  Use `--retry-failed` after you have analysed a specific confirmed failure.
  When a POST result is ambiguous, first find out the status of the call and the charge.
  A change to the main input packet requires a new revision. Old
  frozen API profiles and receipts are kept as history.
- For a confirmed upstream 429 with no generation and no `usage.cost`, stop the
  authors that use the dedicated key. `reconcile_openrouter_429.py --baseline <receipt>`
  compares the key's accumulated spend with the previous exact reconciliation and the sum of all
  confirmed receipts for that interval. When they are equal, it writes separate
  records bound to the response hashes. The original receipts are not changed. Unknown
  timeouts, responses with partial output and discrepancies remain blockers.
- On repeated 429s on long requests, `--compact-packet` removes only two
  reproducible copies from the author's packet. The originals of the shared facts, calculations,
  E/V rows and research, all the previous text and the state remain. The first
  affected section is recorded in `wire-packets/`. The earlier successful sections
  are still verified against their original requests. If visuals were corrected
  after the author started, `--resume-frozen-visuals` keeps the original copy for the
  author as long as the identifiers and the insertion points match. Editing and visual
  QA use the current verified files.
- The standard limit of a revision is $15, the reserve of one call is $8, at most two
  workers. The reserve before a POST acts as the limiter. For a large packet set
  the permitted limit through `--max-call-cost-usd` in a new revision. In the next
  revision `--max-cost-usd` lets you account for what has already been spent. The saved
  profile sets the values on resume.
- `runs/guide-api/<job>/<revision>/usage.writer-by-page.json` sums
  `usage.cost` over the author's receipts, including paid retries, and
  shows the number of unknown charges. `usage.latest.json` and the immutable
  attempt receipts keep the tokens and the provider's summary data.
- In the country's final report add up the actual charges of all its revisions.
  If part of the sum is unknown, show the known part and the number of such attempts.
  Take the Codex limit readings separately, following the instruction in `AGENTS.md`.
  They are observed at account level.

[OpenRouter Responses API](https://openrouter.ai/docs/api/api-reference/responses/create-responses) · [OpenRouter billing](https://openrouter.ai/support)
