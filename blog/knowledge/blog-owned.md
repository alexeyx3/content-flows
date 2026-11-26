# Blog (owned) — track rules
**Applies to: the Example Co blog only.** Stacks on top of positioning.md, legal.md,
seo-requirements.md, geo-guidelines.md, article-structure-rules.md, draft-rules.md.
Distilled from the publisher's editorial decisions for the blog track and from proofreading notes on published articles.

## Temporary format restrictions

The publisher may pause the preparation of new pages in particular formats — for example new
**alternatives** pages and standalone **X vs Y / versus** comparisons, including comparisons of
specific services. A pause is recorded in this section and applies to the selection of the next
batches until the publisher lifts it. No format is paused by default.
A pause on those formats does not cover **Best / Top** roundups, such as contractor management
software; comparing options inside such a roundup is not in itself prohibited.

Topics that fit a currently paused format are deferred with an explicit reason in the topic
sheet and stay in the queue. A format restriction is not grounds for marking a topic as a
duplicate or removing it from the queue.

## Voice and frame

- The article is published in the company's voice: the positioning card applies
  (positioning.md §1).
- **Invoice approval belongs in the description of Example Co — it may and should be named:**
  in the card, the key features, the table row, the price and the conclusion, but not in every
  sentence. Rotate the wording: invoice approval / approvals / sign-off. Who uses it is named
  in combination: finance and operations teams and the founder who handles contractor paperwork
  personally; do not write that Example Co is a tool "for freelancers" alone.
- **Describe it from the client's side:** companies sign agreements with their contractors and
  approve their invoices in Example Workspace. Do not write "Example Co works with contractors
  in X" — it reads as if the contractors were Example Co's own.
- **Never next to Example Co:** the labels staffing agency, marketplace, employer of record, law
  firm, legal adviser, payment provider; speed claims (instant, same-day, in minutes); the words
  "cheap", "free", "low-cost" about the price of Example Co; guarantees (audit-proof, fully
  compliant, risk-free — write "helps keep contractor documents in order"); superlatives without a
  public source (best, leading, number one); background checks, identity verification or vetting as a feature; a list of regions; a hedged
  chatty tone.
- **The market and competitors are described freely:** staffing, employer-of-record and payment
  vocabulary, the fees of banks and of other vendors, other vendors' turnaround times are the
  ordinary subject of an article.
- **Synonyms instead of repeats.** The full category formula appears once per page, after that
  the short variants. One wording for the whole article reads as a template.
- Never, in any form: advice on a reader's individual legal situation, roadmap announcements,
  customer counts or growth figures that are not published on the site, and brands listed in
  `config/stop-brands.json`.
- Product pages (Solutions, the home page, use cases) are not our track.

## Vendors in cards and comparisons

- **Banks and payment services** as a class do NOT go into vendor cards and comparison
  tables. In the text they are mentioned freely as a class: "a transfer through a bank or a
  payment service" is a legitimate phrase.
- **Brands listed in `config/stop-brands.json` are never mentioned anywhere** — text, tables,
  rankings, sources, links, metadata, images. That includes cards, enumerations, the FAQ and the
  inside of quotations.
- **No article is written about a stop-listed brand, and it appears in no field.**
  A competitor that is not on the stop-list may be mentioned under the same rules of evidence and
  relevance as any other competitor.
- First-tier leaders (Northwind, Contoso, Fabrikam, Globex, Initech) are named freely:
  a roundup without the obvious player looks incomplete and is cited less.
- The heading of a vendor card is **the service name only**, with no descriptors or scenarios.

## How to name Example Co and what must not be written about it

Rules:

- **"Agent of Record" is not a label and not the product name of Example Co.** The term is fine
  for describing the market and for "what is an AOR" explanations. It may describe how an
  arrangement works: "the company uses an agent of record arrangement", "one agreement with the
  agent; the agent signs agreements with the contractors". About ourselves we write the category
  formula from positioning.md: "software for companies that work with independent contractors
  abroad: agreements, invoices and approvals in one place"; the product is Example Workspace. The
  retired labels "contractor compliance suite" and "freelancer management platform" are not
  used.
