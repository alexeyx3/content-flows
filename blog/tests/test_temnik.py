from pathlib import Path

import pytest

from scripts.temnik import HEADERS, TemnikError, find_row, job_data, plan_updates


def test_find_row_requires_unique_cluster():
    rows = [
        {HEADERS["cluster"]: "b-1", "_row": "2"},
        {HEADERS["cluster"]: "b-2", "_row": "3"},
    ]
    assert find_row(rows, "b-2")["_row"] == "3"
    with pytest.raises(TemnikError):
        find_row(rows, "missing")


def test_plan_updates_is_idempotent_and_conflict_safe():
    row = {HEADERS["action"]: "new", HEADERS["status"]: "in progress"}
    assert plan_updates(row, {HEADERS["action"]: "new"}) == []
    changes = plan_updates(
        row, {HEADERS["status"]: "written"}, allowed_statuses={"in progress"}
    )
    assert changes == [(HEADERS["status"], "in progress", "written")]
    with pytest.raises(TemnikError):
        plan_updates(row, {HEADERS["action"]: "skip"})
    assert plan_updates(
        {HEADERS["google_doc"]: "old"},
        {HEADERS["google_doc"]: "new"},
        allowed_overwrites={HEADERS["google_doc"]},
    ) == [(HEADERS["google_doc"], "old", "new")]


def test_job_data_reads_temnik_identity(tmp_path: Path, monkeypatch):
    job = tmp_path / "job"
    job.mkdir()
    (job / "job.yaml").write_text(
        'topic: "PEO vs payroll"\n'
        'temnik_cluster_id: "b-1302"\n'
        'language: EN\narticle_type: comparison\nown_product_rank: first\n'
        'author: "john.roe"\n',
        encoding="utf-8",
    )
    _path, data = job_data(str(job))
    assert data["cluster_id"] == "b-1302"
    assert data["author"] == "john.roe"
