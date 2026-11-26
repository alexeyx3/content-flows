> Design document. The current run instructions are `AGENTS.md` and `.agents/skills/country-guide/SKILL.md` in the project root; the binding rules are in `knowledge/guides-rules.md`. Where this guide and the rules differ, the rules win.

# Country guides: instructions for the editor

How to set up a country in the `/guides/` section and what to write where in Strapi.

The structure of the sections below is the one the site's country pages use: a country record
with header fields and one body, and up to two subpage records.

## How the section is built

Every country has up to three pages:

| page | address | what it is about |
|---|---|---|
| country | `/guides/germany/` | reference: figures, taxes, leave, termination, ways to hire |
| EOR | `/guides/germany/employer-of-record/` | how the Employer of Record model works in this country |
| contractors | `/guides/germany/independent-contractors/` | how to engage and pay contractors in this country |

In Strapi these are **separate records**: one «Country» and up to two «Subpages». Subpages
are optional — a country can go live without them, and the EOR and contractors pages can be
added later.

**What the site does itself — no manual work needed:**

- the page header with the flag, date, author, editor and the «share» button;
- the disclaimer «General information, not legal or tax advice…» above the text;
- the table of contents — from the second-level headings in the text;
- the flag — by the country code;
- the region — by the country code, from the UN reference: Germany is Europe, Japan and
  India are Asia;
- the country card on the `/guides/` hub and the tab of its region;
- the EOR and Contractors buttons — in the country header and on the hub, only if the
  subpage is published;
- the «More guides in <region>» block at the bottom — with links to other countries of the
  same region;
- the banner in the right column — its own for each page type (see «Banners»).

## Step 1. The «Country» record

Content Manager → **Country guide** → Create new entry.

| field | what to write | example |
|---|---|---|
| `name` | the country name in English | Germany |
| `slug` | the address; filled in from the name automatically, check it | germany |
| `code` | the ISO country code — choose from the list. The United Kingdom is `GB`, not `UK`. The site takes the flag and the region by the code. Strapi will not allow two countries with one code | DE |
| `minimumWage` | minimum wage | €13.90 / hour |
| `averageSalary` | average salary | €4,323 / month |
| `employerContributions` | employer contributions on top of salary, **as a number, in per cent, without the % sign** | 21.7 |
| `incomeTax` | income tax | 14–45% |
| `paidLeave` | paid leave | 20 days |
| `publicHolidays` | public holidays | 9–13 |
| `probation` | probation period | up to 6 months |
| `noticePeriod` | notice period on termination | 4 weeks – 7 months |
| `contentHtml` | the whole text of the page — see step 2 | |
| `metaTitle` | the title for search, up to 70 characters. May be left empty — then «Hiring in Germany: rules, costs and contractors» | |
| `metaDescription` | the description for search, up to 200 characters. May be left empty — then a template is used | |
| `disclaimer` | the page's own disclaimer, up to 300 characters. Usually empty — then the general one stands at the bottom of the figures card: «General information, not legal or tax advice — confirm with a local adviser before you act.» Fill it in only if this country needs a special warning, for example about a law that is about to change | |
| `indexable` | leave switched on if the page should get into search | ✓ |
| `author` | who wrote it | |
| `editors` | the editor. As in the blog: the page shows one — the first in the list | |

**The eight header figures are short and carry no explanations.** It is a shop window, not a
reference: «4 weeks – 7 months», not «4 weeks, grows with tenure». Details go into the text
below.

**The header figures must match the text.** If the header says 21.7%, the total in the tax
table below is 21.7% too. The site does not check this; it is yours to watch. When a rate
changes, edit both places.

**If a country has no such value, that is a value too.** For example, Denmark has no statutory
minimum wage: write «None — set by collective agreements», do not leave the field
empty.

The page heading (H1) is always «Hiring in <country>»; it is not written separately.

## Step 2. The text of the country page

Everything except the header is one field, `contentHtml`, like the body of a blog article.
The sections go in this order:

