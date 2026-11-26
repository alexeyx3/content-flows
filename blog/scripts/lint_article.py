"""Mechanical proofreading of a finished article against the hard bans of the track.

Every rule here encodes a recurring publisher edit. Caught by eye, such slips get through:
a mixed-case abbreviation can repeat across a whole text, or an internal wording can reach an
article that has already been sent out. The QA gate checks them too, but an agent reads and
reasons, while grep does not get tired and costs nothing.

Only what is visible in a line is checked. Matters of meaning (card parity, the order of
our own card, entailment of facts) stay with the QA agent and the orchestrator.

Writing-craft rules live in this file. Everything that is the company's own editorial
policy — the brand, banned topics, labels and claims that must not stand next to the
brand — is read from config/brand-rules.json; the brand stop-list is read from
config/stop-brands.json.

Usage:
  python3 scripts/lint_article.py --job jobs/<job-dir>            # edited.md
  python3 scripts/lint_article.py --input <file>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NEVER = re.compile(r"(?!)")      # matches nothing: an empty list blocks nothing


def compile_stop_brands(brands: list[str]) -> re.Pattern[str]:
    """Stop-list entries -> one pattern. Each entry is a whole word, case-insensitive;
    a trailing * makes it a prefix. An empty list never matches."""
    parts = [r"(?<!\w)" + re.escape(name.rstrip("*")) + ("" if name.endswith("*") else r"(?!\w)")
             for name in (item.strip() for item in brands) if name.rstrip("*")]
    return re.compile("|".join(parts), re.I) if parts else NEVER


def load_stop_brands(path: Path | None = None) -> re.Pattern[str]:
    data = json.loads((path or ROOT / "config" / "stop-brands.json").read_text(encoding="utf-8"))
    return compile_stop_brands(data.get("brands", []))


def any_of(patterns: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I) if patterns else NEVER


BRAND_RULES = json.loads((ROOT / "config" / "brand-rules.json").read_text(encoding="utf-8"))
BRAND: str = BRAND_RULES["brand"]
PRODUCT: str = BRAND_RULES["product"]
SITE_HOST: str = BRAND_RULES["site_host"]
_BRAND = r"(?<!\w)" + re.escape(BRAND) + r"(?!\w)"       # the brand as a regex fragment
_HOST = re.escape(SITE_HOST)
BRAND_RE = re.compile(_BRAND, re.I)
PRODUCT_RE = re.compile(r"(?<!\w)" + re.escape(PRODUCT) + r"(?!\w)", re.I)

# Applies in every field of the site, with no exception for the subject of the article itself.
STOP_BRANDS = load_stop_brands()

# The arrangement may be described — “works on an <industry term> model”; the label and the
# product name may not. The word after the term tells a scheme from a label.
_TERM_RULE = BRAND_RULES["industry_term_not_a_label"]
_TERM = r"\b" + re.escape(_TERM_RULE["term"]) + r"\b"
TERM_SCHEME = r"(?!\s+(?:" + "|".join(re.escape(w) for w in _TERM_RULE["scheme_words"]) + r")\b)"
TERM_SELF_LABEL = re.compile(
    _TERM + TERM_SCHEME + r"(?=[^.|]{0,80}" + _BRAND + r")|"
    + _BRAND + r"[^.|]{0,60}" + _TERM + TERM_SCHEME, re.I)
NEGATION_PARAPHRASE = any_of(BRAND_RULES["negation_paraphrases"]["patterns"])

# Publication objects distinguish author/source narration from operational
# reconciliation (for example, output checked against source records).
VERIFICATION_SOURCE = (
    r"(?:(?:the|a|an|its|their|live|official|public|published|vendor|provider|company|"
    r"product|pricing|support|own|\w+['’]s|(?-i:[A-Z][\w.-]*))\s+){0,6}"
    r"(?:sites?|pages?|websites?|pricing|documentation|docs|materials|help centers?"
    r"|rate cards?)\b|https?://[^\s]+"
)

FRESHNESS_DATE = re.compile(
    r"\bas of\s+(?:\d{1,2}\s+)?"
    r"(?:january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+20\d\d\b", re.I)


def configured_rules(block: str) -> list[tuple[re.Pattern[str], str]]:
    return [(re.compile(rule["pattern"], 0 if rule.get("case_sensitive") else re.I), rule["message"])
            for rule in BRAND_RULES[block]["rules"]]


# (pattern, message). Case is ignored unless a configured rule is marked case_sensitive.
RULES: list[tuple[re.Pattern[str], str]] = [
    # Absolute bans of the track and house wording: company policy, config/brand-rules.json.
    *configured_rules("banned_topics"),
    *configured_rules("site_wide_wording"),
    (re.compile(r"\b(?:in|by|during|from)\s+Q[1-4]\s*20\d\d\b|\bQ[1-4]\s*20\d\d\b", re.I),
     "product timelines and plans do not go into the text"),
    (re.compile(r"\b(?:coming|planned|expected|launching|slated)\s+(?:in|for|by)\s+20\d\d\b", re.I),
     "product timelines and plans do not go into the text"),
    (FRESHNESS_DATE,
     "hard-coded freshness date: the page itself shows the update date, write “at the time of writing”"),
    # “search for” in its ordinary sense (“open the alternatives search for four reasons”)
    # must not be caught — only talk about search behaviour is. Employee,
    # regulator and database queries are ordinary subject matter. People search
    # is also the name of a consumer lookup category in screening articles.
    (re.compile(r"\b(?:buyers|users|(?<!versus )people|companies|teams|readers)\s+(?:actually\s+)?"
                r"(?:search|google|type)\b|\bsearchers\b|\bsearch intent\b"
                r"|\bsearch volume\b|\bwhat (?:people|buyers) (?:search|google|type)\b"
                r"|\b(?:buyers|readers|teams|people) looking for\b"
                r"|\ba search for\b|(?<!people[- ])\bsearch results?\b"
                r"|\bsurfaces? under\b.{0,20}\bqueries\b"
                r"|\b(?:search|SEO|keyword|Google|Bing)[ -]+quer(?:y|ies)\b"
                r"|\bquer(?:y|ies)\s+(?:in|on|from)\s+(?:Google|Bing|search engines?)\b", re.I),
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
    # Our own search query in quotation marks as the topic of a sentence.
    (re.compile(r"[“\"]([^”\"]{3,60}\b(?:alternatives?|vs\.?|pricing|review)\b[^”\"]{0,40})[”\"]",
                re.I),
     "your own search query in quotes as the topic of a sentence is a heavy SEO cliché"),
    # Verification narration: the reader needs the fact, not a report on how we obtained it.
    # “confirmed on close” is about handing over work, not about our check: the preposition
    # on without a vendor page does not count (it was a false positive on a vendor article).
    # Likewise, reconciling payroll output with records is the reader's workflow;
    # these prepositions alone do not establish author verification narration.
    (re.compile(r"\b(?:confirmed|verified|checked)\s+(?:through|via|against)\s+(?:"
                + VERIFICATION_SOURCE + r")"
                r"|\b(?:we|our (?:review|research|analysis)|this (?:article|comparison))\s+"
                r"(?:have\s+)?(?:confirmed|verified|checked)\s+(?:through|via|against)\b"
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
                r"|\bround-?ups?\b|\bSERPs?\b|\blistic(?:le|les)\b", re.I),
     "talk about the SERP and other publishers' articles in prose: the subject is the market "
     "and the vendors, not the SERP"),
    # A table-cell border breaks the window: in a comparison row “… (<industry term>) |
    # One agreement with <brand> …” the neighbouring cells speak about DIFFERENT vendors.
    (TERM_SELF_LABEL, _TERM_RULE["message"]),
]

LINK = re.compile(r"\]\((https?://(?:www\.)?" + _HOST + r"[^)\s]*)\)")
HOME = re.compile(r"^https?://(?:www\.)?" + _HOST + r"/?(?:\?|#|$)")
HEADING = re.compile(r"^(#{1,6})\s")
TABLE_SEPARATOR = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)


# “Do not open with what we are not” (a publisher's edit). In the vendor card and in the
# honest-limit column a negation is in its place, while in the intro it reads as a defence.
# The zone checked runs from the start to the second H2, that is the title and the key
# takeaways.
SELF_NEGATION = re.compile(
    r"(?:" + _BRAND + r"|(?:^|[.!?]\s+)(?:"
    + "|".join(re.escape(s) for s in BRAND_RULES["self_negation_intro"]["subjects"])
    + r")) (?:is |are |does )?"
    r"(?:not|isn't|aren't|no)\b|\bwrong (?:shortlist|pick|choice|tool) for\b", re.I)

# Claims from config/brand-rules.json that are forbidden only next to the brand: about the
# market and competitors the same words remain ordinary subject matter. An explicit sentence
# with the brand and the brand's own heading block are checked, so that a competitor's
# neighbouring cell in a summary table is not caught.
SELF_FORBIDDEN: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rule["pattern"], re.I), rule["message"])
    for rule in BRAND_RULES["self_forbidden"]["rules"]
]
SELF_NEGATED = re.compile(r"\b(?:not|no|never|without)\b|n['’]t\b", re.I)
_SELF_NOUNS = "|".join(re.escape(noun) for noun in BRAND_RULES["self_reference_nouns"])
SELF_REFERENCE = re.compile(
    r"(?:" + _BRAND + r"|\b(?:" + _SELF_NOUNS + r"|it|we)\b)", re.I
)
SELF_PRONOUN = re.compile(r"^\s*(?:It|We|" + _SELF_NOUNS + r")\b", re.I)
COORDINATED_PREDICATE = r"(?:and|but)\s+(?:offers?|provides?|supports?|sends?|handles?|processes?|charges?|pays?)\b"
CLAUSE_BOUNDARY = re.compile(
    rf"(?<=[.!?;])\s+|,\s+(?=(?:while|whereas|but|and|separately)\b)|\s+(?={COORDINATED_PREDICATE})",
    re.I)
SELF_CONTINUATION = re.compile(rf"^\s*{COORDINATED_PREDICATE}", re.I)
MARKDOWN_LINK_TARGET = re.compile(r"\]\([^)]+\)")
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\([^)]+\)")
IMAGE_MARKDOWN = re.compile(r'^\s*!\[([^\]]*)\]\(\S+\s+"([^"\n]*)"\)\s*$')
OWNPRODUCT_HEADING = re.compile(r"^#{2,4}\s+" + re.escape(BRAND) + r"\s*$", re.I)
OWNPRODUCT_ROW = re.compile(
    r"^\s*\|\s*[*_\[]*" + re.escape(BRAND) + r"[*_\]]*\s*\|(?P<claims>.*)$", re.I)
CLASSIFICATION_GUARANTEE = any_of(BRAND_RULES["classification_guarantee"]["patterns"])


def self_forbidden_claim(prose: str, in_ownproduct_section: bool, *, own_row: bool = False):
    """Match forbidden self-claims only in a clause attributable to the brand.

    Returns (match, reason) or None. A negated clause (“is not a <label>”) is a
    permitted boundary statement, not a claim.
    """
    previous_self = False
    for clause in CLAUSE_BOUNDARY.split(prose):
        direct = bool(BRAND_RE.search(clause))
        continuation = previous_self and bool(SELF_PRONOUN.match(clause) or SELF_CONTINUATION.match(clause))
        own_section = in_ownproduct_section and bool(SELF_REFERENCE.search(clause))
        if direct or continuation or own_section or own_row:
            for pattern, reason in SELF_FORBIDDEN:
                match = pattern.search(clause)
                if match and not SELF_NEGATED.search(clause[:match.start()]):
                    return match, reason
        previous_self = direct or continuation or own_section
    return None


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


def wide_markdown_tables(lines: list[str]) -> list[str]:
    """Report rendered table width from its header, not from literal pipe counts.

    Python-Markdown is already a pipeline dependency. Its table tokenizer handles
    escaped pipes, escaped backslashes, and matching variable-length code spans.
    Keep fence handling local to this rule so existing prose checks do not change.
    """
    from markdown import Markdown

    processor = Markdown(extensions=["tables"]).parser.blockprocessors["table"]
    problems: list[str] = []
    fence_char, fence_size = "", 0
    visible: list[str | None] = []
    for line in lines:
        # A blockquote can contain a real table or a fenced example of one.
        content = re.sub(r"^(?: {0,3}>[ \t]?)+", "", line)
        if fence_char:
            visible.append(None)
            if re.fullmatch(r" {0,3}" + re.escape(fence_char) + "{" + str(fence_size) + r",}[ \t]*", content):
                fence_char, fence_size = "", 0
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", content)
        if opening and not (opening[1][0] == "`" and "`" in opening[2]):
            fence_char, fence_size = opening[1][0], len(opening[1])
            visible.append(None)
        elif content.startswith(("    ", "\t")):
            visible.append(None)  # Indented code is not a rendered table.
        else:
            visible.append(content)

    for index in range(len(lines) - 1):
        header, separator = visible[index:index + 2]
        if header is None or separator is None:
            continue
        # A real table needs a matching delimiter row. The existing HTML
        # converter accepts two or more dashes per delimiter cell.
        if not processor.test(None, header + "\n" + separator) or not all(
                re.fullmatch(r":?-{2,}:?", cell.strip()) for cell in processor.separator):
            continue
        width = len(processor.separator)
        if width > 5:
            problems.append(f"line {index + 1}: table has {width} columns (no more than five); "
                            f"header: {lines[index].strip()}")
    return problems


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


def quotation_style(lines: list[str], skip: set[int], lang: str) -> list[str]:
    """Enforce the publisher's language-specific quotation typography."""
    problems: list[str] = []
    language = lang.lower()
    for i, line in enumerate(lines):
        if i in skip:
            continue
        # Image title delimiters belong to Markdown syntax, not prose typography.
        # Retain alt/title text so their visible quotation marks still get checked.
        image = re.fullmatch(r'\s*!\[([^\]]*)\]\((\S+)\s+"([^"\n]*)"\)\s*', line)
        if image:
            line = image.group(1) + ' ' + image.group(3)
        if language.startswith("en"):
            if m := re.search(r"[«»]", line):
                problems.append(
                    f"line {i + 1}: outer quotation marks in EN text are “…” — “{m.group(0)}”"
                )
            if m := re.search(r'"', line):
                problems.append(
                    f"line {i + 1}: replace straight double quotes with “…” — “{m.group(0)}”"
                )
        elif language.startswith("ru"):
            if m := re.search(r'[”"]', line):
                problems.append(
                    f"line {i + 1}: outer quotation marks in RU text are «…» — “{m.group(0)}”"
                )
            elif "“" in line and "„" not in line:
                problems.append(
                    f"line {i + 1}: outer quotation marks in RU text are «…» — ““”"
                )
    return problems


