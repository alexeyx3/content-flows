---
name: blog-research-map
description: Identifies the reader decisions that all parallel research specialists must investigate before the article brief.
---

Read the assigned job's `job.yaml`, `semantics.csv`, `serp.serp_synthesis.md`,
`serp.hybrid_outline.md` when present, and `audience.reddit.md` when present.
Read `knowledge/positioning.md` and `knowledge/icp-jtbd.md`.

Write only `research_map.json` in the job. Do not draft headings or article prose.
For each distinct material decision, record a stable `Q-xx` ID, the reader's
question, the action they need to take, the relevant population, and the
outcome or mechanism that would help answer it. Include affected worker and
operator perspectives when relevant. The map is compact: combine questions
that genuinely share one evidence need, but do not omit a distinct decision to
make the research shorter. Identify adjacent outcomes that may add value if
the direct statistic is unavailable. Search results from the four SERP markets
are discovery context, not an instruction to write about those countries.

JSON shape:

```json
{"version": 1, "decisions": [
  {"id": "Q-01", "question": "Which arrangement applies?",
   "reader_action": "Choose a route before requesting documents",
   "population": "Businesses and affected workers",
   "outcome": "Comparable implementation consequences"}
]}
```

Run `python3 scripts/validate_research_map.py --job <job>` before returning.
This is the short prerequisite for four independent research specialists; do
not perform their document, study or quotation searches yourself.
