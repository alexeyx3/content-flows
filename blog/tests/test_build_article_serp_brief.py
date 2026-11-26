from __future__ import annotations

import csv
import json
import threading
import urllib.error
from collections import Counter
from pathlib import Path

import pytest

from scripts import build_article_serp_brief as serp_brief
from scripts.build_article_serp_brief import (
    build_cards,
    build_synthesis,
    missing_organic_geos,
    parse_page,
    pick_serp_rows,
    write_outputs,
)


def test_parse_page_combines_nested_heading_text_and_skips_chrome() -> None:
    parsed = parse_page(
        """
        <html>
          <head><title>Example title</title><meta name="description" content="Example description"></head>
          <body>
            <nav><h2>Navigation heading</h2></nav>
            <header><h1>Best <span>Northwind</span> alternatives</h1></header>
            <main>
              <h2>Choose by <strong>use case</strong></h2>
              <h4>Contractor-heavy teams</h4>
            </main>
            <aside><h3>Related posts</h3></aside>
            <footer><h2>Company</h2></footer>
          </body>
        </html>
        """
    )

    assert parsed["headings"] == [
        {"level": "H1", "text": "Best Northwind alternatives"},
        {"level": "H2", "text": "Choose by use case"},
        {"level": "H4", "text": "Contractor-heavy teams"},
    ]
    assert parsed["heading_tree"] == [
        {
            "level": "H1",
            "text": "Best Northwind alternatives",
            "children": [
                {
                    "level": "H2",
                    "text": "Choose by use case",
                    "children": [
                        {
                            "level": "H4",
                            "text": "Contractor-heavy teams",
                            "children": [],
                        }
                    ],
                }
            ],
        }
    ]


def test_synthesis_exposes_serp_metadata_h4_outlines_and_failures() -> None:
    cards = [
        {
            "query": "northwind alternatives",
            "geo_key": "US",
            "position": "1",
            "serp_title": "13 Northwind alternatives",
            "serp_snippet": "Compare HR and contractor tools.",
            "url": "https://example.com/northwind-alternatives",
            "domain": "example.com",
            "status": "ok",
            "error": "",
            "title": "Best Northwind alternatives",
            "description": "A full comparison.",
            "headings": [
                {"level": "H1", "text": "Best Northwind alternatives"},
                {"level": "H2", "text": "Compare platforms"},
                {"level": "H4", "text": "Reviews"},
                {"level": "H5", "text": "Hidden detail"},
            ],
            "question_headings": [],
            "word_count": 1200,
            "page_type": "comparison",
        },
        {
            "query": "northwind alternatives",
            "geo_key": "US",
            "position": "2",
            "serp_title": "Unavailable result",
            "serp_snippet": "",
            "url": "https://blocked.example/article",
            "domain": "blocked.example",
            "status": "error",
            "error": "HTTP Error 403: Forbidden",
            "headings": [],
            "question_headings": [],
            "word_count": 0,
            "page_type": "unknown",
        },
    ]

    synthesis = build_synthesis(cards)

    assert "## Recurring H1-H4 themes" in synthesis
    assert "- H4: reviews (1)" in synthesis
    assert "SERP title: 13 Northwind alternatives" in synthesis
    assert "SERP description: Compare HR and contractor tools." in synthesis
    assert "      - H4: Reviews" in synthesis
    assert "H5: Hidden detail" not in synthesis
    assert "## Pages not parsed" in synthesis
    assert "HTTP Error 403: Forbidden" in synthesis


def test_structures_csv_keeps_explicit_serp_and_heading_fields(tmp_path: Path) -> None:
    cards = [
        {
            "query": "query",
            "geo_key": "US",
            "position": "1",
            "serp_title": "SERP title",
            "serp_snippet": "SERP description",
            "url": "https://example.com",
            "final_url": "https://example.com",
            "domain": "example.com",
            "status": "ok",
            "error": "",
            "page_type": "comparison",
            "word_count": 100,
            "title": "HTML title",
            "description": "Meta description",
            "h1": "Page H1",
            "headings": [
                {"level": "H1", "text": "Page H1"},
                {"level": "H4", "text": "Deep section"},
                {"level": "H5", "text": "Raw detail"},
            ],
            "question_headings": [],
            "table_count": 0,
        }
    ]

    prefix = tmp_path / "serp"
    write_outputs(prefix, cards)

    with prefix.with_suffix(".competitor_structures.csv").open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["serp_title"] == "SERP title"
    assert row["serp_description"] == "SERP description"
    assert "H4: Deep section" in row["headings_h1_h4"]
    assert "H5: Raw detail" not in row["headings_h1_h4"]
    assert "H5: Raw detail" in row["headings"]
    assert "H5: Raw detail" in row["headings_all"]

    payload = json.loads(prefix.with_suffix(".competitor_cards.json").read_text(encoding="utf-8"))
    assert payload[0]["serp_title"] == "SERP title"


