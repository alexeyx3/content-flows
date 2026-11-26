> Design document. The current run instructions are `AGENTS.md` and `.agents/skills/country-guide/SKILL.md` in the project root; the binding rules are in `knowledge/guides-rules.md`. Where this specification and the rules differ, the rules win.

# Country guides: the specification of the section

What the section is, how its pages and its CMS records are built, and why. How the pages are
produced is in `country-guides-flow.md`; what an editor types where is in
`country-guides-editor-guide.md`.

## Address and structure

The section is `/guides/<country>/`, **a folder per country, three pages**:

```
/guides/<country>/                         ← the root: routing + facts
/guides/<country>/employer-of-record/      ← the EOR model in this country
/guides/<country>/independent-contractors/ ← the model of working with contractors
```

Further in the text the subpages are called `/eor/` and `/contractors/` for brevity: these are
names of the pages, not addresses.

The segments are written as full terms (see «Addresses and headings of the subpages»).

A neutral noun in the section segment (`guides`) was chosen by measurement: in the competitor
research, folders named with a noun returned noticeably more visits per page than folders whose
segment contains a verb. The word «contractors» is not in the root but on a subpage
next to `/eor/` — the root does not change when a new model is added.

Splitting into a fourth and further page (`/taxes/`, `/leave/`) is **not done**.

## What each page does

**The root.** Routing to the two models plus a fact reference: minimum wage,
average salary, contributions, working time, leave, holidays, termination. It targets the
cluster `hire in` / `hiring in <country>`.

The intent is a deliberate decision: this cluster attracts the job seeker as well, and that is
accepted — independent professionals are the other side of the agreements our clients sign,
so their traffic is not waste for us. The consequence: the root earns on fact queries and on
routing, and the queries from the employer's side are picked up by the subpages. Fact blocks
are intent-neutral and take their queries under any framing.

**`/eor/`.** The head commercial query of a country: `employer of record <country>` — the
most expensive traffic in the topic. It is written **educationally**: how the model is set up
in this country, without «we do this».

**`/contractors/`.** The model of working with contractors and our node of irreplaceability:
the thresholds where the status breaks, what a contractor must produce to get paid, who pays
for a mistake. There is almost no search demand at country level (a query such as
`pay contractors in germany` has none), so the page wins not by volume but by being
impossible to copy from a competitor.

## The rule against self-repetition

The facts will be on all three pages, and that creates the risk that the GIST approach calls
self-created redundancy. The rule:

> **A canonical fact lives in the root. A subpage repeats only what its model
> changes.**

This is not bureaucracy but a source of strong nodes: the minimum wage does not apply to a
contractor at all — on `/contractors/` this is not a repeat of the fact but a limit that
competitors do not state.

## What the template takes from the research of competitors' sections

1. **Every fact is a separate answerable block with its own heading.** The traffic of country
   pages goes to single-fact queries (`<country> minimum wage`, `<country> payroll`,
   `average salary in <country>`), not to «how to find an employee».
2. **A freshness block:** the update date in view, a source for every figure, the name of the
   author and the editor. In the niche few sites had it, while the figures change once a
   year. One author and one editor, as in the blog; there is no separate
   reviewer (see «Author, editor and markup»).
3. **A block of recent changes with dates** — the second cheapest win.
4. **The first third is not a definition of EOR** but the irreplaceable part: thresholds,
   risks with figures.
5. **Content CTAs inside a section**, not five «book a demo» buttons.
6. **The hub is grouped by regions**, not alphabetically: a long alphabetical list of
   countries is impassable.
7. **Links to neighbouring countries at the bottom** — most competitors in the sample have
   them; cheap and effective.
8. **No second axis per country.** A competitor's second per-country folder on a narrower
   topic brought almost no visits compared with its main country folder — for search it is
   dead.
9. **Volume by itself does not win:** a competitor with very long pages got far fewer visits
   per page than a competitor whose pages were several times shorter.

## Cross-country topics go to a pillar article

Queries about working with international contractors in general — agreements, invoices,
classification, getting them paid — carry demand **without a country in them**. So such topics
are pillar articles, and the country guides feed them with links. Inside a guide the contractor
blocks (what a contractor produces to get paid, how the money arrives) remain as nodes of
irreplaceability and points of interlinking, but the section does not bet on country-level
traffic for these topics.

