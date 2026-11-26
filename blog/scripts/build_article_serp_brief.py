from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_SLEEP_SECONDS = 1.0
DEFAULT_CONCURRENCY = 4
MAX_TEXT_CHARS = 2_000_000


class PageHTMLParser(HTMLParser):
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
    SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "nav", "footer", "aside"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.headings: list[dict[str, str]] = []
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self.table_count = 0
        self.current_heading: str | None = None
        self.current_heading_parts: list[str] = []
        self.current_link: str | None = None
        self.in_title = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs = {key.lower(): value or "" for key, value in attrs_list}

        if self.skip_depth:
            if tag in self.SKIP_TAGS:
                self.skip_depth += 1
            return

        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            key = (attrs.get("name") or attrs.get("property") or attrs.get("http-equiv") or "").lower()
            content = attrs.get("content", "").strip()
            if key and content:
                self.meta[key] = content
        elif tag in self.HEADING_TAGS:
            if self.current_heading and self.current_heading_parts:
                self._finish_heading()
            self.current_heading = tag
            self.current_heading_parts = []
        elif tag == "a":
            self.current_link = attrs.get("href") or ""
        elif tag == "table":
            self.table_count += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            if tag in self.SKIP_TAGS:
                self.skip_depth -= 1
            return

        if tag == "title":
            self.in_title = False
        elif tag in self.HEADING_TAGS and tag == self.current_heading:
            self._finish_heading()
        elif tag == "a":
            self.current_link = None

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return

        text = clean_space(data)
        if not text:
            return

        if self.in_title:
            self.title_parts.append(text)

        if self.current_heading:
            self.current_heading_parts.append(text)

        if self.current_link and text:
            self.links.append(text)

        self.text_parts.append(text)

    def close(self) -> None:
        super().close()
        if self.current_heading:
            self._finish_heading()

    def _finish_heading(self) -> None:
        text = clean_space(" ".join(self.current_heading_parts))
        if self.current_heading and text:
            self.headings.append({"level": self.current_heading.upper(), "text": text})
        self.current_heading = None
        self.current_heading_parts = []


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def load_csv(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "windows-1251", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                rows = list(csv.DictReader(handle))
            if rows:
                return rows
        except UnicodeDecodeError:
            continue
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def load_features(path: Path | None) -> list[dict[str, object]]:
    if not path:
        return []
    if not path.exists():
        raise FileNotFoundError(f"Features file not found: {path}")
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    rows = load_csv(path)
    loaded: list[dict[str, object]] = []
    for row in rows:
        extra_json = row.pop("extra_json", "") if "extra_json" in row else ""
        try:
            row["extra"] = json.loads(extra_json) if extra_json else {}
        except json.JSONDecodeError:
            row["extra"] = {}
        loaded.append(row)
    return loaded


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_url(url: str) -> str:
    url = clean_space(url)
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") or "/"
    tracking_names = {
        "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source",
        "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term",
    }
    query = urllib.parse.urlencode(
        [
            (key, value)
            for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in tracking_names
        ],
        doseq=True,
    )
    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def extract_domain(url: str) -> str:
    domain = urllib.parse.urlsplit(url).netloc.lower()
    return domain[4:] if domain.startswith("www.") else domain


def is_probably_html(content_type: str) -> bool:
    lowered = content_type.lower()
    return not lowered or "text/html" in lowered or "application/xhtml" in lowered


def decode_body(body: bytes, headers: object) -> str:
    charset = ""
    try:
        charset = headers.get_content_charset() or ""
    except AttributeError:
        charset = ""

    encodings = [charset, "utf-8", "windows-1251", "cp1251", "latin-1"]
    for encoding in [item for item in encodings if item]:
        try:
            return body.decode(encoding, errors="replace")
        except LookupError:
            continue
    return body.decode("utf-8", errors="replace")


def fetch_page(url: str, timeout: int) -> tuple[str, str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        content_type = response.headers.get("content-type", "")
        body = response.read(MAX_TEXT_CHARS)
        if not is_probably_html(content_type):
            raise ValueError(f"non-html content-type: {content_type}")
        return final_url, content_type, decode_body(body, response.headers)


def build_heading_tree(
    headings: list[dict[str, str]], max_level: int = 6
) -> list[dict[str, object]]:
    """Turn a flat HTML heading sequence into an ordered hierarchy.

    Pages often skip levels (for example H2 -> H4). In that case the H4 remains
    attached to the nearest preceding shallower heading instead of being dropped.
    """
    roots: list[dict[str, object]] = []
    stack: list[tuple[int, dict[str, object]]] = []

    for heading in headings:
        match = re.fullmatch(r"H([1-6])", heading.get("level", ""))
        text = clean_space(heading.get("text", ""))
        if not match or not text:
            continue
        level = int(match.group(1))
        if level > max_level:
            continue

        node: dict[str, object] = {
            "level": f"H{level}",
            "text": text,
            "children": [],
        }
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            parent_children = stack[-1][1]["children"]
            assert isinstance(parent_children, list)
            parent_children.append(node)
        else:
            roots.append(node)
        stack.append((level, node))

    return roots


def parse_page(html_text: str) -> dict[str, object]:
    parser = PageHTMLParser()
    parser.feed(html_text)
    parser.close()

    title = clean_space(" ".join(parser.title_parts))
    description = clean_space(
        parser.meta.get("description")
        or parser.meta.get("og:description")
        or parser.meta.get("twitter:description")
        or ""
    )
    canonical = clean_space(parser.meta.get("og:url") or "")
    body_text = clean_space(" ".join(parser.text_parts))
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9'’-]*", body_text)

    questions = []
    for heading in parser.headings:
        text = heading["text"]
        if text.endswith("?") or re.match(r"^(how|what|why|when|where|which|who|can|is|are|does|do)\b", text, re.I):
            questions.append(text)
        if re.match(r"^(как|что|почему|когда|где|какой|какая|можно ли|зачем)\b", text, re.I):
            questions.append(text)

    return {
        "title": title,
        "description": description,
        "canonical": canonical,
        "headings": parser.headings,
        "heading_tree": build_heading_tree(parser.headings),
        "word_count": len(words),
        "question_headings": list(dict.fromkeys(questions))[:20],
        "table_count": parser.table_count,
        "text_sample": body_text[:1200],
    }


def classify_page(url: str, title: str, headings: list[dict[str, str]]) -> str:
    haystack = " ".join([url, title, " ".join(item["text"] for item in headings[:10])]).lower()
    if any(item in haystack for item in ["pricing", "price", "plans", "стоимость", "цены", "тариф"]):
        return "pricing"
    if any(item in haystack for item in ["compare", "vs ", "versus", "alternative", "alternatives", "сравнение", "альтернатив"]):
        return "comparison"
    if any(item in haystack for item in ["best ", "top ", "лучшие", "топ", "rating", "ratings"]):
        return "listicle"
    if any(item in haystack for item in ["guide", "how to", "what is", "learn", "blog", "гайд", "как ", "что такое", "статья"]):
        return "blog_article"
    if any(item in haystack for item in ["faq", "questions", "вопросы"]):
        return "faq"
    if any(item in haystack for item in ["software", "platform", "service", "solution", "сервис", "платформа"]):
        return "landing_or_product"
    return "other"


def pick_serp_rows(rows: list[dict[str, str]], max_per_query_geo: int) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if (row.get("block") or "organic") != "organic":
            continue
        if not row.get("url"):
            continue
        grouped[(row.get("query", ""), row.get("geo_key", ""))].append(row)

    selected_by_url: dict[str, dict[str, str]] = {}
    for key in sorted(grouped):
        sortable = []
        for row in grouped[key]:
            try:
                position = int(row.get("position", "9999"))
            except ValueError:
                position = 9999
            sortable.append((position, row))
        for _, row in sorted(sortable, key=lambda item: item[0])[:max_per_query_geo]:
            normalized = normalize_url(row.get("url", ""))
            geo_key = row.get("geo_key", "")
            if normalized in selected_by_url:
                existing = selected_by_url[normalized]
                geos = [item for item in existing.get("geo_keys", "").split(",") if item]
                if geo_key and geo_key not in geos:
                    geos.append(geo_key)
                existing["geo_keys"] = ",".join(geos)
                positions = [item for item in existing.get("geo_positions", "").split(",") if item]
                position_label = f"{geo_key}:{row.get('position', '')}"
                if geo_key and position_label not in positions:
                    positions.append(position_label)
                existing["geo_positions"] = ",".join(positions)
                try:
                    existing_position = int(existing.get("position", "9999"))
                except ValueError:
                    existing_position = 9999
                try:
                    current_position = int(row.get("position", "9999"))
                except ValueError:
                    current_position = 9999
                if current_position < existing_position:
                    existing["position"] = row.get("position", "")
                continue
            selected_row = dict(row)
            selected_row["geo_keys"] = geo_key
            selected_row["geo_positions"] = f"{geo_key}:{row.get('position', '')}" if geo_key else ""
            selected_by_url[normalized] = selected_row
            selected.append(selected_row)
    return selected


def missing_organic_geos(
    rows: list[dict[str, str]], required_geos: list[str] | None
) -> list[str]:
    """Return required geo keys that have no usable organic result rows."""
    required = {item.lower() for item in required_geos or []}
    present = {
        str(row.get("geo_key", "")).lower()
        for row in rows
        if (row.get("block") or "organic") == "organic" and row.get("url")
    }
    return sorted(required - present)


def build_card(row: dict[str, str], timeout: int) -> dict[str, object]:
    source_url = row.get("url", "")
    card: dict[str, object] = {
        "query": row.get("query", ""),
        "geo_key": row.get("geo_key", ""),
        "geo_keys": row.get("geo_keys", row.get("geo_key", "")),
        "geo_positions": row.get("geo_positions", ""),
        "position": row.get("position", ""),
        "serp_title": clean_space(row.get("title", "")),
        "serp_snippet": clean_space(row.get("snippet", "")),
        "url": source_url,
        "domain": row.get("domain") or extract_domain(source_url),
        "status": "ok",
        "error": "",
    }

    try:
        final_url, content_type, html_text = fetch_page(source_url, timeout=timeout)
        parsed = parse_page(html_text)
        headings = parsed["headings"]
        title = parsed["title"] or card["serp_title"]
        card.update(
            {
                "final_url": final_url,
                "content_type": content_type,
                "title": title,
                "description": parsed["description"],
                "canonical": parsed["canonical"],
                "h1": " | ".join(item["text"] for item in headings if item["level"] == "H1"),
                "headings": headings,
                "heading_tree": parsed["heading_tree"],
                "word_count": parsed["word_count"],
                "question_headings": parsed["question_headings"],
                "table_count": parsed["table_count"],
                "page_type": classify_page(final_url, str(title), headings),
                "text_sample": parsed["text_sample"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        card.update(
            {
                "status": "error",
                "error": str(exc),
                "final_url": "",
                "content_type": "",
                "title": card["serp_title"],
                "description": "",
                "canonical": "",
                "h1": "",
                "headings": [],
                "heading_tree": [],
                "word_count": 0,
                "question_headings": [],
                "table_count": 0,
                "page_type": "unknown",
                "text_sample": "",
            }
        )
    return card


def build_cards(
    selected_rows: list[dict[str, str]],
    timeout: int,
    sleep_seconds: float,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> list[dict[str, object]]:
    """Fetch selected, deduplicated URLs with bounded workers and stable output order.

    Each worker retains the post-fetch pause. ``concurrency=1`` provides the
    original serial behavior, including calls to the public ``build_card`` and
    ``fetch_page`` functions used by callers and test fakes.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")

    def fetch_row(row: dict[str, str]) -> dict[str, object]:
        card = build_card(row, timeout=timeout)
        time.sleep(sleep_seconds)
        return card

    cards: list[dict[str, object]] = []
    total = len(selected_rows)
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # map returns results in input order even when later requests finish first.
        for index, card in enumerate(executor.map(fetch_row, selected_rows), start=1):
            print(f"[{index}/{total}] {card.get('position')} {card.get('url')}", flush=True)
            cards.append(card)
    return cards


def flatten_heading_text(
    headings: list[dict[str, str]],
    max_items: int = 120,
    levels: set[str] | None = None,
) -> str:
    filtered = [item for item in headings if not levels or item.get("level") in levels]
    parts = [f"{item['level']}: {item['text']}" for item in filtered[:max_items]]
    return "\n".join(parts)


def render_heading_outline(headings: list[dict[str, str]], max_level: int = 4) -> list[str]:
    lines: list[str] = []
    for heading in headings:
        match = re.fullmatch(r"H([1-6])", heading.get("level", ""))
        if not match or int(match.group(1)) > max_level:
            continue
        level = int(match.group(1))
        lines.append(f"{'  ' * (level - 1)}- H{level}: {heading.get('text', '')}")
    return lines


def write_outputs(
    output_prefix: Path,
    cards: list[dict[str, object]],
    features: list[dict[str, object]] | None = None,
) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    features = features or []

    cards_path = output_prefix.with_suffix(".competitor_cards.json")
    cards_path.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    if features:
        output_prefix.with_suffix(".serp_features.json").write_text(
            json.dumps(features, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    structure_rows = []
    for card in cards:
        structure_rows.append(
            {
                "query": card["query"],
                "geo_key": card["geo_key"],
                "geo_keys": card.get("geo_keys", card["geo_key"]),
                "geo_positions": card.get("geo_positions", ""),
                "position": card["position"],
                "domain": card["domain"],
                "url": card["url"],
                "final_url": card.get("final_url", ""),
                "status": card["status"],
                "page_type": card.get("page_type", ""),
                "word_count": card.get("word_count", 0),
                "serp_title": card.get("serp_title", ""),
                "serp_description": card.get("serp_snippet", ""),
                "title": card.get("title", ""),
                "description": card.get("description", ""),
                "h1": card.get("h1", ""),
                "headings": flatten_heading_text(card.get("headings", [])),  # type: ignore[arg-type]
                "headings_h1_h4": flatten_heading_text(  # type: ignore[arg-type]
                    card.get("headings", []), levels={"H1", "H2", "H3", "H4"}
                ),
                "headings_all": flatten_heading_text(card.get("headings", [])),  # type: ignore[arg-type]
                "question_headings": " | ".join(card.get("question_headings", [])),  # type: ignore[arg-type]
                "table_count": card.get("table_count", 0),
                "error": card.get("error", ""),
            }
        )

    write_csv(
        output_prefix.with_suffix(".competitor_structures.csv"),
        [
            "query",
            "geo_key",
            "geo_keys",
            "geo_positions",
            "position",
            "domain",
            "url",
            "final_url",
            "status",
            "page_type",
            "word_count",
            "serp_title",
            "serp_description",
            "title",
            "description",
            "h1",
            "headings",
            "headings_h1_h4",
            "headings_all",
            "question_headings",
            "table_count",
            "error",
        ],
        structure_rows,
    )

    output_prefix.with_suffix(".serp_synthesis.md").write_text(
        build_synthesis(cards, features),
        encoding="utf-8",
    )


def feature_text(feature: dict[str, object]) -> str:
    text = clean_space(str(feature.get("text") or ""))
    title = clean_space(str(feature.get("title") or ""))
    if title and title != text and len(title) < 220:
        return f"{text} — {title}"
    return text


def grouped_features(features: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for feature in features:
        feature_type = str(feature.get("feature_type") or "unknown")
        text = feature_text(feature)
        if not text:
            continue
        key = (feature_type, text.lower())
        if key in seen:
            continue
        seen.add(key)
        grouped[feature_type].append(feature)
    return grouped


def build_feature_synthesis(features: list[dict[str, object]]) -> list[str]:
    if not features:
        return [
            "",
            "## SERP features",
            "- No SERP feature file was provided. FAQ, related searches, AI Overview, and highlighted terms were not available to this brief.",
        ]

    grouped = grouped_features(features)
    lines = ["", "## SERP features"]
    labels = [
        ("answer_box", "Answer box / featured snippet"),
        ("ai_overview", "AI Overview structure"),
        ("people_also_ask", "People Also Ask / FAQ candidates"),
        ("faq_snippet", "FAQ rich snippets"),
        ("related_search", "Related searches"),
        ("highlighted_term", "Highlighted terms / topical entities"),
    ]

    for feature_type, title in labels:
        items = grouped.get(feature_type, [])
        lines.extend(["", f"### {title}"])
        if not items:
            lines.append("- Not found in provided feature data.")
            continue
        limit = 3 if feature_type in {"answer_box", "ai_overview"} else 30
        for feature in items[:limit]:
            text = feature_text(feature)
            if feature_type in {"answer_box", "ai_overview"} and len(text) > 600:
                text = text[:597].rstrip() + "..."
            lines.append(f"- {text}")

    lines.extend(
        [
            "",
            "## SEO brief additions from SERP features",
            "- Use PAA and FAQ snippets as the first source for FAQ questions.",
            "- Use related searches as secondary keyword candidates.",
            "- Use highlighted terms as entity and synonym candidates, but insert them naturally.",
            "- Use answer box and AI Overview to inform key takeaway structure. Do not copy wording.",
        ]
    )
    return lines


def build_synthesis(cards: list[dict[str, object]], features: list[dict[str, object]] | None = None) -> str:
    features = features or []
    ok_cards = [card for card in cards if card.get("status") == "ok"]
    word_counts = [int(card.get("word_count") or 0) for card in ok_cards if int(card.get("word_count") or 0) > 0]
    page_types = Counter(str(card.get("page_type") or "unknown") for card in ok_cards)
    domains = Counter(str(card.get("domain") or "") for card in cards)
    questions: list[str] = []
    heading_counter: Counter[tuple[str, str]] = Counter()
    geo_counts: Counter[str] = Counter()
    geo_unique_counts: Counter[str] = Counter()

    for card in ok_cards:
        card_geos = [
            item for item in str(card.get("geo_keys") or card.get("geo_key") or "").split(",")
            if item
        ]
        for geo in card_geos:
            geo_counts[geo] += 1
        if len(card_geos) == 1:
            geo_unique_counts[card_geos[0]] += 1
        questions.extend(str(item) for item in card.get("question_headings", []))
        for heading in card.get("headings", []):
            if isinstance(heading, dict) and heading.get("level") in {"H1", "H2", "H3", "H4"}:
                level = str(heading.get("level"))
                text = clean_space(str(heading.get("text", ""))).lower()
                if text:
                    heading_counter[(level, text)] += 1

    if word_counts:
        avg_words = round(sum(word_counts) / len(word_counts))
        min_words = min(word_counts)
        max_words = max(word_counts)
    else:
        avg_words = min_words = max_words = 0

    lines = [
        "# SERP competitor synthesis",
        "",
        "## Coverage",
        f"- URLs processed: {len(cards)}",
        f"- Successfully parsed: {len(ok_cards)}",
        f"- Failed: {len(cards) - len(ok_cards)}",
        "",
        "## Geographic coverage",
    ]

    for geo in sorted(geo_counts):
        lines.append(
            f"- {geo}: {geo_counts[geo]} parsed URLs; {geo_unique_counts[geo]} unique to this geo"
        )

    lines.extend(["", "## Page types"])

    for page_type, count in page_types.most_common():
        lines.append(f"- {page_type}: {count}")

    lines.extend(
        [
            "",
            "## Word count guardrail",
            f"- Average parsed words: {avg_words}",
            f"- Min parsed words: {min_words}",
            f"- Max parsed words: {max_words}",
            "- Use this as a guardrail, not as a target. Intent coverage is more important than matching volume.",
            "",
            "## Recurring H1-H4 themes",
        ]
    )

    for (level, heading), count in heading_counter.most_common(40):
        if heading:
            lines.append(f"- {level}: {heading} ({count})")

    lines.extend(["", "## Question candidates"])
    for question in list(dict.fromkeys(questions))[:30]:
        lines.append(f"- {question}")

    lines.extend(["", "## Competitor outlines (H1-H4)"])
    for card in sorted(ok_cards, key=lambda item: int(item.get("position") or 9999)):
        lines.extend(
            [
                "",
                f"### #{card.get('position')} {card.get('domain')} "
                f"[{card.get('geo_keys') or card.get('geo_key')}]",
                f"- SERP title: {card.get('serp_title')}",
                f"- SERP description: {card.get('serp_snippet')}",
                f"- HTML title: {card.get('title')}",
                f"- Meta description: {card.get('description')}",
                f"- URL: {card.get('url')}",
            ]
        )
        outline = render_heading_outline(card.get("headings", []))  # type: ignore[arg-type]
        lines.extend(outline or ["- No H1-H4 headings found."])

    failed_cards = [card for card in cards if card.get("status") != "ok"]
    if failed_cards:
        lines.extend(["", "## Pages not parsed"])
        for card in failed_cards:
            lines.append(f"- {card.get('url')} — {card.get('error') or 'unknown error'}")

    lines.extend(["", "## Top parsed competitors"])
    for card in sorted(cards, key=lambda item: int(item.get("position") or 9999))[:20]:
        lines.append(
            f"- #{card.get('position')} {card.get('domain')} | "
            f"geos {card.get('geo_keys') or card.get('geo_key')} | {card.get('page_type')} | "
            f"{card.get('word_count')} words | {card.get('title')}"
        )
        lines.append(f"  {card.get('url')}")

    if domains:
        lines.extend(["", "## Repeated domains"])
        for domain, count in domains.most_common(20):
            if count > 1:
                lines.append(f"- {domain}: {count}")

    lines.extend(build_feature_synthesis(features))

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build article-oriented competitor cards from the normalized SERP CSV."
    )
    parser.add_argument("--input-file", required=True, help="CSV from fetch_google_serp.py")
    parser.add_argument("--output-prefix", required=True, help="Output prefix without extension")
    parser.add_argument("--max-per-query-geo", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
        help="Maximum simultaneous competitor fetches (default: 4; use 1 for serial fetching).",
    )
    parser.add_argument("--features-file", help="Optional SERP features JSON/CSV from fetch_google_serp.py")
    parser.add_argument(
        "--require-geo", action="append", dest="required_geos",
        help="Fail before page fetching when this geo has no organic rows (repeatable).",
    )
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    rows = load_csv(Path(args.input_file))
    missing_geos = missing_organic_geos(rows, args.required_geos)
    if missing_geos:
        print(
            "Missing organic SERP rows for required geos: " + ", ".join(missing_geos),
            file=sys.stderr,
        )
        return 2
    features = load_features(Path(args.features_file)) if args.features_file else []
    selected_rows = pick_serp_rows(rows, max_per_query_geo=args.max_per_query_geo)
    if not selected_rows:
        print("No organic SERP rows found.", file=sys.stderr)
        return 1

    cards = build_cards(
        selected_rows,
        timeout=args.timeout_seconds,
        sleep_seconds=args.sleep_seconds,
        concurrency=args.concurrency,
    )

    write_outputs(Path(args.output_prefix), cards, features)
    print(f"Saved outputs with prefix: {args.output_prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
