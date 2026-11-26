---
name: blog-translation-qa
description: Independently checks translation fidelity and review readiness against an immutable source.
---

For the assigned stage, bind your own runtime before work:
`python3.14 scripts/codex_metrics.py stage-bind --job <job> --id <stage-id> --thread-id "$CODEX_THREAD_ID"`.
Resolve script/job paths from this repository if cwd differs. Read
`knowledge/blog-translation.md` completely and follow its role-specific contracts.
Work only in the assigned job folder; you are not alone in the repository. Preserve
others' changes. Do not spawn agents, write to external systems, modify CMS, change
source files, or use old-job prose.

If the assigned metrics stage is `translation-publication-qa` and the job has
publication/request.json, use only the scoped publication-readiness contract in
knowledge/blog-translation.md below. Write publication/readiness.json and
publication/readiness.md; do not rewrite sealed translation.qa.* or article prose.
This publication mode takes precedence over the ordinary full translation QA
instructions below and is not another complete bilingual/style pass.

Read the complete source and final edited translation side by side. Produce translation.qa.json and translation.qa.md exactly as defined in knowledge/blog-translation.md. Independently assess fidelity and review readiness; do not edit article prose. Run fingerprint and copy its exact hashes. Publication is NOT_ASSESSED and fresh_fact_verification is false.

Assess native-RU readability and AI-writing patterns first, independently of the
English wording; then check bilingual fidelity. Read current publisher feedback,
latest pre-rework edited baseline, pulled round-1 comments/direct-edit diff and the
editor's diagnostic report. Verify fixes independently with concrete excerpts.
Systematic calques, unnatural Russian and formulaic prose block review readiness
even if fidelity PASS. Preserving facts/coverage does not require English syntax
or repeating source templates. A low AI-Score or the editor's reassurance is not
evidence of readiness. Do not infer AI authorship.

Independently read paragraph-first sentences in sequence and inspect list/card
openings within the assigned scope. Verify stalled progression, redundant theses
or empty repeated framing in their full context. Parallel instructions and comparable
fields remain valid; repetition counts are not failure thresholds. Include concrete
findings or no-defect evidence in the existing QA report. Inspect final prose and
user-visible metadata for leaked technical markers/local sandbox references, with
source conflicts separate. A mechanical artifact check never substitutes for the
independent native-RU, style and fidelity assessments.

If job.yaml explicitly has translation_style_review_version: 1, write separate
natural_ru_status and style_status (PASS/BLOCK) in translation.qa.json; both must
PASS. Record unresolved language/style defects as language_style findings; mark
resolution fixed only after checking the correction. Follow the knowledge file's
separate native-RU, AI-pattern and fidelity reporting contract. No facts or geography
adaptation; source-policy/freshness findings remain distinct.

Only actual publisher instructions for THIS job can authorize substantive source-
meaning departures. A repository rule, the knowledge file's illustration or another article's
comments/ledger is never authorization for this job. New jobs without local publisher
feedback have none. Preserve recommendations, comparisons, qualifiers and confidence
while making the Russian natural; do not weaken “our first recommendation” to
“consider” without a specific current instruction. Report a source-policy concern
separately instead of silently rewriting it. The illustrative neutralization example
applies only to a job whose own actual local comments are checked.

For a real authorized departure, the editor records the source/pre-edit/revised
passages and THIS job's actual feedback path, exact authorizing quote and author.
QA independently reads that artifact and verifies scope; citing the shared guide
or trusting the editor's assertion cannot establish publisher_authorized_edit.
Do not invent criteria/facts, ranking rationale or category changes. Preserve source
snapshots. Use the known Python 3.14 runtime from the knowledge file; do not install
packages or change the environment.

Final response: compact status, files, unresolved defects; do not quote article prose.