def test_cross_geo_rows_fetch_duplicate_url_once_and_keep_every_geo() -> None:
    rows = [
        {"block": "organic", "query": "topic", "geo_key": "us", "position": "1",
         "url": "https://example.com/guide?utm_source=us"},
        {"block": "organic", "query": "topic", "geo_key": "gb", "position": "3",
         "url": "https://example.com/guide"},
        {"block": "organic", "query": "topic", "geo_key": "de", "position": "2",
         "url": "https://germany.example/guide"},
    ]

    selected = pick_serp_rows(rows, max_per_query_geo=10)

    assert len(selected) == 2
    shared = next(row for row in selected if "example.com/guide" in row["url"])
    assert set(shared["geo_keys"].split(",")) == {"us", "gb"}
    assert set(shared["geo_positions"].split(",")) == {"us:1", "gb:3"}
    assert shared["position"] == "1"


def test_required_geo_check_fails_only_for_missing_organic_rows() -> None:
    rows = [
        {"block": "organic", "geo_key": "us", "url": "https://us.example"},
        {"block": "people_also_ask", "geo_key": "gb", "url": "https://gb.example"},
        {"block": "organic", "geo_key": "de", "url": ""},
        {"block": "organic", "geo_key": "au", "url": "https://au.example"},
    ]

    assert missing_organic_geos(rows, ["us", "gb", "de", "au"]) == ["de", "gb"]


def test_synthesis_labels_geographic_coverage() -> None:
    cards = [
        {
            "geo_key": "us", "geo_keys": "us,gb", "position": "1",
            "domain": "shared.example", "status": "ok", "page_type": "blog_article",
            "word_count": 100, "title": "Shared", "headings": [],
            "question_headings": [], "url": "https://shared.example", "serp_title": "Shared",
            "serp_snippet": "", "description": "",
        },
        {
            "geo_key": "au", "geo_keys": "au", "position": "2",
            "domain": "au.example", "status": "ok", "page_type": "blog_article",
            "word_count": 100, "title": "Australia", "headings": [],
            "question_headings": [], "url": "https://au.example", "serp_title": "Australia",
            "serp_snippet": "", "description": "",
        },
    ]

    synthesis = build_synthesis(cards)

    assert "## Geographic coverage" in synthesis
    assert "- gb: 1 parsed URLs; 0 unique to this geo" in synthesis
    assert "- au: 1 parsed URLs; 1 unique to this geo" in synthesis
    assert "[us,gb]" in synthesis


def test_parallel_fetches_are_bounded_and_keep_selected_order(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"url": f"https://example.com/{index}", "position": str(index + 1)}
        for index in range(6)
    ]
    lock = threading.Lock()
    batch = threading.Barrier(3)
    second_finished = threading.Event()
    active = maximum_active = 0
    finished: list[str] = []

    def fake_fetch(url: str, timeout: int) -> tuple[str, str, str]:
        nonlocal active, maximum_active
        assert timeout == 7
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        batch.wait(timeout=5)
        if url == rows[0]["url"]:
            assert second_finished.wait(timeout=5)
        with lock:
            finished.append(url)
            active -= 1
        if url == rows[1]["url"]:
            second_finished.set()
        return url + "/redirect", "text/html", f"<h1>{url}</h1><h4>Detail</h4>"

    monkeypatch.setattr(serp_brief, "fetch_page", fake_fetch)
    cards = build_cards(rows, timeout=7, sleep_seconds=0, concurrency=3)

    assert maximum_active == 3
    assert finished.index(rows[1]["url"]) < finished.index(rows[0]["url"])
    assert [card["url"] for card in cards] == [row["url"] for row in rows]
    assert all(card["status"] == "ok" for card in cards)
    assert all(card["headings"][-1] == {"level": "H4", "text": "Detail"} for card in cards)


