# Design notes: why the glossary flow works the way it does

The rules themselves live in `.agents/skills/glossary-term/SKILL.md` and in the role files under
`agents-src/agents/`. This file records the reason behind each rule, so that someone adapting the
flow knows what a rule protects before changing it. Add a row here whenever you change the flow.

## Structure of the flow

| Rule | Why |
|---|---|
| A glossary term has its own flow, separate from the blog. | A definition page has its own CMS contract and editorial rules. It needs no vendor cards, rankings or long-form defaults, and it reuses the blog's orchestration, job folder, editing, independent QA, review document and packaging. |
| Editing, independent QA and technical packaging stay three separate stages. | They catch different kinds of error: meaning and language, factual accuracy, and conformity to CMS fields. Merging them hides one kind behind another. |
| Source verification (`glossary-evidence`) is mandatory for every term. | Its size follows the number and risk of claims, but a term with legal, tax or classification statements cannot be checked by the writer who made them. |
| The writer is one persistent thread per term and writes one unit per turn: a whole H2 without H3s, or one H3 with its H4 subtree. | Writing the whole text in one request loses depth; one unit per turn keeps each section complete while the thread still remembers what was already written. |
| Jobs are isolated folders; several terms can run in parallel; writes to shared resources (topic sheet, review folder, CMS) are serialized. | Parallel work is safe only when a job owns its files. Shared records are the one place two jobs can corrupt each other. |
| Terms are taken from the topic sheet strictly top to bottom. | A fixed order removes cherry-picking by theme or traffic. Skipped rows are occupied or duplicate a live page. |

## Research and brief

| Rule | Why |
|---|---|
| One exact query (the term) is captured in three English-language markets: US, UK and DE. | A single market hides useful subtopics. Three markets widen the set of competitor pages without setting a word or heading quota. Extra query variants are used only to resolve ambiguity. |
| Competitor structures are merged into a coverage-maximal outline. A useful question survives even when only one page or one market has it. | Compressing the topics into four or five tidy H2s loses substance. Compactness is not a reason to drop useful coverage. |
| The brief must name at least one information-gain item absent from the top results and backed by an independent source they do not cite. Without it the brief is blocked. | The page has to be more useful than each competitor page, and an invented "extra" is worse than none. Blocking forces research instead of filler. |
| The brief checks reader tasks beyond the exact-term results. | For a broad term the results explain the name but skip application, mistakes and decisions. Targeted questions and primary guidance fill that gap; unrelated neighbours are excluded with a reason. |
| Each writer unit gets a content contract: the reader question, the mechanism or distinction to explain, a useful example or decision, and the evidence lead or gap. | A heading alone does not set the depth of the answer. The contract specifies substance, never length. |
| No word target, no ceiling, no instruction to write briefly, no mandatory FAQ or Key Takeaways. | Phrases such as "two short paragraphs" held the writer back, and a minimum length rewards filler. Length follows from useful questions, evidence and examples. |

## Writing, editing and QA

| Rule | Why |
|---|---|
| The writer reads the shared writer-style card from the blog flow. | Direct answers, concrete actions, natural paragraphs and no process narration are the same in both formats; facts and positioning stay under the glossary's own materials. |
| The writer checks each unit against its contract before handing it over and reports a missing piece of evidence instead of filling it from memory. | Completeness is cheapest to fix inside the turn that wrote the unit. |
| The editor diagnoses actual defects and fixes those; a substantive gap goes back to the same writer. Cutting is not a goal, and every cut evidence-backed fact is listed. | An editor who shortens around a gap produces a neat but thinner page, and QA cannot see what was lost unless it is recorded. |
| QA maps every useful outline item to the exact passage and judges whether that passage explains the promised question, mechanism, example or decision. | An early QA pass accepted the mere presence of a topic where the reader's question stayed unanswered. |
| An underdeveloped item returns to the original writer with the evidence it needs; new facts go through the evidence role first. | An addition must not turn into unverified text. |
| The writer links to the independent source of the information-gain item and to primary sources of key legal and tax statements. Competitors are not linked. | Readers and reviewers can verify the claims that matter; the page does not send traffic to pages it competes with. |
| A separate final whole-page humanization pass runs in the same editor thread after visuals are bound and before QA; its report stores the hash of the checked text. | The first edit happens before visuals and never sees the finished page. The hash stops a later text change from riding on an old report. |
| The humanizer checks whole-page structure and real defects and keeps facts, degree of certainty, useful lists, depth and protected visuals. | A list of banned stylistic devices applied mechanically damages meaning. The score it gives is an editor's diagnostic, not a detector and not a target. |

