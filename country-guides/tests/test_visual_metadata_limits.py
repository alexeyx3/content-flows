"""Reject Strapi-incompatible metadata before rendering or uploading media."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/blog/scripts"))
from article_materials import validate_inputs


@pytest.fixture
def visual_job(tmp_path):
    (tmp_path / "job.yaml").write_text("workflow_version: 2\n")
    for name in ("research.md", "brief.md"):
        (tmp_path / name).write_text("Verified material.\n")
    (tmp_path / "evidence.md").write_text("| F-001 | Statutory value | supports |\n")
    data = {
        "sections.json": {"sections": [{"id": "cost"}], "information_gain": [
            {"section_id": "cost", "reader_value": "Compare the stated costs", "research_ref": "R-A-01"}]},
        "expert_quotes.json": {"quotes": [], "omission_reason": "No editorial quote required."},
        "visuals.json": {"visuals": [{"id": "cost", "section_id": "cost", "type": "bar",
            "purpose": "Compare statutory values", "title": "Cost", "alt": "Two statutory values",
            "caption": "Conditions apply.", "sources": [{"label": "Act", "url": "https://example.gov/act"}],
            "data": {"unit": "EUR", "categories": ["A", "B"], "series": [{"name": "Cost",
                "values": [1, 2], "evidence_ids": [["F-001"], ["F-001"]]}]}}]},
    }
    for name, value in data.items():
        (tmp_path / name).write_text(json.dumps(value))
    return tmp_path


@pytest.mark.parametrize("field", ["title", "alt", "caption"])
def test_metadata_limit_accepts_255_characters_and_blocks_256(visual_job, field):
    path = visual_job / "visuals.json"
    data = json.loads(path.read_text())
    data["visuals"][0][field] = "я" * 255
    path.write_text(json.dumps(data))
    assert validate_inputs(visual_job) == []
    data["visuals"][0][field] += "я"
    path.write_text(json.dumps(data))
    assert any(field in error and "255" in error for error in validate_inputs(visual_job))


@pytest.mark.parametrize("index", [True, False, None, -1, 0, 2, 1.5, "1"])
def test_announced_line_boundary_rejects_invalid_index(visual_job, index):
    path = visual_job / "visuals.json"
    data = json.loads(path.read_text())
    visual = data["visuals"][0]
    visual["type"] = "line"
    visual["data"]["x_label"] = "Year"
    visual["data"]["series"][0]["announced_from_index"] = index
    path.write_text(json.dumps(data))
    assert any("announced_from_index" in error for error in validate_inputs(visual_job))


def test_announced_boundary_is_valid_for_line_only(visual_job):
    path = visual_job / "visuals.json"
    data = json.loads(path.read_text())
    visual = data["visuals"][0]
    visual["type"] = "line"
    visual["data"]["x_label"] = "Year"
    visual["data"]["series"][0]["announced_from_index"] = 1
    path.write_text(json.dumps(data))
    assert validate_inputs(visual_job) == []
    visual["type"] = "bar"
    path.write_text(json.dumps(data))
    assert any("announced_from_index" in error for error in validate_inputs(visual_job))


@pytest.mark.parametrize("precision", [True, None, -1, 7, 2.5, "3"])
def test_bar_precision_rejects_invalid_value(visual_job, precision):
    path = visual_job / "visuals.json"
    data = json.loads(path.read_text())
    data["visuals"][0]["data"]["value_decimals"] = precision
    path.write_text(json.dumps(data))
    assert any("value_decimals" in error for error in validate_inputs(visual_job))


def test_bar_accepts_millime_precision(visual_job):
    path = visual_job / "visuals.json"
    data = json.loads(path.read_text())
    data["visuals"][0]["data"]["value_decimals"] = 3
    path.write_text(json.dumps(data))
    assert validate_inputs(visual_job) == []


@pytest.mark.parametrize("label", [None, "", "   ", 1, "x" * 81])
def test_future_rate_label_rejects_invalid_text(visual_job, label):
    path = visual_job / "visuals.json"
    data = json.loads(path.read_text())
    data["visuals"][0]["type"] = "line"
    data["visuals"][0]["data"]["future_rate_label"] = label
    path.write_text(json.dumps(data))
    assert any("future_rate_label" in error for error in validate_inputs(visual_job))


def test_future_rate_label_is_line_only(visual_job):
    path = visual_job / "visuals.json"
    data = json.loads(path.read_text())
    visual = data["visuals"][0]
    visual["type"] = "line"
    visual["data"]["x_label"] = "Year"
    visual["data"]["series"][0]["announced_from_index"] = 1
    visual["data"]["future_rate_label"] = "Enacted future rates: not yet in force"
    path.write_text(json.dumps(data))
    assert validate_inputs(visual_job) == []
    visual["type"] = "bar"
    path.write_text(json.dumps(data))
    assert any("future_rate_label" in error for error in validate_inputs(visual_job))