def test_parallel_cards_equal_serial_with_dedup_geos_errors_and_all_headings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {"query": "topic", "geo_key": "us", "position": "1",
         "url": "https://shared.example/guide?utm_source=us"},
        {"query": "topic", "geo_key": "gb", "position": "3",
         "url": "https://shared.example/guide"},
        {"query": "topic", "geo_key": "de", "position": "2",
         "url": "https://blocked.example/guide", "title": "Blocked", "snippet": "SERP lead"},
        {"query": "topic", "geo_key": "au", "position": "4",
         "url": "https://au.example/guide"},
    ]
    selected = pick_serp_rows(rows, max_per_query_geo=10)
    calls: list[str] = []
    pauses: list[float] = []
    long_outline = "<h1>Guide</h1><h2>Parent</h2><h3>Child</h3>" + "".join(
        f"<h4>Detail {index}</h4>" for index in range(150)
    )

    def fake_fetch(url: str, timeout: int) -> tuple[str, str, str]:
        calls.append(url)
        if "blocked.example" in url:
            raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)
        return url + "#redirected", "text/html; charset=utf-8", long_outline

    monkeypatch.setattr(serp_brief, "fetch_page", fake_fetch)
    monkeypatch.setattr(serp_brief.time, "sleep", pauses.append)
    serial = build_cards(selected, timeout=8, sleep_seconds=0.25, concurrency=1)
    parallel = build_cards(selected, timeout=8, sleep_seconds=0.25, concurrency=4)

    assert parallel == serial
    assert Counter(calls) == Counter({row["url"]: 2 for row in selected})
    assert pauses == [0.25] * 6
    shared = next(card for card in parallel if "shared.example" in card["url"])
    assert shared["geo_keys"] == "gb,us"
    assert shared["geo_positions"] == "gb:3,us:1"
    assert shared["position"] == "1"
    assert len(shared["headings"]) == 153
    assert shared["headings"][-1] == {"level": "H4", "text": "Detail 149"}
    failed = next(card for card in parallel if card["status"] == "error")
    assert failed["error"] == "HTTP Error 403: Forbidden"
    assert failed["serp_title"] == failed["title"] == "Blocked"
    assert failed["serp_snippet"] == "SERP lead"
    assert failed["final_url"] == ""
    assert failed["headings"] == []


def test_main_validates_four_geos_before_fetching_and_uses_default_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {"query": "topic", "geo_key": geo, "position": "1", "url": f"https://{geo}.example"}
        for geo in ["us", "gb", "de", "au"]
    ]
    input_path = tmp_path / "serp.csv"
    prefix = tmp_path / "output"
    serp_brief.write_csv(input_path, list(rows[0]), rows[:-1])
    argv = [
        "build_article_serp_brief.py", "--input-file", str(input_path),
        "--output-prefix", str(prefix), "--sleep-seconds", "0",
    ]
    for geo in ["us", "gb", "de", "au"]:
        argv.extend(["--require-geo", geo])
    monkeypatch.setattr(serp_brief.sys, "argv", argv)
    calls: list[str] = []

    def fake_fetch(url: str, timeout: int) -> tuple[str, str, str]:
        calls.append(url)
        return url, "text/html", "<h1>Guide</h1>"

    monkeypatch.setattr(serp_brief, "fetch_page", fake_fetch)
    assert serp_brief.main() == 2
    assert calls == []
    assert not prefix.with_suffix(".competitor_cards.json").exists()

    observed_concurrency: list[int] = []
    original_build_cards = build_cards

    def record_build_cards(*args: object, **kwargs: object) -> list[dict[str, object]]:
        observed_concurrency.append(kwargs["concurrency"])
        return original_build_cards(*args, **kwargs)

    monkeypatch.setattr(serp_brief, "build_cards", record_build_cards)
    serp_brief.write_csv(input_path, list(rows[0]), rows)
    assert serp_brief.main() == 0
    assert observed_concurrency == [4]
    cards = json.loads(prefix.with_suffix(".competitor_cards.json").read_text(encoding="utf-8"))
    assert [card["geo_key"] for card in cards] == ["au", "de", "gb", "us"]
    assert Counter(calls) == Counter(row["url"] for row in rows)


def test_main_rejects_nonpositive_concurrency_before_fetching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(serp_brief.sys, "argv", [
        "build_article_serp_brief.py", "--input-file", str(tmp_path / "absent.csv"),
        "--output-prefix", str(tmp_path / "output"), "--concurrency", "0",
    ])
    with pytest.raises(SystemExit) as exc:
        serp_brief.main()
    assert exc.value.code == 2