| # | section (H2 heading) | what is in it |
|---|---|---|
| — | *no heading* | 2–3 sentences — the direct answer: how one can hire in this country at all |
| 1 | Three ways to hire in Germany | the table of ways to hire (see below) |
| 2 | The labour market | a paragraph about the market, the main cities, H3 «Salary reference points» — a table of salaries by role |
| 3 | Registering as an employer, step by step | the table «Step / What happens / Takes» and a line with the total time |
| 4 | Hiring and onboarding | a paragraph, H3 «Legal limits to keep in mind» — a list, H3 «Onboarding checklist» — a list |
| 5 | Minimum wage | table |
| 6 | Taxes and contributions | table, H3 «What an employee actually costs you» — the calculation of what an employee costs |
| 7 | Working time and overtime | table |
| 8 | Leave, sick pay and parental leave | table |
| 9 | Termination: notice and payments | table |
| 10 | Public holidays | table — **where relevant** |
| 11 | 13th salary and bonuses | table — **where relevant** |
| 12 | Visas and work permits | table — **where relevant** |
| 13 | How work is done here | table: deadlines, the language of contracts, the currency of payment — only what can be verified, no stereotypes |
| 14 | Recent changes | list: date — what changed — source |
| 15 | What a mistake costs and who pays | the table «Party / Risk / Amount» |
| 16 | Questions people actually ask | FAQ |
| 17 | Sources | the list of sources — **always last** |

Sections 5–9 are present in every country. Sections 10–12 appear only where they say
something: public holidays split by region exist only in federal countries, a 13th salary
in a minority of countries, visas are not needed everywhere. Where a section has no point,
there is no section; it is not left empty.

All these tables are ordinary sections of the text; there are no separate fields for them.

**The contractor status thresholds** («Where contractor status breaks») are not written on
the country page — only on the contractors page, to avoid repetition.

**The table of ways to hire** always has three rows and four columns:

| Route | Legal employer | What you pay on top of salary | How you end it |
|---|---|---|---|
| Your own entity | You, through a German entity | 21.7% contributions + setup and payroll admin | 4 weeks – 7 months statutory notice |
| [Employer of record](/guides/germany/employer-of-record/) | The provider | 21.7% contributions + €400–700 / month fee | 4 weeks – 7 months statutory notice, run by the provider |
| [Contractor](/guides/germany/independent-contractors/) | No one — the contractor is self-employed | Invoice only, no contributions | As agreed in the contract |

The contribution percentage and the notice period here are the same as in the header. The
names of the routes are links to the subpages, if they exist.

## Step 3. The EOR and contractors subpages

Content Manager → **Guide subpage** → Create new entry. One record per subpage.

| field | what to write |
|---|---|
| `country` | choose the country from the list — required, a subpage will not save without a country |
| `kind` | `eor` or `contractors` — which subpage this is. A country can have only one of each kind: Strapi will not save a second |
| `title` | the page heading (H1): «Employer of Record in Germany» or «Hiring contractors in Germany» |
| `contentHtml` | the text — the structure is below |
| `metaTitle`, `metaDescription`, `disclaimer`, `indexable`, `author`, `editors` | as for the country; a subpage's disclaimer stands as a separate note before the text |

**The main rule of subpages: do not repeat the country's figures.** The minimum wage, taxes
and leave live on the country page. A subpage writes only what its model changes and links
to the country for the rest. For example, the minimum wage does not apply to a contractor at
all — the contractors page should say so, but need not repeat the figure itself.

### EOR

| # | section (H2) |
|---|---|
| — | *no heading*: the direct answer, 2–3 sentences |
| 1 | What an employer of record is — one sentence and a link to the glossary term |
| 2 | How the model qualifies under local law |
| 3 | The provider licence, and how to check it — with a link to the registry, if there is one |
| 4 | Who signs what — the table «client — EOR — employee» |
| 5 | Hiring step by step, with real timings — a table of steps |
| 6 | What it costs, line by line — a cost table, H3 «What an employee actually costs you» |
| 7 | Where the model runs out — the maximum duration, the risks |
| 8 | When you do not need it here |
| 9 | Alternatives, and when each fits |
| 10 | How to choose a provider — questions for the provider |
| 11 | Questions people actually ask — FAQ |

