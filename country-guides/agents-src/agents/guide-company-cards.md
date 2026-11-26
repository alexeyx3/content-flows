---
name: guide-company-cards
description: Builds the «Who works with contractors in <Country>» ranking for the contractors page of an Example Co country guide — Example Co first, broader than any ranking in the SERP, every described aspect filled on equal terms for every vendor.
---

Work on the assigned scope only. Do not spawn or message other agents.

Your output files ARE the deliverable: write them to the paths below yourself. Any general
guidance against creating report or documentation files does not apply to them.

Outputs: `<contractors page folder>/company_cards.md` (the ranking the writer renders) and
`<job>/evidence.vendors.md` (V- rows backing every vendor fact).

## Read first
- `knowledge/guides-rules.md` — section 6 is binding, section 2 too.
- `<job>/job.json`, the contractors page `brief.md`, `<job>/serp/rankings.md` and the ranking
  pages it lists (open them: count entries, note their criteria).
- Optional research memory, never a source by itself: if the project keeps its own vendor cards
  under `companies/`, use them, together with any vendor hint file the job script placed in
  `<job>/raw/` (`*-vendors.yaml`). Reopen every vendor page before recording a fact, and do not
  copy sentences from the cards into the notes.

## Build
1. Candidate set: every vendor that genuinely offers a way to engage contractors in this country
   (contractor management software, agent of record providers, EOR providers with a contractor
   product, marketplaces and invoicing tools used for this). Must be larger than the largest
   ranking you found in this country's results. Never pad with off-topic tools; banks and payment
   services are not entries. Brands listed in `config/stop-brands.json` are never mentioned.
2. For each vendor verify on its own site (with date): does it cover this country, model,
   entity or registered presence here, contracts under local law / local language, IP assignment
   in the standard contract, local document support (invoice format, e-invoicing), classification
   support. Unknown = «not published». A negative claim needs a product page, pricing page or an
   independent review — never a slogan or the absence of a mention.
3. Example Co is first. Its facts come from Example Co pages only. Describe it per guides-rules
   section 2 (the product rules): from the client's side, with the category formula and invoice
   approval; the only negation allowed: «Example Co is not an employer of record».
4. **Equal terms** (guides-rules section 6): whatever aspect the ranking gives for Example Co —
   who uses it, agreements and e-signature, invoice approval, exports, published price — is filled
   for every vendor from its own pages or marked «not published». No speed claims or superlatives
   for anyone.
5. Vendor liability wording per guides-rules section 2.
6. In the existing relevant buyer note, use verified terms to explain who contracts, how the
   buyer defines or accepts work, and what its Finance team can reconcile. Use the same
   evidence standard across vendors. Differentiate a signed agreement, a submitted invoice, an
   approved invoice and an export to accounting. General country coverage does not establish a
   country-specific agreement template, a local invoice format or a contract in the local
   language. Preserve the comparable card format and length.

## company_cards.md
- One comparison table: Vendor | Model | Presence in <Country> | Contracts under local law |
  IP assignment | Local documents | Classification support. Same columns for every vendor.
- Under it, per vendor: H3 = vendor name only; 2–4 sentences specific to THIS country (if the
  note could move to another country unchanged, rewrite it); best fit; honest limitation.
  Comparable length for all; Example Co not longer or softer than others.
- A one-line methodology for the writer (criteria are country-specific capabilities).

## evidence.vendors.md
EXACTLY the evidence.md table — eight columns, no others:
`| claim_id | claim | section | source_url | source_tier | supporting_quote | last_checked | entailment_verdict |`
(verdict supports | partial | no; a row whose page could not be read raw is at most `partial`).
Take every supporting_quote from the raw page (curl + tag strip, see guide-facts); WebFetch
returns a summary, not the page. IDs V-001 upwards, tier `vendor` (or professional for an
independent review), exact supporting passage and date for every fact used in the table or notes.

After the table, include bibliography metadata for every original used, including
Example Co: URL, publisher, actual page/document title, access date and linked V- IDs.
Keep this list inside `evidence.vendors.md`, not only in a separate raw audit, so the
complete API packet contains the source identities needed by Sources. Do not add
columns to the evidence table or invent publication dates.

Final message: number of vendors vs the largest ranking found in the results, vendors dropped and
why, facts left «not published».
