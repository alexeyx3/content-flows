# Country guides on example.com — binding rules for every guide-* agent

Section: `https://example.com/guides/<slug>/`. Each country has THREE pages, three Strapi records:

| page id | URL | H1 | job folder |
|---|---|---|---|
| `country` | `/guides/<slug>/` | `Hiring in <Country>` (set by the site, not by us) | `pages/guide-<slug>/` |
| `eor` | `/guides/<slug>/employer-of-record/` | `Employer of Record in <Country>` | `pages/guide-<slug>-eor/` |
| `contractors` | `/guides/<slug>/independent-contractors/` | `Hiring contractors in <Country>` | `pages/guide-<slug>-contractors/` |

English only. The pages must be MORE useful and MORE complete than anything in the search
results for the country: new research, new interpretations of data the top already quotes,
calculations, dated changes, thresholds and sources. A page that merely re-synthesises the top
is a failure even if it is accurate.

Design behind these rules: `docs/country-guides-flow.md` (flow), `docs/country-guides-spec.md`
and `docs/country-guides-editor-guide.md` (template).

## 1. What the site renders itself — never write it

Header with flag, date, author, editor, share, AI summary; the eight header figures (country page
only); the one-line disclaimer «General information, not legal or tax advice…» above the body;
the table of contents (built from H2); the banner; «More guides in <region>» links. The body
starts after the H1 — `edited.md` keeps ONE `# H1` line that the converter strips.

## 2. Positioning (company's own site, company voice)

This is an informational reference section on the company's own site.

- The product rules apply (full card: `knowledge/product-positioning.md`, «Naming & category»
  and §1).
- Country vocabulary describes the country: employee, employer, payroll, salary, payment, bank
  transfer, notice. Example Co itself is never called a staffing agency, a marketplace, an
  employer of record, a law firm or legal adviser, a payment provider or a payroll provider.
- Example Co is named as «Example Co». Product: Example Workspace. Category formula, in full at
  most once per page: «software for companies that work with independent contractors abroad:
  agreements, invoices and approvals in one place»; after that short variants in turn (contractor
  agreements, contractor paperwork, work with contractors abroad). The labels «freelancer
  management system», «contractor compliance platform» and «global workforce platform» are never
  used for Example Co.
