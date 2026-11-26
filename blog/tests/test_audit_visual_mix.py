import json
from pathlib import Path

from scripts.audit_visual_mix import audit


def make_job(root: Path, name: str, types: list[str]) -> Path:
    job = root / name
    job.mkdir()
    (job / "visuals.json").write_text(json.dumps({
        "version": 1, "visuals": [{"type": kind} for kind in types],
    }))
    return job


def test_identical_process_decision_pairs_trigger_batch_review(tmp_path: Path) -> None:
    jobs = [make_job(tmp_path, str(i), ["process", "decision"]) for i in range(3)]
    report = audit(jobs)
    assert report["needs_editorial_review"]
    assert report["type_totals"] == {"decision": 3, "process": 3}


def test_varied_visual_sets_do_not_trigger_review(tmp_path: Path) -> None:
    jobs = [
        make_job(tmp_path, "a", ["process", "decision"]),
        make_job(tmp_path, "b", ["bar", "decision"]),
        make_job(tmp_path, "c", ["line"]),
    ]
    assert not audit(jobs)["needs_editorial_review"]
