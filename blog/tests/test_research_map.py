import json

from scripts.validate_research_map import validate


def test_map_required_only_for_new_protocol(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "job.yaml").write_text("workflow_version: 2\n")
    assert validate(job) == []
    (job / "job.yaml").write_text("research_v3_version: 1\n")
    assert any("research_map.json" in error for error in validate(job))


def test_map_requires_distinct_actionable_decisions(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "job.yaml").write_text("research_v3_version: 1\n")
    data = {"version": 1, "decisions": [{
        "id": "Q-01", "question": "Which form applies?",
        "reader_action": "Request it before payment", "population": "US payers",
        "outcome": "Correct reporting route",
    }]}
    (job / "research_map.json").write_text(json.dumps(data))
    assert validate(job) == []
    data["decisions"].append({**data["decisions"][0], "reader_action": ""})
    (job / "research_map.json").write_text(json.dumps(data))
    errors = validate(job)
    assert any("duplicate" in error for error in errors)
    assert any("reader_action" in error for error in errors)
