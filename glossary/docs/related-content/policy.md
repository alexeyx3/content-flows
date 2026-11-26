# Related content for the glossary

## Reader purpose

`relatedTerms` and `relatedArticles` answer different follow-up questions. A related term explains a prerequisite, the next concept in a process, or a distinction readers commonly need. A related article helps the reader apply the term through a task, workflow, or comparison. Select each destination because it helps the reader continue from the source page, not because two titles share a word. Contextual links inside the article can coexist with these blocks.

There is no required count. Prefer a small set of strong links: usually 2–4 related terms and 0–2 related articles when suitable destinations exist. The current page renders at most six terms and three articles; those are interface limits, not targets. Leave either list empty with a recorded reason when the live catalog has no useful destination.

## Selection and review

1. The brief proposes candidates from the **published, English, indexable** glossary and blog inventories, naming the specific reader question each destination answers. A planned article is not a live destination.
2. The editor reads the candidate destination, checks its actual scope and currency, and orders the useful links by reader value. Check worker type, jurisdiction, terminology, and the source page's intent. Exclude a near duplicate, a misleading analogy, an outdated article, a promotional detour, and a destination that merely restates the source.
3. QA checks the reviewed list against both pages. For terms, classify the relationship as `prerequisite`, `next_step`, or `distinction`; for articles, as `application`, `workflow`, or `comparison`. Record one short, concrete reason per link. The classification explains selection; it does not force a link of every type.
4. At the end of a publication batch, revisit candidates against the now-live batch and review useful links **from older pages to new pages**. Relationships are directional. Add the reverse direction only when it independently helps readers of that page.
5. Before a CMS update, confirm the destination belongs to the correct Strapi collection, has a live canonical English URL, returns HTTP 200, is indexable, is not the source page, and fits the page's displayed cap. Verify the actual relation fields and rendered blocks after the update. Preserve unrelated fields and existing justified links. Serialize Strapi writes and follow the project's explicit authorization rule.

Keep a reviewable relation manifest for each batch or backfill: source slug and Strapi ID; ordered destination slugs and IDs for each block; relationship type and reader reason; exclusions or an empty-list reason; reviewer and check date; current relation values; and post-update verification. Refresh the catalog with `scripts/glossary_related_inventory.py`, then run `scripts/glossary_related.py preview` on the reviewed manifest. Its `apply` mode checks live values against the snapshot, writes only changed relations, and verifies the public API and rendered blocks. It must not select semantic relationships or run before editorial review and an authorized Strapi action. For a large verified backfill, notify IndexNow once through the glossary sitemap after the updates are complete.

## Initial backfill

When the flow is introduced on a site that already has published glossary terms, start with a backfill. Save a dated inventory snapshot of the live glossary terms and English blog articles with `scripts/glossary_related_inventory.py` (for example `inventory-<YYYY-MM-DD>.json` next to the manifest). Review every published source page, including any links its blocks already hold, then apply approved changes in small serial batches and verify the rendered pages. Afterward, repeat the relation review whenever a new glossary batch goes live.
