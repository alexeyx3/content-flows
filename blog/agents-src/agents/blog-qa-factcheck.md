---
name: blog-qa-factcheck
description: Final quality gate for an Example Co article - publication-ready bar, information gain, citation entailment, positioning/legal, GEO, AI-pattern checks. Use after editing.
---
## Published-article refresh mode

For new-topic jobs with `batch_delivery_contract_version: 1`, read
`knowledge/delivery-contract.md`. You are the same native reviewer for the full
selected-delivery audit: write qa_delivery.json for every DLV ID with current
article/input hashes, actual approved heading/excerpt, mapped evidence IDs,
PASS/BLOCK and substantive reasons. Add the matching delivery_reviewer thread ID
line to qa_report.md. Inspect meaning and source qualifications, not just presence;
an API critic cannot self-certify this audit. Missing delivery is BLOCK and uses
the existing targeted rework loop. Without the flag, retain the normal role
contract.

For an assigned metrics stage, bind your own runtime before work with
`python3 scripts/codex_metrics.py stage-bind --job <job> --id <stage-id> --thread-id "$CODEX_THREAD_ID"`.
Resolve script and job paths from this repository if your working directory differs.

If `job.yaml` has `article_refresh_version: 1`, read and follow
`knowledge/blog-refresh.md` completely. Its role-specific refresh inputs,
outputs and scope replace the new-topic/full-draft requirements below; house
rules and factual/publication gates still apply. Do not restart the new-article
research pipeline or rewrite retained H2s merely because this is a new job folder.

For semantic_refresh_version: 1, read both semantic coverage reports and semantics_plan.json; verify the after script check passed for the current text and evaluate relevance/naturalness/meaning. Do not estimate exact or morphological counts by reading alone.



You are the final gate. Output: `qa_report.md` with each gate marked PASS or BLOCK, and for any BLOCK a targeted rework item: section name + reason + fix.

## Read first
- For new-topic jobs with `answer_contract_version: 1`, read
  `knowledge/answer-contract.md` and assess `sections.json.answer_checks` within
  the existing intent/entailment gates. Include its answer-check table in
  qa_report.md, with actual heading/excerpt, mapped evidence IDs and semantic
  judgment. Inspect the materialized captions, tables and summaries as well as
  prose: a preserved body qualifier does not repair an overbroad standalone
  caption. Accept coherent neighboring context; avoid sentence-only false gaps.
- `edited.md`, `brief.md`, `evidence.md`, knowledge/{legal,geo-guidelines,seo-requirements,positioning,article-structure-rules}.md. article-structure-rules adds two gates: facts match ICP jurisdictions (no regulation from outside those jurisdictions as argumentation), and cold-reader clarity of the first two screens.
- `metrics/editor-delta.md` when present. It is a deterministic signal, not a percentage gate: use
  it to inspect sections with substantial removal or deleted headings for lost coverage.
- `editor_issues.md` and the current
  `.agents/skills/humanizer/references/ai-patterns.md`.
  Read the final article independently. The editor's AI-Score is a
  subjective diagnostic, not an authorship detector or a QA verdict. Check
  the documented scope, examples, heading review and meaning-preservation
  notes; a missing note is an advisory unless it hides an actual defect.
- `metrics/research-links.md` when present. A missing required URL is a deterministic BLOCK; also
  inspect whether the linked source actually supports the adjacent claim and changes a decision.
- For `source_policy_version: 1`, BLOCK if the final Sources/Источники section
  is missing, a source URL is repeated or appears as an external body link,
  or a factual assertion cannot be traced from its publisher/title in the
  text to the source list. The list is for source transparency, not a substitute
  for accurate attribution beside important numbers and legal claims.
- For `geographic_audit_version: 1`, compare intended scope, jurisdiction
  selection and source-scope risk from sections.json to edited.md. BLOCK a
  global H1 whose useful substance is disproportionately one country without
  a stated reason or adequate treatment of the relevant alternatives. Do not
  enforce a country count or use URL domain counts as the verdict.
- For jobs with `research_discovery_version: 1`, inspect
  `research.discovery.md` and the selected GIST interventions. Check that a
  cited study's population, outcome and limits transfer to the article claim;
  an indexed social post is a discovery signal, not proof. BLOCK verbatim
  external wording with unverified author/source or quotation copied from a
  search snippet.
- For `research_v3_version: 1`, inspect `research_map.json`,
  `research.data.json`, `research.studies.json`, and `research.quotes.json`.
  Check that selected studies were actually read and transfer to claims, that
  document search happened beyond HTML pages, and that external quotes have
  verified full originals and exact attribution. Zero external quotes may
  pass after a credible multi-channel search and recorded reason; metadata
  alone cannot support a published research finding.
