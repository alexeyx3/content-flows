import csv
import json
from pathlib import Path

from scripts.validate_primary_data_research import validate as validate_data
from scripts.validate_article_brief import validate as validate_brief


def packet() -> dict:
    return {
        "version": 1,
        "reader_decisions": ["Which cost scenario applies?"],
        "search_log": [{
            "question": "Are two costs comparable?", "channel": "official",
            "query": "site:gov.example filetype:pdf employer costs",
            "outcome": "found", "note": "Original schedule, table 2.",
        }],
        "candidates": [{
            "id": "D-01", "status": "read_original", "chart_status": "chartable",
            "question": "How do costs differ?", "decision_use": "Budget the statutory cost.",
            "proposed_section": "costs", "visual_type": "bar",
            "source_url": "https://gov.example/costs.pdf", "source_title": "Cost schedule",
            "publisher": "Official agency", "publication_date": "2026-01-01",
            "file_type": "pdf", "source_location": "p. 12, table 2",
            "unit": "USD/year", "period": "2026", "geography": "Exampleland",
            "population": "Large employers", "denominator": "not applicable",
            "method": "Original table values", "transfer_risk": "Other employers differ.",
            "points": [
                {"label": "A", "value": 100, "source_location": "p. 12, row A"},
                {"label": "B", "value": 150, "source_location": "p. 12, row B"},
            ],
        }],
        "no_data_reason": "",
    }


def job_with_packet(tmp_path: Path, data: dict | None = None) -> Path:
    job = tmp_path / "job"
    job.mkdir(exist_ok=True)
    (job / "job.yaml").write_text("workflow_version: 2\nprimary_data_research_version: 1\n")
    if data is not None:
        (job / "research.data.json").write_text(json.dumps(data))
    return job


def test_new_job_requires_primary_data_packet_and_accepts_original(tmp_path: Path) -> None:
    job = job_with_packet(tmp_path)
    assert any("research.data.json is required" in e for e in validate_data(job))
    (job / "research.data.json").write_text(json.dumps(packet()))
    assert validate_data(job) == []


def test_empty_search_result_can_omit_chart_with_reason(tmp_path: Path) -> None:
    data = packet()
    data["candidates"] = []
    data["search_log"][0]["outcome"] = "none"
    data["no_data_reason"] = "Original documents had no comparable outcome data."
    assert validate_data(job_with_packet(tmp_path, data)) == []


def test_chart_needs_original_and_traceable_comparable_points(tmp_path: Path) -> None:
    data = packet()
    data["candidates"][0]["status"] = "lead"
    data["candidates"][0]["reason"] = "Search result only."
    data["candidates"][0]["points"][1]["source_location"] = ""
    problems = validate_data(job_with_packet(tmp_path, data))
    assert any("cannot be chartable" in e for e in problems)
    data["candidates"][0]["status"] = "read_original"
    problems = validate_data(job_with_packet(tmp_path, data))
    assert any("point 2 needs label and source_location" in e for e in problems)


def test_brief_audit_must_account_for_selected_original(tmp_path: Path) -> None:
    job = job_with_packet(tmp_path, packet())
    (job / "research.md").write_text("R-01: reader decision and source")
    (job / "brief.md").write_text("# Brief\n\n## Independent research\n\nD-01 explains costs.\n")
    sections = {
        "title": "Costs", "sections": [{"id": "costs", "title": "Costs"}],
        "information_gain": [{"section_id": "costs", "reader_value": "Budget costs", "research_ref": "D-01"}],
        "visual_candidates": [{"section_id": "costs", "type": "bar", "purpose": "Compare costs", "data_ref": "D-01"}],
        "expert_questions": [],
    }
    (job / "sections.json").write_text(json.dumps(sections))
    assert any("visual_audit" in e for e in validate_brief(job))
    sections["visual_audit"] = {
        "considered_data_ids": ["D-01"], "selected_chart_ids": ["D-01"],
        "decision": "The comparable costs change the budget decision.",
    }
    (job / "sections.json").write_text(json.dumps(sections))
    assert validate_brief(job) == []


def test_existing_job_does_not_need_new_packet(tmp_path: Path) -> None:
    job = tmp_path / "job"
    job.mkdir()
    (job / "job.yaml").write_text("workflow_version: 2\n")
    assert validate_data(job) == []