- **Plans and dates from internal documents never go into the text.** No "payments will arrive
  next quarter", no "an EOR service is planned for next year". The absence of a product is written
  in the present tense and without a date.
- **Specific dates in the text only where they cannot be avoided.** Instead of "As of 31 August"
  write "at the time of writing": the page itself shows the update date, and a date baked into
  the text turns into an obligation to rewrite the article.
- **Lists of verticals end with an open clause.** Not "software studios, agencies, e-commerce,
  EdTech" but "…and other companies": a closed list reads as a refusal to everyone else.
- **Abbreviations are written uniformly.** Upper case is chosen: EOR, AOR — a mix of
  "AoR" or "EoR" next to "EOR" looks careless.

## The Example Co card in comparisons: how many limitations

**Negative labels are not mandatory.** Example Co is not an employer of record or a payment
provider, but an article is not obliged to say so every time. It is enough not to claim
that Example Co belongs to those categories. If the distinction is necessary for the reader's
decision, state it once in the card or in the comparative conclusion and do not repeat it through
the article.

**Not listed beyond that:** the absence of named integrations (a particular accounting package,
a particular HR system), service-level terms that are not public, the absence of products that
are not released yet. The wording "does not hire your contractors" is not used — "not an
employer of record" is enough.

**What this means for the parity gate.** The rule "the same candour in every card"
(the equal-candour test) still applies to format, depth and volume: the same
sequence of fields, comparable length, honest strengths and real weaknesses for every
competitor, no disparagement. But by the NUMBER of limitations the Example Co card is now shorter
than the competitors' cards, and QA does not block for that.

**The risk is named and accepted as part of the rule.** `legal.md` requires a comparison to be
objective and not misleading; silence about a material fact is one way of misleading.
Of what is left out, the missing named integrations look material: every competitor in the
article lists theirs. The trade-off is a standing rule; do not raise the question again.

## Neighbouring blog articles: vendor cards are rewritten, not copied

Articles in the queue share one vendor base and one evidence base, so cards
travel from article to article almost verbatim. A typical overlap check finds dozens of
fragments shared with a neighbouring article, the longest a couple of dozen words long — and the
longest is often our own Example Co card together with its "when to skip" line.

**What to do when writing and editing:** facts and numbers are kept, the wording is written
anew. This covers descriptions of vendor models, category labels, thresholds and caveats,
the "best for" and "when to skip" lines, and the column names of the comparison table.
Rewording a label does not mean inventing an unconfirmed category; it means following the rule.

**Uniqueness is not the main thing.** Clear and accurate matters more than
original at any cost. Identical blocks across articles are acceptable: category definitions,
the explanation of a vendor's model and the structure of cards may repeat when that is more
honest and clearer. Rewriting a wording for the sake of dissimilarity while losing clarity is a mistake.

**The threshold stays, but as a signal, not a gate:** a verbatim shared fragment longer than 40
words is worth rewriting; 20–40 words are acceptable when it is a definition or a vendor card.
Checked mechanically: `python3 scripts/text_overlap.py <new>/edited.md <neighbour>/edited.md`.
The orchestrator runs the check before packaging; QA has no shell access.

## How Example Co describes itself and what it does not deny

**Example Co is not a payment provider and not an EOR, but public copy is not built on
negations.** It is enough not to call Example Co a payment provider or an employer of
record. The wording `not an employer of record` is permitted when the reader needs the
distinction, but it is not a mandatory element of the card and is not repeated for parity.

**Do not write "the only product".** The wording "our flagship and only product"
in the internal positioning document is internal. Publicly: the category formula from positioning.md,
and the product is called Example Workspace. No "only", "the sole", "the one product".
In fact the company does more than fits into such a wording.

**Do not build headings and sentences around search.** "…the comparison buyers actually search",
"when people search for X, they want Y" reads as keyword stuffing. A heading names the subject
of the comparison, not search behaviour. (This extends an earlier ban: it used to cover quotation
marks around a query, now it covers any reference to what people search for and how.)

## Two bans from proofreading

**A search query in quotation marks as the subject of the conversation is forbidden.** Wordings
like "when people search for 'northwind alternative', they usually want…" are a heavy SEO cliché.
The reader did not search for a query, the reader is solving a task. Write about the task and keep the query to yourself.