KEY_FEATURES = re.compile(r"^\*\*Key features:?\*\*\s*$", re.I)


def card_blocks(lines: list[str], skip: set[int]) -> list[str]:
    """Layout of vendor cards.

    A publisher's edit on a vendor article: “key features, but for some reason a single one
    in a bulleted list, as if the cards were unfinished”. A list of one item is exactly a
    truncated card — either there are enough facts for a list, or the fact goes into the card
    text as a sentence. Also the --- line between cards: the blog has none, cards are
    separated by an H3 heading.
    """
    problems: list[str] = []
    for i, line in enumerate(lines):
        if i in skip:
            continue
        if line.strip() == "---" and i > 0:
            problems.append(f"line {i + 1}: --- separator between cards — "
                            "a heading separates the cards, the blog has no rule lines")
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


def check(text: str, subject: str, site_urls: dict[str, dict] | None,
          lang: str = "en") -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    skip = code_spans(lines)
    problems: list[str] = []

    for i, line in enumerate(lines):
        if m := STOP_BRANDS.search(line):
            problems.append(f"line {i + 1}: a stop-listed brand (config/stop-brands.json) is "
                            f"never mentioned on the site — “{m.group(0)}”")
        if i in skip:
            continue
        image = IMAGE_MARKDOWN.fullmatch(line)
        # Check visible alt/title words, but do not treat Markdown's title
        # delimiters as an author quoting a search query.
        rule_line = image.group(1) + " " + image.group(2) if image else line
        for pattern, message in RULES:
            # A glossary link target names the site but makes no self-label claim.
            # Keep its visible label so linked actual self-labels still get caught.
            target = MARKDOWN_LINK_TARGET.sub("]", rule_line) if pattern is TERM_SELF_LABEL else rule_line
            m = pattern.search(target)
            if m:
                # A dated observation is part of the source's measurement, not
                # a claim that this article's prices are current on that date.
                if pattern is FRESHNESS_DATE and re.search(
                        r"\b(?:recorded|measured|observed|counted)\b[^.!?]*"
                        r"\b(?:cost|count|number|share|rate|total)\b[^.!?]*\d[^.!?]*$",
                        target[:m.start()], re.I):
                    continue
                problems.append(f"line {i + 1}: {message} — “{m.group(0)}”")
    ownproduct_heading_level = None
    for i, line in enumerate(lines):
        if i in skip:
            continue
        # Ignore URLs when deciding whether a sentence names the brand: an internal link to a
        # guide is not a claim that the product itself does what the guide is about.
        # A visual caption appends source links on one line. Their titles are not
        # a claim about the brand, even if one source title carries a forbidden word and
        # another is the brand's own product page.
        # Bound visual captions append plain-text source titles separated by middle dots.
        # Those titles describe other publishers, not the caption's claim about the brand.
        prose_line = (MARKDOWN_LINK.sub("", line.split(" · ", 1)[0])
                      if line.startswith("Caption:") else MARKDOWN_LINK_TARGET.sub("]", line))
        if heading := HEADING.match(prose_line):
            level = len(heading.group(1))
            if OWNPRODUCT_HEADING.fullmatch(prose_line):
                ownproduct_heading_level = level
                continue
            if ownproduct_heading_level is not None and level <= ownproduct_heading_level:
                ownproduct_heading_level = None
        in_ownproduct_section = ownproduct_heading_level is not None
        table_row = prose_line.lstrip().startswith("|")
        own_row = OWNPRODUCT_ROW.match(prose_line)
        direct_self_description = bool(
            own_row or (not table_row and BRAND_RE.search(prose_line))
        )
        # A vendor row assigns claims to its own vendor. Scan each cell of the brand's row
        # independently so an adjacent cell's wording does not negate its claim.
        if table_row:
            cells = own_row["claims"].split("|") if own_row else []
            hit = next((result for cell in cells
                        if (result := self_forbidden_claim(cell, False, own_row=True))), None)
        else:
            hit = self_forbidden_claim(prose_line, in_ownproduct_section)
        if hit:
            problems.append(
                f"line {i + 1}: not allowed next to {BRAND}: {hit[1]} — “{hit[0].group(0)}”")
        if (in_ownproduct_section or direct_self_description or
                PRODUCT_RE.search(prose_line)) and \
                (m := NEGATION_PARAPHRASE.search(line)):
            problems.append(
                f"line {i + 1}: {BRAND_RULES['negation_paraphrases']['message']} — “{m.group(0)}”")
        if (in_ownproduct_section or direct_self_description) and \
                (m := CLASSIFICATION_GUARANTEE.search(line)):
            problems.append(
                f"line {i + 1}: {BRAND_RULES['classification_guarantee']['message']} — “{m.group(0)}”")

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
        m = SELF_NEGATION.search(line)
        if m:
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
    problems += quotation_style(lines, skip, lang)
    problems += wide_markdown_tables(lines)

    # The sitemap list is an internal-navigation allowlist. The final Sources
    # section cites original evidence, including the site's own legal documents that the
    # navigation sitemap intentionally excludes; source validity is checked by
    # check_research_links.py rather than by this navigation rule.
    sources_heading = re.search(r"^##\s+(?:Sources|Источники)\s*$", text, re.I | re.M)
    navigation_text = text[:sources_heading.start()] if sources_heading else text
    urls = LINK.findall(navigation_text)
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