## Limits

- The set of countries is a publisher's policy held by the CMS: a country whose code is not
  in the CMS list cannot be created (see «`code` must be checked against the ISO-2 list»).
- The section is owned and educational: the country's vocabulary is acceptable as a reference
  about the country, but not as «Example Co does this».
- **Homonyms.** `georgia minimum wage` and `average salary in georgia` are about the US state,
  not the country. Figures for such a country cannot be taken from general keyword exports, and
  the page itself will compete with the intent about the state.

## The hub, the CMS and covers

**The hub `/guides/` exists from the start**, without waiting for the section to grow, and is
linked from the site's main navigation next to the blog and the glossary.

**The content lives in Strapi**, like the glossary. The type is frozen after the page has
been assembled on mocks: before the layout the set of fields is guesswork, and changing a
schema after the content is loaded is expensive.

**There are no covers in the section.** The figures live as a strip in the layout and are
updated by editing one field. Generated pictures were rejected on maintenance grounds:
figures inside a picture go stale, and across the whole section every update of a minimum
wage would mean regenerating files for three pages per country, plus a permanent chain
«edit the figure → rebuild → re-upload».

## Layout decisions that are part of the template

- **The country header** carries all the article furniture (author, editor, date,
  sharing, AI summary) and the header figures instead of a cover.
- **The body is the article template**: tables, lists and headings are styled by the same
  code as blog articles. The section has no tables of its own.
- **FAQ and interlinking are full-width sections** after the article column, as in the
  glossary: inside the column they are squeezed by the table of contents and the banner.
- **The hub is a card with a divider** plus search, tabs by region and «show all». All
  countries stay in the DOM: the hub is the crawler's entry point, and a country outside the
  DOM loses its incoming link.
- **Interlinking is by region**, a ceiling of 6, the hub as the first link, the anchor is the
  head query of the target («Hiring in Poland»). Ring interlinking was rejected.
- **The criterion for a diagram:** it shows a relation that would otherwise be computed in
  the head; a single number stays a table row.

## Addresses and headings of the subpages

The segments are full terms:

| short name | address segment | H1 |
|---|---|---|
| `/eor/` | `/employer-of-record/` | Employer of Record in Germany |
| `/contractors/` | `/independent-contractors/` | Hiring contractors in Germany |

The abbreviation `eor` in an address saves characters but loses the key: the head query of
the page is `employer of record <country>`, and it lies in the segment in full.
`independent contractors` is the model's own name in English-language sources; `contractors`
without the adjective is confused in the SERP with contractors in construction.

The term is written **Employer of Record** in the interface strings of the section:
headings, breadcrumbs, buttons, meta. (In body prose the pages use `employer of record` or
`EOR` consistently — `knowledge/guides-rules.md`, section 10.)

### Navigation between the three pages

Routing buttons on the subpages are **not used**: the way up is given by the breadcrumbs, and
there is no point in duplicating it with buttons. Instead, the links to the subpages are built
into the block that compares the routes on the country page — the reader chooses a model
where they compare them, not through a separate pair of buttons.

The address of a subpage is assembled by the page, and the data carry only a marker
(`page: 'eor' | 'contractors'`): otherwise the same pair of paths would lie in every country
and would have to be fixed in all of them when a segment is renamed.

### The strip of figures — on the country page only

It is not shown on the subpages. The strip obliges every level to store typed data, not
just the body of an article. This coincides with the rule against self-repetition: a minimum
wage in the header of `/eor/` is a self-repeat, and the subpages have almost no facts of their
own.

It also matches how a strong competitor lays its content out: its EOR article is prose and
**links** to the country guide for leave, taxes and working time. The numbers are carried by
one page, not by all three.

### The provider checklist on `/eor/`

Five questions that change the outcome: the licence, whose entity signs the contract, what
the fee includes, who runs and pays for a termination, the maximum duration of work through
an EOR. Plus a caption under the cost lines: the fees are a market range from our review, not
a quotation.

### The calculator — a later addition