The page is **educational**: how the model is set up in the country, without «Example Co does
this». Example Co is not an employer of record.

### Contractors

| # | section (H2) |
|---|---|
| — | *no heading*: the direct answer, 2–3 sentences |
| 1 | Where the line runs — the signs by which a contractor is told apart from an employee |
| 2 | Where contractor status breaks — a table of thresholds |
| 3 | How a contractor is registered here — the forms of registration |
| 4 | The contract: what must be in it — H3 «Clauses that have to be there», H3 «Ending the contract» |
| 5 | What a contractor must produce to get paid |
| 6 | How the money actually arrives |
| 7 | Payment terms and late payment |
| 8 | What breaks, and at which step |
| 9 | What a mistake costs and who pays |
| 10 | Models and when each fits |
| 11 | One contractor versus ten |
| 12 | Who works with contractors in Germany — a table of vendors; Example Co first **only in countries where it is really available** |
| 13 | Questions people actually ask — FAQ |

## How to format the text

The text is written in the same editor as blog articles and goes through the same cleaning:
anything that is not on the editor's toolbar is cut out on save.

- **H2** — sections. Only they get into the table of contents, so every fact with a query of
  its own — «Minimum wage», «Paid leave» — gets its own H2. **H3** — subsections inside.
  H4 is the smallest level the editor has.
- **Tables — with the table button in the editor.** Not as a picture: neither search nor AI
  assistants read text in a picture. A diagram or a picture may be added next to a table, not
  in place of it.
- **A fact table** — two columns «what — value», the third is the short name of the source:
  `Current rate | €13.90 / hour — since January 2026 | BMAS`. No header row is needed.
  Comparison tables (ways to hire, «who pays for a mistake») do have a header row.
- **FAQ** — H2 «Questions people actually ask», every question is an H3, the answer is a
  paragraph under it. 3–7 questions, real ones — those people ask in search.
- **Sources** — the last section, H2 «Sources», a numbered list, each item with:
  the publisher, the document title, the link, the access date:
  `Destatis. Verdienste in Deutschland. https://www.destatis.de/…. Accessed 1 September 2026.`
  The link goes to the page where the figure stands, not to the site's home page. The access
  date is when you checked the figure against that page.
- **Pasting from Google Docs and Word is fine**: fonts, colours and sizes are cleaned out on
  save; headings, lists, tables and links remain.

## Step 4. Publication

1. Publish the **country** first, then the **subpages**. A draft is not visible on the site
   even by its direct address.
2. After publication the country appears on the hub by itself, gets its flag and the tab of
   its region; its neighbours in the region get a link to it.
3. Once a subpage is published, the country and the hub get a button to it. Once it is
   unpublished, the button disappears and the address returns 404.
4. The date in the header is the date of the last save. Any re-save updates it.

**Check before publication:**

- [ ] the country code is ISO, two letters;
- [ ] the eight header figures are filled in and match the tables in the text;
- [ ] every figure in the text has a source, and all sources are in the «Sources» list;
- [ ] the author and the editor are set;
- [ ] the subpages do not repeat the country's figures;
- [ ] the table of ways to hire carries the same contribution percentage and notice period as the header.

## Banners

If your site attaches banners to page types, give the three page types three separate banner
places, for example `guide-country`, `guide-eor`, `guide-contractors`. A banner is attached to a
place, not to a country: one banner for all countries of its type.

In a Strapi set-up with a banner collection: Content Manager → **Banner** → the banner you need →
its places field → add a place → Save. One banner can stand in several places at once. If a place
has no banner, the column is simply empty.

## What not to do

- **Do not create pages for countries whose codes are not in the CMS list.** The list of
  codes holds the publisher's country policy; Strapi will not save a record with a code that
  is not on it.
- **Do not write «Example Co does this»** on the EOR page — the page is educational.
- **Do not put figures into pictures** — only into tables.
- **Do not invent your own sections and do not reorder them**: the same structure is needed
  so that countries read alike and the table of contents is predictable.