- «Agent of Record» describes a market arrangement. It may explain how such an arrangement works
  («under an agent of record arrangement a third party signs the agreements and collects the
  invoices on the company's behalf»); it is never a product name and never a label for Example Co.
  The only permitted negation about Example Co: «Example Co is not an employer of record».
- **Invoice approval belongs in the description of Example Co** — the opening paragraph and the
  ranking — not in every sentence. Rotate invoice approval / approvals / sign-off; with «invoice»
  already in the sentence write just «approval». Who uses it: finance and operations teams and, in
  a small company, the founder who handles contractor paperwork personally — never a product for
  the contractor alone. What it keeps, «agreements from templates, e-signature and a document
  trail per contractor», and «exports to accounting software» at most once per page each. Coverage
  «contractors in 60+ countries» at most once per page, never a list of regions. Price only where
  the text describes price, verbatim from the pricing page: «from $25 per active contractor per
  month, charged only for months with an approved invoice; no setup fee» — never «cheap», «free»
  or «low-cost», never «per seat».
- Never next to Example Co: speed claims (instant, same-day, in minutes; at most «in a few
  steps»); guarantees (audit-proof, fully compliant, risk-free — write «helps keep contractor
  documents in order»); handling money as an Example Co function (pays contractors, sends or
  holds money — write «the invoice is approved for payment; the company pays through its own bank
  or payment service»); onboarding as an Example Co function (write «collecting the contractor's
  details and a signed agreement before work starts»); superlatives without a public source (best,
  leading, number one); customer counts or growth figures not published on the site; conversational
  or hedged tone. Vary wording: one formulation repeated through the page reads as a template.
- The EOR page is educational: how the model works in the country. No «we do EOR», no hint of a
  future Example Co product, no roadmap or product dates of any kind.
- Example Co appears in the body only where it carries a fact: the contractors-page ranking and,
  once near the opening, a short explanation written from both sides, when current first-party
  coverage supports that country: «companies can sign agreements with and approve invoices from
  independent contractors in <Country> in Example Co, and contractors based in <Country> can work
  with clients abroad». Never «Example Co works with contractors in <Country>» — it reads as if
  the contractors were Example Co's own.
  Keep this part of the reading flow, without a catalogue of features or repeated product names.
  On EOR pages, explicitly limit this route to genuinely independent services. Use at most one
  useful product link in this paragraph. No CTAs in the body — the site renders the banner.
- Brands listed in `config/stop-brands.json` are never mentioned anywhere: text, tables, the
  ranking, Sources, links, meta, images. The list is empty by default.
- Vendor liability: never state as fact that a vendor or an arrangement (agent of record, employer
  of record, any platform) «takes on / assumes / carries liability», «indemnifies», «eliminates
  risk» or «guarantees compliance». Correct form: say who the contracting party is under the
  arrangement; whether any liability moves depends on the contract's indemnification clause.
  Vendor claims only as attributed quotes («Northwind says…»).
- No legal advice framed as certainty about the reader's case. State the rule, the threshold, the
  source; the site disclaimer covers the rest.
- No dates as freshness markers («As of October 2026»). Dates belong to facts: effective dates,
  «since 1 January 2026», entries in Recent changes. The page shows its own update date.
- Competitor numbers that are wrong are an INTERNAL finding (the «Top audit (internal)» section of
  `research/angle.md`). The page states the correct figure with its source; it never names a
  competitor as wrong.
- Zero outbound links to competitors (EOR/contractor vendors). Their URLs live only in internal
  files. Exception: none — the ranking cites vendor facts by name without links.

## 3. Structure

### 3.1 Core — always present, always in this order

**country** (H2 wording may be adapted to the country, the topic may not be dropped):
1. *(no heading)* direct answer, 2–3 sentences: how a foreign company can hire here.
2. Three ways to hire in <Country> — routes table (see 3.4).
3. The labour market — cities, H3 «Salary reference points» table.
4. Registering as an employer, step by step — table Step / What happens / Takes + total.
5. Hiring and onboarding — H3 legal limits, H3 onboarding checklist.
6. Minimum wage
7. Taxes and contributions — with H3 «What an employee actually costs you».
8. Working time and overtime
9. Leave, sick pay and parental leave
10. Termination: notice and payments
11. Recent changes — dated list.
12. What a mistake costs and who pays — table Party / Risk / Amount.
13. Questions people actually ask — FAQ.
14. Sources — always last.

**eor**:
1. *(no heading)* direct answer.
2. What an employer of record is — one sentence + link to the Example Co glossary term.
3. Is an employer of record legal in <Country> — how the model qualifies under local law.
4. The provider licence, and how to check it — registry URL if one exists; if no licence regime
   exists, say so and what to check instead.
5. Who signs what — client / EOR / employee table.
6. Hiring step by step, with real timings.
7. What it costs, line by line.
8. Where the model runs out — maximum duration, permanent establishment, IP, non-compete, penalties.
9. When you do not need it here — including «can I hire directly without an entity».
10. Alternatives, and when each fits.
11. How to choose a provider — questions to ask.
12. Questions people actually ask — FAQ.
13. Sources.

**contractors**:
1. *(no heading)* direct answer.
2. Where the line runs — employee vs contractor tests.
3. Where contractor status breaks — thresholds table.
4. How a contractor is registered here — forms and what each means for the client.
5. The contract: what must be in it — H3 clauses, H3 ending the contract.
6. What a contractor must produce to get paid — invoice requirements, tax IDs, VAT.
7. How the money actually arrives — country reference: local rails, currency, FX, who pays fees.
   Never as an Example Co service.
8. Payment terms and late payment.
9. What breaks, and at which step.
10. What a mistake costs and who pays.
11. Models and when each fits — incl. moving a contractor to employment.
12. One contractor versus ten.
13. Who works with contractors in <Country> — the ranking (section 6).
14. Questions people actually ask — FAQ.
15. Sources.

### 3.2 Additional sections — encouraged

Any section that the search results or the research show to be useful may be added, including
new H2s: public holidays, 13th salary and bonuses, visas and work permits, regional differences,
sector collective agreements, special tax regimes (IT parks, flat-tax regimes, small-business
schemes), how work is done here (only verifiable norms), anything the top answers and we must
answer better. The brief decides the place. Core order stays readable: additions go next to the
core section they extend, never between FAQ and Sources.

### 3.3 Unique block

Every page carries at least one block no neighbouring country page has — a country-specific
regime, threshold, registry, recent law or calculation. The brief names it.

### 3.4 Fixed formats

- **Fact tables**: headerless, three columns — what | value | short source name. Markdown first
  row `| | | |`. Example: `| Current rate | €13.90 / hour — since 1 January 2026 | BMAS |`.
- **Comparison tables** (routes, who pays, who signs, ranking): with a header row.
- **Routes table** on the country page: three rows (Your own entity / Employer of record /
  Contractor), columns «Route | Legal employer | What you pay on top of salary | How you end it».
  The contribution rate and notice period equal the header fields exactly. Route names link to
  the subpages: `/guides/<slug>/employer-of-record/`, `/guides/<slug>/independent-contractors/`.
- **FAQ**: a clear H2 such as «Frequently asked questions» or «Questions people actually ask»;
  the label is editable during humanization. Each question is an H3, with an answer paragraph of 2–4
  sentences with a figure where one exists. 4–8 real questions (PAA, related searches, AI Overview,
  Reddit), phrased the way people ask them.
- **Sources**: H2 «Sources», numbered list, one entry per URL in order of first visible use — a link in the
  text, a visual citing it, or its short name in a table cell, whichever comes first
  (`scripts/order_sources.py` renumbers it):
  `1. Publisher. [Document title](https://exact-page-with-the-figure). Accessed <D Month YYYY>.`
  The access date is the `accessed` / `last_checked` date of the fact or evidence row — never today's
  date by default and never a date from an example.
  During prepublication review, an unpublished same-country guide used only for internal
  navigation may instead say `Draft reviewed <D Month YYYY>.`, using its actual local review
  date. Keep its unpublished-route provenance in internal notes. This exception never applies
  to factual originals or vendor evidence. Before publication, verify the destination is live
  and replace the draft-review label with the actual access date; repeat affected QA.
  Every URL used in the body appears here, as does every original supporting a factual claim,
  even when the claim has no inline link. Sources without a visible citation follow the visibly
  cited entries in stable order. Keep the fact/source-to-section mapping in running_state.md;
  absence of an inline link never weakens the evidence requirement.
  Parentheses inside a URL are written %28 / %29
  (a raw «)» ends a Markdown link early). Vendor pages behind the ranking are listed WITHOUT a
  link (zero outbound links to competitors): `Northwind. Contractors in Germany (northwind.example/…). Accessed <D Month YYYY>.` Link to the page that carries the figure, never the
  home page. Short source names in table cells match a Sources entry. When one publisher has
  several originals, use a document-specific label and repeat that unique alias as a final
  parenthetical in the bibliography title if needed; retain the original title, URL and date.
  Audit first visible use manually before final QA, including relative internal links and each
  component of compound table citations. A successful sorter run is not that audit.
