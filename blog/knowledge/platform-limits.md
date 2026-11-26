# Publication format: the Example Co blog
**Applies to: the Example Co blog.** A purely operational card; there are no wording restrictions here.
Distilled from the blog's CMS contract and the publisher's decisions on length and publication;
it describes this one blog.

## Length

**No ceiling.** The task is an article that ranks and is
cited, and that can be a long read: measure the median length of your own published articles
(for example, a blog whose median is several thousand words, with a good share of long reads)
before believing any ceiling.

- Competitor word counts from the SERP are a research diagnostic only. They are never copied
  into `brief.md` or `sections.json`: neither carries a total length, a competitor range, a
  minimum, a target or per-section word budgets. `scripts/validate_article_brief.py` rejects a
  brief or a section instruction that exposes a word-count target. Length follows from the full
  approved H2–H4 structure (see «Length» in `knowledge/blog-owned.md`).
- QA does not block on length: the actual length goes into the report as a reference line.
- Count the length with the script, not by eye: `python3 scripts/wordcount.py --job jobs/<job-dir>`.
  Agents have no shell, and their estimates differ from the fact by several hundred words.

A fixed editorial word ceiling that has never been measured against what the blog already
publishes is not used: an unmeasured default can differ by a factor of two from the real articles.

## Tables

Supported: the blog has its own renderer and the article body is stored as HTML. A comparison may be given as
a table where it reads better than prose. The site itself wraps a table in a container with
horizontal scrolling; there is no need to care about layout.

## Markup of the article body

The body goes into the `contentHtml` field and passes through the allow-list of the Strapi sanitizer
(the reference copy is `tools/sanitize/check.js`). Everything that is not on the list disappears silently.

| | |
|---|---|
| Headings | **H2–H4 only.** The page renders H1 itself from the `title` field; H5 and deeper do not survive |
| Text | `p`, `strong`, `em`, `s`, `u`, `sub`, `sup`, `br` |
| Lists | `ul`, `ol`, `li` |
| Other | `a`, `blockquote`, `code`, `pre`, `hr` |
| Tables | `table`, `thead`, `tbody`, `tr`, `th`, `td` (cells may carry `colspan`, `rowspan`, `scope`) |
| Images | `figure`, `img`, `figcaption`; absolute address only — a relative path is thrown out |
| Classes | only `figure.table` and `figure.image` |
| Link schemes | `http`, `https`, `mailto` |

Converter: `python3 scripts/md_to_strapi_html.py --input <job>/edited.md --output <job>/out/article.html`.
The check is mandatory: the output must survive the sanitizer byte for byte
(`node tools/sanitize/check.js < article.html | diff - article.html`).

## Meta fields for publication

Count in characters, deliver in `out/meta.md`:

| Field | Limit |
|---|---|
| `metaTitle` | ≤70 |
| `metaDescription` | ≤200 |
| `summary` | ≤400 |
| `slug` | lower-case Latin letters, digits and hyphens; unique across the whole blog |

Slug uniqueness is checked by `scripts/strapi_publish.py` before sending: the public API does not
return drafts, and Strapi rejects a duplicate only at write time.

## Publication

`scripts/strapi_publish.py` creates a **draft** by default (an entry with `publishedAt: null`).
It publishes only with the explicit `--publish` flag, and the pipeline runs that only on an
explicit publisher request in the current conversation. Otherwise the publisher publishes the
draft in the admin panel.
