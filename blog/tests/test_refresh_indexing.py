from unittest.mock import Mock

import pytest

from scripts import refresh_indexing

URL = "https://example.com/blog/example/"


@pytest.mark.parametrize("result,status,ready", [
    ({"verdict": "PASS", "googleCanonical": URL}, "indexed", True),
    ({"verdict": "PASS", "googleCanonical": "https://example.com/blog/other/"}, "canonical_mismatch", False),
    ({"verdict": "PASS"}, "unknown", False),
    ({"verdict": "NEUTRAL", "coverageState": "URL is unknown to Google"}, "index_problem", False),
    ({"verdict": "NEUTRAL", "coverageState": "Crawled - currently not indexed"}, "index_problem", False),
    ({"verdict": "FAIL", "indexingState": "BLOCKED_BY_META_TAG"}, "index_problem", False),
    ({}, "unknown", False),
])
def test_preselection_requires_confirmed_index_and_exact_canonical(result, status, ready):
    svc = Mock()
    svc.urlInspection.return_value.index.return_value.inspect.return_value.execute.return_value = {
        "inspectionResult": {"indexStatusResult": result}}
    receipt = refresh_indexing.inspect(URL, service=svc)
    assert receipt["status"] == status
    assert receipt["ready_for_semantic_refresh"] is ready
    assert receipt["index_status"] == result
    svc.urlInspection.return_value.index.return_value.inspect.assert_called_once_with(body={
        "inspectionUrl": URL, "siteUrl": "sc-domain:example.com", "languageCode": "en-US"})


def test_api_failure_is_not_nonindexation_and_does_not_expose_secret():
    svc = Mock()
    svc.urlInspection.side_effect = ValueError("credential-secret")
    result = refresh_indexing.inspect(URL, service=svc)
    assert result["status"] == "unavailable"
    assert result["ready_for_semantic_refresh"] is False
    assert "credential-secret" not in str(result)


def test_invalid_url_does_not_call_api():
    svc = Mock()
    with pytest.raises(ValueError):
        refresh_indexing.inspect("https://example.com/", service=svc)
    svc.urlInspection.assert_not_called()