- Headings H2–H4 only. Tables and lists are Markdown. No HTML.
- Visual markers `[[VISUAL:<id>]]` on their own line, once each, where visuals.json says.

## 4. Numbers

- Every number comes from `facts.json` (IDs `F-…`), `derived.json` (IDs `C-…`) or the job's
  evidence (IDs `E-…`). There is no other source. A number not in these files is a fabrication.
- The eight header fields in facts.json appear in the country page body **character for
  character** (minimumWage, averageSalary, incomeTax, paidLeave, publicHolidays, probation,
  noticePeriod; employerContributions as a percentage with the same decimals, e.g. `12.5%`). `check_guide.py` enforces it.
  Exception for the evidenced fixed-levy model in facts-schema: use its exact short
  `display` label in the body and routes table, never a fictitious `0%` headline.
  This permits truthful review materials; CMS publication remains blocked until
  the country header can display fixed levies.
- Subpages do not introduce their own versions of root figures. Where the subpage needs one, it
  uses the same value from facts.json.
- Currency: local currency with symbol or ISO code, as in facts.json. Conversions only from
  derived.json with the stated rate and date.

## 5. Subpages vs the country page

Subpages may cover the same topic as the country page (e.g. notice periods on the EOR page) when
their model changes the answer or the reader needs it there. They write such passages from
scratch, in their own words, for their model, and link to the country page for the full table.
Copying paragraphs or table blocks between the three pages is forbidden; small overlaps are fine.
`text_overlap.py` flags runs of 20+ identical words; QA judges whether they are a real repeat.
The same applies across countries: shared skeleton yes, shared sentences no.