The model: it calculates an employee through an EOR and a contractor side by side, so that
they can be compared, with a disclaimer under it. If an email form is used, the calculation
must be shown without it as well.

It is built **after** the structure of the page is complete. It requires the employer
contributions as numbers for every country — it cannot be computed from prose. This is why
`employerContributions` is a number.

### The section is in English only

A second language is deferred. That removes the heaviest blocker found: Strapi does not
allow the same slug in two locales, so there would be `/guides/germany/` and
`/de/guides/deutschland/`, while all the code builds addresses from **one** `slug`. Return to
it if languages are added.

## The strip in the country header

**One set of eight indicators in every country**, two rows by meaning:

| | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| what it costs | Minimum wage | Average salary | Employer contributions | Income tax |
| what you commit to give | Paid leave | Public holidays | Probation | Notice period |

The working week is not in the set: German law, for instance, has no «standard 40-hour week»
(it limits the day to 8 hours), no decision is made on it, and its place is the Working time
section. Income tax and the probation period are in the set.

Why a fixed set and not a selection per country: a grid row is never left empty (8 = 2×4 on
desktop and 4×2 on a phone), the strips are comparable between countries, and in Strapi these
are eight named fields instead of a free list. A missing value is a fact too: «None — set by
collective agreements».

**There are no captions under the figures.** The strip is a shop window, not a reference.
The meaning a caption would carry moves into the value itself («4 weeks – 7 months» instead of
«4 weeks, grows with tenure») or into the section below.

**The figures are not links.** The rule that remains: **an indicator of the strip must have a
row in a section below** — that is why the sections carry the average salary, the income tax,
the probation period and the top of the notice range. The source is shown there, in the
section's table; the header has none.

**Employer contributions** are one number, and the same number is used wherever the page
shows the rate. A discrepancy such as «≈ 21%» in one place against «21.7%» in another on the
same country page must not be possible.

## The disclaimer and the Sources section

**At the top — a mini note, one sentence**, as the first element of the body on all three
pages:

> General information, not legal or tax advice — confirm with a local adviser before you act.

About 95 characters. The section publishes rates, thresholds and deadlines from laws, so the
disclaimer stands **before the text**, not in small print at the end: at the bottom only
someone who has read to the end sees it, while a person makes the decision by the numbers at
the top. At the top there is only the legal essence: it is noticed before the person has made
a decision by the figures, and it takes almost nothing from the answer at the start of the
page. Rejected: four sentences of boilerplate as the first paragraph of the article, a line in
the header (there is a lot there already), an `<aside>`, a link to the Terms of use. The text
lives in the interface strings, not in the country data: it does not depend on the country.

The site's Terms of use hold the legally complete text. The final wording of the note should
be shown to whoever handles the company's legal matters.

**At the bottom — the «Sources» section**, the last section of the body. The list has the
accepted form: publisher, document title, link, access date —

> Destatis. Verdienste in Deutschland. https://www.destatis.de/…. Accessed 1 September 2026.

A paragraph «About these figures» with a reviewer and a date was rejected in favour of the
generally accepted form of a list of sources; the editor and the date stand in the header
anyway.

One address is one entry, in order of first appearance. The date lives in the source, not in
the figure itself: this covers the requirement «every figure has a date and a source». In a
table, next to the figure, only the short name of the source is shown.

## Author, editor and markup

- **Each of the three pages has its own indexing switch**: the country, the EOR page and the
  contractors page are independent. A closed country does not take its subpages out of the
  sitemap; `noindex` in `<head>` follows the page's own flag.
- **Markup for search is `Article`, as in the blog**: the author and the dates.
- **Long links wrap in all articles of the site**, not only in guides: the cause is common — a
  bare address in the text has no spaces and does not wrap.
- **The subpages are one route**, the block of neighbours is one component.
- **One author and one editor, as in the blog and the glossary.** There is no separate
  «reviewer»: a review date derived from the record's last save would declare any save to be
  an expert's check, and a brand account in the role of a person is not acceptable. Advice to
  «appoint a specialist from the country as the editor» is not given.

## The storage model: one body, three records

Only the header figures are stored as fields; everything else is one body, as in the blog and
the glossary.

