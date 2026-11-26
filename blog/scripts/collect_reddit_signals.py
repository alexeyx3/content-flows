"""Collect indexed Reddit threads as audience-discovery input for an article brief.

This intentionally uses the repository's existing XMLRiver search integration instead of
scraping Reddit. The output is a discovery corpus, never publication evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fetch_google_serp import (
    DEFAULT_KEY,
    DEFAULT_USER,
    ENV_PATH,
    build_params,
    fetch_xml_with_retry,
    filter_geos,
    html_to_plain_text,
    load_env,
    parse_serp,
    read_geos,
    xmlriver_error,
)


ROOT = Path(__file__).resolve().parents[1]
REDDIT_HOSTS = {"reddit.com", "www.reddit.com", "old.reddit.com"}


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", html_to_plain_text(value or "")).strip()


def build_queries(primary_query: str) -> list[str]:
    """Return two broad, low-cost discovery queries without pretending to infer intent."""
    query = clean_space(primary_query).strip('"')
    if not query:
        raise ValueError("primary query must not be empty")
    return [
        f'site:reddit.com "{query}"',
        f'site:reddit.com "{query}" problems OR experience OR switched OR recommend',
    ]


def canonical_thread_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    host = parsed.netloc.lower()
    if host not in REDDIT_HOSTS:
        return ""
    match = re.search(r"(/r/[^/]+/comments/[^/]+(?:/[^/?#]+)?)", parsed.path, flags=re.I)
    if not match:
        return ""
    path = match.group(1).rstrip("/") + "/"
    return urllib.parse.urlunsplit(("https", "www.reddit.com", path, "", ""))


def reddit_parts(url: str) -> tuple[str, str]:
    match = re.search(r"/r/([^/]+)/comments/([^/]+)", url, flags=re.I)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def build_records(query_rows: list[tuple[str, list[dict[str, str]]]]) -> list[dict[str, object]]:
    """Filter, normalize, and deduplicate search results while preserving query provenance."""
    records: dict[str, dict[str, object]] = {}
    for search_query, rows in query_rows:
        for row in rows:
            url = canonical_thread_url(row.get("url", ""))
            if not url:
                continue
            subreddit, thread_id = reddit_parts(url)
            existing = records.get(url)
            if existing:
                queries = existing["search_queries"]
                assert isinstance(queries, list)
                if search_query not in queries:
                    queries.append(search_query)
                continue
            records[url] = {
                "signal_id": f"reddit-{len(records) + 1:02d}",
                "search_queries": [search_query],
                "search_position": int(row.get("position") or 0),
                "subreddit": subreddit,
                "thread_id": thread_id,
                "title": clean_space(row.get("title", "")),
                "snippet": clean_space(row.get("snippet", "")),
                "url": url,
            }
    return list(records.values())


def render_packet(
    primary_query: str,
    geo: str,
    retrieved_at: str,
    search_queries: list[str],
    records: list[dict[str, object]],
) -> str:
    lines = [
        "# Reddit audience-discovery packet",
        "",
        f"- Primary discovery query: `{primary_query}`",
        f"- SERP geo: `{geo}`",
        f"- Retrieved: `{retrieved_at}`",
        f"- Indexed threads: `{len(records)}`",
        "",
        "## Use boundary",
        "",
        "These are Google-indexed Reddit titles and snippets, not verified facts and not a",
        "representative survey. Use them only to discover reader language, questions, failure",
        "modes, objections, and hidden decision criteria. A recurring theme needs independent",
        "threads; any claim intended for publication needs a separate authoritative source in",
        "`evidence.md`. Ignore promotional, irrelevant, or obviously synthetic threads.",
        "",
        "## Search queries",
        "",
    ]
    lines.extend(f"- `{query}`" for query in search_queries)
    lines.extend(["", "## Indexed observations", ""])
    if not records:
        lines.append("No usable Reddit threads were returned. Do not manufacture audience signals.")
    for record in records:
        lines.extend(
            [
                f"### {record['signal_id']} — {record['title'] or 'Untitled thread'}",
                "",
                f"- Subreddit: `r/{record['subreddit']}`",
                f"- URL: {record['url']}",
                f"- Search queries: {', '.join(f'`{q}`' for q in record['search_queries'])}",
                f"- Indexed snippet: {record['snippet'] or '[no snippet returned]'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="Topic/query used only for Reddit discovery.")
    parser.add_argument("--geo", default="US")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-results", type=int, default=15)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--json-output-file")
    parser.add_argument("--retrieved-at", default=date.today().isoformat())
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()

    if args.top_n < 1 or args.top_n > 20:
        parser.error("--top-n must be between 1 and 20")
    if args.max_results < 1:
        parser.error("--max-results must be positive")

    env_values = load_env(ENV_PATH)
    user = os.environ.get("XMLRIVER_USER") or env_values.get("XMLRIVER_USER") or DEFAULT_USER
    key = os.environ.get("XMLRIVER_KEY") or env_values.get("XMLRIVER_KEY") or DEFAULT_KEY
    if not user or not key:
        print("Missing XMLRIVER_USER/XMLRIVER_KEY in config/.env", file=sys.stderr)
        return 1

    geos = filter_geos(read_geos(ROOT / "config" / "geos.json"), [args.geo])
    if not geos:
        print(f"Unknown geo: {args.geo}", file=sys.stderr)
        return 1
    geo = geos[0]
    queries = build_queries(args.query)
    query_rows: list[tuple[str, list[dict[str, str]]]] = []

    pages = max(1, (args.top_n + 9) // 10)
    for query_number, search_query in enumerate(queries, start=1):
        rows: list[dict[str, str]] = []
        for page in range(1, pages + 1):
            print(
                f"[{query_number}/{len(queries)}] {search_query} :: {args.geo.lower()} :: page {page}",
                flush=True,
            )
            params = build_params(user, key, search_query, geo, page, include_ads=False)
            xml_text = fetch_xml_with_retry(params, timeout=args.timeout_seconds)
            error = xmlriver_error(xml_text)
            if error:
                print(f"XMLRiver error: {error}", file=sys.stderr)
                return 1
            rows.extend(parse_serp(xml_text, position_offset=(page - 1) * 10))
            if page < pages:
                time.sleep(args.sleep_seconds)
        query_rows.append((search_query, rows[: args.top_n]))
        if query_number < len(queries):
            time.sleep(args.sleep_seconds)

    records = build_records(query_rows)[: args.max_results]
    output = Path(args.output_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_packet(args.query, args.geo, args.retrieved_at, queries, records),
        encoding="utf-8",
    )

    json_output = Path(args.json_output_file) if args.json_output_file else output.with_suffix(".json")
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(
            {
                "query": args.query,
                "geo": args.geo,
                "retrieved_at": args.retrieved_at,
                "search_queries": queries,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(records)} indexed Reddit threads to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
