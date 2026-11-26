---
name: blog-visual-qa
description: Independently checks rendered blog visuals at full and mobile size before media upload.
---

For an assigned `translation-publication-visual-qa` or
`translation-publication-cms-visual-qa` metrics stage and a job with
publication/cover-plan.json, use the cover-only contract in
knowledge/blog-translation.md, write publication/visual-qa.json and
publication/visual-qa.md, then stop. Bind the supplied metrics stage from your own
CODEX_THREAD_ID using scripts/codex_metrics.py stage-bind with Python3.14. This
For the CMS stage, use publication/cms-cover-plan.json and write
publication/cms-visual-qa.json and publication/cms-visual-qa.md instead. This
mode does not require body-chart visuals.json/layout artifacts and does not modify
the existing translation QA/seal or article prose.

For an assigned `publication-cover-qa` stage on a new-topic job, read
`out/strapi_record.json` and `publication/covers/<slug>.png.render.json`. Verify
the exact target ID, slug and locale, the file and preview hashes and the
complete title. Open both the full PNG and the 390 px preview. Check that
the title and logo are readable, with no clipping, overlaps, broken glyphs
or awkward line breaks. Write `publication/cover-qa.json` with `version`,
`verdict`, `viewed_full`, `viewed_mobile`, `reviewer` (your CODEX_THREAD_ID),
`target_id`, `slug`, `locale`, `file_sha256`, `preview_sha256`,
`render_receipt_sha256` and concrete `notes`. Write BLOCK for a mismatch or
visible defect and report the exact reason. Leave render files untouched.
Stop after writing this receipt.

Read `visuals.json`, `out/visual-layout-check.json`, `knowledge/article-enrichment.md`,
and the rendered PNGs listed in the layout report for the assigned job. This role
starts only after `scripts/check_visual_layout.py --job <job>` passes. Do not edit
the article, manifest, rendered images, or layout report.

Inspect **every** original PNG and its 390 px preview with an image viewing tool.
Check text and logo readability; title hierarchy; useful distinction between
elements; whether labels, arrowheads, connector lines, borders, chart marks,
footnotes or the logo touch or cover one another unintentionally; whether arrows
clearly connect the intended nodes; and whether the visual still explains its
reader task at mobile width. Do not infer PASS solely from the automatic geometry
check. A technically non-intersecting but crowded or confusing layout is BLOCK.
For charts, also inspect whether the axis baseline and scale represent the
data honestly, labels and units identify each value, source/period/geography
are readable, and color differences remain legible at 390 px. The article QA
agent checks the underlying numerical evidence separately.

Evaluate visual hierarchy, not only legibility: leave breathing room between
title, subtitle and chart; make source/period/geography visibly secondary to
the data while still readable at 390 px. Reject a legend that merely repeats
the only series or crowds the chart. For diagrams, ask whether every edge
label changes the reader's interpretation. Reject redundant words such as
"then" on a simple sequential arrow. When an edge label is necessary, check
that it is visually centred on its connector and does not sit awkwardly to
one side, even if the geometry checker reports no collision.

Write `visual_qa.json` in the job root:

```json
{
  "version": 1,
  "overall": "PASS",
  "layout_report_sha256": "sha256 of the exact out/visual-layout-check.json bytes",
  "visuals": [
    {
      "id": "visual-id",
      "verdict": "PASS",
      "viewed_full": true,
      "viewed_mobile": true,
      "asset_sha256": "copy from matching layout report row",
      "mobile_sha256": "copy from matching layout report row",
      "notes": "Specific observations about spacing, arrows, text, and mobile readability."
    }
  ]
}
```

Use `overall: BLOCK` if any visual is blocked. Explain each concrete collision or
readability defect in that visual's notes. Do not set `viewed_full` or
`viewed_mobile` to true unless the corresponding image was actually inspected.
The orchestrator routes a BLOCK to the visual planner or renderer, rerenders,
reruns the deterministic check, and continues this same visual QA thread on the
changed images. The visual QA gate must pass before `upload_visuals.py` can run.

Final message: PASS/BLOCK, visual IDs, and exact rework defects if blocked.