**Do not open with what we are not.** "This is the wrong shortlist for an employee EOR" and
the like at the start of an article is a defensive stance. First we say who we are and what we do;
limitations go in the vendor card, in their own place, not in the introduction.

## A fact whose explanation leads into a prohibited topic is not mentioned at all

The case behind the rule: a vendor that is a spin-off of another company,
where the parent keeps working in a market the blog never covers. The fact is real and
confirmed, but any explanation of how the two companies differ today leads into that market —
a topic that does not exist on the blog.

**Rule:** if a fact is acceptable in itself but cannot be explained to the reader without entering
prohibited ground, the fact is not mentioned — neither cautiously nor by hint. A mention without
an explanation is worse than silence: it invites a question we cannot answer.

In that case it means: the parent company is not named in the article about the spin-off, the
spin-off's origin is not discussed, and a marketing tenure that predates the company itself
(for example "a decade of experience" for a company founded a few years ago) is not commented on.

## A cancelled fact is corrected in evidence, not only in the text

The typical failure: the content of a vendor's pricing page cancels some of our claims and the
text is rewritten, but the matching rows in evidence (for example `GX-05`, `UM-03`) are left as
they were. The very next edit legitimately brings the cancelled claim back into the article, and
QA finds it as a discrepancy with evidence. The same leftover tends to survive in neighbouring
articles that reuse the card.

**Rule:** when you cancel or refine a fact, correct the row in `evidence.md` — with the mark CANCELLED or
REFINED, the previous wording and a note on what replaced it. **And in a vendor card a cancelled
claim lives in more than one field.** Fixing `pricing.notes` and `biggestLimitation` is not
enough when the same cancelled claims stay in `editorial.cons` — QA then finds them articles
later. Every field has to be checked: `pricing`, `notes`, `editorial.biggestLimitation`, `cons`, `pros`,
`bestFor`, `notIdealFor`, `faq` and the prose description at the end of the file. The article text is derived;
the source of truth for editing and for QA is evidence. The row is not deleted: a deleted row cannot
be traced, while a marked one explains why the text says something different from older neighbouring files.

## A vendor rebrand is checked before the card

The typical case: a line-up includes a vendor that was renamed some time ago, and its old domain
returns a 301 to the new one. A card under the old name in a current article is stale evidence
that the reader will check with the very first click.

**Rule:** for every vendor in the cards, check whether its domain resolves to itself. A redirect to
another name means a rebrand: in the text the vendor is called "New name (formerly Old name)",
and this is recorded in `companies/<slug>.mdx`.

## Negative claims about competitors need the same proof as positive ones

The kind of case behind the rule: a draft card for Tyrell says "EOR is not supported" because
the vendor's home page carries a slogan such as "Contracts, not middlemen". That is positioning, not the absence of a product: the vendor's own pricing page may
describe an EOR plan, and independent reviews may confirm it works. In an article it would become
a false comparative claim about a competitor.

**Rule:** "vendor X cannot do Y" is confirmed by a product page, a pricing page or an
independent review — never by a marketing headline and never by the absence of a mention.
If it could not be verified, we write what the vendor publishes, not what it supposedly lacks.

## A vendor's positioning is described in its own words, not in our observations

The kind of question proofreading raises: "Oscorp is mostly used by design studios and small
agencies — is that positioning real, or was it invented for the sake of uniqueness?" Such a
phrase looks like a fact and is a generalization.

**Rule:** "vendor X is positioned as Y", "is known for", "mostly serves" is a claim about
the vendor and requires a row in evidence with the vendor's own wording or an
independent review. Without such a row we write what the vendor publishes: which products and plans
are named on its pages and for whom they are described there. The observation "this is how it is usually
perceived" does not go into the article: it cannot be verified, yet it sounds like an established fact.

## Links

- **Internal links follow sense, not a quota.** Where a link helps the reader, it is there;
  there is no need to push one into every paragraph. A numeric reference, if one is needed: 3–8 per article.