**Why.**
- A questionnaire of several hundred values per country and a separate component for almost
  every block is complexity that did not get simpler with time.
- The main argument for fields — a stable table of contents across languages — fell away with
  the decision to keep the section in English only. A table of contents built from the
  headings of the body works, as in the blog.
- The glossary uses exactly this model: a few fields plus `contentHtml`. The article
  pipeline, the sanitizer and publication to Strapi already work with one body — guides become
  almost a copy of the glossary, not a new machine. The sitemap for server-rendered pages is
  solved the same way.
- The calculator needs one figure — the total contribution rate — and it stays a header field.

**The model.** The three pages of a country are three separate records in Strapi, not three
forms in one (editing three pages in one card is awkward).

```
Country              service fields · 8 header fields · contentHtml
Subpage              kind (EOR / contractors) · relation to the country · service fields · contentHtml
```

Two types, not three: the EOR and contractors subpages have the same set of fields.

**What stays in the template:** the header with eight figures, the disclaimer note, the table
of contents from the h2s of the body, the banner in the column, the buttons to the subpages,
the block «more guides in the region».

**What became rules for the pipeline, not fields:** the routes table (the columns «Legal
employer», «What you pay on top of salary», «How you end it»), the list of sources in the
form «title — link — access date» as the last section of the body, the fact tables, the FAQ.

**What it costs.**
- **Numbers in two places.** The header figures are fields, and the body carries them as text
  in tables. Nothing reconciles them automatically on the site, so the final check of the
  pipeline carries the rule «the header figures match the body». The subpages receive the
  country page as input and do not write their own figures where the country page has them.
- **Diagrams are tables in the body.** A picture may add to a table but not replace it: text
  in a picture is read neither by search nor by AI assistants, and registration steps are
  exactly what people ask about. Start with tables; add pictures where verified data exists.
- **FAQ is plain text in the body**, as in the glossary, without an accordion.
- **Given up:** automatic assembly of the list of sources, automatic substitution of the rate
  and the notice period into the routes table, most of the section's components.
- **What is lost, honestly:** comparability on deep facts (a summary table across countries
  cannot be assembled from prose); automatic checks of a typed field (a currency from ISO, a
  percentage in a range) — prose is checked by the pipeline's scripts and by a person; reuse
  of a number from prose in another place.

## Hiring routes — as a table

The routes are an ordinary table in the style of the blog's tables. A separate block of
cards is not needed where a table copes; on desktop three cards are three narrow columns.
A time bar is the only thing a table does not convey, and the numbers show an
order-of-magnitude difference anyway («6–12 weeks» against «1–3 working days»).

- **Routes are rows, attributes are columns.** Rows scale if a country gets a fourth route
  (PEO, agent of record); columns would narrow again.
- **The name of a route is a link to the subpage.**
- **The columns are «Legal employer», «What you pay on top of salary», «How you end it».**
  «Time to the first pay run» and «who carries the risk» are not used: a risk in the EOR cell
  can mislead (in Germany, without an AÜG licence, the client can be deemed the employer), and
  an assessed risk belongs on the subpages. «Limit in <country>» was rejected too.
- **Why not only general columns.** «Is an entity needed» and «who is the employer» are the
  same in any country and duplicate each other — that is a definition of the routes, not a
  fact about the country; they are merged into «Legal employer». The same table as the first
  thing after the opening paragraph on every country page would be a template with
  substitution. The two other columns make the table country-specific: the contribution rate
  and the EOR fee, and the notice period.
- **The numbers in the cells are not a separate version.** The contribution rate and the
  notice period equal the header fields exactly.
- **Above the table — the h2 «Three ways to hire in {country}» and an item in the table of
  contents.** The country targets the cluster `hire in` / `hiring in <country>`, and the
  comparison of routes is the direct answer to it.

## The composition of the country's sections

- **Holidays, the 13th salary, visas are sections of the text where relevant**; there are no
  fields for them. Minimum wage, taxes, working time, leave, termination are in every
  country: they are searched for, and every top page in the measurement had them. The
  optional ones: holidays (a split by region exists only in federal countries), the 13th
  salary (a minority of countries; elsewhere the row would say «none»), visas (the most
  laborious topic, changes most often, could carry a page of its own).
