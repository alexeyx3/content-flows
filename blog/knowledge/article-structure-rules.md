# Article structure rules (all tracks, all languages)
Source: distilled from publisher review comments on a first article.

## Applicability
- **The blog (the company's own site), EN + RU.** These are baseline structural rules; platform limits stack on top.

## Audience & jurisdictions
- **Write for people first, LLMs second.** GEO citability never justifies dense unreadable prose — a well-structured block is quoted just as well. Balance, don't sacrifice.
- **The ICP is a foreign company (US/EU/UK entity) with contractors in several countries.** Regulatory facts, thresholds and examples must match ICP jurisdictions: US (IRS/DOL, ABC test), EU (platform-work directive, national misclassification regimes), UK (IR35). **Regulation of any other jurisdiction is banned as argumentation** — even in articles in other languages, even when the local SERP is full of it. `geo` in job.yaml selects SERP geography ONLY; it never localizes the facts. Language is set by `language`, facts are always global.

## Structure
- **English H1-H4 use sentence case.** Capitalize the first word plus real proper nouns, brands, and acronyms — never every important word.
- **Build the fullest useful hybrid.** Treat the relevant ranking pages as a combined research corpus. The outline is the de-duplicated union of every useful intent, question, entity, distinction, example, and subtopic across that corpus, enriched with decision value the ranking pages lack. Remove only true duplicates, irrelevant material, navigation, and promotional boilerplate. Never remove a useful subtopic to make the outline shorter, tidier, or fit a numerical section limit. The article should answer the query more completely and usefully than any single ranking page. Heading depth still follows meaning: criteria or steps may be a table or list when that is clearer than extra H3/H4 headings.
- **Enrich beyond the SERP.** Use the GIST information-gain approach for genuinely new evidence, synthesis, calculations, or decision tools. Use the Reddit Mapper packet for reader language, objections, hidden criteria, failure modes, and questions competitors miss; Reddit is discovery context, never factual proof. Verify publishable facts independently before drafting.
- **No numerical outline cap.** The topic determines the number of H2-H4 headings. A short topic may need few; a broad competitive query may need many. Never merge or discard useful content merely to satisfy a fixed number of sections.
- **Standalone does not mean sentence-length.** A heading must be understandable without neighboring headings, but should remain short and natural rather than carrying the entire argument.
- **Vendor-card form follows the planned content.** Research every decision-useful dimension the query and SERP expose, plus useful missing dimensions. Then choose tables, labels, lists, and prose according to what makes that particular card clearest. Comparable facts should remain easy to compare, but no fixed row count, paragraph count, or universal template may cap the substance.
- **Cold-reader test for the first two screens.** Key takeaways and the intro must make sense to someone new to the topic: frame first ("there are N formats, here are the risk classes"), details second. Don't pack bullets with facts at the cost of clarity.
- **One motif — one section.** If risks (or any other motif) have their own section, other sections must not reopen them as framing.
- **Vendor-card headings are the vendor name only.** No "— if you plan to..." descriptors in headings.
- **Every major section carries at least one concrete example**; where a known market case exists (verified via evidence), prefer it over an invented scenario.
- **FAQ block (4-6 Q&A) before the conclusions by default** — do not drop it when the outline is fixed; ask the publisher only to REMOVE it, never to add it.
- Paragraphs 2-4 sentences; any screen of text needs a structural element (subheading, list, labeled block).

## Additions from review round 2
- **Dates in RU articles: дд.мм.гггг** («данные на 22.07.2026»), never ISO 2026-07-22.
- **Sell, don't scare.** Risk/cost framing must not frighten the reader away from the category the article promotes — frame as "how to choose well" (transparent pricing is visible upfront), not "you will be overcharged". The article's job is to make the reader act, with Example Co as the natural answer.
- **Numbered lists survive publishing**: blank lines between items must not restart numbering. The converter to Strapi HTML handles this, but keep list items blank-line-free where possible.

## Sensitive geos & topics
- Companies use Example Co for contractors in 60+ countries. **On the blog the coverage is stated only in the single wording "contractors in 60+ countries"** — no lists of regions or countries, no statements about individual countries where Example Co is or is not available. Topics about whether Example Co is available in a particular country do not appear on the blog at all.
- Paying contractors is never described as something Example Co does, in any framing; Example Co is not a payment provider. E-signature is never described as legal certification («certified», «notarised», a seal).

## Neighbouring blog articles: do not repeat each other
Neighbouring articles of a cluster draw facts from a shared evidence pool and start to look pasted together from each other.
- Reference chunks from `evidence.md` (taxonomy labels, regulator thresholds and their caveats, descriptions of vendor mechanics, API limits) are reformulated in your own words, keeping the meaning and the numbers. Rewording a label does NOT count as inventing an unverified category.
- Enumerations of proper nouns (countries, regions, currencies) get their own order and their own grouping; long lists in the H1 are not repeated between articles.
- **Each article has 2–3 sections that its cluster neighbours do not have**, not one: a single unique section across five articles gives five almost identical tables of contents. The sections are named in the brief, before the draft.
- Checklist sections ("what to check before onboarding", "what questions to ask a vendor") are the most contagious part: they are built from the scenario of this article, not reassembled from the criteria of a neighbouring one.
- Checking for verbatim matches of eight words or more against neighbouring articles is QA's duty, not the editor's: editors systematically report "no matches" where there are a dozen. Tool: `python3 scripts/text_overlap.py`.

## Links
- **There are no outbound links to competitors** — not one. Their addresses stay in the internal evidence log. On our own site we do not give weight away.
- Internal links to our own sections are placed by meaning, not by quota; addresses come only from `config/site-urls.json`. The earlier restriction of "one link to Example Co per article" does not apply on the blog.

## Length: count with a script, not by eye
- Editors and QA have no shell; their length estimates differ from the fact by several hundred words. Do not ask them to count and do not trust their numbers.
- Canon: `python3 scripts/wordcount.py --job jobs/<job-dir>` — writes the fact to `<job>/wordcount.txt` (the agent can read it) and prints to stdout. The meta block, tables, code and URLs are excluded from the count.
- An error within a hundred words is not critical; check hard platform ceilings with the script.

## Calculations in articles of a topic
- A cost calculation is NOT needed in every article of a cluster. Two or three articles of the cluster are enough; in the rest the price topic can be closed qualitatively, without arithmetic.
- Repeating the break-even comparator between articles is acceptable — it is not a problem. Only the wording and the presentation must differ, not the numbers themselves. The earlier requirement of "its own number in every article" ran into the fact that competitors' real price lists run out.