- Addresses are taken ONLY from `config/site-urls.json` (the map of the site's live URLs). A link to a
  page that is not in this file is an error, not a find.
- **Outbound links to competitors: zero.** Their addresses stay in the internal evidence log.
- The rule "one link to Example Co" does not apply on the blog: we are Example Co.
- **Link to the home page.** The default destination is the home page; do not vary addresses for
  the sake of variety. Audience pages (`/founders/`, `/finance-teams/`, `/operations/`, `/agencies/`)
  go in only when the page is genuinely about the sentence's subject: scattered across an article
  they look random. The ceiling "no more than two links to one address" does not apply to the home page; for all other
  addresses it stays.
- **Only pages in the article's language.** An English article must not link to a blog article
  written in another language. The site's
  `<html lang>` attribute may be the same on every page, so the page language is determined from the title: every
  entry in `config/site-urls.json` has a `lang` field, and `scripts/lint_article.py` checks it against
  the language from `job.yaml`.

## Length

There is no ceiling. The task is to cover the topic in full without padding or repetition; the result may be
a short article or a long read. The writer does not receive a total length, a competitor range,
a minimum, a target size or per-section word budgets. `brief.md` and `sections.json` carry no numeric
length targets. The full approved H2-H4 structure defines the content without detailed
micro-briefs and minimum bullet lists for each section. The writer receives it whole and then,
in one persistent session, writes one complete H2 with all its approved H3/H4 per
message. The next H2 is handed over immediately after the previous one is finished.
Every nested block,
including company cards, is developed in full; combining H3s into one
request is no reason to compress their content. The word
count is measured only after writing — for process analytics, platform limits and metrics
normalised by length. By itself it triggers neither expansion nor shortening of the text.

## SERPs for English articles

For **every** English topic, whatever its category, four English-language SERPs are collected:
US, GB, DE and AU. The script fetches repeated URLs once but keeps every geo and position
in which the page appeared. The strategist compares shared intents and regional differences and builds
the full hybrid structure across the whole corpus. The US SERP is not treated as universal by
default. A regional difference goes into the article only when it helps cover the topic; four
SERPs do not mean four mechanical country sections.

Clarification from the publisher: the SERP collection countries define only the sample
of results and structures. They do not set the countries for research, examples, text, the FAQ or
visuals. An article may have fewer or more countries, or a suitable regional
level (for example the EU). Every mention of a country must help a specific
decision of the reader, not tick off a geo from the SERP. Do not repeat the US/GB/DE/AU set across
sections and do not add Australia for the sake of sample completeness. Keep the jurisdiction of a legal
fact: a national rule must not be renamed into an EU-wide or worldwide rule.

The full hybrid structure is the deduplicated union of all useful intents, questions,
entities, distinctions, examples and subtopics from the relevant pages. Only exact repeats,
irrelevant material, navigation and advertising noise are removed. A useful subtopic is not removed for brevity,
a neat table of contents or a numeric cap on sections. The structure is further enriched with what
the top results lack: GIST provides independent proven value and synthesis, Reddit Mapper provides the reader's language,
objections, hidden criteria and questions. Reddit does not serve as factual proof. The final
article must answer the query more fully and more usefully than any single page in the SERP.

## Clustering

An article links to the supporting materials of its cluster where they exist: the glossary,
country guides, neighbouring blog articles. If the supporting page does not exist yet, we do not invent a link.

## Topic queue

The source of blog topics is the sheet named in `config/temnik.json`. We go strictly top to bottom. A more
attractive topic further down cannot be taken until the previous empty row has been checked. If a topic
belongs to country guides or the glossary, is already covered by a separate page, or does not fit the
positioning, the row is marked skip or duplicate (`scripts/temnik.py skip`, with `--duplicate` for a duplicate) with a specific reason. An overlap
in definitions or mandatory subtopics is not in itself a duplicate: every standalone article
covers its own intent in full.

The topic and `Top keyword` fields are hints taken from someone else's page, not our finished title.
A number (`Top 10`), a year and a competitor's wording are not inherited automatically. The main query
is derived from recurring wordings in SERP titles, descriptions, HTML titles and H1s, and then
our own H1 is created. In `Best` and `Top` articles the current year may appear in the H1 and metaTitle;
there is no year in the slug. The number of companies is defined by the full pool of strong relevant candidates,
not by the number in the competitor's topic.

**Do not write review articles about competitors.** Topics of the form
`<vendor> review`, including reviews of a competitor's individual payroll/EOR/HR products, are not
taken for the blog and are marked in the topic sheet as skipped with this reason. The rule concerns
the review format specifically; standalone comparisons and alternatives are assessed separately by closeness to
the product, intent and absence of a duplicate.

## Markup for Strapi

The article body goes into the `contentHtml` field and passes through the sanitizer's allow-list. What
follows from that for the writer:

- **Headings in the body start at H2.** The page renders H1 itself from the `title` field; an H1 in the body
  would give the page two top headings.
  **This rule is about the HTML that goes into `contentHtml`, NOT about `edited.md`.** In `edited.md`
  the first line is an H1 — and must be: `scripts/md_to_strapi_html.py` takes the article
  title from it and does not carry it into the body. The clarification exists because the wording
  confused two agents: one removed the H1 from the working file, the other flagged it as a defect. Nothing has to
  be removed, the converter does it itself.
- Headings deeper than H4 do not survive — do not use them.
- Tables are supported; a comparison may be given as a table.
- Images only with an absolute address (`https://…`); a relative path is thrown out entirely.
- Allowed markup: paragraphs, **strong**, *em*, lists, links, quotations, code, a horizontal
  rule, tables, images with a caption. Everything else disappears silently on the site.

## Meta fields

Every article brings with it: `metaTitle` ≤70 characters, `metaDescription` ≤200, `summary` ≤400,
`slug` — lower-case Latin letters, unique across the whole blog. Only for the article type
"competitor + Alternatives" the slug always has the form `<competitor>-alternatives`: after
`alternatives` no year, product category, author angle or any other tail may be added.
The rule does not extend to other article types. Tags are not set — the tag set
has not been decided.

## How the blog articles that rank are written (a measurement)

Compare the published "X alternatives" articles that already rank and were checked by an editor
with fresh machine-written drafts. The live articles' manner is the model, not something to
improve. Record the comparison in a table of this shape (the numbers below are illustrative,
measure your own site):

| | live articles | machine-written |
|---|---|---|
| list items per article | ~250 | ~80 |
| "you / your" addresses | ~180 | ~40 |
| mentions of Example Co | ~45 | ~12 |

**Tone: with the reader, not about the market.** The live articles talk — well over a hundred addresses per article.
They name the reader's situation in plain words: "agreements are scattered, approvals are buried
in threads, finance has no supporting documents". The machine-written ones describe market categories
from a distance. Write in the second person and name the pain, not only the structure of the market.

**Paragraphs follow sense, with no numeric norm.** One paragraph holds
one coherent thought; paragraph length varies naturally. Do not split a normal paragraph and do not
merge several thoughts for the sake of a metric. A real enumeration is formatted as a list, but the length
of a paragraph is not in itself a reason to turn it into a list or send it for revision.

**Name Example Co by name, not by hints.** In the live articles the brand appears dozens of times
and it does not look pushy, because every mention carries a fact. A handful of mentions per
long article is a sign that the author is shy of the subject.

**Do NOT pad the length.** Live articles may well be longer than machine drafts, but length does not work
by itself: for example, a very long article about a low-demand brand can bring a few thousand
impressions and a handful of clicks, while a short article about a high-demand brand brings ten
times more. Length is set by the completeness of the topic, not by imitation.

## IndexNow: example.com has its own key, another site's key is not reused

A key that belongs to another site is not placed on example.com: every site
has its own key, and the publisher creates a separate one for example.com. Do not propose another
site's key on a different domain.

Until the key file exists (`/<key>.txt` returns 404), nothing is submitted; the key is added by the publisher.
Once the file is in place, submitting addresses after publication becomes an ordinary pipeline step.

**Google cannot be notified programmatically:** the Indexing API officially works only for job postings and
livestreams, and Google switched off the sitemap ping in 2023. What remains is the manual "URL Inspection →
Request indexing" and the sitemap — new articles appear in the blog sitemap by themselves.

## Slug without a year

There must be no year in addresses — for example `northwind-alternatives`,
`contoso-alternatives`, `globex-alternatives`. A year in
the address means that every January the address has to be rewritten with a redirect and a loss of
signals, although the article itself is refreshed by editing the text and the update date.

A slug of the form `<brand>-alternatives-<year>` is an error even when it is caught right after
publication: renaming it costs a redirect. The format: `<brand>-alternatives`. In the title and in
metaTitle the year stays — there it works for the click and is updated together with the text.
Checked mechanically: `scripts/strapi_publish.py` does not send a slug with a four-digit year.

## Publication: from the pipeline, but only with an explicit flag

The rule: publish straight from the pipeline rather than by hand in the admin panel. The flag
is mandatory and explicit:
`python3 scripts/strapi_publish.py --job <job> --publish` (or `--update <id> --publish`
for a draft that already exists). Without the flag the script still creates a draft — there must be no
accidental publication, `publishedAt` is passed as an explicit value in both directions.

The order of operations: draft → cover → publication. The cover is uploaded by slug and does not affect
the status of the entry, but an article should not be published without a cover.

## The vendor card: content defines form

A card starts not from a template but from research. From the SERP and additional sources we
collect every parameter that helps to choose: category, scenario, the contracting or
legal-employer model, countries and the way they are covered, sign-up, documents, payroll/benefits,
visa options, integrations, support, price and extra costs, termination and switching,
strengths, limitations and the situations where the vendor does not fit. The set changes with the topic and
is neither a mandatory checklist nor a ceiling.

The presentation is chosen after the content is planned: a table for genuinely comparable
parameters, a list for an enumeration, labelled blocks for scanning, prose for explanation and
assessment. Neither a headerless table, nor six rows, nor two or three paragraphs, nor a Key
features block is mandatory. Useful researched material must not be removed to fit a template. At the same time
comparable facts must be easy to compare, a table is not then repeated in ordinary text, and all
vendors receive equally serious research, honest strengths and limitations.
This rule replaces the earlier fixed card format and its ceiling.

## The «X vs Y vs Example Co» format: what own_product_rank means in it

The rule: the title of every head-to-head comparison of two competitors
must contain `vs Example Co`. The rule applies both to new articles and to
comparisons already written that are being prepared for publication. Example Co must not be passed off as a third
provider of the same service when the competitors offer payroll, staffing or EOR; the difference is explained by
the text, not by the title.

**Template for titles and meta:**

- H1: «A vs B vs Example Co: Which Fits Your Work with Contractors Abroad?» The tail changes from article to
  article: «…Your Business?», «…Your Finance Team?».
- metaTitle: «A vs B vs Example Co: 2027 Comparison & Reviews», no longer than 60 characters. If longer —
  «…: 2027 Comparison», then «… (2027)».
- metaDescription: «A vs B vs Example Co in 2027: compare …, with a review of each platform»,
  130–155 characters.
- No «best», «better», «expert reviews» and no category descriptors like «EOR vs Contractor
  Paperwork».

The format is not a listicle but a face-off of two platforms that the buyer
already compares, plus us as the third. The order in the title is set by the format itself, and Example Co
stands third in it (for example "Northwind vs Fabrikam vs Example Co"), which is also what
comparison pages of this shape usually do.

So `own_product_rank` reads differently here than in a listicle. The placement is still a recorded
publisher decision in `job.yaml` (`own_product_placement` and, when `ranked`, the rank); the job
template's default `own_product_rank: first` is not that decision. When the recorded rank is
`first`, it means: **Example Co is the recommendation for the contractor-paperwork task, it gets
the same depth of analysis as the others and it wins the verdict for that task**, not "goes as the
first section". With another recorded rank the verdict follows the evidence and the recorded
decision. Agents must not understate the recommendation the decision records, and must not
inflate it beyond that decision. A negative label is not a mandatory part of the verdict: it is
enough to limit the recommendation correctly to contractor paperwork and not to attribute payments
or EOR to Example Co.

## Category-mismatch exception for provider lists

If an article ranks a specific category to which Example Co does not in fact belong —
for example EOR providers, staffing agencies or payment providers — Example Co must not be inserted into that list
or table as if it were an EOR, a staffing agency or a payment provider. The approved brief moves it into
a separate frame of comparable depth: Example Workspace for contractor paperwork.

In that format, when the recorded publisher decision is `ranked` with rank `first`,
`own_product_rank: first` means that Example Co is the first and strongest recommendation
for the contractor-paperwork scenario and is not understated in the final decision path. It does not mean
literally the first row of another category's list. The "one ranked list" rule still applies
when all entries honestly belong to one category or the article explicitly ranks cross-category
alternatives under a single methodology; a separate category-safe frame from the approved brief is not a
forbidden split-list.

## Placement of Example Co in listicles is agreed separately

For every listicle, ranking, `Best` or `Top`, before evidence and writing, the publisher separately
confirms `own_product_placement`: `ranked`, `separate` or `omit`. The default value
`own_product_rank: first` is not in itself such a confirmation.

- `ranked`: Example Co genuinely answers the main intent of the list; the rank itself (one of the
  values the job template accepts for `own_product_rank`) is agreed separately and recorded.
- `separate`: Example Co is not part of the ranked list and its comparison table; one
  non-ranked block after the full answer to the main intent is allowed.
- `omit`: Example Co is not mentioned as an option in the article.

The strategist has no right to widen the category or change the criteria only to put Example Co first.
For example, in a list of sites for finding and hiring contractors, a service without a sourcing function does not become
"the best hiring site" by adding post-hire operations. The placement decision is shown to
the publisher together with the H1, the angle and the full structure, and is recorded in `job.yaml`.

A separate product rule: Example Co does not run background checks or verify a
contractor's identity, and there is no «vetted contractors» badge. These wordings («background
checks», «identity verification», «vetting», «vetted contractors») are used neither in the article, nor in
evidence, nor in the company card. Only confirmed functions are described: agreements from templates, e-signature, invoice
collection and approval, the document trail per contractor, exports to accounting software.

