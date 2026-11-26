# Question, qualified fact and actual answer

For new-topic jobs with `answer_contract_version: 1`, use the existing strategy,
evidence, writer, editor and QA stages. No new agent, full-text triplet extraction,
graph database or extra rewriting pass. Refresh and translation jobs retain their
own contracts. Existing jobs are not migrated; an absent flag is a no-op.

In finished articles the defects this check typically catches are a heading/answer
mismatch and a qualifier broadened in a materialized caption, while most other
checks duplicate existing controls. This supports a compact
decision-led check, not a claim of ranking gains or measured quota savings.

## Strategy: specify the answer before the wording

Add `answer_checks` to sections.json for load-bearing reader decisions, concrete
FAQ promises, responsibility allocations and consequential numerical/contract
claims. Use the smallest useful set; do not create a check for every sentence or
force one check/H2 per question. Do not introduce facts before evidence.

```
"answer_checks": [{
  "id": "A-01",
  "section_id": "existing-h2-id",
  "question": "Who is responsible under the arrangement being discussed?",
  "answer_needed": "Identify the responsible party and applicable arrangement, or explain the specific unresolved dependency without claiming a universal answer.",
  "qualifiers": ["arrangement type", "jurisdiction", "material exception"]
}]
```

IDs are unique `A-xx`. section_id references the approved H2. question is the
reader's actual question; answer_needed describes what would answer it, not a
preferred keyword, conclusion or invented value. qualifiers names dimensions
to verify; it may be empty where none are material. Keep Q-ID research questions
as the existing discovery map; this is the selected final-answer contract.

## Evidence: connect the existing atomic claims

Append `answer_check_ids` to the normal evidence.md claim table. Use comma-separated
A-IDs for a related claim and `-` for other evidence. Keep the existing columns
and one row per claim. All selected checks need mapped supports/partial rows with
an actual source and supporting quote before writing. Rejected rows are audit trail,
not coverage. Do not lower the evidence standard to fill an ID.

Express actor → action/relation → object/result in the claim's natural wording.
Keep material conditions, exceptions, negation, modality, jurisdiction, period,
denominator and counterparty in claim/supporting_quote; preserve exact source
locations where available. Do not duplicate every claim into three more columns.
Bare triples do not capture these qualifications. A real unknown needs a bounded,
supported account of what the source establishes and leaves unresolved; silence
is not evidence of absent product capability. If the planned answer cannot be
supported, route the gap back before drafting. A substantive change to the
approved question/coverage still needs the normal publisher checkpoint.

## Writing and editing: preserve the result the reader needs

Give the substantive answer early where natural. It can span a coherent paragraph,
neighboring paragraph or a table with clear headers; it need not fit one sentence
or a fixed word order. Define the actor before using an ambiguous pronoun.
Do not force every sentence into an identical subject–verb–object template.

During the existing meaning comparison, distinguish a supported paragraph from an
answered question: explaining classification factors does not by itself identify
the payer promised by a "Who pays?" heading. Do not invent an answer to fix this.
Preserve fact qualifiers through the edit and every format change. In particular,
check captions, diagram labels, tables, summaries and FAQs after visual binding:
accurate body prose does not automatically repair an overbroad standalone caption.

## QA: record the semantic judgment in the existing report

Inspect every selected check in the normal QA pass. Add a table to qa_report.md:

`answer_check_id | evidence_ids | article_heading | article_excerpt | verdict | note`

Use one row per A-ID, existing mapped claim IDs, the exact actual H2/H3/H4 title,
and an exact contiguous excerpt of edited.md (escape literal pipes as `\|`). A
complete table or paragraph is a valid excerpt. The answer may be elsewhere than
the initially assigned H2 when context/cross-reference makes it clear; record its
actual location rather than demanding repetition. The note explains answer
completeness and material qualifications, not just occurrence of a phrase.

PASS means the selected question is answered within the evidence's scope. NOTE
records a non-blocking limitation without inventing certainty; explain why the
reader's promised result is still met. A missing promised answer, unsupported
allocation or lost material condition is BLOCK and goes to its original specialist.
Use the existing targeted rework/diff loop; no second full QA without a structural
or unrelated change. Do not add optional polish during re-check.

## Deterministic checks and their limits

`scripts/answer_contract.py --job <job> --target brief|inputs|qa` checks schema,
section/claim references, evidence mapping and whether QA's quoted excerpt really
occurs under its stated heading. Brief validation and writer inputs use the first
two checks; QA sealing and review/Strapi export also require the final mapping.
The existing QA fingerprint already binds sections.json, evidence.md, edited.md
and qa_report.md. No new receipt is needed.

A script PASS proves neither entailment nor semantic completeness. Those remain
independent QA judgments. An ID link cannot prove that a condition survived, and
an AI detector score cannot prove natural language or accurate meaning.

Always block material factual, attribution or publication defects. Treat answer
clarity as editorial judgment. Treat word counts, keyword density, term coverage,
sentence rhythm, passive voice, competitor percentiles and entity order as optional
diagnostics, never as imported numeric gates or quotas. Do not copy competitors'
sentence skeletons or optimize anchors to an invented length. This adaptation
uses the practical fact/answer discipline of the supplied triplets presentation;
its ranking claims, betting examples, click manipulation and arbitrary thresholds
are not adopted as rules for the Example Co blog.
