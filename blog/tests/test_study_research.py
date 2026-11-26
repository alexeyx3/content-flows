import json
from pathlib import Path

from scripts.validate_study_research import validate


def job(tmp_path: Path, *, flagged: bool = True) -> Path:
    path = tmp_path / "job"
    path.mkdir()
    (path / "job.yaml").write_text(
        "workflow_version: 2\n" + ("research_v3_version: 1\n" if flagged else ""),
        encoding="utf-8",
    )
    (path / "research_map.json").write_text(json.dumps({
        "version": 1,
        "decisions": [{"id": "Q-01", "question": "What changes?", "reader_action": "Choose", "population": "Buyers", "outcome": "Cost"}],
    }), encoding="utf-8")
    return path


def packet() -> dict:
    return {
        "version": 1,
        "search_log": [
            {"decision_refs": ["Q-01"], "channel": "catalogue", "query": "OpenAlex buyers cost", "outcome": "found", "note": "Relevant title."},
            {"decision_refs": ["Q-01"], "channel": "repository", "query": "site:university.example buyer cost pdf", "outcome": "found", "note": "Original read."},
        ],
        "candidates": [{
            "id": "S-01", "decision_refs": ["Q-01"], "status": "read_original",
            "source_url": "https://example.org/paper", "original_url": "https://university.example/paper.pdf",
            "source_title": "An example study", "authors": "A. Researcher", "publisher": "Research Journal",
            "publication_year": 2025, "original_access": "full_text", "access_note": "Read PDF",
            "source_location": "p. 8, table 2", "study_design": "Cohort", "method": "Measured at baseline",
            "population": "Defined buyers", "outcome": "Cost", "finding": "One scoped result",
            "decision_use": "Compare cost", "transfer_status": "usable", "transfer_risk": "Industry differs",
        }],
        "no_transferable_study_reason": "",
    }


def write(path: Path, data: dict) -> None:
    (path / "research.studies.json").write_text(json.dumps(data), encoding="utf-8")


def test_old_job_is_unchanged(tmp_path: Path) -> None:
    assert validate(job(tmp_path, flagged=False)) == []


def test_new_job_needs_packet_and_accepts_read_original(tmp_path: Path) -> None:
    path = job(tmp_path)
    assert any("research.studies.json is required" in e for e in validate(path))
    write(path, packet())
    assert validate(path) == []


def test_catalogue_alone_is_insufficient(tmp_path: Path) -> None:
    path = job(tmp_path)
    data = packet()
    data["search_log"] = data["search_log"][:1]
    write(path, data)
    assert any("direct original or repository" in e for e in validate(path))


def test_unread_metadata_cannot_be_finding(tmp_path: Path) -> None:
    path = job(tmp_path)
    data = packet()
    item = data["candidates"][0]
    item["status"] = "lead"
    item["reason"] = "Only catalogue metadata accessible"
    data["no_transferable_study_reason"] = "Original remained inaccessible."
    write(path, data)
    assert any("unread study cannot report" in e for e in validate(path))


def test_read_original_needs_methods_and_original_access(tmp_path: Path) -> None:
    path = job(tmp_path)
    data = packet()
    item = data["candidates"][0]
    item["original_access"] = "abstract"
    item["source_location"] = ""
    item["population"] = ""
    write(path, data)
    errors = validate(path)
    assert any("original_access: full_text" in e for e in errors)
    assert any("source_location" in e for e in errors)
    assert any("population" in e for e in errors)


def test_no_transferable_study_is_valid_after_credible_search(tmp_path: Path) -> None:
    path = job(tmp_path)
    data = packet()
    data["candidates"] = []
    data["search_log"][1]["outcome"] = "none"
    data["search_log"][1]["note"] = "Repository search returned no applicable originals."
    data["no_transferable_study_reason"] = "Catalogue candidate covered unrelated population; direct search found no applicable original."
    write(path, data)
    assert validate(path) == []


def test_decision_refs_must_exist_and_be_covered(tmp_path: Path) -> None:
    path = job(tmp_path)
    data = packet()
    data["search_log"][1]["decision_refs"] = ["Q-02"]
    write(path, data)
    assert any("unknown decision_ref" in e for e in validate(path))
    data["search_log"][0]["decision_refs"] = ["Q-02"]
    write(path, data)
    errors = validate(path)
    assert any("research decision Q-01 has no scholarly search" in e for e in errors)


def test_context_only_study_needs_no_transferable_reason(tmp_path: Path) -> None:
    path = job(tmp_path)
    data = packet()
    data["candidates"][0]["transfer_status"] = "context_only"
    write(path, data)
    assert any("no_transferable_study_reason" in e for e in validate(path))