## 6. Ranking — «Who works with contractors in <Country>» (contractors page only)

- Example Co is first, in every country where Example Co is available. Availability is recorded
  per country in the topic sheet (column «Example Co in country», `docs/topic-sheet.md`); only
  countries marked `yes` enter the queue.
- **Equal terms for every entry.** Whatever aspect the ranking describes for Example Co — who
  uses it (finance and operations teams, a founder), agreements from templates and e-signature,
  invoice approval, exports to accounting software, the published price — the same aspect is
  filled for every vendor from its own pages, or marked «not published». No column or note that
  exists only for Example Co. For Example Co the wording and the verbatim price follow section 2;
  speed claims and superlatives stay out for everyone.
- Broader than any ranking found in this country's search results (check serp rankings in
  `serp/rankings.md`); never a padded standard top-10. Every entry is a genuine option for hiring
  contractors in this country.
- Columns describe what changes by country: model (contractor management software / agent of
  record / EOR / marketplace / invoicing tool), entity or registered presence in the country,
  contracts under local law or in the local language, IP assignment in the standard contract,
  local documents supported (e.g. invoice format, e-invoicing), classification support.
  Unknown = «not published».
- Each entry gets a short note that is specific to THIS country. If the note could move to another
  country unchanged, it is not good enough.
- Vendor facts come from the vendor's own page (with access date) via evidence. No third-party
  ranking sites as sources. Negative claims about a vendor need a product/pricing page or an
  independent review, never a slogan or the absence of a mention.
- No ranking on the EOR page.
- If the project keeps its own vendor cards under `companies/`, they are research memory, never a
  source by themselves, and the notes do not copy their sentences: same facts are fine, same
  sentences are not.

## 7. Visuals

At least 2–3 per page wherever verified data exists; no ceiling. A visual may duplicate a table
(minimum wage by year: table and line chart) — the table always stays, because search engines and
AI assistants do not read text inside images. Types: bar, line, process, decision (renderer of
the blog, brand colours, brand font and original logo from `vendor/brand/`). Every data point and node cites F-/C-/E- IDs.
Catalogue:

| page | candidates |
|---|---|
| country | minimum wage by year (line); employer cost at 2–3 salary levels (bar, series = cost parts or totals); notice period by tenure (bar); employer registration timeline (process); salaries by role (bar) |
| eor | client–EOR–employee contracts (process); EOR hiring steps with timings (process); EOR cost vs own entity (bar); «do you need an EOR here» (decision) |
| contractors | classification test (decision); status thresholds (bar or process); from contract to paid invoice (process); who pays for a mistake (bar) |

Labels short — the renderer refuses to truncate. Title, alt, caption ≤255 characters each.

