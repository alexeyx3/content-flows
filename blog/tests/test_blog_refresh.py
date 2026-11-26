import json
import sqlite3
from pathlib import Path

import pytest

from scripts import blog_refresh as refresh
from scripts import temnik


class Sheet:
    def __init__(self, headers, rows):
        self.values = [headers[:]] + [row[:] for row in rows]

    def get_all_values(self):
        return [row[:] for row in self.values]

    def row_values(self, number):
        return self.values[number - 1][:]

    def update_cell(self, row, col, value):
        cells = self.values[row - 1]
        cells.extend([""] * (col - len(cells)))
        cells[col - 1] = value

    def batch_update(self, payload, value_input_option=None):
        for item in payload:
            import gspread
            row, col = gspread.utils.a1_to_rowcol(item["range"])
            self.update_cell(row, col, item["values"][0][0])

    def append_row(self, row, value_input_option=None):
        self.values.append(row[:])

    def update(self, cell_range, values, value_input_option=None):
        row = int(cell_range.split(":")[0][1:])
        self.values[row - 1] = values[0][:]


class Book:
    def __init__(self):
        self.history = None

    def worksheet(self, title):
        if self.history is None:
            raise temnik.gspread.WorksheetNotFound(title)
        return self.history

    def add_worksheet(self, title, rows, cols):
        self.history = Sheet([], [])
        self.history.values = []
        return self.history


def data(tmp_path: Path, cycle="cycle-01", note="First pass"):
    return {"cycle_id": cycle, "cluster_id": "own-0016", "job": str(tmp_path / cycle),
            "source_job": str(tmp_path / "source"), "source_url": "https://example.com/blog/contoso-alternatives/",
            "cycle_number": None, "review_doc_url": "", "note": note}


def setup_sheet(monkeypatch):
    headers = [temnik.HEADERS["cluster"], temnik.HEADERS["status"],
               temnik.HEADERS["url"], temnik.HEADERS["title"],
               temnik.HEADERS["google_doc"], temnik.HEADERS["published"]]
    original = ["own-0016", "", "https://example.com/blog/contoso-alternatives/",
                "Published title", "Original Doc", ""]
    sheet = Sheet(headers, [original])
    book = Book()
    monkeypatch.setattr(temnik, "connect", lambda: (book, sheet))
    return book, sheet, original


def test_registration_is_idempotent_and_versions_per_cluster(tmp_path):
    db = tmp_path / "monitor.sqlite3"
    first = data(tmp_path)
    assert refresh.register(first, "in progress", apply=True, db_path=db)["version"] == 1
    assert refresh.register(first, "in progress", apply=True, db_path=db)["version"] == 1
    with pytest.raises(refresh.RefreshError, match="different identity"):
        refresh.register({**first, "job": str(tmp_path / "other")}, "in progress", apply=True, db_path=db)
    second = data(tmp_path, "cycle-02")
    assert refresh.register(second, "in progress", apply=True, db_path=db)["version"] == 2
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM refresh_cycles").fetchone()[0] == 2


def test_sync_repeats_without_duplicate_history_and_preserves_legacy_fields(tmp_path, monkeypatch):
    db = tmp_path / "monitor.sqlite3"
    book, sheet, original = setup_sheet(monkeypatch)
    cycle = data(tmp_path)
    refresh.register(cycle, "in progress", apply=True, db_path=db)
    review = {**cycle, "review_doc_url": "https://docs.google.com/document/d/abc123/edit"}
    refresh.sync(review, "in review", apply=False, db_path=db)
    assert sheet.values[1] == original
    assert book.history is None
    refresh.sync(review, "in review", apply=True, db_path=db)
    refresh.sync(review, "in review", apply=True, db_path=db)
    assert len(book.history.values) == 2
    assert book.history.values[1][0] == "cycle-01"
    assert sheet.values[1][:6] == original
    assert sheet.values[1][sheet.values[0].index(refresh.SUMMARY[2])] == "in review"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT status FROM refresh_cycles").fetchone()[0] == "in review"


def test_later_cycle_updates_summary_and_keeps_earlier_history(tmp_path, monkeypatch):
    db = tmp_path / "monitor.sqlite3"
    book, sheet, _ = setup_sheet(monkeypatch)
    first = data(tmp_path)
    refresh.register(first, "in progress", apply=True, db_path=db)
    refresh.sync(first, "in progress", apply=True, db_path=db)
    old_history = book.history.values[1][:]
    second = data(tmp_path, "cycle-02", "Second pass")
    refresh.register(second, "in progress", apply=True, db_path=db)
    refresh.sync(second, "in progress", apply=True, db_path=db)
    assert len(book.history.values) == 3
    assert book.history.values[1] == old_history
    assert sheet.values[1][sheet.values[0].index(refresh.SUMMARY[0])] == "cycle-02"
    with pytest.raises(refresh.RefreshError, match="newer"):
        refresh.sync(first, "in progress", apply=True, db_path=db)


def test_invalid_transition_and_no_unverified_publish(tmp_path, monkeypatch):
    db = tmp_path / "monitor.sqlite3"
    setup_sheet(monkeypatch)
    cycle = data(tmp_path)
    refresh.register(cycle, "in progress", apply=True, db_path=db)
    with pytest.raises(refresh.RefreshError, match="review_doc_url"):
        refresh.sync(cycle, "in review", apply=True, db_path=db)
    with pytest.raises(refresh.RefreshError, match="CMS evidence"):
        refresh.sync(cycle, "published", apply=True, db_path=db)


