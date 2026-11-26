import datetime as dt
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import collect_refresh_baseline as baseline


def test_collect_exact_windows_separates_page_totals_and_queries(monkeypatch, tmp_path):
    calls = []

    def fake_query(_svc, prop, start, end, dimensions, filters):
        calls.append((str(start), str(end), tuple(dimensions), filters))
        if dimensions == []:
            return [{"clicks": 100, "impressions": 1000}]
        if dimensions == ["query"]:
            return [{"keys": ["contoso alternative"], "clicks": 2, "impressions": 20}]
        return []

    monkeypatch.setattr(baseline, "query", fake_query)
    monkeypatch.setattr(baseline, "bing_snapshot", lambda url: {"status": "unavailable"})
    svc = Mock()
    svc.urlInspection.return_value.index.return_value.inspect.return_value.execute.return_value = {}
    url = "https://example.com/blog/contoso-alternatives/"
    artifacts = baseline.collect(tmp_path, {"source_url": url, "source_published_at": "2026-09-07"},
                                 dt.date(2026, 10, 16), [{"url": url, "title": "Contoso alternatives"}],
                                 client_factory=lambda: svc)
    data = json.loads(artifacts["raw/analytics.json"])
    assert data["periods"]["recent28"]["startDate"] == "2026-09-19"
    assert data["periods"]["recent28"]["endDate"] == "2026-10-16"
    assert data["periods"]["previous28"]["startDate"] == "2026-08-22"
    assert data["periods"]["previous28"]["endDate"] == "2026-09-18"
    assert data["periods"]["recent28"]["totals"][0]["impressions"] == 1000
    assert data["periods"]["recent28"]["queries"][0]["impressions"] == 20
    assert len(data["weekly_queries"]) == 6
    assert all(row["complete"] for row in data["weekly_queries"])
    assert data["weekly_queries"][-1]["endDate"] == "2026-10-11"  # last full Sunday
    assert any("before publication" in line for line in artifacts["raw/data-limitations.md"].splitlines())
    assert "lexical-only" in json.loads(artifacts["raw/owned-pages.json"])["embedding_status"]
    assert calls[-1][2] == ("query", "page")


def test_existing_baseline_is_never_overwritten(tmp_path):
    (tmp_path / "raw").mkdir()
    path = tmp_path / "raw/analytics.json"
    path.write_text("original")
    with pytest.raises(baseline.BaselineError, match="must not be overwritten"):
        baseline.save(tmp_path, {"raw/analytics.json": "replacement", "semantics.csv": "query\n"})
    assert path.read_text() == "original"
    assert not (tmp_path / "semantics.csv").exists()


def test_bing_failure_records_type_without_secret(monkeypatch):
    monkeypatch.setattr(baseline, "bing_key", lambda: ("top-secret-key", "https://example.com/"))

    def failing_get(*args, **kwargs):
        raise ValueError("top-secret-key leaked in request")

    snapshot = baseline.bing_snapshot("https://example.com/blog/example/", get=failing_get)
    assert snapshot["status"] == "partial"
    assert snapshot["index_verdict"] == "not_inferred_from_crawl_metadata"
    assert "top-secret-key" not in json.dumps(snapshot)
    assert snapshot["GetUrlInfo"]["error_type"] == "ValueError"


def test_bing_key_file_reference_selects_verified_index_without_exposing_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    config = tmp_path / "config"
    config.mkdir()
    first, verified = "a" * 32, "b" * 32
    secret_file = tmp_path / "bing-keys.txt"
    secret_file.write_text(f"other site: {first}\nExample Co: {verified}\n")
    (config / "bing-webmaster.json").write_text(json.dumps({
        "api_key_file": str(secret_file), "key_index": 1, "site_url": "https://example.com/"}))
    assert baseline.bing_key() == (verified, "https://example.com/")
    (config / "bing-webmaster.json").write_text(json.dumps({
        "api_key_file": str(secret_file), "key_index": 2, "site_url": "https://example.com/"}))
    with pytest.raises(baseline.BaselineError, match="key_index") as caught:
        baseline.bing_key()
    assert first not in str(caught.value) and verified not in str(caught.value)


def test_transient_retry_and_permanent_failure(monkeypatch):
    from googleapiclient.errors import HttpError

    def error(code):
        response = Mock(status=code)
        return HttpError(response, b'{"error":{"message":"error"}}')

    attempts = [error(503), {"rows": []}]
    def call():
        result = attempts.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
    sleeps = []
    assert baseline.retry(call, sleep=sleeps.append) == {"rows": []}
    assert sleeps == [1]
    with pytest.raises(HttpError):
        baseline.retry(lambda: (_ for _ in ()).throw(error(400)), sleep=sleeps.append)
    assert sleeps == [1]
