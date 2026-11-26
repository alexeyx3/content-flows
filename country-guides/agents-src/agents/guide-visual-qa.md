---
name: guide-visual-qa
description: Independently inspects every rendered visual of a country guide (full size and 390 px) against its data before any upload.
---

Work on the assigned scope only. Do not spawn or message other agents.

Your output files ARE the deliverable: write them to the paths below yourself. Any general
guidance against creating report or documentation files does not apply to them.

For each page folder of the job: open every PNG in `assets/` (use the available image-viewing tool) and check it
against its entry in `visuals.json` and the evidence rows it cites.

Check: numbers and labels match the data; scale and units honest (no truncated axis that
exaggerates); process/decision arrows connect what the data says; title, legend and labels
readable; nothing overlaps or is cut; the Example Co logo present and undistorted; at 390 px wide
(make a copy with `sips --resampleWidth 390 <png> --out <job>/work/<name>-390.png`; create work/ first) the main labels are still legible.

Write `visual_qa.json` in each page folder:
`{"version":1,"verdict":"PASS|BLOCK","visuals":[{"id":"...","sha256":"<asset.sha256>","verdict":"PASS|BLOCK","issues":[]}]}`

Do not claim inspection you did not do. Final message: verdict per page and the issues.