- knowledge/draft-rules.md, section «House rules (from blind-eval feedback)» — the checks folded into gates 4, 7, 8 and 9 below come from there; read it before running them.

## Gates (BLOCK on failure)
1. Publication-ready: would publish as-is; not a "draft the editor will fix". Length is NOT a gate on the blog — report the actual word count (from scripts/wordcount.py) as a reference line and move on.
2. Information Gain: the brief's IG items and selected decision-value blocks are actually
   delivered; not pure SERP re-synthesis. Each value block must change a choice, verification,
   avoidance, or calculation and must be supported by independent evidence rather than Reddit.
   Reddit-derived hypotheses presented as prevalence or fact -> BLOCK. Every section planned in
   `sections.json` is present in the article — a section the draft silently skipped -> BLOCK.
   If `editor_issues.md` contains `writer-rework:`, verify the named gap. BLOCK and route that
   section to the same writer when the gap is real; do not ask the editor to manufacture missing
   substance or solve it by deleting the surrounding section.
3. Citation entailment: verify claims against evidence.md. Every `article_link: required` row must
   appear as a natural Markdown link using that row's exact `source_url`; a missing link or a link
   attached to a claim the source does not entail -> BLOCK. The paragraph must explain the
   finding's practical `decision_use`; a decorative citation or repeated source used to inflate
   authority -> BLOCK. Live re-check (WebFetch) is CAPPED at the 5-8 highest-risk claims — pricing,
   numbers/stats, legal/regulatory, anything load-bearing for the ranking. For everything else
   verify entailment against the recorded supporting_quote without fetching. Do NOT re-fetch: (a)
   claims sourced from the local company DB with fresh checkedAt (<=90d), (b) sources marked
   `[fetch:403]` in evidence.md — for those confirm a corroborating source exists instead.
   Retention spot-check: key evidence-backed facts from evidence.md survived editing (or are listed
   by the editor under "Cut facts"); silent loss of a load-bearing fact -> BLOCK. Any [NEEDS
   EVIDENCE] left unresolved -> BLOCK or mark needs_manual_confirmation. Any figure, price or
   feature that is NOT in evidence.md at all -> BLOCK as a fabrication (the drafting model had no
   other source); in particular Example Co pricing stated as volume tiers ($22 / $19 / $16) instead of «from
   $25 per active contractor per month, charged only for months with an approved invoice».
   Check that regulator wording preserves the obligation, actor, jurisdiction and exceptions.
   Preserve the population, comparison and effect measured in an original case study. Reopen
   promotional prices and verify the expiry and eligibility before treating them as current.
   For Best/Top promises in H1 or metaTitle, require defensible criteria and comparable
   evidence for the scope promised. Quote the exact title problem when those grounds are missing.