On guide pages, captions use compact numbered references to the page's Sources section,
instead of repeating long linked bibliographies under each image. Every original stays in
Sources and visuals.json. After Sources are renumbered, refresh the references with
`package_article.py --bind-visuals` before recording the humanization hash or sealing QA.

## 8. Quotes

Only verbatim quotes from external practitioners (local law firms, tax advisers, chambers,
associations, regulators' officials) whose original was opened and read: exact words ≤25 words,
name, role, organisation, date, URL, location in the source. No staff comments, no invented or
paraphrased quotes. A quote explains a decision or a trade-off; it never proves a fact by itself.
Format in Markdown:

```
> exact words
>
> — Name, Role, Organisation
```

The original goes into Sources.

Prefer quotes published in English. A quote in the local language may be used in our English
translation, marked in the attribution: `— Name, Role, Organisation (translated from German)`.
The evidence row keeps the original words; the translation must not add or soften anything.

## 9. Sources and evidence

Priority: law and official gazette → ministry, tax authority, social insurance, labour inspectorate,
central bank, statistics office → Big Four and law firms → vendors only about themselves. Never:
content farms, third-party «best EOR» rankings, AI-generated aggregators, competitors' country
guides as a source of a country fact (they are leads; open the original). Local-language official
pages are preferred over English summaries. Every value has an access date. If a figure cannot be
confirmed at an official or professional source, it is not written.

## 10. Writing

- Answer first: every section opens with its answer in one plain sentence.
- Paragraphs follow one coherent thought, normally 2–4 connected sentences. There is no 40-word
  ceiling or minimum length. Do not split a rule, its conditions and its consequence into tiny
  paragraphs merely to meet a word count. Short paragraphs are fine when the thought is complete;
  split a long block at a real change of subject. Enumerations become useful lists. Second person
  to the employer. A machine word-count warning is a review prompt, not a demand to split.
- Links serve the reader, not the fact checker. The opening uses relevant internal links to this
  country's EOR/contractor pages; do not send its basic hiring choices to a law firm's article or
  a legal PDF. Normally leave external citations out of the opening. In later sections, link a
  registry, form or specific official provision when opening it helps the reader act or inspect
  the rule. Keep professional interpretation and other supporting originals in Sources rather
  than turning each fact or qualification into an anchor. Avoid multiple links per sentence,
  repeated destinations and long underlined phrases. Evidence and full source coverage stay mandatory.
- Concrete over generic: thresholds, amounts, deadlines, registries, form names in the local
  language with an English gloss on first use (e.g. «Betriebsnummer (employer number)»).
- No SEO talk (queries, SERPs, «other guides»), no verification narration («the page states»,
  «we confirmed via»), no research artefacts (HTTP codes), no instruction echo.
- No AI patterns: «it's not X, it's Y», forced triples, inflated significance, «in today's world»,
  «it's important to note», rhetorical-question headings, emoji. Apply skill humanizer.
- Headings answer the reader's question; do not build every heading on one template.
- Run a separate whole-page humanization pass after materializing images and before
  final QA. Keep `humanization_report.md` with concrete examples and the reviewed
  `edited.md` SHA-256; repeat affected checks after later edits. Editorial AI-Scores
  are judgments, not detector measurements, and never substitute for independent QA.
- The editor, humanization pass and QA must also assess the whole-page reading experience:
  paragraph continuity, link clutter, abrupt fragment-like blocks and repetitive cards. Clean
  individual sentences alone do not make a page ready to publish.
- Use ordinary Markdown bullets for checklists. The CMS path does not render GFM
  task-list tokens (`- [ ]`) as checkboxes; do not publish literal `[ ]` brackets.
- In prose, use `employer of record` or `EOR` consistently. URL slugs retain their
  hyphens. Prefer a concrete country heading such as `How an employer of record
  works in Portugal` over `What an employer of record is, in Portuguese terms`.
- Internal links only from `config/site-links.json`: the country page and subpages of this
  country, guides hub `/guides/`, glossary terms, relevant blog posts. With trailing slash.
