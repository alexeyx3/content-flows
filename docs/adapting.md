# Adapting the flows to your product

Everything that describes a company in this repository describes **Example Co**, which does not
exist. The fictional content is deliberately as detailed as the real thing has to be: the roles
check text against these files line by line, and a thin card produces thin checks.

Work through the list in order. An agent can do most of it for you: give it this file, your
positioning and editorial documents, and ask it to rewrite one card at a time while keeping the
headings.

## 1. Product rules (the part that decides quality)

| File | What to write | Used by |
|---|---|---|
| `blog/knowledge/positioning.md` | How the brand is written; the category formula and its short variants; a table "internal meaning → allowed public wording"; value pillars; what the product is not; product line; differentiation; how competitors may be mentioned; entry points by reader role and by industry | brief, writer, editor, QA, company cards |
| `blog/knowledge/blog-owned.md` | Voice of the blog; article types and their skeletons; comparison and ranking rules; title and meta templates. Most of it is process and can stay; rewrite the passages about the product | almost every blog role |
| `blog/knowledge/icp-jtbd.md` | Audience segments, triggers, jobs to be done, objections, the reader's own vocabulary, who is not your reader | brief, research |
| `blog/knowledge/editorial-owned.md`, `blog/knowledge/legal.md` | Editorial rules of your own site; legal requirements for claims and comparisons in your jurisdiction | editor, QA |
| `blog/companies/example-co.mdx` | Your own vendor card in the common card format: verified facts with a source URL and check date for each | company cards |
| `blog/companies/*.mdx`, `blog/knowledge/competitors.csv` | Cards of the vendors you compare yourself with, built from their own pages; the competitor list | company cards, brief |
| `country-guides/knowledge/guides-rules.md` sections 2 and 6, `country-guides/knowledge/product-positioning.md` | How the product is named and described in a guide; where it may appear; the vendor list on the contractors page | every guide role |
| `glossary/knowledge/positioning.md` | The short card for glossary entries | glossary editor, QA |
| `.agents/skills/copywriter/` in `blog/` and `country-guides/` | Your copywriting policy: vocabulary, forbidden wording, checklist | editor |

Keep the headings of these files. Roles and tests refer to sections by name.

How detailed is enough: for every sentence a writer could plausibly produce about your product,
the card should say whether it is allowed, and if not, what to write instead. "Never next to the
brand" lists with a permitted alternative for each item do most of this work.

## 2. Mechanical rules

| File | What it holds |
|---|---|
| `blog/config/brand-rules.json`, `country-guides/config/brand-rules.json` | The brand name and host; topics the site never covers; claims that are blocked only in a clause attributable to your brand (speed, labels, guarantees, superlatives, price words, customer counts), each as a regular expression with a message; an industry term that must not be used as your product label |
| `<flow>/config/stop-brands.json` | Brands that must never appear anywhere. Empty by default. The linter and the CMS script both read it |

The first file feeds the linters (`blog/scripts/lint_article.py`, `country-guides/scripts/check_guide.py`);
the glossary has no linter and relies on its positioning card and QA.
After editing them, run the flow's tests: the linter tests use the same file, so adjust their
fixtures to your rules.

## 3. Names and addresses

```sh
grep -rn "Example Co\|Example Workspace\|example\.com" --exclude-dir=node_modules .
```

- `Example Co` → your brand, `Example Workspace` → your product name.
- `https://example.com` → your site, `https://cms.example.com/api` → your CMS API.
- URL shapes assumed by scripts: `/blog/<slug>/`, `/glossary/<slug>/`, `/guides/<country>/`,
  `/guides/<country>/employer-of-record/`, `/guides/<country>/independent-contractors/`.
- Authors and editors: `john.roe`, `jane.doe`, `ann.poe` and their CMS user IDs are configured in
  two files, `blog/config/blog-authors.json` (read by the blog and, through `../blog`, by the
  glossary) and `country-guides/vendor/blog/config/blog-authors.json` (read by the guides). Both
  have a `defaults` block with the default author and editor; the guides take their author and
  editor from it (`AUTHOR`, `EDITOR` in `country-guides/scripts/common.py`). Change both files.
- Fictional vendors in examples and test fixtures (Northwind, Contoso, Fabrikam and others) can
  stay; they are only examples.
- The blog's topic script is called `temnik.py` and its config `config/temnik.json`: *temnik* is
  an editorial term for a topic plan. The names are kept because scripts and tests import them.

## 4. Site data