# The manner measured on the site's published articles (blog-owned.md): they passed the
# editor and they rank. The numbers are company data and live in config/brand-rules.json.
# There is no numeric norm for paragraph length: paragraphs follow the meaning and
# naturally differ in length.
#
# IMPORTANT: absolute numbers must not be compared. The published articles run to about
# LIVE_WORDS words and a new one to 4,000–6,000, so a gap in absolute counts is an artefact
# of length, not dryness: an article can look three times “drier” by absolute counts and
# have the same density per thousand words. Agents never chase absolute values.
_MANNER = BRAND_RULES["reference_manner"]
LIVE_PER_1K = {(BRAND if key == "brand" else key): value
               for key, value in _MANNER["per_1000_words"].items()}
LIVE_WORDS = _MANNER["words"]


WALL = 40      # beyond this a paragraph reads as a wall of text and goes to revision


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


def walls(text: str) -> list[tuple[int, int]]:
    """Legacy helper retained for old diagnostics and split_walls.py.

    The active article workflow has no numeric paragraph-length target and does not call this
    helper.
    """
    return [(n, w) for n, w in paragraphs(text) if w > WALL]


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
        # Density is counted from prose, as in scripts/wordcount.py: table rows are left out
        # of the count, otherwise eleven card tables understate the value by a third.
        "prose words": sum(len(ln.split()) for ln in text.split("\n")
                           if not ln.lstrip().startswith("|")),
        # CommonMark permits spaces inside separator rows (`| --- | --- |`).
        # Count separator rows rather than one compact spelling of them.
        "tables": sum(1 for line in lines if TABLE_SEPARATOR.match(line)),
        # “X, not Y” contrasts: QA gate 7 counts them by hand against a ceiling of about five
        # per long article. Count them in advance — the ceiling is about 1 per 1,000 words.
        "contrasts": len(re.findall(r"(?:,|—|–)\s+not\s+\w", text, re.I))
                     + len(re.findall(r"\brather than\b|\binstead of\b", text, re.I)),
    }


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
    problems = check(text, subject, load_site_urls(), lang)

    m = manner(text)
    print(f"{path.name}: {m['words']} words, {m['tables']} tables")
    per1k = max(m["prose words"], 1) / 1000
    for key, live in LIVE_PER_1K.items():
        print(f"  {key:12} {m[key]:4}   {m[key] / per1k:5.1f} per 1,000 words, published articles {live}")

    # The count here is broader than QA's (QA takes only strict appositions), so it is compared
    # not with the ceiling of gate 7 but with the published articles.
    print(f"  contrasts    {m['contrasts']:4}   published articles {_MANNER['contrasts_per_article']}")

    if not problems:
        print(f"prohibitions: clean, {len(RULES)} rules")
        return
    print(f"prohibitions: {len(problems)} violation(s)")
    for p in problems:
        print(f"  {p}")
    sys.exit(1)


if __name__ == "__main__":
    main()
