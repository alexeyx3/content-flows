from __future__ import annotations

import json
import sys

from scripts.fetch_google_serp import (
    SerpProviderError,
    build_dataforseo_task,
    dataforseo_result,
    parse_dataforseo_features,
    parse_dataforseo_serp,
)


def test_resume_serp_refetches_only_missing_markets_and_keeps_features(tmp_path, monkeypatch):
    from scripts import fetch_google_serp as serp
    csv_file, json_file = tmp_path / "serp.csv", tmp_path / "features.json"
    monkeypatch.setattr(sys, "argv", ["fetch", "--query", "payroll", "--geo", "us", "--geo", "au",
                                     "--sleep-seconds", "0", "--output-file", str(csv_file),
                                     "--features-output-file", str(json_file), "--provider", "xmlriver"])
    monkeypatch.setenv("XMLRIVER_USER", "test")
    monkeypatch.setenv("XMLRIVER_KEY", "test")
    requested = []
    fail = {"au"}

    def fetch(user, key, query, geo, *args):
        market = geo["geo_key"]
        requested.append(market)
        if market in fail:
            raise serp.SerpProviderError("temporary error")
        return ([{"position": 1, "result_type": "organic", "url": f"https://example.org/{market}"}],
                [{"feature_type": "paa", "text": market}], [])

    monkeypatch.setattr(serp, "collect_xmlriver_serp", fetch)
    assert serp.main() == 1
    assert requested == ["us", "au"]
    fail.clear()
    requested.clear()
    sys.argv.append("--resume")
    assert serp.main() == 0
    assert requested == ["au"]
    assert {row["geo_key"] for row in json.loads(json_file.read_text())} == {"us", "au"}
    assert "https://example.org/us" in csv_file.read_text()
    assert "https://example.org/au" in csv_file.read_text()
    assert "temporary error" not in csv_file.read_text()


def sample_payload() -> dict[str, object]:
    return {
        "status_code": 20000,
        "status_message": "Ok.",
        "tasks": [
            {
                "status_code": 20000,
                "status_message": "Ok.",
                "result": [
                    {
                        "items": [
                            {
                                "type": "organic",
                                "rank_group": 1,
                                "rank_absolute": 2,
                                "domain": "example.com",
                                "title": "A <b>useful</b> guide",
                                "url": "https://example.com/guide",
                                "description": "Decision-ready overview.",
                            },
                            {
                                "type": "people_also_ask",
                                "items": [
                                    {
                                        "type": "people_also_ask_element",
                                        "title": "What does this cost?",
                                        "expanded_element": [
                                            {
                                                "description": "It depends on scope.",
                                                "url": "https://example.org/answer",
                                            }
                                        ],
                                    }
                                ],
                            },
                            {
                                "type": "related_searches",
                                "items": [{"title": "Related decision", "url": "https://google.com/"}],
                            },
                            {
                                "type": "featured_snippet",
                                "title": "Quick answer",
                                "description": "A concise answer.",
                                "url": "https://answer.example/",
                            },
                        ]
                    }
                ],
            }
        ],
    }


def test_dataforseo_task_reuses_country_code_and_normalizes_language() -> None:
    task = build_dataforseo_task(
        "global expansion",
        {"country_id": 2840, "language_code": "lang_en"},
        20,
        ai_overview=True,
    )

    assert task == {
        "keyword": "global expansion",
        "location_code": 2840,
        "language_code": "en",
        "device": "desktop",
        "os": "windows",
        "depth": 20,
        "load_async_ai_overview": True,
    }


def test_dataforseo_parser_preserves_existing_serp_row_shape() -> None:
    rows = parse_dataforseo_serp(sample_payload())

    assert rows == [
        {
            "position": "1",
            "result_type": "organic",
            "block": "organic",
            "title": "A useful guide",
            "url": "https://example.com/guide",
            "domain": "example.com",
            "ads_url": "",
            "snippet": "Decision-ready overview.",
        }
    ]


def test_dataforseo_features_map_to_existing_feature_types() -> None:
    features = parse_dataforseo_features(sample_payload())

    assert [(item["feature_type"], item["text"]) for item in features] == [
        ("people_also_ask", "What does this cost?"),
        ("related_search", "Related decision"),
        ("answer_box", "A concise answer."),
    ]
    assert features[0]["title"] == "It depends on scope."


def test_dataforseo_task_error_is_not_treated_as_empty_serp() -> None:
    payload = {
        "status_code": 20000,
        "tasks": [{"status_code": 40101, "status_message": "Authentication failed"}],
    }

    try:
        dataforseo_result(payload)
    except SerpProviderError as exc:
        assert "40101" in str(exc)
    else:
        raise AssertionError("expected SerpProviderError")
