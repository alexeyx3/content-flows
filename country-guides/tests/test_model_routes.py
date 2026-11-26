import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_model_route import inspect_rollout


def test_runtime_mismatch_cannot_pass_config_only(tmp_path):
    path = tmp_path / "rollout.jsonl"
    path.write_text(json.dumps({"timestamp": "2026-10-15T12:00:00Z", "type": "turn_context",
                               "payload": {"model": "gpt-6.1-sol", "effort": "high"}}) + "\n")
    receipt = inspect_rollout(path, {"model": "gpt-6-sol", "reasoning_effort": "medium"})
    assert receipt["status"] == "FAIL"
    assert len(receipt["mismatches"]) == 1


def test_switched_chat_checks_only_new_contexts(tmp_path):
    path = tmp_path / "rollout.jsonl"
    path.write_text("\n".join(json.dumps({"timestamp": timestamp, "type": "turn_context",
                      "payload": {"model": model, "effort": effort}}) for timestamp, model, effort in [
        ("2026-10-15T12:00:00Z", "gpt-6.1-sol", "high"),
        ("2026-10-15T13:00:00Z", "gpt-6-sol", "medium")]) + "\n")
    receipt = inspect_rollout(path, {"model": "gpt-6-sol", "reasoning_effort": "medium"},
                              "2026-10-15T12:30:00+00:00")
    assert receipt["status"] == "PASS"
    assert len(receipt["contexts"]) == 1


def test_missing_runtime_context_is_pending(tmp_path):
    path = tmp_path / "rollout.jsonl"
    path.write_text("")
    assert inspect_rollout(path, {"model": "gpt-6-sol", "reasoning_effort": "medium"})["status"] == "PENDING"