def test_verified_publication_keeps_original_fields_and_single_history(tmp_path, monkeypatch):
    db = tmp_path / "monitor.sqlite3"
    book, sheet, original = setup_sheet(monkeypatch)
    cycle = {**data(tmp_path), "review_doc_url": "https://docs.google.com/document/d/abc123/edit"}
    refresh.register(cycle, "in progress", apply=True, db_path=db)
    refresh.sync(cycle, "in review", apply=True, db_path=db)
    proof = {"id": 100, "updatedAt": "2026-10-19T10:00:00Z", "publishedAt": "2026-01-15T10:00:00Z",
             "next_review_date": "2026-11-10", "article_sha256": "exact-reviewed-hash"}
    monkeypatch.setattr(refresh, "verify_publication", lambda _: proof)
    refresh.sync(cycle, "published", apply=True, db_path=db)
    refresh.sync(cycle, "published", apply=True, db_path=db)
    assert sheet.values[1][:6] == original
    assert len(book.history.values) == 2 and book.history.values[1][4] == "published"
    assert sheet.values[1][sheet.values[0].index(refresh.PUBLICATION_SUMMARY[1])] == "2026-11-10"
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM refresh_publications").fetchone()[0] == 1
        assert conn.execute("SELECT status FROM refresh_cycles").fetchone()[0] == "published"


def test_changed_publication_receipt_rejected_before_sheet_write(tmp_path, monkeypatch):
    db = tmp_path / "monitor.sqlite3"
    book, sheet, _ = setup_sheet(monkeypatch)
    cycle = {**data(tmp_path), "review_doc_url": "https://docs.google.com/document/d/abc123/edit"}
    refresh.register(cycle, "in progress", apply=True, db_path=db)
    refresh.sync(cycle, "in review", apply=True, db_path=db)
    proof = {"id": 100, "updatedAt": "2026-10-19T10:00:00Z", "publishedAt": "2026-01-15T10:00:00Z",
             "next_review_date": "2026-11-10", "article_sha256": "hash"}
    monkeypatch.setattr(refresh, "verify_publication", lambda _: proof)
    refresh.sync(cycle, "published", apply=True, db_path=db)
    frozen = sheet.get_all_values()
    proof["next_review_date"] = "2026-11-11"
    with pytest.raises(refresh.RefreshError, match="immutable"):
        refresh.sync(cycle, "published", apply=True, db_path=db)
    assert sheet.get_all_values() == frozen


def test_publication_verifies_utf8_live_body_and_rejects_other_body(tmp_path, monkeypatch):
    import hashlib
    import requests
    from scripts import strapi_publish as cms
    cycle = {**data(tmp_path), "next_review_date": "2026-11-10"}
    job = Path(cycle["job"])
    (job / "out").mkdir(parents=True)
    (job / "edited.md").write_text("Approved — text")
    content = '<h2>Contoso — alternatives</h2>\n<p>From $25 — per active contractor.</p>\n'
    (job / "out/article.html").write_text(content)
    proof = {"id": 100, "slug": "contoso-alternatives", "url": cycle["source_url"],
             "updatedAt": "2026-10-19T10:00:00Z", "publishedAt": "2026-01-15T10:00:00Z",
             "article_sha256": hashlib.sha256((job / "edited.md").read_bytes()).hexdigest(),
             "content_sha256": hashlib.sha256(content.encode()).hexdigest()}
    (job / "out/refresh-publication.json").write_text(json.dumps(proof))
    monkeypatch.setattr(cms, "api", lambda _: {"data": {**proof, "content": content,
                                                       "indexable": True, "cover": {"id": 4}}})
    response = requests.Response()
    response.status_code = 200
    response.url = cycle["source_url"]
    response.encoding = "ISO-8859-1"
    response._content = (f'<html><head><link rel="canonical" href="{cycle["source_url"]}"></head>'
                         f'<body><div class="prose">{content}</div></body></html>').encode()
    monkeypatch.setattr(requests, "get", lambda *a, **k: response)
    assert refresh.verify_publication(cycle)["next_review_date"] == "2026-11-10"
    response._content = response._content.replace(b"alternatives", b"stale body")
    with pytest.raises(refresh.RefreshError, match="canonical/body"):
        refresh.verify_publication(cycle)


def test_analytics_snapshot_is_idempotent_and_keeps_page_totals_separate(tmp_path):
    db = tmp_path / "monitor.sqlite3"
    cycle = data(tmp_path)
    raw = Path(cycle["job"]) / "raw"
    raw.mkdir(parents=True)
    analytics = {
        "property": "sc-domain:example.com", "source_url": cycle["source_url"],
        "periods": {
            "recent28": {"startDate": "2026-09-21", "endDate": "2026-10-18", "totals": {"clicks": 100}},
            "previous28": {"startDate": "2026-08-24", "endDate": "2026-09-20", "totals": {"clicks": 80}}},
        "daily_page": {"rows": [{"date": "2026-10-18", "clicks": 10}]},
        "weekly_queries": [{"startDate": "2026-10-12", "endDate": "2026-10-18", "complete": True,
                            "rows": [{"query": "contoso alternative", "clicks": 3}]}]}
    (raw / "analytics.json").write_text(json.dumps(analytics))
    refresh.register(cycle, "in progress", apply=True, db_path=db)
    refresh.register(cycle, "in progress", apply=True, db_path=db)
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cycle_baseline").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM page_daily").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM query_weekly").fetchone()[0] == 1
        assert json.loads(conn.execute("SELECT recent_totals_json FROM cycle_baseline").fetchone()[0])["clicks"] == 100
    analytics["periods"]["recent28"]["totals"]["clicks"] = 101
    (raw / "analytics.json").write_text(json.dumps(analytics))
    with pytest.raises(refresh.RefreshError, match="immutable"):
        refresh.register(cycle, "in progress", apply=True, db_path=db)
