from copy import deepcopy
import json
from unittest.mock import Mock

import pytest

from scripts import blog_monitor as monitor
from scripts import temnik


URL = "https://example.com/blog/example/"


def page(**changes):
    return {"url": URL, "status": "index_problem", "checked_at": "2026-10-20T12:00:00Z",
            "index_status": {"verdict": "NEUTRAL", "coverageState": "URL is unknown to Google"}, **changes}


def row():
    return {temnik.HEADERS['cluster']: 'b-1234', temnik.HEADERS['url']: URL,
            temnik.HEADERS['topic']: 'Example', 'Refresh: status': 'in review', '_row': '3'}


def test_not_indexed_is_skip_without_changing_completed_review_status():
    original = row()
    prior = deepcopy(original)
    updates = monitor.index_values(page())
    assert updates['Refresh: selection'] == 'Skipped: not indexed'
    assert updates['Google: indexing'] == 'Not indexed'
    assert 'Refresh: status' not in updates
    assert 'Status' not in updates
    assert original == prior


def test_unavailable_does_not_claim_not_indexed():
    values = monitor.index_values(page(status='unavailable', index_status={}, error_type='HttpError'))
    assert values['Google: indexing'] == 'Check unavailable'
    assert 'not indexed' not in values['Refresh: selection']


def test_conflicting_indexed_claim_and_naive_timestamp_rejected():
    with pytest.raises(ValueError, match='PASS/canonical'):
        monitor.index_values(page(status='indexed'))
    with pytest.raises(ValueError, match='timezone'):
        monitor.index_values(page(checked_at='2026-10-20T12:00:00'))


def test_matching_by_url_and_cluster_never_guesses_between_duplicates():
    first = row(); second = {**row(), temnik.HEADERS['cluster']: 'b-9999'}
    with pytest.raises(ValueError, match='found 2'):
        monitor.find_page([first, second], page())
    assert monitor.find_page([first, second], page(cluster_id='b-9999')) == second
    with pytest.raises(ValueError, match='found 0'):
        monitor.find_page([first], page(cluster_id='b-9999'))


def test_linked_view_looks_up_stable_id_and_does_not_copy_stale_cycle_values():
    values = monitor.dashboard_row(row(), page(), 5, 'Topic sheet - blog')
    assert len(values) == len(monitor.HEADERS)
    assert values[0] == 'b-1234'
    assert 'MATCH($A5,' in values[3]
    assert 'Refresh: status' in values[3]
    assert 'Refresh: Google Doc' in values[4]
    assert values[7].startswith('=IFERROR(LET(v,INDEX(')


def test_russian_sheet_formula_separator_does_not_change_quoted_labels():
    formula = monitor.linked('Topic sheet - blog', '$A2', 'Google: reason', ';')
    assert 'MATCH($A2;\'Topic sheet - blog\'!A:A;0)' in formula
    assert 'MATCH("Google: reason";' in formula
    assert 'IF(v="";"";v)' in formula
    assert ',' not in formula


def test_dry_run_does_not_mutate_sheet_or_create_local_db(monkeypatch, tmp_path):
    book, sheet = Mock(), Mock()
    book.url = 'https://docs.google.com/spreadsheets/d/test'
    book.worksheet.side_effect = temnik.gspread.WorksheetNotFound('absent')
    monkeypatch.setattr(temnik, 'connect', lambda: (book, sheet))
    monkeypatch.setattr(temnik, 'table', lambda _: (list(row()), [row()]))
    path = tmp_path/'monitor.sqlite3'
    receipt = {'pages': [page()]}
    before = json.dumps(receipt)
    result = monitor.sync(receipt, apply=False, db_path=path)
    assert result['status'] == 'planned'
    assert not path.exists()
    sheet.batch_update.assert_not_called()
    sheet.update.assert_not_called()
    book.add_worksheet.assert_not_called()
    assert json.dumps(receipt) == before


def test_older_inspection_cannot_replace_newer_sheet_status(monkeypatch):
    book, sheet = Mock(), Mock()
    source = {**row(), 'Google: checked': '2026-10-21T00:00:00Z'}
    monkeypatch.setattr(temnik, 'connect', lambda: (book, sheet))
    monkeypatch.setattr(temnik, 'table', lambda _: (list(source), [source]))
    with pytest.raises(ValueError, match='older inspection'):
        monitor.sync({'pages': [page()]}, apply=True)
    sheet.batch_update.assert_not_called()
