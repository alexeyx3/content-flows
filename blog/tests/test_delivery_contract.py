"""Selected delivery checks are opt-in references plus a current native QA audit."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import delivery_contract as d
import article_materials as materials
import validate_article_brief as brief_validator
import workflow_gate


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def plan(job):
    return json.loads((job / "sections.json").read_text())


def audit(job):
    return json.loads((job / "qa_delivery.json").read_text())


def bind_audit(job):
    value = audit(job)
    value["article_sha256"] = d.digest(job / "edited.md")
    value["input_sha256"] = {name: d.digest(job / name) for name in d.AUDIT_INPUTS}
    save(job / "qa_delivery.json", value)


@pytest.fixture
def job(tmp_path):
    (tmp_path / "job.yaml").write_text("workflow_version: 2\nbatch_delivery_contract_version: 1\n")
    (tmp_path / "brief.md").write_text(
        "# Brief\n\n## Selected delivery\n\nRetain the original 2025 US sample scope.\n"
        "Use a workflow table for the selected actions.\n")
    save(tmp_path / "sections.json", {
        "sections": [{"id": "comparison", "title": "Comparison", "subheadings": [{"level": 3, "title": "Scope"}]},
                     {"id": "other", "title": "Other"}],
        "delivery_checks": [
            {"id": "DLV-01", "section_id": "comparison", "kind": "source_qualifier",
             "requirement": "Retain the source's 2025 US sample qualification.", "evidence_required": True,
             "basis": {"brief_heading": "Selected delivery", "brief_excerpt": "Retain the original 2025 US sample scope."}},
            {"id": "DLV-02", "section_id": "comparison", "kind": "table",
             "requirement": "Deliver the selected workflow actions in a table.", "evidence_required": False,
             "basis": {"brief_heading": "Selected delivery", "brief_excerpt": "Use a workflow table for the selected actions."}}
        ]})
    (tmp_path / "evidence.md").write_text(
        "| claim_id | claim | section | source_url | source_tier | supporting_quote | last_checked | entailment_verdict | article_link | decision_use | delivery_check_ids |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
        "| E-01 | The finding concerns the 2025 US sample. | comparison | https://example.com/original | primary | Finding in the 2025 US sample. | 2026-11-07 | supports | required | Keep sample scope | DLV-01 |\n")
    (tmp_path / "edited.md").write_text(
        "# Article\n\n## Comparison\n\n| Action | Next step |\n|---|---|\n| Review | Check the scope |\n"
        "\n### Scope\n\nThe finding concerns the 2025 US sample.\n\n## Other\n\nAnother result.\n")
    (tmp_path / "qa_report.md").write_text("overall: PASS\ndelivery_reviewer: native-qa-thread\n")
    save(tmp_path / "qa_delivery.json", {
        "schema_version": 1, "reviewer": "native-qa-thread", "summary": "Reviewed both selected obligations against the current article.",
        "checks": [
            {"id": "DLV-01", "verdict": "PASS", "article_heading": "Scope",
             "article_excerpt": "The finding concerns the 2025 US sample.", "evidence_ids": ["E-01"],
             "reason": "The finding retains the source's period and US sample limitation."},
            {"id": "DLV-02", "verdict": "PASS", "article_heading": "Comparison",
             "article_excerpt": "| Action | Next step |\n|---|---|\n| Review | Check the scope |", "evidence_ids": [],
             "reason": "The selected nonfactual workflow is delivered as the promised table."}
        ]})
    bind_audit(tmp_path)
    return tmp_path


def test_complete_plan_supported_scope_and_table_audit(job):
    assert d.plan_errors(job) == d.evidence_errors(job) == d.qa_errors(job) == []
    assert materials.evidence_ids(job) == {"E-01"}


@pytest.mark.parametrize("config", ["workflow_version: 2\n", "batch_delivery_contract_version: 0\n",
    "batch_delivery_contract_version: 1\narticle_refresh_version: 1\n",
    "batch_delivery_contract_version: 1\narticle_translation_version: 1\n"])
def test_legacy_refresh_and_translation_are_noop_without_reading_artifacts(tmp_path, config):
    (tmp_path / "job.yaml").write_text(config)
    (tmp_path / "sections.json").write_text("invalid JSON")
    assert not d.enabled(tmp_path)
    assert d.plan_errors(tmp_path) == d.evidence_errors(tmp_path) == d.qa_errors(tmp_path) == []


@pytest.mark.parametrize("defect", ["missing-list", "not-list", "not-object", "bad-id", "duplicate-id",
    "unknown-section", "bad-kind", "empty-requirement", "missing-basis", "invented-basis", "wrong-basis-heading",
    "missing-evidence-choice", "qualifier-not-evidenced"])
def test_missing_invalid_or_untraceable_plan_references_block(job, defect):
    value = plan(job); row = value["delivery_checks"][0]
    if defect == "missing-list": value.pop("delivery_checks")
    elif defect == "not-list": value["delivery_checks"] = {}
    elif defect == "not-object": value["delivery_checks"].append("invalid")
    elif defect == "bad-id": row["id"] = "01"
    elif defect == "duplicate-id": value["delivery_checks"].append(row.copy())
    elif defect == "unknown-section": row["section_id"] = "absent"
    elif defect == "bad-kind": row["kind"] = "quota"
    elif defect == "empty-requirement": row["requirement"] = " "
    elif defect == "missing-basis": row.pop("basis")
    elif defect == "invented-basis": row["basis"]["brief_excerpt"] = "Invented brief promise."
    elif defect == "wrong-basis-heading": row["basis"]["brief_heading"] = "Nonexistent"
    elif defect == "missing-evidence-choice": row.pop("evidence_required")
    elif defect == "qualifier-not-evidenced": row["evidence_required"] = False
    save(job / "sections.json", value)
    assert d.plan_errors(job)


@pytest.mark.parametrize("value", [None, [], "invalid", {"delivery_checks": []},
    {"sections": [{"id": "comparison", "title": []}], "delivery_checks": []},
    {"sections": [{"id": "comparison", "title": "Comparison", "subheadings": "invalid"}], "delivery_checks": []}])
def test_malformed_plan_is_a_validation_block_not_a_crash(job, value):
    save(job / "sections.json", value)
    assert d.plan_errors(job) and d.qa_errors(job)


def test_empty_selection_requires_native_review_explanation_and_still_current_qa(job):
    value = plan(job); value["delivery_checks"] = []
    save(job / "sections.json", value)
    assert any("no_additional_obligations" in e for e in d.plan_errors(job))
    value["delivery_review"] = {"reviewer": "native-strategy-thread", "no_additional_obligations": "Reviewed the selected brief; no additional deliverables were selected."}
    save(job / "sections.json", value)
    # Remove prior mappings; no factual obligation is being fabricated.
    (job / "evidence.md").write_text((job / "evidence.md").read_text().replace("| DLV-01 |", "| - |"))
    result = audit(job); result["checks"] = []; save(job / "qa_delivery.json", result); bind_audit(job)
    assert d.plan_errors(job) == d.evidence_errors(job) == d.qa_errors(job) == []
    (job / "qa_delivery.json").unlink()
    assert d.qa_errors(job)


@pytest.mark.parametrize("before,after", [
    ("| supports |", "| no |"), ("https://example.com/original", "-"),
    ("Finding in the 2025 US sample.", "-"), ("| DLV-01 |", "| - |"),
    ("| DLV-01 |", "| DLV-99 |")])
def test_factual_qualifier_needs_actual_supported_mapped_source(job, before, after):
    path = job / "evidence.md"; path.write_text(path.read_text().replace(before, after))
    assert d.evidence_errors(job)


@pytest.mark.parametrize("target", ["edited.md", "brief.md", "sections.json", "evidence.md", "qa_report.md"])
def test_audit_is_stale_after_any_bound_input_changes(job, target):
    path = job / target; path.write_text(path.read_text() + "\n")
    assert any("stale audit" in e for e in d.qa_errors(job))


@pytest.mark.parametrize("defect", ["missing-id", "duplicate-id", "unknown-id", "block", "reason", "fake-excerpt",
    "wrong-heading", "outside-approved-section", "wrong-evidence", "no-evidence", "different-reviewer", "no-reviewer-marker"])
def test_qa_cannot_pass_incomplete_invented_or_unresolved_delivery(job, defect):
    value = audit(job); row = value["checks"][0]
    if defect == "missing-id": value["checks"].pop()
    elif defect == "duplicate-id": value["checks"].append(row.copy())
    elif defect == "unknown-id": row["id"] = "DLV-99"
    elif defect == "block": row["verdict"] = "BLOCK"
    elif defect == "reason": row["reason"] = " "
    elif defect == "fake-excerpt": row["article_excerpt"] = "Unsupported universal finding."
    elif defect == "wrong-heading": row["article_heading"] = "Missing heading"
    elif defect == "outside-approved-section": row.update(article_heading="Other", article_excerpt="Another result.")
    elif defect == "wrong-evidence": row["evidence_ids"] = ["E-99"]
    elif defect == "no-evidence": row["evidence_ids"] = []
    elif defect == "different-reviewer": value["reviewer"] = "api-critic"
    elif defect == "no-reviewer-marker": (job / "qa_report.md").write_text("overall: PASS\n")
    save(job / "qa_delivery.json", value); bind_audit(job)
    assert d.qa_errors(job)


def test_plan_is_integrated_into_existing_brief_validator(job):
    value = plan(job); value.pop("delivery_checks"); save(job / "sections.json", value)
    assert any("delivery_checks" in e for e in brief_validator.validate(job))


def test_input_and_writer_gates_block_unsupported_delivery_before_drafting(job):
    (job / "evidence.md").write_text("No mapped source found.\n")
    assert any("delivery evidence mapping" in e for e in materials.validate_inputs(job))
    assert any("delivery evidence mapping" in e for e in materials.writer_ready_errors(job))


@pytest.mark.parametrize("defect", ["missing", "stale", "non-pass", "missing-check"])
def test_qa_acceptance_and_seal_refuse_invalid_audit_despite_overall_pass(job, monkeypatch, defect):
    if defect == "missing":
        (job / "qa_delivery.json").unlink()
    else:
        value = audit(job)
        if defect == "stale":
            value["article_sha256"] = "0" * 64
        elif defect == "non-pass":
            value["checks"][0]["verdict"] = "BLOCK"
        else:
            value["checks"].pop()
        save(job / "qa_delivery.json", value)
    assert not materials.qa_is_pass(job)
    monkeypatch.setattr(workflow_gate, "article_errors", lambda *a, **kw: [])
    # Even a caller trusting only overall: PASS cannot bypass the final audit.
    monkeypatch.setattr(workflow_gate, "qa_is_pass", lambda *a: True)
    monkeypatch.setattr(sys, "argv", ["workflow_gate.py", "seal-qa", "--job", str(job)])
    with pytest.raises(SystemExit, match="delivery QA|delivery requirement"):
        workflow_gate.main()
    assert not (job / "qa_receipt.json").exists()


def setup_fingerprint_files(job):
    for name in materials.QA_FILES:
        path = job / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
    save(job / "expert_quotes.json", {"quotes": []})


@pytest.mark.parametrize("target", ["review", "strapi"])
@pytest.mark.parametrize("defect", ["missing", "stale", "non-pass", "missing-check"])
def test_direct_export_checks_current_audit_even_with_existing_qa_receipt(job, monkeypatch, target, defect):
    monkeypatch.setattr(materials, "article_errors", lambda *a, **kw: [])
    monkeypatch.setattr(materials, "qa_fingerprint", lambda *a: {})
    save(job / "qa_receipt.json", {"hashes": {}})
    if defect == "missing":
        (job / "qa_delivery.json").unlink()
    else:
        value = audit(job)
        if defect == "stale":
            value["input_sha256"]["brief.md"] = "0" * 64
        elif defect == "non-pass":
            value["checks"][0]["verdict"] = "BLOCK"
        else:
            value["checks"].pop()
        save(job / "qa_delivery.json", value)
    assert materials.export_errors(job, target, remote=False)


def test_seal_and_export_bind_delivery_audit_and_brief_in_existing_fingerprint(job, monkeypatch):
    setup_fingerprint_files(job)
    assert d.qa_errors(job) == []
    monkeypatch.setattr(workflow_gate, "article_errors", lambda *a, **kw: [])
    monkeypatch.setattr(materials, "article_errors", lambda *a, **kw: [])
    monkeypatch.setattr(sys, "argv", ["workflow_gate.py", "seal-qa", "--job", str(job)])
    workflow_gate.main()
    receipt = json.loads((job / "qa_receipt.json").read_text())
    assert receipt["hashes"]["qa_delivery.json"] == d.digest(job / "qa_delivery.json")
    assert receipt["hashes"]["brief.md"] == d.digest(job / "brief.md")
    assert materials.export_errors(job, "review", remote=False) == []
    # This remains a structurally valid audit, but its post-seal change needs a
    # current seal. A truthful semantic reason must not bypass byte binding.
    value = audit(job); value["checks"][0]["reason"] += " Checked again."
    save(job / "qa_delivery.json", value)
    assert d.qa_errors(job) == []
    assert any("seal-qa" in e for e in materials.export_errors(job, "review", remote=False))


def test_unflagged_fingerprint_retains_legacy_file_set(job):
    setup_fingerprint_files(job)
    (job / "job.yaml").write_text("workflow_version: 2\n")
    (job / "qa_delivery.json").unlink()
    fingerprint = materials.qa_fingerprint(job)
    assert "brief.md" not in fingerprint and "qa_delivery.json" not in fingerprint
