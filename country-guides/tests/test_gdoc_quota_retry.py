"""Quota rejections recover without retrying uncertain write outcomes."""
import sys
from pathlib import Path

import httplib2
import pytest
from googleapiclient.errors import HttpError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/blog/scripts"))
import md_to_gdoc


def rejected(status):
    return HttpError(httplib2.Response({"status": str(status)}), b'{"error":{"message":"rejected"}}')


class Request:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = 0

    def execute(self):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_quota_rejection_recovers_with_bounded_backoff(monkeypatch):
    pauses = []
    monkeypatch.setattr(md_to_gdoc.time, "sleep", pauses.append)
    monkeypatch.setattr(md_to_gdoc.random, "random", lambda: 0.5)
    request = Request([rejected(429)] * 7 + [{"replies": ["inserted once"]}])
    assert md_to_gdoc.execute_quota_retry(request) == {"replies": ["inserted once"]}
    assert request.calls == 8
    assert pauses == [1.5, 2.5, 4.5, 8.5, 16.5, 32, 32]


@pytest.mark.parametrize("error", [rejected(403), rejected(500), TimeoutError("unknown outcome")])
def test_other_errors_are_not_retried(monkeypatch, error):
    pauses = []
    monkeypatch.setattr(md_to_gdoc.time, "sleep", pauses.append)
    request = Request([error])
    with pytest.raises(type(error)):
        md_to_gdoc.execute_quota_retry(request)
    assert request.calls == 1
    assert pauses == []


def test_quota_retry_budget_is_finite(monkeypatch):
    pauses = []
    monkeypatch.setattr(md_to_gdoc.time, "sleep", pauses.append)
    request = Request([rejected(429)] * 3)
    with pytest.raises(HttpError):
        md_to_gdoc.execute_quota_retry(request, retries=2)
    assert request.calls == 3
    assert len(pauses) == 2