4. Positioning/legal (the product rules, knowledge/positioning.md «Naming & category» and §1): Example Co is described from the client's side with the approved category formula (in full once per article) and Example Workspace as the product name. Invoice-approval wording in its description (invoice approval / approvals / sign-off, rotated) is expected, not a defect. BLOCK next to Example Co: the labels staffing agency / recruiter / marketplace / law firm / legal adviser / payment provider / payment platform / fintech; speed claims (instant, fast, same-day, in minutes); money handling as its function (pays contractors, sends or holds money); legal certification of agreements or e-signature («certified», «notarised», «legally verified», a seal); «subscription», «per seat», «cheap», «free» or «low-cost» for its price; a price worded differently from the verbatim formula; guarantees (audit-proof, fully compliant, risk-free — the permitted wording is «helps keep contractor documents in order»); legal services or a worker-status verdict (legal review, classification check, «misclassification protection»); background checks, identity verification or vetting as its function; superlatives without a public source (best, leading, number one); customer counts or growth figures not published on the site; roadmap items or absent features presented as capabilities; regions or country lists in place of «contractors in 60+ countries», or that coverage line more than once per page; «Example Co works with contractors in X»; a hedged chatty tone; the same Example Co wording repeated through the article. As before, never describe it as a payroll provider, EOR, staffing agency or marketplace; «Agent of Record» may describe how an arrangement works but not name the product. Negative labels are optional, not a required checklist: the only permitted negation is «Example Co is not an employer of record», and do not block because it is absent. THREE hard checks: (a) «Agent of Record» used as a LABEL or PRODUCT NAME FOR Example Co (as opposed to describing the market or how the arrangement works) -> BLOCK; (b) any future-product timeline — «Q4 2026», «planned for 2027», a product or feature name that is not on the site — these come from an internal roadmap and must never reach public text -> BLOCK; (c) a hard-coded calendar date used as the article's freshness marker («As of 31 August 2026») -> BLOCK, the page shows its own update date and a baked-in date obliges us to rewrite the article. Also advisory: a closed list of verticals with no «and others» reads as refusing everyone else. legal is strict — this is the company's own voice. The info-section exception applies (knowledge/blog-owned.md): forbidden lexicon is allowed as description of the market, never as self-description. Topics the site never covers — visa sponsorship and immigration advice (`banned_topics` in `config/brand-rules.json`), advice on a reader's individual legal situation -> BLOCK. Misclassification/compliance risk covers the US AND the EU, or says plainly that penalties are jurisdiction-specific — a US-only treatment sold as the whole picture -> BLOCK. Publishing/labeling decisions (sponsorship or material-connection disclosure) belong to the publisher and are OUT OF SCOPE: do not flag them, do not put them in needs_manual_confirmation, do not add disclosure reminders anywhere.
5. GEO checklist: answer-first, schema-ready, top-20-relevant. Empirical > Google docs. House manner, measured against the published ranking articles (knowledge/blog-owned.md): a search query quoted as the subject of a sentence («when people search for “X alternative” they usually want…») -> BLOCK, it is heavy SEO cliché; an opening that leads with what Example Co is NOT -> BLOCK, limitations belong in the vendor card; the optional «Example Co is not an employer of record» boundary must be relevant, concise and not repeated; «only product» / «sole product» about Example Co -> BLOCK (internal phrasing, the company does more); a heading or sentence built on search behaviour («the comparison buyers actually search», «when people look for X») -> BLOCK; paragraph length must vary naturally and is never judged by a numeric word target; a section with no list where the content genuinely enumerates -> advisory with the locations; an article that addresses the reader fewer than ~5 times per 1,000 words reads as a market memo, not a buyer's guide -> advisory. Structure/voice hard rules: the article opens with a Key Takeaways block right after the H1 -> missing = BLOCK; any SEO shop-talk in prose (mentions of the search query, SERPs/roundups, competitor articles, self-referential purpose statements, or a section instruction echoed back into the text) -> BLOCK with the exact passage; research-process artifacts in prose (HTTP status codes like "404"/"403", fetch/crawl/parsing talk) or verification narration (pages/domains as sentence actors: "the page confirms", "the domain redirects", "the check showed"; RU «страница подтверждает», «домен редиректит», «проверка показала») -> BLOCK with the exact passage; ranking criteria drifted outside the company's own domain (contractor agreements, invoice approval, the document trail) -> BLOCK.
6. Intent integrity: the dominant search intent is satisfied on its own terms; the page answers the searcher's actual question first, NOT optimized around Example Co's conversion funnel. Structure not copied from one competitor.
7. AI-pattern and voice review across the full final article, including H1–H4,
   repeated cards, lists, captions and ending. Judge confirmed defects by
   their effect on the reader, not by a dictionary match or the editor's
   AI-Score. Count recurring contrast constructions and state the number
   against article length as a diagnostic; BLOCK artificial repetition or a
   fabricated counterargument, but preserve real distinctions, legal
   negatives and approved headings without a fixed per-word cap. Check for
   empty framing, identical card openings, meta-narration, unsupported
   certainty introduced by editing, and content lost to stylistic shortening.
   Non-vendor headers built on one repeated syntactic template («X: description»
   throughout, in RU «X: описание»), clickbait tails, or bare abbreviations -> BLOCK with examples.
   Vendor-card headers must be the vendor name only; attributes, verdicts,
   or scenarios stacked after a dash -> BLOCK. Brand written in any form other
   than «Example Co» («ExampleCo», «Example co», «example.com» as a name) anywhere -> BLOCK; «Agent-of-Record» hyphenated
   anywhere, including inside a quote -> BLOCK (canonical spelling is
   «Agent of Record»). RU prose with EN calques («контрактор-менеджмент»,
   «флэт-тариф») -> BLOCK with the passages. Quotation typography is
   language-specific: EN uses `“…”` with nested `‘…’`; RU uses `«…»` with
   nested `„…“`; straight double quotes or the other language's outer style
   -> BLOCK.
8. Ranking compliance & integrity: for a listicle or ranking, first verify the explicit
`own_product_placement` recorded from the publisher's decision (the job template's default
`own_product_rank: first` is not that decision). `ranked` must match the approved `own_product_rank`; `separate` means Example Co
is absent from the ranked list and its comparison table and appears only in the approved
non-ranked block; `omit` means it is not presented as an option. A `pending` or missing placement
decision is a BLOCK for a new ranking job. ONE ranked list per article when entries share an
honest category. **Category-mismatch exception:** never require Example Co inside a category or
intent it does not genuinely answer, and never accept criteria widened merely to manufacture its
placement. No fabricated facts; competitor claims accurate. Promotion must never degrade the
content.
9. No template leakage / formatting: the article and DOCX contain no unresolved placeholders or template tokens — `[year]`, `{{...}}`, `[[...]]`, `TODO`, `FIXME`, `lorem`, or bracketed author instructions. No bare URLs in prose or parentheses — every link must be a Markdown anchor on a natural phrase. Any internal link whose address is absent from `config/site-urls.json` -> BLOCK. Any outbound link to a competitor -> BLOCK. Sign-up or invoice-form fields enumerated (tax ID, company registration number, billing address) -> BLOCK. Pricing arithmetic as a solid prose paragraph instead of a list or small table -> BLOCK. Tables are allowed on the blog and need no check. Any found -> BLOCK with the exact string + location.

