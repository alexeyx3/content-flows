"""Country selection must stop before content work for unsupported/unverified CMS routes."""
import copy
import json
from pathlib import Path
import sys
import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_cms_country as cms
import common
import new_guide_job


def schemas():
    country = {"code": {"type": "enumeration", "enum": ["NZ", "ZA"], "required": True},
               "name": {"type": "string"}, "slug": {"type": "string"},
               "employerContributions": {"type": "decimal", "required": True},
               "contentHtml": {"type": "richtext"},
               **{key: {"type": "string", "maxLength": 32} for key in cms.HEADER_STRINGS}}
    subpage = {"kind": {"type": "enumeration", "enum": ["eor", "contractors"]},
               "country": {"type": "relation", "target": cms.COUNTRY_UID},
               "contentHtml": {"type": "richtext"}}
    return {cms.COUNTRY_UID: country, cms.SUBPAGE_UID: subpage}


def transport(monkeypatch, data):
    calls = []

    def get(path, method="GET", body=None):
        assert method == "GET" and body is None, "Compatibility checks must never write to CMS"
        uid = path.removeprefix("/content-type-builder/content-types/")
        calls.append(path)
        return {"data": {"uid": uid, "schema": {"attributes": copy.deepcopy(data[uid])}}}

    monkeypatch.setattr(cms, "api", get)
    return calls


def test_supported_country_checks_both_live_schemas_without_writes(monkeypatch):
    calls = transport(monkeypatch, schemas())
    result = cms.check_country("NZ", "new-zealand")
    assert result["status"] == "PASS" and result["errors"] == []
    assert result["iso"] == "NZ" and result["checked_at_utc"]
    assert len(calls) == 2


def test_taiwan_is_blocked_without_substituting_its_identity(monkeypatch):
    transport(monkeypatch, schemas())
    result = cms.check_country("TW", "taiwan")
    assert result["status"] == "BLOCK" and result["iso"] == "TW"
    assert any("TW is unsupported" in error for error in result["errors"])


@pytest.mark.parametrize("change", ["code_unverifiable", "numeric_header_changed", "missing_contractors", "wrong_relation"])
def test_incompatible_export_contract_blocks_selection(monkeypatch, change):
    data = schemas()
    if change == "code_unverifiable":
        data[cms.COUNTRY_UID]["code"] = {"type": "string"}
    elif change == "numeric_header_changed":
        data[cms.COUNTRY_UID]["employerContributions"]["type"] = "json"
    elif change == "missing_contractors":
        data[cms.SUBPAGE_UID]["kind"]["enum"] = ["eor"]
    else:
        data[cms.SUBPAGE_UID]["country"]["target"] = "api::article.article"
    transport(monkeypatch, data)
    assert cms.check_country("NZ")["status"] == "BLOCK"


def test_unavailable_schema_is_not_a_success(monkeypatch):
    def unavailable(*_):
        raise urllib.error.URLError("offline")
    monkeypatch.setattr(cms, "api", unavailable)
    result = cms.check_country("NZ")
    assert result["status"] == "BLOCK" and len(result["errors"]) == 2


def test_wrong_schema_response_is_not_a_success(monkeypatch):
    monkeypatch.setattr(cms, "api", lambda *_: {"data": {"uid": "other", "schema": {"attributes": {}}}})
    assert cms.check_country("NZ")["status"] == "BLOCK"


@pytest.mark.parametrize("iso", ["", "nz", "CN/TW", None])
def test_bad_identity_never_reaches_transport(monkeypatch, iso):
    monkeypatch.setattr(cms, "api", lambda *_: pytest.fail("Invalid identity must stop before a network call"))
    assert cms.check_country(iso)["status"] == "BLOCK"


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    (root / "config").mkdir(parents=True)
    data = {"countries": [{"slug": "taiwan", "name": "Taiwan", "iso": "TW", "status": "pending",
                           "geo_key": "tw", "eor_query": "employer of record taiwan", "query_name": "taiwan",
                           "order": 1, "icp": False, "pilot": False}]}
    (root / "config/queue.json").write_text(json.dumps(data))
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(new_guide_job, "ROOT", root)
    monkeypatch.setattr(new_guide_job, "HINTS", root / "no-hints")
    return root


def test_blocked_job_leaves_queue_and_files_untouched(project, monkeypatch):
    transport(monkeypatch, schemas())
    before = (project / "config/queue.json").read_bytes()
    with pytest.raises(SystemExit, match="CMS compatibility BLOCK"):
        new_guide_job.create("taiwan", "2099-01-01")
    assert (project / "config/queue.json").read_bytes() == before
    assert not (project / "jobs").exists()


def test_schema_outage_leaves_job_and_queue_untouched(project, monkeypatch):
    monkeypatch.setattr(cms, "api", lambda *_: (_ for _ in ()).throw(TimeoutError()))
    before = (project / "config/queue.json").read_bytes()
    with pytest.raises(SystemExit, match="Cannot verify live CMS schema"):
        new_guide_job.create("taiwan", "2099-01-01")
    assert (project / "config/queue.json").read_bytes() == before
    assert not (project / "jobs").exists()


def test_successful_job_retains_live_compatibility_receipt(project, monkeypatch):
    data = schemas()
    data[cms.COUNTRY_UID]["code"]["enum"].append("TW")
    transport(monkeypatch, data)
    relative = new_guide_job.create("taiwan", "2099-01-01")
    receipt = json.loads((project / relative / "raw/cms-compatibility.json").read_text())
    assert receipt["status"] == "PASS" and receipt["iso"] == "TW"
    assert len(list((project / relative / "pages").glob("*/job.yaml"))) == 3
    assert json.loads((project / "config/queue.json").read_text())["countries"][0]["status"] == "in_progress"
