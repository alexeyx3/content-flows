from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "config" / ".env"
DEFAULT_USER = ""
DEFAULT_KEY = ""
XMLRIVER_ENDPOINT = "https://xmlriver.com/search/xml"


def load_env(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def read_geos(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_brands(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_intents(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_params(
    user: str,
    key: str,
    query: str,
    geo: dict[str, object],
    page: int,
    include_ads: bool,
    additional_features: list[str] | None = None,
    highlights: bool = False,
    ai_overview: bool = False,
) -> dict[str, str]:
    params: dict[str, str] = {
        "user": user,
        "key": key,
        "query": query,
        "groupby": "10",
        "page": str(page),
        "country": str(geo["country_id"]),
        "domain": str(geo["domain_id"]),
        "device": "desktop",
    }
    if include_ads:
        params["ads"] = "1"
    additional = list(additional_features or [])
    if include_ads:
        additional.extend(["topads", "bottomads"])
    if additional:
        params["additional"] = ",".join(dict.fromkeys(additional))
    if highlights:
        params["highlights"] = "1"
    if ai_overview:
        params["ai"] = "1"
    loc_id = geo.get("loc_id")
    if loc_id:
        params["loc"] = str(loc_id)
    language_code = geo.get("language_code")
    if language_code:
        params["lr"] = str(language_code)
    return params


def fetch_xml(params: dict[str, str], timeout: int) -> str:
    url = f"{XMLRIVER_ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        charset = response.headers.get_content_charset()
        if charset:
            return body.decode(charset, errors="replace")

        for encoding in ("utf-8", "cp1251", "windows-1251", "latin-1"):
            try:
                text = body.decode(encoding)
                if "<response" in text or "<yandexsearch" in text:
                    return text
            except UnicodeDecodeError:
                continue
        return body.decode("utf-8", errors="replace")


def xmlriver_error(xml_text: str) -> str | None:
    """Return "<code>: <message>" if XMLRiver replied with an error node."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    node = root.find("./response/error")
    if node is None:
        return None
    code = (node.get("code") or "").strip()
    message = clean_xml_text(node.text or "")
    return f"{code}: {message}" if code else message


def fetch_xml_with_retry(
    params: dict[str, str],
    timeout: int,
    attempts: int = 3,
    sleep_seconds: float = 3.0,
    fetcher=fetch_xml,
    sleeper=time.sleep,
) -> str:
    """Fetch with retries: XMLRiver returns transient 500s that need a re-request."""
    last_body = ""
    for attempt in range(1, attempts + 1):
        try:
            last_body = fetcher(params, timeout)
        except Exception as exc:  # noqa: BLE001 - transport errors are retryable too
            if attempt == attempts:
                raise
            print(f"    transport error ({exc}), retry {attempt}/{attempts - 1}", flush=True)
            sleeper(sleep_seconds)
            continue
        error = xmlriver_error(last_body)
        if error is None:
            return last_body
        if attempt == attempts:
            break
        print(f"    XMLRiver error ({error}), retry {attempt}/{attempts - 1}", flush=True)
        sleeper(sleep_seconds)
    return last_body


def extract_aio_sources(xml_text: str) -> list[dict[str, str]]:
    """Extract AI Overview source links from /response/ai/item nodes.

    Verified against XMLRiver 2026-07-27: the `ai` node holds a base64 `answer`
    plus one `item` per cited source. The generic SERP-feature extractor only
    picks up the first URL, which is why this lives separately.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    ai_node = root.find("./response/ai")
    if ai_node is None:
        return []

    sources: list[dict[str, str]] = []
    for item in ai_node.findall("item"):
        url = clean_xml_text(item.findtext("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        sources.append(
            {
                "position": str(len(sources) + 1),
                "url": url,
                "domain": extract_domain(url),
                "title": clean_xml_text(item.findtext("title") or ""),
                "snippet": clean_xml_text(item.findtext("snippet") or ""),
            }
        )
    return sources


def extract_domain(url: str) -> str:
    domain = urllib.parse.urlparse(url).netloc.lower()
    if domain.startswith("www."):
        return domain[4:]
    return domain


def extract_snippet(node: ET.Element) -> str:
    passages = node.find("passages")
    if passages is not None:
        text_parts = [" ".join(part.strip().split()) for part in passages.itertext() if part.strip()]
        if text_parts:
            return " ".join(text_parts)
    return " ".join((node.findtext("snippet") or "").strip().split())


def clean_xml_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def tag_name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1].lower()


def node_text(node: ET.Element) -> str:
    return clean_xml_text(" ".join(part.strip() for part in node.itertext() if part.strip()))


def first_child_text(node: ET.Element, names: set[str]) -> str:
    for child in node.iter():
        if child is node:
            continue
        if tag_name(child) in names:
            text = node_text(child)
            if text:
                return text
    return ""


def first_child_url(node: ET.Element) -> str:
    for child in node.iter():
        if child is node:
            continue
        if tag_name(child) in {"url", "link", "href"}:
            text = node_text(child)
            if text.startswith(("http://", "https://")):
                return text
    return ""


def feature_record(
    feature_type: str,
    text: str,
    title: str = "",
    url: str = "",
    source_tag: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, object]:
    return {
        "feature_type": feature_type,
        "source_tag": source_tag,
        "title": clean_xml_text(title),
        "text": clean_xml_text(text),
        "url": clean_xml_text(url),
        "extra": extra or {},
    }


def looks_like_base64_html(value: str) -> bool:
    text = clean_xml_text(value)
    if len(text) < 80:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9+/=\s]+", text)) and text.startswith(("PG", "PGR", "PHA"))


def html_to_plain_text(value: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_xml_text(html.unescape(text))


def decode_possible_ai_html(value: str) -> str:
    text = clean_xml_text(value)
    if not looks_like_base64_html(text):
        return text
    try:
        decoded = base64.b64decode(text + "===").decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return text
    plain = html_to_plain_text(decoded)
    plain = re.sub(r"(.{0,80})", lambda m: m.group(0), plain)
    return plain


def extract_questions_from_container(container: ET.Element, source_tag: str) -> list[dict[str, object]]:
    features: list[dict[str, object]] = []
    seen: set[str] = set()
    for node in container.iter():
        name = tag_name(node)
        if name not in {"question", "q", "item"}:
            continue
        text = (
            first_child_text(node, {"question", "q", "text", "title"})
            if name == "item"
            else node_text(node)
        )
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        answer = first_child_text(node, {"answer", "a", "snippet", "description"})
        features.append(
            feature_record(
                "people_also_ask",
                text,
                title=answer,
                url=first_child_url(node),
                source_tag=source_tag,
            )
        )
    return features


def extract_text_items_from_container(
    container: ET.Element,
    feature_type: str,
    source_tag: str,
    child_names: set[str],
) -> list[dict[str, object]]:
    features: list[dict[str, object]] = []
    seen: set[str] = set()
    for node in container.iter():
        name = tag_name(node)
        if name not in child_names:
            continue
        text = node_text(node)
        if not text or text.lower() in seen:
            continue
        if text.startswith(("http://", "https://")):
            continue
        seen.add(text.lower())
        features.append(
            feature_record(
                feature_type,
                text,
                url=first_child_url(node),
                source_tag=source_tag,
            )
        )
    return features


def extract_serp_features(xml_text: str) -> list[dict[str, object]]:
    root = ET.fromstring(xml_text)
    features: list[dict[str, object]] = []
    seen_blocks: set[int] = set()

    for node in root.iter():
        name = tag_name(node)
        node_id = id(node)
        if node_id in seen_blocks:
            continue

        if name in {"relatedquestions", "related_questions", "rq", "peoplealsoask", "people_also_ask"}:
            features.extend(extract_questions_from_container(node, name))
            seen_blocks.add(node_id)
            continue

        if name in {"relatedsearches", "related_searches", "relatedqueries", "related_queries", "rs"}:
            features.extend(
                extract_text_items_from_container(
                    node,
                    "related_search",
                    name,
                    {"query", "text", "phrase", "item"},
                )
            )
            seen_blocks.add(node_id)
            continue

        if name in {"faqsnippet", "faq_snippet", "faq"}:
            features.extend(extract_questions_from_container(node, name))
            if not features or features[-1].get("source_tag") != name:
                text = node_text(node)
                if text:
                    features.append(feature_record("faq_snippet", text, source_tag=name))
            seen_blocks.add(node_id)
            continue

        if name in {"google_first_position", "first_position", "answerbox", "answer_box", "featuredsnippet", "featured_snippet"}:
            text = node_text(node)
            if text:
                title = first_child_text(node, {"title", "name"})
                features.append(
                    feature_record(
                        "answer_box",
                        text,
                        title=title,
                        url=first_child_url(node),
                        source_tag=name,
                    )
                )
            seen_blocks.add(node_id)
            continue

        if name == "ai":
            text = decode_possible_ai_html(node_text(node))
            present = first_child_text(node, {"present"})
            if present == "1" and text == "1":
                features.append(
                    feature_record(
                        "ai_overview_status",
                        "AI Overview present, but text was not returned in XMLRiver response.",
                        source_tag=name,
                    )
                )
            elif text:
                features.append(
                    feature_record(
                        "ai_overview",
                        text,
                        url=first_child_url(node),
                        source_tag=name,
                    )
                )
            seen_blocks.add(node_id)
            continue

    highlights: list[str] = [
        clean_xml_text(html.unescape(item))
        for item in re.findall(r"<hlword>(.*?)</hlword>", xml_text, flags=re.I | re.S)
    ]
    for node in root.iter():
        name = tag_name(node)
        if name in {"hlword", "highlight", "highlighted", "b", "em"} or "highlight" in name:
            if name in {"user_highlights"}:
                continue
            text = node_text(node)
            if text:
                highlights.append(text)
    for text in dict.fromkeys(highlights):
        features.append(feature_record("highlighted_term", text, source_tag="highlights"))

    deduped: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for feature in features:
        text = str(feature.get("text") or "")
        if not text:
            continue
        key = (
            str(feature.get("feature_type") or ""),
            text.lower(),
            str(feature.get("url") or "").lower(),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(feature)
    return deduped


def parse_serp(xml_text: str, position_offset: int) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []

    for idx, doc in enumerate(root.findall(".//doc"), start=1):
        url = (doc.findtext("url") or "").strip()
        items.append(
            {
                "position": str(position_offset + idx),
                "result_type": (doc.findtext("contenttype") or "organic").strip() or "organic",
                "block": "organic",
                "title": (doc.findtext("title") or "").strip(),
                "url": url,
                "domain": extract_domain(url),
                "ads_url": "",
                "snippet": extract_snippet(doc),
            }
        )

    for block_name in ("topads", "bottomads"):
        for idx, query in enumerate(root.findall(f".//{block_name}/query"), start=1):
            url = (query.findtext("url") or "").strip()
            ads_url = (query.findtext("adsurl") or "").strip()
            items.append(
                {
                    "position": str(idx),
                    "result_type": "ad",
                    "block": block_name,
                    "title": (query.findtext("title") or "").strip(),
                    "url": url,
                    "domain": extract_domain(url),
                    "ads_url": ads_url,
                    "snippet": extract_snippet(query),
                }
            )
    return items


def build_query_records(
    brands: list[dict[str, str]],
    intents: list[str],
    direct_queries: list[str] | None,
) -> list[dict[str, str]]:
    if direct_queries:
        return [
            {
                "brand": query,
                "brand_domain": "",
                "brand_category": "manual_query",
                "is_target_brand": "",
                "intent": "",
                "query": query,
            }
            for query in direct_queries
        ]

    records: list[dict[str, str]] = []
    for brand in brands:
        for intent in intents:
            records.append(
                {
                    "brand": brand["brand"],
                    "brand_domain": brand["domain"],
                    "brand_category": brand["category"],
                    "is_target_brand": brand["is_target_brand"],
                    "intent": intent,
                    "query": f"{intent} {brand['brand']}",
                }
            )
    return records


def filter_brands(brands: list[dict[str, str]], only_brands: list[str] | None) -> list[dict[str, str]]:
    if not only_brands:
        return brands

    lookup = {item.lower() for item in only_brands}
    return [brand for brand in brands if brand["brand"].lower() in lookup or brand["domain"].lower() in lookup]


def filter_geos(geos: list[dict[str, object]], only_geos: list[str] | None) -> list[dict[str, object]]:
    if not only_geos:
        return geos

    lookup = {item.lower() for item in only_geos}
    return [geo for geo in geos if str(geo["geo_key"]).lower() in lookup]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_features_json(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_features_csv(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_parent(path)
    fieldnames = [
        "brand",
        "brand_domain",
        "brand_category",
        "is_target_brand",
        "intent",
        "query",
        "geo_key",
        "country_name",
        "country_code",
        "city_name",
        "page",
        "feature_type",
        "source_tag",
        "title",
        "text",
        "url",
        "extra_json",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            serialized["extra_json"] = json.dumps(serialized.pop("extra", {}), ensure_ascii=False)
            writer.writerow(serialized)


def safe_slug(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug[:80] or "query"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brands-file", default=str(ROOT / "data" / "brands.csv"))
    parser.add_argument("--geos-file", default=str(ROOT / "config" / "geos.json"))
    parser.add_argument("--intents-file", default=str(ROOT / "data" / "intents.txt"))
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--brand", action="append", dest="brands")
    parser.add_argument("--geo", action="append", dest="geos")
    parser.add_argument("--intent", action="append", dest="intents")
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--limit-brands", type=int)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--target-only", action="store_true")
    parser.add_argument("--ads", action="store_true")
    parser.add_argument(
        "--serp-features",
        action="store_true",
        help="Request and parse PAA, related searches, FAQ snippets, and answer box blocks.",
    )
    parser.add_argument("--highlights", action="store_true", help="Request highlighted snippet terms.")
    parser.add_argument("--ai-overview", action="store_true", help="Request AI Overview if XMLRiver supports it.")
    parser.add_argument("--features-output-file", help="Optional JSON output file for parsed SERP features.")
    parser.add_argument("--features-csv-output-file", help="Optional CSV output file for parsed SERP features.")
    parser.add_argument("--raw-xml-dir", help="Optional directory to save raw XML responses for debugging.")
    args = parser.parse_args()

    env_values = load_env(ENV_PATH)
    user = os.environ.get("XMLRIVER_USER") or env_values.get("XMLRIVER_USER") or DEFAULT_USER
    key = os.environ.get("XMLRIVER_KEY") or env_values.get("XMLRIVER_KEY") or DEFAULT_KEY
    if not user or not key:
        print("Missing XMLRIVER_USER/XMLRIVER_KEY in config/.env", file=sys.stderr)
        return 1

    geos = filter_geos(read_geos(Path(args.geos_file)), args.geos)
    direct_queries = [query.strip() for query in (args.queries or []) if query.strip()]

    brands: list[dict[str, str]] = []
    intents: list[str] = []
    if not direct_queries:
        brands = read_brands(Path(args.brands_file))
        if args.target_only:
            brands = [brand for brand in brands if brand["is_target_brand"] == "1"]
        brands = filter_brands(brands, args.brands)
        if args.limit_brands:
            brands = brands[: args.limit_brands]

        intents = read_intents(Path(args.intents_file))
        if args.intents:
            requested = {intent.lower() for intent in args.intents}
            intents = [intent for intent in intents if intent.lower() in requested]

    query_records = build_query_records(brands, intents, direct_queries)
    if not geos or not query_records:
        print("Nothing to fetch: check query/brand/geo/intent filters.", file=sys.stderr)
        return 1

    output_path = Path(args.output_file)
    ensure_parent(output_path)
    feature_rows: list[dict[str, object]] = []
    raw_xml_dir = Path(args.raw_xml_dir) if args.raw_xml_dir else None
    if raw_xml_dir:
        raw_xml_dir.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "brand",
        "brand_domain",
        "brand_category",
        "is_target_brand",
        "intent",
        "query",
        "geo_key",
        "country_name",
        "country_code",
        "city_name",
        "position",
        "result_type",
        "block",
        "domain",
        "url",
        "ads_url",
        "title",
        "snippet",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        pages_per_query = max(1, (args.top_n + 9) // 10)
        total_requests = len(query_records) * len(geos) * pages_per_query
        request_number = 0

        for query_record in query_records:
            for geo in geos:
                query = query_record["query"]
                for page in range(1, pages_per_query + 1):
                    request_number += 1
                    additional_features = (
                        ["rq", "rs", "faqsnippet", "google_first_position"]
                        if args.serp_features
                        else []
                    )
                    params = build_params(
                        user,
                        key,
                        query,
                        geo,
                        page,
                        include_ads=args.ads,
                        additional_features=additional_features,
                        highlights=args.highlights,
                        ai_overview=args.ai_overview,
                    )
                    print(
                        f"[{request_number}/{total_requests}] {query} :: {geo['geo_key']} :: page {page}",
                        flush=True,
                    )

                    try:
                        xml_text = fetch_xml(params, timeout=args.timeout_seconds)
                        if raw_xml_dir:
                            raw_path = raw_xml_dir / f"{safe_slug(query)}__{geo['geo_key']}__page-{page}.xml"
                            raw_path.write_text(xml_text, encoding="utf-8")
                        if args.serp_features or args.highlights or args.ai_overview:
                            for feature in extract_serp_features(xml_text):
                                feature_rows.append(
                                    {
                                        **query_record,
                                        "geo_key": geo["geo_key"],
                                        "country_name": geo["country_name"],
                                        "country_code": geo["country_code"],
                                        "city_name": geo.get("city_name") or "",
                                        "page": page,
                                        **feature,
                                    }
                                )
                        rows = parse_serp(xml_text, position_offset=(page - 1) * 10)
                    except Exception as exc:  # noqa: BLE001
                        writer.writerow(
                            {
                                **query_record,
                                "geo_key": geo["geo_key"],
                                "country_name": geo["country_name"],
                                "country_code": geo["country_code"],
                                "city_name": geo.get("city_name") or "",
                                "position": "",
                                "result_type": "error",
                                "block": "",
                                "domain": "",
                                "url": "",
                                "ads_url": "",
                                "title": f"ERROR: {exc}",
                                "snippet": "",
                            }
                        )
                        continue

                    for row in rows:
                        if int(row["position"]) > args.top_n:
                            continue
                        writer.writerow(
                            {
                                **query_record,
                                "geo_key": geo["geo_key"],
                                "country_name": geo["country_name"],
                                "country_code": geo["country_code"],
                                "city_name": geo.get("city_name") or "",
                                **row,
                            }
                        )

                    time.sleep(args.sleep_seconds)

    print(f"Saved results to {output_path}")
    if args.features_output_file:
        write_features_json(Path(args.features_output_file), feature_rows)
        print(f"Saved SERP features to {args.features_output_file}")
    if args.features_csv_output_file:
        write_features_csv(Path(args.features_csv_output_file), feature_rows)
        print(f"Saved SERP features CSV to {args.features_csv_output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