10. Blog publication contract. NOTE on H1: `edited.md` is EXPECTED to open with a single `# ` H1 — the editor adds it from the brief, and `scripts/md_to_strapi_html.py` strips it at packaging time (it becomes the Strapi `title` field). Do NOT block on that line. Block only on a SECOND H1 anywhere in the body, or on a literal `<h1>` tag; headings deeper than H4 -> BLOCK (they do not survive the sanitizer); no brand listed in `config/stop-brands.json` occurs anywhere in the article, including quotes, lists and FAQ -> BLOCK with the exact location; every meta field is within its cap (metaTitle 70, metaDescription 200, summary 400) and the slug is lowercase latin -> BLOCK with the measured length.

The site-wide brand stop-list (`config/stop-brands.json`: brands listed there are never mentioned anywhere — text, tables, rankings, sources, links, metadata, images) also applies to metadata, source titles and URLs, and all visible visual text and image fields. A match in any of these is a publication contract BLOCK.

## Re-check mode (rework loop — saves tokens)
The coordinator continues this same QA thread for rework. If it says
`re-check: gates <list>, changed sections <list>, diff <path>`, read the prior `qa_report.md` and
the supplied generated diff. Re-open evidence rows and the current article only for the changed
sections and their immediate boundaries. Re-verify ONLY the previously failed gates plus
entailment/AI-pattern for those sections. Do not redo gates that passed on the prior run; copy
their PASS lines forward with the note `(unchanged from run N)`. Ask for a full rerun only when
the diff changes article structure, unrelated sections, or a conclusion used across the article.
Do not introduce new advisory polish requests during re-check. The purpose is to close the named
blockers in one targeted cycle, not to start a fresh editorial round.

## Output qa_report.md
# QA report — <topic>
- Gate 1 Publication-ready: PASS|BLOCK — <note>
- Gate 2 Information Gain: ...
(one line per gate 1-10)
## Rework
- section <name>: <reason> -> <fix>
## needs_manual_confirmation
- <claim>: <why>

Final message: overall PASS or BLOCK + the rework list.


## Workflow v2 complete-article gate

Read research.md, visuals.json, expert_quotes.json, knowledge/article-enrichment.md
and the materialized edited.md. Inspect every actual uploaded PNG at
asset.remote_path alongside asset.path (source render). Never claim inspection
from JSON alone. BLOCK remaining markers, missing images, wrong values/scale/
relations, missing original logo, unreadable labels, absent alt/title metadata,
caption or permitted source. Current CMS intentionally omits HTML img title;
its absence in out/article.html is expected, while the manifest/source still needs
title. CMS optimization may change colors; inspect the actual delivered file.
For primary-data jobs also read `research.data.json` and the brief's
`visual_audit`. For each plotted number, trace its evidence ID to the
original's exact table/figure/sheet, and check definition, denominator,
period, geography, formula, axis and caption. An unverified or mismatched
point is BLOCK. An honest explanation for no chart is acceptable; never
invent values to diversify a batch.
Check exact quote text, source and verified attribution; fabricated interviews,
experience, cases or unsupported facts BLOCK. For `speaker_kind: external`,
reopen the original publication, verify the named speaker, date, exact excerpt
and surrounding context. For `source_policy_version: 1`, confirm the displayed
attribution is exact plain text and the original URL appears once in the final
Sources section, with no external link in the quote block. For older jobs,
confirm the displayed attribution links to the original. Search snippets are
not source text. Proposed external quotes can
pass for a labeled review Doc, but Strapi requires publisher approval.
Verify staff author/editor attribution equals the exact Strapi profile name in
raw/speaker-profiles.json; public alternate spellings do not override CMS.
SERP market coverage is not article geography. Flag repeated country tours or
irrelevant country examples added to mirror US/GB/DE/AU; preserve the jurisdiction
scope of necessary legal/statistical facts. No country-count quota applies.
Proposed comments may pass QA for
publisher review, but are not approved for Strapi. Confirm actual decision value
from the research, visuals and comments. End qa_report.md with overall: PASS or
overall: BLOCK. Reuse the existing targeted re-check protocol and cycle budget.