- **The contractor status thresholds are on the contractors page only.** On the country page
  the section would be a self-repeat.
- **External links in the text open in the same tab.** The editor has no «open in a new tab»
  switch, and the site does not add such a rule.

## Regions

**The UN geographic scheme, the M49 standard** (UN Statistics Division). Membership
organisations are not regions, so the division is taken from a geographic reference, not from
the membership of organisations. The World Bank's variant was rejected: it merges a large
group of countries into «Europe & Central Asia» together with Europe.

- **5 regions**: Africa, Americas, Asia, Europe, Oceania. They define the tabs of the hub and
  the block «more guides in the region».
- **Subregions are stored but not displayed.** A candidate for the future is the block of
  neighbours: a country's neighbours would then be the countries of its subregion, not the
  whole region.
- **A consequence to remember:** the standard does not always match intuition — Azerbaijan and
  Türkiye, for example, are Asia / Western Asia in M49, not Europe.
- **On the site:** the region is looked up in the M49 table by ISO code (the export from
  https://unstats.un.org/unsd/methodology/m49/overview/). Antarctica has no region in the
  standard and is not included.

## The template

The structures below are a hybrid: the union of all unique blocks of the top-10 plus nodes
that the top does not have at all. The order of the blocks is a contract for the pipeline: a
writer may not reorder them. The current binding list of H2s is `knowledge/guides-rules.md`,
section 3.1.

**There is no ceiling on volume.** The competitor with the longest pages lost not because of
length but because one page carried all the clusters at once and they competed with each
other. Here the routing to three pages removes that mistake by architecture. Only the
repeating core is compressed; the irreplaceable nodes are cut last.

### The root `/guides/<country>/` — 13 blocks

1. H1 and the direct answer in 2–3 sentences.
2. The strip of facts: the flag and the header figures.
3. The freshness block: the date, the author, the editor, a source for every figure.
4. The labour market: why the country is interesting, the top cities, salary reference
   points by role.
5. Routing to the two models — the links to `/eor/` and `/contractors/` in the routes table.
6. The sequence of registering as an employer, step by step.
7. Hiring: where to look, the limits of a vacancy under anti-discrimination law, what goes
   into an offer, whether checking a candidate is lawful, NDA and IP, the onboarding checklist.
8. The fact reference by block: minimum wage · average salary · taxes and contributions
   (table) · working time and overtime · leave, sick pay, parental leave (table) ·
   termination · holidays · the 13th salary · visas and permits.
9. How work is done here — **as facts, not reflections**: notice deadlines, the attitude to
   overtime, the norms of business correspondence, what counts as an acceptable response time.
10. Recent changes with dates.
11. What a mistake costs and who pays — separately the client, the worker, the accounts
    department.
12. FAQ.
13. Neighbouring countries.

### `/eor/` — 12 blocks

1. H1 and the direct answer.
2. What an EOR is — one sentence and a link to the glossary.
3. How the model qualifies under this country's law.
4. The provider's licence: whether one is needed and how to check it, with the address of the
   registry.
5. The three-party scheme of contracts client–EOR–employee.
6. Hiring step by step, with the timing of every step.
7. The cost: what it consists of, with the contribution percentages.
8. The limits of the model: the maximum duration of work through an EOR, the risk of a
   permanent establishment, IP and non-compete, what happens on a breach and what it costs.
9. When an EOR is not needed here — including a direct answer to «can one hire directly
   without an entity».
10. Alternatives and the criteria for choosing a provider.
11. FAQ.
12. Neighbouring countries.

### `/contractors/` — 15 blocks

1. H1 and the direct answer.
2. Classification: where the line runs and by which signs it is checked.
3. The thresholds at which contractor status breaks.
4. The forms of registering a contractor in the country and what each means for the client.
5. The contract: mandatory clauses as a checklist, termination.
6. What a contractor must produce to get paid: invoice requirements, tax
   identifiers, VAT and when it arises for the client.
7. Payment rails: how the money really arrives, what costs more, who pays the fee.
8. Payment terms and late payment.
9. What breaks in the payment process and at which step.
10. Who pays for a mistake and how much — separately by party.
11. Engagement models and when each fits, including moving a contractor to employment.
12. One contractor against ten: your own effort or a platform.
13. **Who works with contractors in this country** — the ranking, Example Co first.
14. FAQ.
15. Neighbouring countries.

## About the ranking on `/contractors/`

The block closes a gap: listicles in the search results exist only for EOR; for contractors
there are none. Two conditions without which it does harm.

**Country criteria, not a general vendor card.** If the cards coincide word for word from
country to country, it is a template with substitution. The criteria are tied to the country:
whether the vendor works in it at all, its entity or registered presence there, contracts
under local law or in the local language, IP assignment in the standard contract, the local
documents it supports, classification support (`knowledge/guides-rules.md`, section 6).

**Limited to the list of supported countries.** We may be put first only where the product is
really available; across the whole section this is taken from data (the topic sheet's column
«Example Co in country», see `topic-sheet.md`), not set by hand.

A ranking of EOR providers on `/eor/` is **not made**: Example Co is not an employer of
record, and a ranking in a category where the publisher has no product would not be honest.

## Blocks of the top that are deliberately not taken

| block | where it appears | why |
|---|---|---|
| Managing the equipment and access of remote employees | one vendor's guides | a description of their product; no facts about the country |
| Health insurance item by item: dental, vision, co-payments | one vendor's guides, 30+ headings | their insurance product, not a fact about the country |
| A hiring cost calculator | several vendors' guides | requires an exact base of contributions; see «The calculator» |
| A ranking of EOR providers | two vendors' guides | the publisher is not an employer of record |

## Rules the template must hold

- **A canonical fact lives in the root.** A subpage repeats only what its model
  changes. The minimum wage does not apply to a contractor at all — on `/contractors/` this is
  not a repeat of the fact but a limit that competitors do not state.
- **The ten common blocks are given in full, but compactly and as tables, and not in the first
  third.** Cutting the base for the sake of originality is a separate way to lose.
- **At least one block that neighbouring countries do not have.** Otherwise we create
  redundancy for ourselves across many pages of one type. For a country these are thresholds,
  rails and regimes.
- **A source for every figure**, the update date, the author and the editor.
- **CTAs are content CTAs, inside a section** («more about taxes»). The body of a guide page
  itself carries no CTA: the site renders the banner (`knowledge/guides-rules.md`, section 2).
- **Compress the repeating core, not the page as a whole.** The visits-per-page comparison is
  a comparison of architectures — one fat page against a folder of subpages — not of length:
  the competitor with the shorter pages writes far more than the other on the commercial EOR
  query. There is no ceiling on volume.

## The specification of the types in Strapi

The flow writes to Strapi 4. The two content types below are what `scripts/strapi_guides.py`
writes and what `scripts/check_cms_country.py` reads before a job can start, so the CMS must have
them before the first country. On another CMS keep the same fields and replace both scripts
(README, «Adapting»).

Two records instead of one form for three pages. Two types, not three: the EOR and contractors
subpages have the same set of fields.

### `country-guide` — the country page `/guides/<slug>/`

API ID `api::country-guide.country-guide`, REST path `/country-guides`.

| field | type | purpose |
|---|---|---|
| `name` | string, required | the name of the country; the label of the record in the admin panel |
| `slug` | uid ← `name`, required | the address |
| `code` | enumeration of ISO-2 codes, required, unique | the site takes the flag and the region by it — there are no fields for them. The list of values is the publisher's country policy: `check_cms_country.py` blocks a country whose code is not in it |
| `minimumWage`, `averageSalary`, `incomeTax`, `paidLeave`, `publicHolidays`, `probation`, `noticePeriod` | string, up to 32 characters | seven header figures |
| `employerContributions` | decimal, 0–100 | the eighth header figure, **as a number**: the calculator computes from it |
| `contentHtml` | rich text (HTML) | the rest of the body |
| `content` | text, hidden | the body after the sanitizer, written by a lifecycle hook; the public endpoints serve it and the flow reads it back |
| `metaTitle` (70), `metaDescription` (200) | string | search metadata |
| `indexable` | boolean | the page's own indexing switch |
| `disclaimer` | string, up to 300 characters, optional | a page-specific warning; when empty the site shows the general note. The flow does not write it |
| `author` | user, manyToOne | the author |
| `editors` | user, manyToMany | the editor; as in the blog, the page shows one — the first |
| `subpages` | oneToMany → `guide-subpage`, `mappedBy: country` | links to the subpages in the country card; the subpages themselves are not edited there |

### `guide-subpage` — `/guides/<slug>/employer-of-record/` and `/independent-contractors/`

API ID `api::guide-subpage.guide-subpage`, REST path `/guide-subpages`.

| field | type | purpose |
|---|---|---|
| `country` | manyToOne → `country-guide`, `inversedBy: subpages`, required | which country it belongs to |
| `kind` | enumeration with at least `eor` and `contractors`, required | which subpage; the site builds the address segment from it |
| `title` | string, required | the H1 and the label of the record in the admin panel — without it the list of subpages in the admin panel would be nameless |
| `contentHtml`, `content`, `metaTitle`, `metaDescription`, `indexable`, `disclaimer`, `author`, `editors` | as for the country | |

A subpage has no slug of its own: the address is fully determined by the country and the kind.

### Behaviour

- **The body hook**, on both types: on save, the sanitizer cleans `contentHtml` and writes the
  result to `content`. The flow keeps a copy of that sanitizer in
  `vendor/blog/tools/sanitize/check.js` and refuses a body that would lose anything in it; keep
  the two in step.
- **What the sanitizer must allow:** headings, paragraphs, lists, links, images, `table`,
  `thead`, `tbody`, `tr`, `th`, `td`, `figure` — tables and figures in the body work. It allows
  no `id` attribute on any tag and no `svg`: anchors are built from the heading text when
  headings are parsed, and diagrams go in as images.
- **One subpage of each kind per country.** A Strapi schema cannot express composite
  uniqueness, so a check in the `beforeCreate` / `beforeUpdate` hook with an error is needed.
  From the admin panel the relation arrives not as an id but as `{ connect, disconnect }`; the
  check has to handle both forms.
- **Serve only published records** (`publishedAt: $notNull`): otherwise an unfinished page
  opens by its direct address and gets into the index.
- **Endpoints the flow calls:** `GET /country-guides/:slug/findBySlug` — the country with
  `content`, the author, the editors and the list of published subpages (only `kind`);
  `GET /country-guides/:slug/subpages/:kind` — a subpage with its `content`; the list
  `GET /country-guides` — `name`, `slug`, `code`, `indexable` and the subpages' `id` and `kind`,
  without bodies (the flow finds existing records by it; the site uses it for the hub and the
  sitemap); `POST`/`PUT` on `/country-guides` and `/guide-subpages` for writes.
- **The API token** used by the flow needs write access to both types, upload access to the
  media library, and read access to the content-type-builder schemas
  (`/content-type-builder/content-types/<API ID>`): `check_cms_country.py` and
  `new_guide_job.py` read the live schema before any job is created.
- **Whitelists of fields** on the public endpoints; `contentHtml` is not served outside.
- **Field hints in the admin panel** are useful for editors: the eight header figures are
  short, without explanations; a number in the header matches the body; the sources are the last
  section of the body.
- **Public role permissions** for both types (`find`, `findOne`, the custom endpoints) are a
  manual step on every environment; without them the section returns 403.
- **i18n**: the section is English only. If the i18n plugin is enabled, localise only the text
  fields; switching it on for a filled type costs more.

### What the site derives from the records

- The flag and the region come from `code`; a new country is only a record in the CMS. A wrong
  code (for example «UK» instead of «GB») would leave the country without a flag and a region,
  which is why `code` is an enumeration and not free text.
- The hub, the subpage buttons and the guides sitemap are built from the same records:
  publish a country — its card appears; a subpage exists — its button exists; an unpublished
  subpage disappears and returns 404. Only records with `indexable: true` go into the sitemap.
- Preview pages are not prerendered into the build output, or a sitemap built from the output
  would list drafts.

## What is deliberately not done

- A second axis per country.
- A fourth and further page (`/taxes/`, `/leave/`).
- Covers.
- A ranking of EOR providers.
- A second language.