Topic selection in this format follows the SERP, not the volume of demand: a pair query may show a
couple of thousand impressions while most of the top-20 results are news about something other
than choosing a vendor (for example a lawsuit, a merger or an outage) — there is no buyer
query there, and the article is not written. The run is stopped at the SERP, and the reason is recorded in the job folder.

## A price that is not on the vendor's site

The typical failure: several articles name a price for a vendor's product — say "$NN per
employee per month" for Northwind's payroll — and a check with three live requests (the pricing
page, the product page and the use-case page) finds it nowhere: the pricing page lists other plans
and prices, and payroll is not among them. The confirmation exists only in a paraphrase of
search results, not on a page. Meanwhile the same figure turns out to be the published price of a
neighbouring vendor in the same article, and the figures have been mixed up between the vendors.

Two rules follow:

1. **A search engine's paraphrase is not a source.** A row in the evidence is confirmed by an opened
   page with a quotation, not by a summary of search results.
2. **Neighbouring vendors get their prices mixed up.** When two vendors in one article have the same
   figure, that is a reason to re-check both, not a sign that the plans coincide.

Every published article that carries such a price is corrected in Strapi; the publication dates
are not touched.

## Public ≠ on the pricing page

The typical failure: an article claims that a vendor does not publish a limit of one of its
plans or add-ons. The pricing page shows only one headline figure, while the vendor's terms of
service carry the full wording with every limit. Only the price of an add-on itself may be
genuinely unpublished, for example when the terms say the amount is shown inside the product
after sign-up.

