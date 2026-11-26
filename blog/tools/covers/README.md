# Covers

Draws the blog article covers and uploads them to Strapi.

```bash
npm install                        # once
node article-covers.mjs            # for articles without a cover
node article-covers.mjs --force    # redraw for all
node article-covers.mjs --slug=... --out=/tmp   # file only, no upload
node article-covers.mjs --slug=... --no-logo    # only when the publisher decides to drop the brand
node article-covers.mjs --slug=... --locale=ru --id=123 --format=png --out=/absolute/job/publication/covers
```

## Localised covers

`locale=en` is the default and the former WebP format is kept. For any
other language a single `--slug` is mandatory; bulk RU processing is forbidden.
`--id` additionally binds the chosen slug/locale to the exact numeric CMS ID.
A response with a different locale, slug or ID is blocked before upload/association; the same
check is repeated before the link to the media is written. A changed title or
a concurrently replaced cover also blocks the write.

`--out` always means **local render only**. Next to the source image
`.390.png` and `<image>.render.json` appear: the full title, ID/locale/slug,
dimensions, line layout, glyph check and SHA-256 of both files. Cyrillic comes
from a separate Exo 2 file. A missing glyph or a full title that does not fit
blocks the render; the text is never truncated. For PNG use `--format=png`.

After an independent visual check and explicit authorisation of the CMS media upload,
upload **the same verified bytes**, without regenerating:

```bash
node article-covers.mjs --slug=contractor-onboarding --locale=ru --id=123 \
  --file=/absolute/job/publication/covers/contractor-onboarding.png \
  --receipt=/absolute/job/publication/cover-upload.json
```

`--file` requires `--slug`, `--id`, `--receipt` and the neighbouring
`<image>.render.json`; `--out` is incompatible with it. SHA-256, format,
dimensions and the match of the render to the current record are checked. The receipt is written before the POST,
the media ID/URL before the PUT. After an ambiguous POST there is no automatic
re-upload; when the media ID is known, a retry uses it, checks the current cover and
does not create a duplicate. The final `status=complete` means the cover ID was read back.
The receipt contains `target_id`, `locale`, `slug`, `title`, `file_path`,
`file_sha256`, `format`, `cover_before`, `media_id`, `media_url`; it does not replace
an independent visual QA or the authorisation to publish.

**Where things are.** The template is in `article-covers.mjs`, the font handling in
`lib-cover-font.mjs`, the font files in `assets/`.

**Where it lives.** The tool is included in the repository so that the article
pipeline does not depend on writing into neighbouring projects. It does not run on the Strapi
server: it calls the API from outside.

**What it targets.** The Strapi address is `STRAPI_URL`, `https://cms.example.com` by default.
The token is taken from `STRAPI_TOKEN`, then from `config/strapi-api-token`, the same
source that `scripts/strapi_publish.py` uses. The logo is taken from
`assets/logo.svg`.

## Two pitfalls this was written around

**The font cannot be set through `font-family` in SVG.** sharp draws text
with the system font matcher, and `Exo 2` silently turned into Times; on macOS the directory
from `FONTCONFIG_FILE` is not read at all. So the text is drawn as outlines from
the font file.

**`opentype.js` 2.0.0 returns NaN** in the outline, depending on the font size and the fractional
baseline coordinate, and librsvg silently stops drawing on a non-numeric coordinate:
"Contractor misclassification" turned into "Contr". So
the outline is always taken in one configuration (origin at zero, natural
font size), while the position and scale go into `transform`. The code checks
for NaN so that this cannot reach the picture unnoticed.