| File | How to fill it |
|---|---|
| `blog/config/site-urls.json` | `python3 scripts/fetch_site_urls.py` builds it from your sitemap. Writers may link only to addresses in this file |
| `country-guides/config/site-links.json` | `python3 scripts/fetch_links.py` |
| `country-guides/config/queue.json` | Your queue of countries with the search query for each |
| `<flow>/config/geos.json` and `glossary/config/glossary-serp-geos.json` | Search markets for SERP capture. Country and search-domain IDs are your SERP provider's |
| `blog/config/site-brand-tokens.json`, `country-guides/config/site-brand-tokens.json`; logos in `blog/tools/covers/assets/logo.svg`, `glossary/tools/covers/assets/logo.svg`, `country-guides/vendor/brand/logo.svg` | Palette and logo for charts, diagrams and covers. The glossary's cover reads the blog's palette (`yellow.default` and `black` in `blog/config/site-brand-tokens.json`; `glossary/tools/covers/render-glossary-cover.mjs` has fallback values used only when that file is missing). Fonts are open fonts bundled with the cover tools; replace them with your own |
| `blog/config/topic-sheet-template.csv`, `glossary/config/topic-sheet-template.csv` | Import into a Google Sheet; see each flow's `docs/topic-sheet.md` |

## 5. Second language

The blog supports a second language, with Russian as the worked example: translation of published
English articles (`knowledge/blog-translation.md`), a search market for Russian results in
`config/geos.json`, morphology checks for refreshes, and Russian patterns in the humanizer and
linter. To use another language, add its search market, its patterns in
`.agents/skills/humanizer/references/ai-patterns.md` and its typography rules in
`knowledge/draft-rules.md`, and adjust the translation card. If you publish in English only, the
Russian parts stay inactive.

## 6. Integrations

| Integration | Where | If you use something else |
|---|---|---|
| SERP provider | `blog/scripts/fetch_google_serp.py` (XMLRiver first, DataForSEO second) | Replace the provider functions; keep the CSV columns the brief builder reads |
| Google Sheets, Docs, Drive | `sheets_client.py`, `temnik.py`, `gdoc_review.py`, `md_to_gdoc.py` | The topic queue and the review document are the two human touchpoints; any replacement needs to keep "preview by default, write with a flag" |
| CMS | `strapi_publish.py`, `strapi_glossary.py`, `strapi_guides.py`, `tools/sanitize/check.js` | Replace the publish scripts and keep the package format in the job's `out/` folder. Set the sanitizer's allow-list to what your CMS keeps, otherwise the "HTML survives the CMS" check is meaningless |
| IndexNow | `indexnow_blog.py`, `indexnow_glossary.py` | Optional; needs your key file at the site root |
| OpenRouter | `blog_openrouter.py`, `glossary_writer.py`, `guide_api.py` | Optional in the blog and the glossary: choose the native writer when creating a job. Required in the country guides, whose writer runs only through the API |

## 7. Models

`<flow>/config/codex-model-routing.json` names the models the flows were tuned on. When you move
to newer models, keep the split between strong, mid and light roles described in
`docs/how-it-works.md` (the table there maps every model ID in the three files to its class), and update the pinned OpenRouter routes and price caps in
`blog/config/blog-openrouter.json`, `glossary/config/codex-model-routing.json` and
`country-guides/config/guide-execution.json`. The scripts verify the model and provider reported
in each response against these files and stop on a mismatch. In the country guides the expected
model names are also checked in code: `scripts/guide_api.py` (`load_profile`) and
`OPENROUTER_SNAPSHOTS` in `scripts/openai_guide_experiment.py`; change them together with the config.

## 8. Copies that can diverge

Some files exist in more than one copy. A change to one does not reach the others, and the copies
already differ in places, so edit each one on purpose:

- The CMS sanitizer exists in three copies: `blog/tools/sanitize`, `glossary/tools/sanitize`
  and `country-guides/vendor/blog/tools/sanitize`. Set the allow-list to what your CMS keeps in
  all three.
- `country-guides/vendor/blog/` holds older copies of the blog scripts the guides use (including
  its own `lint_article.py`, `strapi_publish.py`, `render_visuals.py`, `md_to_strapi_html.py`), and
  its own `config/` with `blog-authors.json`, `geos.json` and `site-urls.json`. The guides never
  read `../blog`; update the vendored copy when you change the blog version, or leave it as it is.
- Authors: `blog/config/blog-authors.json` and `country-guides/vendor/blog/config/blog-authors.json`
  (see section 3).

## 9. Check

1. Tests of each flow pass (`docs/setup.md`).
2. No fictional names are left outside the tests:
   `grep -rn "Example Co\|Example Workspace" --include='*.md' --include='*.json' --include='*.mdx' . | grep -v -e /tests/ -e node_modules`
   returns nothing. Test fixtures may keep them; adjust the tests that assert on them.
3. Run one job end to end with publication switched off and read the review document as an
   editor would. The first run usually shows which card was left too thin.
