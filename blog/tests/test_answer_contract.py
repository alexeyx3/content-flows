"""Answer links cannot substitute for evidence or actual reviewed text."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import answer_contract as a
import article_materials as materials
import workflow_gate


def save_plan(job, checks=None):
    data = {"sections": [{"id": "responsibility", "title": "Responsibility"}],
            "answer_checks": checks if checks is not None else [{
                "id": "A-01", "section_id": "responsibility", "question": "Who signs?",
                "answer_needed": "Identify the signing party and condition.",
                "qualifiers": ["agreement type"]}]}
    (job / "sections.json").write_text(json.dumps(data))
    return data


def save_evidence(job, verdict="supports", check="A-01", quote="Company A signs subject to the agreement."):
    (job / "evidence.md").write_text(
        "| claim_id | claim | section | source_url | source_tier | supporting_quote | last_checked | entailment_verdict | article_link | decision_use | answer_check_ids |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
        f"| E-01 | Company A signs subject to the agreement. | responsibility | https://example.com/original | primary | {quote} | 2026-11-06 | {verdict} | required | Select a party | {check} |\n")


def save_qa(job, *, heading="Responsibility", excerpt="Company A signs subject to the agreement.",
            cid="E-01", verdict="PASS"):
    (job / "qa_report.md").write_text(
        "overall: PASS\n\n"
        "| answer_check_id | evidence_ids | article_heading | article_excerpt | verdict | note |\n"
        "|---|---|---|---|---|---|\n"
        f"| A-01 | {cid} | {heading} | {excerpt} | {verdict} | Actor and arrangement remain scoped. |\n")


@pytest.fixture
def job(tmp_path):
    (tmp_path / "job.yaml").write_text("workflow_version: 2\nanswer_contract_version: 1\n")
    save_plan(tmp_path)
    save_evidence(tmp_path)
    (tmp_path / "edited.md").write_text("# Article\n\n## Responsibility\n\nCompany A signs subject to the agreement.\n\n## Other\n\nAnother answer.\n")
    save_qa(tmp_path)
    return tmp_path


def test_complete_trace_and_existing_evidence_readers_remain_compatible(job):
    assert a.plan_errors(job) == a.evidence_errors(job) == a.qa_errors(job) == []
    assert materials.evidence_ids(job) == {"E-01"}


def test_existing_jobs_are_noop_without_reading_new_artifacts(tmp_path):
    (tmp_path / "job.yaml").write_text("workflow_version: 2\n")
    (tmp_path / "sections.json").write_text("not JSON")
    assert a.plan_errors(tmp_path) == a.evidence_errors(tmp_path) == a.qa_errors(tmp_path) == []


@pytest.mark.parametrize("mode", ["refresh", "translation"])
def test_scaffold_flag_does_not_migrate_other_branches(tmp_path, mode):
    (tmp_path / "job.yaml").write_text(f"answer_contract_version: 1\narticle_{mode}_version: 1\n")
    assert a.qa_errors(tmp_path) == []


def test_dangling_section_duplicate_check_and_non_object_fail(job):
    data = save_plan(job)
    data["answer_checks"][0]["section_id"] = "missing"
    data["answer_checks"] += [data["answer_checks"][0], "invalid"]
    (job / "sections.json").write_text(json.dumps(data))
    errors = a.plan_errors(job)
    assert any("unknown section_id" in e for e in errors)
    assert any("duplicate A-01" in e for e in errors)
    assert any("expected an object" in e for e in errors)


def test_empty_or_missing_selected_contract_is_not_silent_pass(job):
    data = save_plan(job, [])
    assert a.plan_errors(job)
    del data["answer_checks"]
    (job / "sections.json").write_text(json.dumps(data))
    assert a.plan_errors(job)


@pytest.mark.parametrize("change", ["rejected", "no_source", "no_quote", "unknown_check"])
def test_unverified_or_dangling_evidence_cannot_fulfil_answer(job, change):
    save_evidence(job, verdict="no" if change == "rejected" else "supports",
                  check="A-99" if change == "unknown_check" else "A-01",
                  quote="-" if change == "no_quote" else "Original passage.")
    if change == "no_source":
        p = job / "evidence.md"
        p.write_text(p.read_text().replace("https://example.com/original", "-"))
    assert a.evidence_errors(job)


def test_real_table_excerpt_with_pipe_and_nearby_qualification_is_accepted(job):
    text = "| Party | Condition |\n|---|---|\n| Company A | Named agreement only |"
    (job / "edited.md").write_text("# Article\n\n## Responsibility\n\n" + text + "\n")
    save_qa(job, excerpt=text.replace("|", r"\|").replace("\n", " "))
    assert a.qa_errors(job) == []


def test_excerpt_elsewhere_in_article_does_not_validate_false_location(job):
    save_qa(job, heading="Other")
    assert any("actual article_heading" in e for e in a.qa_errors(job))


def test_changes_after_qa_or_invented_excerpt_need_affected_review(job):
    save_qa(job, excerpt="Company A always guarantees the result.")
    assert any("QA excerpt is absent" in e for e in a.qa_errors(job))


def test_unrelated_claim_id_or_block_is_rejected_even_with_overall_pass(job):
    save_qa(job, cid="E-99")
    assert any("evidence_ids" in e for e in a.qa_errors(job))
    save_qa(job, verdict="BLOCK")
    assert any("semantic-review note" in e for e in a.qa_errors(job))


def test_missing_and_duplicate_review_rows_fail(job):
    (job / "qa_report.md").write_text("overall: PASS\n")
    assert any("missing answer QA row" in e for e in a.qa_errors(job))
    save_qa(job)
    report = job / "qa_report.md"
    report.write_text(report.read_text() * 2)
    assert any("duplicate" in e for e in a.qa_errors(job))


def test_nonblocking_qualification_can_be_recorded_without_polish_cycle(job):
    save_qa(job, verdict="NOTE")
    assert a.qa_errors(job) == []


def test_seal_refuses_missing_answer_review_despite_overall_pass(job, monkeypatch):
    (job / "qa_report.md").write_text("overall: PASS\n")
    assert not materials.qa_is_pass(job)
    monkeypatch.setattr(workflow_gate, "article_errors", lambda *args, **kwargs: [])
    monkeypatch.setattr(workflow_gate, "qa_is_pass", lambda *args: True)
    monkeypatch.setattr(sys, "argv", ["workflow_gate.py", "seal-qa", "--job", str(job)])
    with pytest.raises(SystemExit, match="missing answer QA row"):
        workflow_gate.main()
    assert not (job / "qa_receipt.json").exists()


def test_export_checks_answer_review_in_addition_to_receipt(job, monkeypatch):
    monkeypatch.setattr(materials, "article_errors", lambda *args, **kwargs: [])
    monkeypatch.setattr(materials, "qa_fingerprint", lambda *args: {})
    (job / "qa_receipt.json").write_text('{"hashes": {}}')
    (job / "qa_report.md").write_text("overall: PASS\n")
    assert any("missing answer QA row" in e for e in materials.export_errors(job, "review", remote=False))