The rule: **before writing "the vendor does not publish X", check not only the pricing page
but also the legal documents** — terms of service, terms of use, the product page. The wording
"not on the pricing page" is verifiable and honest; "does not publish" is a claim about the whole site, and
it has to be proven accordingly. Every published article that carries such a claim is corrected
in Strapi; the publication dates are not touched.

## «X, not Y» contrasts: two counts, do not confuse them

QA gate 7 counts STRICT appositions — "a platform, not a payroll tool" — and its ceiling is roughly
one per thousand words, that is five or six for a long article. `scripts/lint_article.py` counts MORE BROADLY:
it also catches "rather than", "instead of" and any construction with a comma before not. By this
broad count the published reference articles (`reference_manner` in `config/brand-rules.json`) come
to a couple of dozen per article, and that is the norm, not an excess.

Agents tend to take the gate's ceiling for the broad count and cut contrasts where
they help the reader. The rule is simple: in the assignment, name which count is meant.
An excess is visible when the broad count goes far beyond the reference value (for example,
half as much again or more).

## Tables

**The summary table** — one per article, **no more than five columns**, placed **right after the key
takeaways**. Wider than five columns, the cells in the layout shrink to
one or two words per line.

**An article may have more than one table — where tables are appropriate.**
A table is appropriate when HOMOGENEOUS entities are compared by THE SAME attributes and there are
more than two attributes: the delimitation of market categories, vendors' pricing models, what each one publishes and
does not publish, the match between scenario and choice. The width limit is the same: five columns.