def test_new_coverage_gate_requires_search_for_each_reader_decision(tmp_path: Path) -> None:
    data = packet()
    data["reader_decisions"] = ["Are two costs comparable?", "What do workers prefer?"]
    job = job_with_packet(tmp_path, data)
    with (job / "job.yaml").open("a") as output:
        output.write("research_coverage_version: 1\n")
    assert any("What do workers prefer?" in error for error in validate_data(job))
    data["search_log"].append({
        "question": "What do workers prefer?", "channel": "original survey",
        "query": "worker preferences original survey", "outcome": "none",
        "note": "No transferable original found.",
    })
    (job / "research.data.json").write_text(json.dumps(data))
    assert validate_data(job) == []


def test_one_search_can_cover_multiple_reader_decisions(tmp_path: Path) -> None:
    data = packet()
    data["reader_decisions"] = ["Which cost scenario applies?", "Which cost components differ?"]
    data["search_log"][0]["decision_refs"] = data["reader_decisions"][:]
    job = job_with_packet(tmp_path, data)
    with (job / "job.yaml").open("a") as output:
        output.write("research_coverage_version: 1\n")
    assert validate_data(job) == []


def test_new_geographic_audit_is_required_before_drafting(tmp_path: Path) -> None:
    job = job_with_packet(tmp_path, packet())
    with (job / "job.yaml").open("a") as output:
        output.write("geographic_audit_version: 1\n")
    (job / "research.md").write_text("R-01: reader decision and source")
    (job / "brief.md").write_text("# Brief\n")
    sections = {
        "title": "Costs", "sections": [{"id": "costs", "title": "Costs"}],
        "information_gain": [{"section_id": "costs", "reader_value": "Budget costs", "research_ref": "D-01"}],
        "visual_candidates": [{"section_id": "costs", "type": "bar", "purpose": "Compare costs", "data_ref": "D-01"}],
        "expert_questions": [],
        "visual_audit": {"considered_data_ids": ["D-01"], "selected_chart_ids": ["D-01"], "decision": "Changes budget."},
    }
    (job / "sections.json").write_text(json.dumps(sections))
    assert any("geographic_audit" in error for error in validate_brief(job))
    sections["geographic_audit"] = {
        "intended_scope": "Global buyers", "jurisdiction_selection": "US and EU affect the decision",
        "source_scope_risk": "One-country surveys cannot describe global workers",
    }
    (job / "sections.json").write_text(json.dumps(sections))
    assert validate_brief(job) == []


def test_v3_requires_real_file_family_search_and_read_original(tmp_path: Path) -> None:
    data = packet()
    data["reader_decisions"] = ["Q-01"]
    data["search_log"] = [{
        "question": "Which cost applies?", "decision_refs": ["Q-01"],
        "channel": "official", "query": "site:gov.example filetype:pdf employer costs",
        "outcome": "found", "note": "Original schedule.",
        "result_urls": ["https://gov.example/costs.pdf"],
    }]
    job = job_with_packet(tmp_path, data)
    with (job / "job.yaml").open("a") as output:
        output.write("research_v3_version: 1\nresearch_coverage_version: 1\n")
    (job / "research_map.json").write_text(json.dumps({"version": 1, "decisions": [{
        "id": "Q-01", "question": "Which cost applies?",
        "reader_action": "Budget", "population": "Employers",
        "outcome": "Comparable annual costs",
    }]}))
    errors = validate_data(job)
    assert any("slides" in error for error in errors)
    assert any("documents" in error for error in errors)
    assert any("spreadsheets" in error for error in errors)
    for extension in ("pptx", "docx", "xlsx"):
        data["search_log"].append({
            "question": "Which cost applies?", "decision_refs": ["Q-01"],
            "channel": "institutional", "query": f"site:edu filetype:{extension} employer costs",
            "outcome": "none", "note": "No relevant original in this format.",
        })
    (job / "raw").mkdir()
    with (job / "raw" / "document-search-us.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("query", "result_type", "url"))
        writer.writeheader()
        for row in data["search_log"]:
            writer.writerow({
                "query": row["query"],
                "result_type": "organic" if row["outcome"] == "found" else "error",
                "url": row.get("result_urls", [""])[0] if row["outcome"] == "found" else "",
            })
    (job / "research.data.json").write_text(json.dumps(data))
    assert validate_data(job) == []
    data["candidates"] = []
    data["no_data_reason"] = "No relevant number."
    (job / "research.data.json").write_text(json.dumps(data))
    assert any("read_original" in error for error in validate_data(job))