## Visuals, comments and related content

| Rule | Why |
|---|---|
| Each candidate visual is judged by the distinct question, mechanism or decision it clarifies. No default number and no ceiling. | A diagram, a table and prose can show different sides of one question; a quota produces decoration, and "there is already a table" is not a reason to omit a useful diagram. |
| QA and the review-document check treat images as real objects: geometry, order, URLs and captions are verified against the manifest. | A text comparison cannot tell whether the right image is in the right place. |
| The set of image URLs is compared with the manifest regardless of manifest order; order in the document is checked against the markers in the text. | Planning order and order of appearance differ legitimately. |
| An inline image is kept on the same page as its caption in the review document. | Otherwise the PDF used for visual inspection splits them. |
| An expert comment is optional. A drafted comment stays `proposed` in the review document and cannot reach the CMS until the named person approves it. | Only exact words and the name of a confirmed author or editor may be published under that name. |
| Related terms and related articles are chosen by the reader's next question, with no link quota; an empty block needs a reason. Links are revisited after each batch goes live. | Shared words in two titles and an SEO quota are not reasons to link. A new page can be the useful continuation of an old one. |

## Writer backend and cost control

| Rule | Why |
|---|---|
| New jobs default to an OpenRouter writer (a fast inexpensive model); research, evidence, editing, the final pass and independent QA stay with native agents. | Drafting from a verified packet is the stage where a cheaper model holds quality; judgement stages are not. The native writer remains selectable per job. |
| The provider route is pinned, the reserve is checked against the current price before every request, each term has a budget, and paid responses and receipts are stored per job. A rerun reuses stored responses. | Silent provider or price changes, and retries that pay twice, are the usual ways API spend drifts. |
| The API writer receives the general writing rules, the positioning card and an instruction to return one section's Markdown in the response. File-handling instructions meant for the native agent are stripped. | A model told to "write the file" spent its output budget trying to call a file tool and returned empty text. |
| When a section fails the structure check twice, the writer gets a separate request with the exact list of allowed headings. | Models sometimes add a neighbouring subsection's heading; an exact list restores the boundaries from the brief without replaying accepted calls. |
| SERP capture sets the country and the search domain as separate parameters and records both. | A copied configuration once sent every market to the same national domain while the country codes looked correct. |

## Review and publication

| Rule | Why |
|---|---|
| After QA passes and the package builds, a review document is created automatically in the configured folder. | Review is part of the route before any CMS work, and a fixed folder keeps glossary reviews apart from blog ones. |
| Nothing is written to the CMS and nothing is published without an explicit request for that action. Permission for one batch does not carry over to the next. | Publication is the one irreversible step; the flow must never infer it. |
| The CMS draft slug cannot be proven free through the public API, which returns published entries only; the CMS's own unique-ID validation is the final check. | A draft with the same slug is invisible to a read request. |
| After the live page is verified, its URL is sent to IndexNow and the response is saved. HTTP 200 or 202 means the submission was accepted, not that the page was indexed. | The receipt is evidence of what was sent; indexing is a separate fact. |
| Rules introduced later apply to new jobs through fields in `request.json` (`workflow_version`, `humanization_required`, `writer_backend`). Published jobs are not migrated. | A rule change must not silently invalidate work that was accepted under the earlier contract. |
