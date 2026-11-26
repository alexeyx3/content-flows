# Selected brief obligations through delivery

Only new-topic jobs explicitly carrying `batch_delivery_contract_version: 1` in
job.yaml use this contract. Absent flag, refresh and translation jobs are no-ops.
Do not activate or migrate a job as part of validation. Use the existing strategy,
evidence, writer, editor and native QA roles; add no research agent or stage.

This contract preserves concrete obligations selected in the approved brief:
particular tables, internal navigation, source qualifications, wording or another
specific deliverable. It does not turn every heading, discovered source or example
into an obligation. There are no word, heading, table, link or source quotas.
`tables: yes` permits Markdown tables; by itself it does not require a table.

## Strategy: extract what the selected brief actually promises

Add a compact `delivery_checks` list to sections.json. IDs are stable, unique
`DLV-xx`; retain them through targeted rework. `section_id` is the approved H2 ID.
`kind` is `table`, `internal_link`, `source_qualifier`, `wording` or `other`.
`requirement` names the concrete selected deliverable, without drafting its prose
or inventing a fact. `basis` quotes the actual brief beneath its exact H1–H4
heading. This is traceability, not proof that the selection is justified.

```json
"delivery_checks": [{
  "id": "DLV-01",
  "section_id": "comparison",
  "kind": "table",
  "requirement": "Deliver the selected comparison table with the approved distinctions.",
  "basis": {
    "brief_heading": "Selected decision tools",
    "brief_excerpt": "Use a comparison table for the selected distinctions."
  },
  "evidence_required": true
}]
```

`evidence_required` is a required boolean. Use true for factual/numerical
obligations in any kind; it must be true for `source_qualifier`. Use false only
for a nonfactual formatting, wording or navigation obligation. Keep the selection
small by relevance, not by an invented limit. Never manufacture an obligation or
a source qualification just to populate the list. If review finds no additional
selected obligations, use an empty list plus:

```json
"delivery_checks": [],
"delivery_review": {
  "reviewer": "<native strategy specialist ID>",
  "no_additional_obligations": "<explicit explanation after reviewing this selected brief>"
}
```

This empty-selection marker records native specialist review, not human approval;
it creates no additional permission checkpoint or claim that a person approved it.
The normal publisher brief checkpoint approves the selected plan. This file does
not grant approval or replace it. A substantive requirement change returns to the
normal checkpoint; do not silently erase a check to make QA pass.

## Evidence: use existing claim rows and preserve scope

Read every selected delivery check during the existing evidence pass. Append
`delivery_check_ids` to the standard evidence.md table, with comma-separated DLV
IDs for related claims and `-` otherwise; keep all other columns and policies.
Every evidence-required check needs mapped `supports`/`partial` rows containing
the actual claim, source URL and supporting quote. Rejected/unverified evidence
cannot fulfil the map. Keep source locations and the material population,
jurisdiction, period, denominator, unit, definitions, exceptions and uncertainty
in claim/supporting_quote. Verify a number together with its qualifications.
An unresolved factual obligation goes back before writing, never into prose as
an invented value or an unqualified generalization.

This mapping does not change source tiers, publication-link permissions or the
existing source-policy gate. Required sources still go in the final Sources list;
the existing internal-navigation exception remains. A selected internal link uses
an allowed address from config/site-urls.json, not a newly invented destination.

## Writer and editor: deliver and preserve the selected result

For the current H2 and its full subtree, consult its selected checks and evidence.
Deliver the promised table, navigation, wording or other result naturally, without
expanding the approved structure by habit. Preserve every material qualification
in tables, captions, summaries and FAQs as well as body paragraphs. Report an
unsupported or contradictory requirement to its original specialist; do not
silently omit it, invent support or replace it with generic surrounding prose.

During the normal meaning comparison, the editor checks that each selected
deliverable survived assembly and editing. Fix a concrete omission in the
existing targeted rework loop. Do not add a second full editing pass or optional
polish because a check exists.

## Native QA: one complete audit in the existing review

The same native reviewer producing qa_report.md inspects every selected check
against the final materialized edited.md and evidence. Add exactly one line
`delivery_reviewer: <native QA thread ID>` to qa_report.md and create
qa_delivery.json. Compute SHA256 from exact file bytes after writing the report;
do not estimate hashes. Do not let an API writer/critic self-certify this audit.

```json
{
  "schema_version": 1,
  "reviewer": "<same native QA thread ID>",
  "article_sha256": "<edited.md SHA256>",
  "input_sha256": {
    "brief.md": "<SHA256>",
    "sections.json": "<SHA256>",
    "evidence.md": "<SHA256>",
    "qa_report.md": "<SHA256>"
  },
  "summary": "<what this reviewer checked, including a reviewed empty selection>",
  "checks": [{
    "id": "DLV-01",
    "verdict": "PASS",
    "article_heading": "<actual approved H2/H3/H4 title>",
    "article_excerpt": "<actual contiguous article excerpt; may include a whole table>",
    "evidence_ids": ["E-01"],
    "reason": "<why the selected requirement and material qualifications are fulfilled>"
  }]
}
```

Record every ID exactly once, including nonfactual checks. `evidence_ids` may be
empty only when evidence is not required; any included IDs must map to that check.
The actual heading/excerpt must lie within the check's assigned approved H2 and
its subtree. Use `BLOCK` and an actual observed excerpt/heading with a concrete
missing-result reason for an unresolved obligation; absent output is itself a
BLOCK, not a fabricated excerpt. Record its location in the targeted rework item.
An audit cannot pass with BLOCK, missing IDs or an invented location. An empty
selection still requires the same native review, current hashes and checks `[]`.
Use the original reviewer for targeted re-checks and regenerate the audit for
current bytes. A formatting, evidence or report change makes the old audit stale.

## Deterministic gates and limits

`scripts/delivery_contract.py --job <job> --target brief|inputs|qa` is read-only.
Brief validation checks schema and actual selected-brief references. Input and
writer gates additionally require supported factual mappings before drafting.
Final QA, seal-qa and direct review/Strapi export require the complete current
same-reviewer audit. The existing QA receipt additionally fingerprints brief.md
and qa_delivery.json only for enabled jobs; changing either invalidates its seal.
The final audit is not required before writing, when edited.md does not yet exist.

A script PASS proves schema, reference/excerpt presence and hash currency. It
cannot prove that a table answers the decision, a phrase is natural, a source
entails a number or all material qualifications survived. Those are native QA
judgments. No new contract grants CMS/upload/publication permission or replaces
the existing source, legal, review or publication gates.
