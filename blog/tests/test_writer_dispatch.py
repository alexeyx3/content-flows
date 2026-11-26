import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import writer_dispatch as dispatch


def make_job(tmp_path):
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections.json").write_text(json.dumps({"sections": [
        {"id": "first", "title": "First", "subheadings": [
            {"level": 3, "title": "One"}, {"level": 4, "title": "Detail"},
            {"level": 3, "title": "Two"}]},
        {"id": "second", "title": "Second"}]}))
    return tmp_path


def test_dispatch_preserves_whole_h2_subtree_in_one_assignment(tmp_path):
    plan = dispatch.dispatch_plan(make_job(tmp_path))
    assert len(plan["units"]) == 2
    assert plan["units"][0]["requested_unit"] == "First"
    assert plan["units"][0]["headings"] == [
        {"level": 2, "title": "First"}, {"level": 3, "title": "One"},
        {"level": 4, "title": "Detail"}, {"level": 3, "title": "Two"}]
    assert plan["units"][1]["path"] == "sections/section_2.md"


def test_recovery_does_not_skip_partial_h2(tmp_path):
    job = make_job(tmp_path)
    (job / "sections/section_1.md").write_text("## First\n\n### One\n\n#### Detail\n\nOnly the first subtree.\n")
    assert dispatch.next_unit(job)["section_id"] == "first"
    with (job / "sections/section_1.md").open("a") as handle:
        handle.write("\n### Two\n\nSecond subtree.\n")
    assert dispatch.next_unit(job)["section_id"] == "second"
    (job / "sections/section_2.md").write_text("## Second\n\nComplete.\n")
    assert dispatch.next_unit(job) is None


@pytest.mark.parametrize("body", ["", "## First\n### One\n#### Detail\n### Two",
                                   "## First\n### One\n#### Detail\nText.\n### Two\n"])
def test_empty_or_heading_only_assignments_are_incomplete(tmp_path, body):
    job = make_job(tmp_path)
    (job / "sections/section_1.md").write_text(body)
    assert dispatch.unit_errors(job, dispatch.writing_units(job)[0])


def test_dispatch_rejects_orphan_h4(tmp_path):
    job = make_job(tmp_path)
    data = json.loads((job / "sections.json").read_text())
    data["sections"][0]["subheadings"] = [{"level": 4, "title": "Orphan"}]
    (job / "sections.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hierarchy"):
        dispatch.writing_units(job)