A table is NOT appropriate where the content is reasoning, a sequence of steps or an enumeration
without shared attributes: those are easier to read as a list, and in a table they turn into a set of long cells.
A table row is a fact, not a paragraph: if a cell ends up holding a sentence with a subordinate clause,
the content belongs in the text.

A headerless parameter table (`| | |`) is a legitimate device for cards and call-outs; the converter outputs
it without an empty header.

## Skeleton of an «X alternatives» article

The skeleton is taken from the site's own published «X alternatives» articles that rank for
brand queries and were checked by an editor — it is what already works, not a hypothesis:

what X is → what counts as an alternative to X → delimitation of market categories (payroll,
contractor management, contractor paperwork, EOR, Agent of Record, freelancer marketplaces,
payment services) → why companies leave X → selection methodology → vendor summary →
vendor cards, with Example Co placed as the recorded `own_product_placement` decision says
(`ranked` at the recorded `own_product_rank`, a `separate` block, or `omit`) → alternatives by
scenario → **Example Co vs X** → how to compare and switch → conclusion → FAQ of 6–12 questions.

**The skeleton is the same for every article in the queue.** Do NOT invent
sections of your own, and no author angle is set: `author_angle` in the assignment stays
empty unless the publisher wrote it personally. Articles written to one skeleton, checked by an
editor and ranking, show that uniformity here is a value, not a flaw.

