"""Mechanical proofreading of a finished page against the hard bans of the track.

Every rule here encodes a recurring publisher edit. Caught by eye, such slips get through:
a mixed-case abbreviation can repeat across a whole text, or an internal wording can reach an
article that has already been sent out. The QA gate checks them too, but an agent reads and
reasons, while grep does not get tired and costs nothing.

Only what is visible in a line is checked. Matters of meaning (card parity, the order of
our own card, entailment of facts) stay with the QA agent and the orchestrator.

Writing-craft rules live in this file. Everything that is the company's own editorial
policy — the brand, banned topics, labels and wording that must not stand next to the
brand — is read from the project's config/brand-rules.json; the brand lists are read from
config/stop-brands.json.

Usage:
  python3 scripts/lint_article.py --job jobs/<job-dir>            # edited.md
  python3 scripts/lint_article.py --input <file> --subject <brand>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]        # the country-guides project that vendors these scripts

NEVER = re.compile(r"(?!)")      # matches nothing: an empty list blocks nothing


def compile_stop_brands(brands: list[str]) -> re.Pattern[str]:
    """Stop-list entries -> one pattern. Each entry is a whole word, case-insensitive;
    a trailing * makes it a prefix. An empty list never matches."""
    parts = [r"(?<!\w)" + re.escape(name.rstrip("*")) + ("" if name.endswith("*") else r"(?!\w)")
             for name in (item.strip() for item in brands) if name.rstrip("*")]
    return re.compile("|".join(parts), re.I) if parts else NEVER


def any_of(patterns: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I) if patterns else NEVER


BRAND_RULES = json.loads((PROJECT / "config" / "brand-rules.json").read_text(encoding="utf-8"))
BRAND: str = BRAND_RULES["brand"]
PRODUCT: str = BRAND_RULES["product"]
SITE_HOST: str = BRAND_RULES["site_host"]
_BRAND = r"(?<!\w)" + re.escape(BRAND) + r"(?!\w)"       # the brand as a regex fragment
_HOST = re.escape(SITE_HOST)
BRAND_RE = re.compile(_BRAND, re.I)

_BRAND_LISTS = json.loads((PROJECT / "config" / "stop-brands.json").read_text(encoding="utf-8"))
# Never mentioned anywhere, with no exception for the subject of the page itself.
STOP_BRANDS = compile_stop_brands(_BRAND_LISTS.get("brands", []))
# Named only on a page about that brand, or in their own card of a guide's vendor ranking.
SUBJECT_ONLY_BRANDS = tuple(_BRAND_LISTS.get("subject_only_brands", []))

# The arrangement may be described — “works on an <industry term> model”; the label and the
# product name may not. The word after the term tells a scheme from a label.
_TERM_RULE = BRAND_RULES["industry_term_not_a_label"]
_TERM = r"\b" + re.escape(_TERM_RULE["term"]) + r"\b"
TERM_SCHEME = r"(?!\s+(?:" + "|".join(re.escape(w) for w in _TERM_RULE["scheme_words"]) + r")\b)"
# A table-cell border breaks the window: in a comparison row “… (<industry term>) |
# One agreement with <brand> …” the neighbouring cells speak about DIFFERENT vendors.
TERM_SELF_LABEL = re.compile(
    _TERM + TERM_SCHEME + r"(?=[^.|]{0,80}" + _BRAND + r")|"
    + _BRAND + r"[^.|]{0,60}" + _TERM + TERM_SCHEME, re.I)
NEGATION_PARAPHRASE = any_of(BRAND_RULES["negation_paraphrases"]["patterns"])

PRODUCT_QUARTER = re.compile(r"\b(?:in|by|during|from)\s+Q[1-4]\s*20\d\d\b|\bQ[1-4]\s*20\d\d\b", re.I)
# Our own search query in quotation marks as the topic of a sentence.
QUOTED_QUERY = re.compile(r"[“\"]([^”\"]{3,60}\b(?:alternatives?|vs\.?|pricing|review)\b[^”\"]{0,40})[”\"]",
                          re.I)


def statistical_quarter(line: str) -> bool:
    """Recognize labour-market observations and publications dated by quarter."""
    visible = re.sub(r"\]\([^)]*\)", "]", line)
    return bool(re.search(r"\b(?:wages?|salar(?:y|ies)|earnings|gross|arithmetic\s+means?|sector\s+means?"
                          r"|labou?r\s+force\s+survey|people\s+in\s+employment|unemployment|NSI|KSH|Eurostat)\b",
                          visible, re.I)
                and not re.search(r"\b(?:" + re.escape(BRAND) + r"|launch\w*|planned|coming|roadmap|rollout|products?|features?)\b", visible, re.I))


def configured_rules(block: str) -> list[tuple[re.Pattern[str], str]]:
    return [(re.compile(rule["pattern"], 0 if rule.get("case_sensitive") else re.I), rule["message"])
            for rule in BRAND_RULES[block]["rules"]]


# (pattern, message). Case is ignored unless a configured rule is marked case_sensitive.
RULES: list[tuple[re.Pattern[str], str]] = [
    # Absolute bans of the track and house wording: company policy, config/brand-rules.json.
    # A banned topic does not depend on whether the statement is true: it can reach an article
    # simply because it is a published feature of the vendor the article is about.
    *configured_rules("banned_topics"),
    *configured_rules("site_wide_wording"),
    (NEGATION_PARAPHRASE, BRAND_RULES["negation_paraphrases"]["message"]),
    (PRODUCT_QUARTER,
     "product timelines and plans do not go into the text"),
    (re.compile(r"\b(?:coming|planned|expected|launching|slated)\s+(?:in|for|by)\s+20\d\d\b", re.I),
     "product timelines and plans do not go into the text"),
    (re.compile(r"\bas of\s+(?:\d{1,2}\s+)?"
                r"(?:january|february|march|april|may|june|july|august|september|october|"
                r"november|december)\s+20\d\d\b", re.I),
     "hard-coded freshness date: the page itself shows the update date, write “at the time of writing”"),
    # “search for” in its ordinary sense (“open the alternatives search for four reasons”)
    # must not be caught — only talk about search behaviour is.
    (re.compile(r"\b(?:buyers|users|people|companies|teams|readers)\s+(?:actually\s+)?"
                r"(?:search|google|type)\b|\bsearchers\b|\bsearch intent\b"
                r"|\bsearch volume\b|\bwhat (?:people|buyers) (?:search|google|type)\b"
                r"|\b(?:buyers|readers|teams|people) looking for\b"
                r"|\ba search for\b|\bsearch results?\b|\b(?:mixed|these) results\b"
                r"|\bsurfaces? under\b.{0,20}\bqueries\b|\bqueries\b", re.I),
     "search-behaviour phrasing reads as keyword stuffing: a heading names the subject, not the query"),
    # A vendor's page as the grammatical subject: the company acts, not its page.
    (re.compile(r"\b(?:the\s+)?(?:\w+\s+){0,2}(?:pricing\s+|product\s+|AOR\s+)?pages?\s+"
                r"(?:state|states|confirm|confirms|show|shows|list|lists|say|says|describe|"
                r"describes|reproduce|reproduces|stop|stops|highlight|highlights|lean|leans)\b"
                r"|\b(?:vendor'?s?\s+own\s+|official\s+|its\s+)?materials\s+"
                r"(?:state|states|describe|describes|highlight|highlights|show|shows)\b"
                r"|\bclaims on (?:official|the vendor)\b"
                r"|\bthe (?:site|domain|website) (?:states|confirms|shows|redirects)\b"
                r"|\b[a-z0-9][a-z0-9-]{2,}\.(?:com|io|co|net|org|work|pro)\s+"
                r"(?:redirects|states|confirms|shows|describes|lists|says)\b", re.I),
     "a vendor's page is not an actor: the subject of the sentence is the company"),
    (QUOTED_QUERY,
     "your own search query in quotes as the topic of a sentence is a heavy SEO cliché"),
    # Verification narration: the reader needs the fact, not a report on how we obtained it.
    # “confirmed on close” is about handing over work, not about our check: the preposition
    # on without a vendor page does not count (it was a false positive on a vendor article).
    (re.compile(r"\b(?:confirmed|verified|checked)\s+(?:through|via|against)\b"
                r"|\b(?:confirmed|verified|checked)\s+on\s+(?:the\s+)?"
                r"(?:live\s+)?(?:\w+'s\s+)?(?:site|page|pages|website|pricing)\b"
                r"|\bvendor-page-confirmed\b|\bat the time of (?:checking|verification)\b"
                r"|\b(?:their|the vendor's) live page (?:states|shows)\b"
                r"|\bpublicly (?:confirmed|verifiable) (?:through|via)\b", re.I),
     "verification narration does not go into the text: write what the vendor publishes"),
    # A retelling of our own assignment: a brief instruction that landed in a paragraph as a
    # promise to the reader.
    (re.compile(r"\bat equal depth\b|\bdo not receive cards\b|\bnot (?:a |an )?fabricated\b"
                r"|\bone-line also-evaluated\b|\bequal card depth\b|\bsame card depth\b"
                r"|\bthe (?:vendor )?cards that follow\b|\bat the same depth\b"
                r"|\bcards? (?:below|above|that follow) (?:carry|carries|unpack)\b"
                r"|\bcarry full depth\b|\bwe did not pad\b|\bfake composite score\b"
                r"|\bsix (?:parameter )?rows?\b|\bsame six-row\b|\bparameter rows\b"
                r"|\binvented (?:number|country counts?|scores?)\b"
                r"|\bomitted rather than padded\b|\bevaluation depth\b", re.I),
     "a brief instruction is retold to the reader: describe the subject, not the method of presentation"),
    # Talk about search results and about other publishers' articles: the subject of an
    # article is the market and the vendors, not the SERP.
    (re.compile(r"\bdirectory hits?\b|\bgeneric top-\w+ lists?\b|\bcompetitor publishers?\b"
                r"|\bround-?ups?\b|\bSERPs?\b|\blistic(?:le|les)\b|\bto card\b", re.I),
     "talk about the SERP and other publishers' articles in prose: the subject is the market "
     "and the vendors, not the SERP"),
    (TERM_SELF_LABEL, _TERM_RULE["message"]),
]

LINK = re.compile(r"\]\((https?://(?:www\.)?" + _HOST + r"[^)\s]*)\)")
HOME = re.compile(r"^https?://(?:www\.)?" + _HOST + r"/?(?:\?|#|$)")
HEADING = re.compile(r"^(#{1,6})\s")


# “Do not open with what we are not” (a publisher's edit). In the vendor card and in the
# honest-limit column a negation is in its place, while in the intro it reads as a defence.
# The zone checked runs from the start to the second H2, that is the title and the key
# takeaways.
SELF_NEGATION = re.compile(
    r"(?:" + _BRAND + r"|(?:^|[.!?]\s+)(?:"
    + "|".join(re.escape(x) for x in BRAND_RULES["self_negation_intro"]["subjects"])
    + r")) (?:is |are |does )?"
    r"(?:not|isn't|aren't|no)\b|\bwrong (?:shortlist|pick|choice|tool) for\b", re.I)


def intro_zone(lines: list[str]) -> int:
    """Index of the line where the intro ends: the second H2."""
    seen = 0
    for i, line in enumerate(lines):
        if line.startswith("## "):
            seen += 1
            if seen == 2:
                return i
    return len(lines)


def code_spans(lines: list[str]) -> set[int]:
    """Indexes of the lines inside ``` — only the very hardest bans are looked for there."""
    inside, out = False, set()
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            inside = not inside
            out.add(i)
        elif inside:
            out.add(i)
    return out


ORDERED_ITEM = re.compile(r"^(\d+)\.\s")


def broken_ordered_lists(lines: list[str], skip: set[int]) -> list[str]:
    """An ordered list broken by an unindented paragraph.

    The converter closes a list at the first line that is neither an item nor indented, so
    every item ends up in its own <ol> and the numbering on the site starts again. QA found
    this in a vendor comparison: eleven lists of “1.” in a row. A continuation paragraph
    indented by two to four spaces stays inside the item and does not break the list.
    """
    problems: list[str] = []
    for i, line in enumerate(lines):
        if i in skip or not ORDERED_ITEM.match(line):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or ORDERED_ITEM.match(lines[j]) or lines[j].startswith("  "):
            continue
        # not an item and not indented — the list has ended; if an item follows, it is “1.” again
        k = j
        while k < len(lines) and not ORDERED_ITEM.match(lines[k]):
            if lines[k].startswith("#"):
                break
            k += 1
        if k < len(lines) and ORDERED_ITEM.match(lines[k]):
            problems.append(f"line {i + 1}: ordered list is broken by an unindented paragraph "
                            f"(line {j + 1}) — the numbering restarts on the site; indent the "
                            "paragraph by three spaces or drop the numbering")
    return problems


KEY_FEATURES = re.compile(r"^\*\*Key features:?\*\*\s*$", re.I)


def card_blocks(lines: list[str], skip: set[int]) -> list[str]:
    """Layout of vendor cards, and the brand stop-list on every line.

    A publisher's edit on a vendor article: “key features, but for some reason a single one
    in a bulleted list, as if the cards were unfinished”. A list of one item is exactly a
    truncated card — either there are enough facts for a list, or the fact goes into the card
    text as a sentence. Also the --- line between cards: the site has none, cards are
    separated by an H3 heading.
    """
    problems: list[str] = []
    for i, line in enumerate(lines):
        for match in STOP_BRANDS.finditer(line):
            problems.append(f"line {i + 1}: a stop-listed brand (config/stop-brands.json) is "
                            f"never mentioned on the site — “{match.group(0)}”")
        if i in skip:
            continue
        if line.strip() == "---" and i > 0:
            problems.append(f"line {i + 1}: --- separator between cards — "
                            "a heading separates the cards, the site has no rule lines")
        if KEY_FEATURES.match(line.strip()):
            j = i + 1
            if j < len(lines) and not lines[j].strip():
                j += 1
            bullets = 0
            while j < len(lines) and LIST_START.match(lines[j]):
                bullets += 1
                j += 1
            if bullets < 2:
                counted = "a single bullet" if bullets == 1 else "no bullets"
                problems.append(f"line {i + 1}: “Key features” with {counted} — "
                                "the card reads as unfinished; give two or three facts, "
                                "or put the fact into the card text as a sentence")
    return problems


def contractor_ranking_brand_lines(lines: list[str]) -> dict[int, set[str]]:
    """Allow named cards and their bibliography in a country-guide ranking only."""
    ranking: set[int] = set()
    inside = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            inside = bool(re.match(r"^## Who works with contractors in .+", line))
        if inside:
            ranking.add(i)
    present = {brand for brand in SUBJECT_ONLY_BRANDS if any(
        re.match(r"^###\s+(?:\d+[.)]\s*)?" + re.escape(brand) + r"\s*$", lines[i], re.I)
        for i in ranking)}
    allowed = {i: {brand for brand in present if re.search(
        r"\b" + re.escape(brand) + r"\b", lines[i], re.I)} for i in ranking}
    inside_sources = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            inside_sources = line.strip() == "## Sources"
        if inside_sources:
            matches = {brand for brand in present if re.match(
                r"^\d+\.\s+" + re.escape(brand) + r"\.\s", line, re.I)}
            if matches:
                allowed[i] = matches
    return allowed


def check(text: str, subject: str, site_urls: dict[str, dict] | None,
          lang: str = "en", guide_contractors: bool = False, guide_page: bool = False) -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    skip = code_spans(lines)
    problems: list[str] = []
    ranking_brand_lines = contractor_ranking_brand_lines(lines) if guide_contractors else {}

    for i, line in enumerate(lines):
        if i in skip:
            continue
        for pattern, message in RULES:
            # A Markdown image title is metadata, not a quoted search query in prose.
            if guide_page and pattern is QUOTED_QUERY and re.fullmatch(
                    r'!\[[^\]\n]*\]\(https://[^\s)]+(?:\s+"[^"\n]*")?\)', line.strip()):
                continue
            if guide_page and pattern is PRODUCT_QUARTER and statistical_quarter(line):
                continue
            m = pattern.search(line)
            if m:
                problems.append(f"line {i + 1}: {message} — “{m.group(0)}”")
        for brand in SUBJECT_ONLY_BRANDS:
            if brand.lower() in subject.lower():
                continue
            if brand in ranking_brand_lines.get(i, set()):
                continue
            if re.search(rf"\b{re.escape(brand)}\b", line, re.I):
                problems.append(
                    f"line {i + 1}: {brand} is named only on a page about this brand "
                    "(config/stop-brands.json, subject_only_brands)")

    for i, line in enumerate(lines[:intro_zone(lines)]):
        if i in skip or line.startswith("|"):      # an honest limit in the summary table is a legitimate place
            continue
        # A name-collision disclaimer is not a negation about ourselves: “This page ranks X.
        # It does not cover Y” speaks about the frame of the article, not about what we are not.
        if re.search(r"\bthis (?:page|article|guide)\b", line, re.I) or \
           re.search(r"\bdoes not cover\b", line, re.I):
            continue
        if not BRAND_RE.search(line):
            continue          # a negation about another vendor is subject matter, not a defence
        matches = list(SELF_NEGATION.finditer(line))
        for m in (matches if guide_page else matches[:1]):
            # Guide rules allow precisely this educational distinction; they
            # do not permit other self-negations or financial-service framing.
            if guide_page and re.match(re.escape(BRAND) + r" is not\b", m.group(0), re.I) and re.match(
                    r"\s+(?:an?\s+)?(?:Employer of Record|EOR)(?=\s*(?:[.;!?]|$))",
                    line[m.end():], re.I):
                continue
            problems.append(
                f"line {i + 1}: the intro does not say what we are not — “{m.group(0).strip()}”; "
                "the limitation goes in the vendor card")

    h1 = [ln for ln in lines if HEADING.match(ln) and ln.startswith("# ")]
    if len(h1) != 1:
        problems.append(f"H1 in the text: {len(h1)} (exactly one is required; it is also the page title)")
    deep = [i + 1 for i, ln in enumerate(lines)
            if (m := HEADING.match(ln)) and len(m.group(1)) > 4]
    if deep:
        problems.append(f"headings deeper than H4 (the sanitizer strips them): lines {deep}")

    problems += card_blocks(lines, skip)
    problems += broken_ordered_lists(lines, skip)

    urls = LINK.findall(text)
    # The home page is the preferred target of an internal link, not an error. Persona pages
    # used to be inserted under an earlier rule to “vary the addresses”, and the publisher
    # did not like it: by meaning they are not needed there. So the cap on repeats does not
    # apply to the home page.
    for url in sorted({u for u in urls if urls.count(u) > 2 and not HOME.match(u)}):
        problems.append(f"the same address {urls.count(url)} times: {url} (no more than two; "
                        f"if one more link is needed, use the home page)")
    if site_urls is not None:
        for url in sorted(set(urls)):
            bare = url.split("#")[0]
            row = site_urls.get(bare) or site_urls.get(bare + "/")
            if row is None:
                problems.append(f"address is not in config/site-urls.json: {url}")
                continue
            if bare not in site_urls:
                # Checked on a live article: /pricing returns 301 to /pricing/.
                problems.append(f"address without a trailing slash returns 301: {url}")
            if lang and row.get("lang") and row["lang"] != lang:
                problems.append(
                    f"link to a page in another language ({row['lang']}): {url} — an article in "
                    f"{lang} links only to pages in {lang}")

    return problems


# The manner measured on the site's published articles: they passed the editor and they
# rank, so their numbers are a reference. The numbers are company data and live in
# config/brand-rules.json. This is not a blocker but an instrument reading: an average
# paragraph of fifty words is the first thing the publisher sends back.
#
# IMPORTANT: absolute numbers must not be compared. The published articles run to about
# LIVE_WORDS words and a new one to 4,000–6,000, so a gap in absolute counts is an artefact
# of length, not dryness: an article can look three times “drier” by absolute counts and
# have the same density per thousand words. Agents never chase absolute values.
_MANNER = BRAND_RULES["reference_manner"]
LIVE_PER_1K = {(BRAND if key == "brand" else key): value
               for key, value in _MANNER["per_1000_words"].items()}
LIVE_WORDS = _MANNER["words"]


WALL = 40      # legacy blog diagnostic; country guides use a separate review prompt
GUIDE_REVIEW_WORDS = 120  # review coherence; never a mandatory split or publication gate


LIST_START = re.compile(r"^(?:[-+>]|\*(?!\*)|\d+\.)\s")


def paragraphs(text: str) -> list[tuple[int, int]]:
    """(line number, words) for every paragraph — headings, lists and tables are not counted.

    A paragraph with a bold lead-in (“**Best for.** …”) is a paragraph, not a list item: the
    `*` marker counts as a marker only with a space after it. Without this the counter showed
    zero walls on an article whose first screen was a 175-word paragraph (found by QA).
    """
    out = []
    for i, line in enumerate(text.split("\n"), 1):
        s = line.strip()
        if s and not s.startswith(("#", "|")) and not LIST_START.match(s):
            out.append((i, len(s.split())))
    return out


def walls(text: str, limit: int = WALL) -> list[tuple[int, int]]:
    """Long blocks to review in context; country guides have no fixed paragraph ceiling."""
    return [(n, w) for n, w in paragraphs(text) if w > limit]


def manner(text: str) -> dict[str, int]:
    lines = text.split("\n")
    paras = [ln.strip() for ln in lines
             if ln.strip() and not ln.strip().startswith(("#", "|"))
             and not LIST_START.match(ln.strip())]
    return {
        "paragraph words": round(sum(len(p.split()) for p in paras) / max(len(paras), 1)),
        "bullets": sum(1 for ln in lines if re.match(r"^\s*[-*]\s", ln)),
        "you / your": len(re.findall(r"\byou\b|\byour\b", text, re.I)),
        BRAND: len(re.findall(re.escape(BRAND), text)),
        "words": len(text.split()),
        # Density is counted from prose: table rows are left out of the count, otherwise
        # eleven card tables understate the value by a third.
        "prose words": sum(len(ln.split()) for ln in text.split("\n")
                          if not ln.lstrip().startswith("|")),
        "tables": text.count("\n|---"),
        # “X, not Y” contrasts: QA gate 7 counts them by hand against a ceiling of about five
        # per long article. Count them in advance — the ceiling is about 1 per 1,000 words.
        "contrasts": len(re.findall(r"(?:,|—|–)\s+not\s+\w", text, re.I))
                      + len(re.findall(r"\brather than\b|\binstead of\b", text, re.I)),
    }


def guide_site_urls(site_urls, slug: str, current_urls: list[str]) -> dict[str, dict]:
    """In-memory link inventory; planned sibling routes are not marked live."""
    if not re.fullmatch(r"[a-z][a-z-]*", slug):
        raise ValueError("invalid country slug")
    result = dict(site_urls or {})
    for url in current_urls:
        result[url] = {"lang": "en"}
    base = f"https://{SITE_HOST}/guides/{slug}/"
    for url in (base, base + "employer-of-record/", base + "independent-contractors/"):
        result[url] = {"lang": "en", "draft": True}
    return result


def load_site_urls() -> dict[str, dict] | None:
    """Map of live addresses: address -> record with the language of the page."""
    path = ROOT / "config" / "site-urls.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    urls = data.get("urls", data) if isinstance(data, dict) else data
    out: dict[str, dict] = {}
    for item in urls:
        row = {"url": item, "lang": ""} if isinstance(item, str) else dict(item)
        u = row.get("url", "")
        if u:
            out[u.split("#")[0].rstrip("/") + "/"] = row
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", help="job folder: edited.md and the topic from job.yaml are used")
    ap.add_argument("--input")
    ap.add_argument("--subject", default="", help="the brand the article is about")
    ap.add_argument("--walls", action="store_true",
                    help="list the long paragraphs to review: line and word count")
    args = ap.parse_args()

    subject = args.subject
    if args.job:
        job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
        path = job / "edited.md"
        if not subject:
            m = re.search(r'^topic:\s*"?([^"\n]+)', (job / "job.yaml").read_text(encoding="utf-8"),
                          re.M)
            subject = m.group(1) if m else ""
    elif args.input:
        path = Path(args.input)
    else:
        sys.exit("--job or --input is required")

    text = path.read_text(encoding="utf-8")
    lang = "en"
    if args.job:
        m = re.search(r"^language:\s*(\S+)", (job / "job.yaml").read_text(encoding="utf-8"), re.M)
        if m:
            lang = m.group(1).strip().lower()
    metadata = path.parent / "job.yaml"
    page_metadata = metadata.read_text(encoding="utf-8") if metadata.exists() else ""
    guide_page = bool(re.search(r"^page:\s*(?:country|eor|contractors)\s*$", page_metadata, re.M)
                      and re.search(r"^country_slug:\s*[a-z][a-z-]*\s*$", page_metadata, re.M))
    guide_contractors = bool(re.search(r"^page:\s*contractors\s*$", page_metadata, re.M)
                             and re.search(r"^country_slug:\s*[a-z][a-z-]*\s*$", page_metadata, re.M))
    site_urls = load_site_urls()
    if guide_page:
        slug = re.search(r"^country_slug:\s*([a-z][a-z-]*)\s*$", page_metadata, re.M).group(1)
        current_path = PROJECT / "config" / "site-links.json"
        current = json.loads(current_path.read_text(encoding="utf-8"))["urls"] if current_path.exists() else []
        site_urls = guide_site_urls(site_urls, slug, current)
    problems = check(text, subject, site_urls, lang, guide_contractors=guide_contractors,
                     guide_page=guide_page)

    m = manner(text)
    print(f"{path.name}: {m['words']} words, {m['tables']} tables")
    print(f"  paragraph words {m['paragraph words']:4}   published articles {_MANNER['paragraph_words']}")
    per1k = max(m["prose words"], 1) / 1000
    for key, live in LIVE_PER_1K.items():
        print(f"  {key:12} {m[key]:4}   {m[key] / per1k:5.1f} per 1,000 words, published articles {live}")

    # The count here is broader than QA's (QA takes only strict appositions), so it is compared
    # not with the ceiling of gate 7 but with the published articles.
    print(f"  contrasts    {m['contrasts']:4}   published articles {_MANNER['contrasts_per_article']}")

    review_limit = GUIDE_REVIEW_WORDS if guide_page else WALL
    wall_list = walls(text, review_limit)
    print(f"  paragraphs over {review_limit} words: {len(wall_list)} of {len(paragraphs(text))}")
    if guide_page:
        print("  for guides: check coherence; there is no fixed word limit and no requirement to split")
    if args.walls and wall_list:
        for n, w in wall_list:
            print(f"    line {n}: {w} words")

    if not problems:
        print(f"prohibitions: clean, {len(RULES)} rules")
        return
    print(f"prohibitions: {len(problems)} violation(s)")
    for p in problems:
        print(f"  {p}")
    sys.exit(1)


if __name__ == "__main__":
    main()