Why this does not contradict the general wish for unique sections: uniqueness matters when
several texts answer the same query and compete with each other. Here it is the opposite — N
different vendors on one blog. Every article has its own subject, so the same frame creates no
footprint and helps the reader: they recognise how the page is built and find what they need in
the same place.

Articles must differ in the evidence about the vendor, not in invented concepts such as "choose by
whose side the tool is on". Such frames are an attempt to make the text original where
clarity is needed.

Measured on your own site, length does not decide: the shortest article in a queue can bring
many times more impressions than the longest one. Demand for the brand decides. Length is set by the completeness of the
topic, not by a wish to outdo a competitor in character count.

## Competitor images — not used

The rule: **no logos and no screenshots of competitor sites in blog articles.**
It is written down explicitly because the silence of a rule reads as permission.

The analysis on which the rule was made:

- **A screenshot of a home page** reproduces someone else's work in full — the design, the texts and
  the third-party licences inside it. A vendor's home page may be running a campaign with a
  well-known person: those are rights to that person's image, which nominative use of a trade
  mark does not cover. In addition a screenshot goes stale together with the other site, while a comparison must
  remain not misleading. Some vendors are closed behind a bot wall and cannot be captured at all
  (the page returns a 403).
- **A logo** is better covered by the legal frame: `legal.md` allows nominative use for
  identification under conditions (alt "<Company> logo", one size for all, no impression of partnership,
  no recolouring). But vendors' brand books usually require written permission, and although the law
  does not make such requirements binding, the risk of a claim is not zero.
- **Market practice is mixed:** some comparison pages put a screenshot of a competitor's home page
  in a browser frame, some use images with the vendor's name, and some vendors in their own
  comparison articles show only THEIR OWN interface and take nobody else's.

If the rule is revisited, checks are added to QA gate 4 together with it: alt text of the form
"<Company> logo", the same size for everyone including our own, no composition
that reads as a partnership. There are no such checks now — the rules are written in `legal.md` but
nothing enforces them, because there have been no images in the articles.

## Cover

Drawn by the generator `tools/covers/article-covers.mjs` from the article title —
typography in the brand colours, 1200×800, the same tool the glossary uses. It is run
after the draft is uploaded, by slug; the draft is not published by it. We do not create templates of
our own: two different kinds of covers on one site are worse than no cover.
