"""Paid-model harness tests: entirely fake HTTP and synthetic credentials."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("openrouter_experiment", Path(__file__).resolve().parents[1] / "scripts/openrouter_experiment.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "KEY_SOURCE", tmp_path / "config/.env")
    monkeypatch.delenv("OPENROUTER_GUIDES_API_KEY", raising=False)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/.env").write_text("OPENROUTER_API_KEY=sk-or-old_generic\ncountries: sk-or-countries_selected\nother: sk-or-other_project\n")
    (tmp_path / "rules.md").write_text("Use only supplied evidence.")
    (tmp_path / "topic.md").write_text("Topic A")
    (tmp_path / "prompt.md").write_text("Produce the requested artifact.")
    manifest = {"schema_version": 1, "experiment_id": "test", "revision": "v1", "run_dir": "runs/test",
                "system_files": ["rules.md"], "max_cost_usd": 10, "max_call_cost_usd": 1,
                "stages": [{"id": "brief", "prompt_file": "prompt.md", "max_tokens": 4000},
                           {"id": "writer", "prompt_file": "prompt.md", "max_tokens": 8000, "input_stages": ["brief"]}],
                "variants": [{"id": "model-topic", "model": "deepseek/model-20261106", "provider": "DeepSeek", "reasoning": {"effort": "low"}, "input_files": ["topic.md"]}]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest


def save(tree):
    path, manifest = tree
    path.write_text(json.dumps(manifest))
    return mod.Experiment(path)


def fake_success(payload, key, timeout):
    assert key == "sk-or-countries_selected"
    return 200, {"id": "gen-fake", "model": payload["model"], "provider": "DeepSeek",
                 "choices": [{"finish_reason": "stop", "message": {"content": "# Full artifact\n\nVerified result."}}],
                 "usage": {"prompt_tokens": 100, "completion_tokens": 80, "cost": .012,
                           "completion_tokens_details": {"reasoning_tokens": 30}}}


def test_countries_key_does_not_fall_back_to_generic(tree):
    assert mod.countries_key() == "sk-or-countries_selected"
    (mod.ROOT / "config/.env").write_text("OPENROUTER_API_KEY=sk-or-old_generic\n")
    with pytest.raises(mod.ExperimentError, match="countries-labeled"):
        mod.countries_key()


def test_countries_key_rejects_ambiguous_labels(tree):
    with (mod.ROOT / "config/.env").open("a") as f:
        f.write("countries backup sk-or-geo_backup\n")
    with pytest.raises(mod.ExperimentError, match="exactly one"):
        mod.countries_key()


def test_explicit_geo_environment_key_wins(tree, monkeypatch):
    monkeypatch.setenv("OPENROUTER_GUIDES_API_KEY", "sk-or-env_selected")
    assert mod.countries_key() == "sk-or-env_selected"


def test_dry_run_validates_without_credentials_or_paid_http(tree, monkeypatch):
    (mod.ROOT / "config/.env").unlink()
    monkeypatch.setattr(mod, "post_json", lambda *a: pytest.fail("Paid HTTP called during dry-run"))
    e = save(tree)
    assert e.dry_run()["stages"] == 2
    assert not e.run_dir.exists()
    assert mod.main(["--manifest", str(tree[0]), "--dry-run"]) == 0


@pytest.mark.parametrize("model", ["openai/gpt-99", "anthropic/claude-99", "google/gemini-99", "deepseek/x:free"])
def test_excluded_models_rejected(tree, model):
    tree[1]["variants"][0]["model"] = model
    with pytest.raises(mod.ExperimentError):
        save(tree)


def test_static_inputs_and_dependency_order_validated(tree):
    tree[1]["stages"][0]["input_stages"] = ["writer"]
    with pytest.raises(mod.ExperimentError, match="later"):
        save(tree)
    tree[1]["stages"][0].pop("input_stages")
    tree[1]["variants"][0]["input_files"] = ["missing.md"]
    with pytest.raises(mod.ExperimentError, match="Missing input"):
        save(tree)


@pytest.mark.parametrize("field", ["input_files", "system_files"])
def test_key_file_is_never_model_input_even_without_key_shaped_tokens(tree, field):
    (mod.ROOT / "config/.env").write_text("OTHER_SERVICE_TOKEN=secret_value")
    tree[1][field] = ["config/.env"]
    if field == "input_files":
        tree[1]["variants"][0][field] = tree[1].pop(field)
    with pytest.raises(mod.ExperimentError, match="cannot be a model input"):
        save(tree)


def test_provider_is_pinned_and_request_has_no_authorization(tree):
    e = save(tree)
    req = e.build_request(e.variants[0], e.stages(e.variants[0])[0])
    assert req["provider"] == {"only": ["DeepSeek"], "allow_fallbacks": False, "require_parameters": True}
    assert req["model"] == "deepseek/model-20261106"
    assert req["reasoning"] == {"effort": "low"}
    assert "Authorization" not in json.dumps(req)
    assert "sk-or-" not in json.dumps(req)


def test_price_ceiling_is_sent_and_oversized_call_never_reaches_transport(tree):
    tree[1]["variants"][0]["max_price"] = {"prompt": 1000000, "completion": 1000000}
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    assert e.build_request(v, s)["provider"]["max_price"]["completion"] == 1000000
    with pytest.raises(mod.ExperimentError, match="cost exceeds"):
        e.run_stage(v, s, mod.countries_key(), transport=lambda *args: pytest.fail("Paid call exceeded reservation"))
    assert not e.attempts()


def test_missing_token_counts_are_unknown_instead_of_zero(tree):
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    e.run_stage(v, s, mod.countries_key(), transport=lambda *args: (429, {"error": {"message": "Rate limit"}}))
    assert e.usage_summary()["prompt_tokens"] is None
    assert e.usage_summary()["completion_tokens"] is None


def test_small_pinned_calls_reserve_their_actual_upper_bound(tree):
    tree[1]["max_cost_usd"] = 1
    tree[1]["variants"][0]["max_price"] = {"prompt": .1, "completion": .2}
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    # Simulate other in-flight work: a second full $1 reservation would fail.
    e.reserved = .5
    assert e.run_stage(v, s, mod.countries_key(), transport=fake_success)["status"] == "success"
    assert e.reserved == pytest.approx(.5)


def test_stage_system_file_only_changes_its_stage_request_and_fingerprint(tree):
    e = save(tree)
    v = e.variants[0]
    first, writer = e.stages(v)
    e.run_stage(v, first, mod.countries_key(), transport=fake_success)
    before_first = e.build_request(v, first)
    before_writer = e.build_request(v, writer)
    (mod.ROOT / "repair-system.md").write_text("For this stage return JSON patches only.")
    tree[1]["stages"][1]["system_files"] = ["repair-system.md"]
    changed = save(tree)
    cv = changed.variants[0]
    after_first = changed.build_request(cv, changed.stages(cv)[0])
    after_writer = changed.build_request(cv, changed.stages(cv)[1])
    assert mod.encoded(before_first) == mod.encoded(after_first)
    assert changed.fingerprint(before_first) == changed.fingerprint(after_first)
    assert changed._resume(cv, changed.stages(cv)[0], changed.fingerprint(after_first))
    assert "JSON patches only" not in after_first["messages"][0]["content"]
    assert after_writer["messages"][0]["content"].endswith("For this stage return JSON patches only.")
    assert after_writer["messages"][1] == before_writer["messages"][1]
    assert changed.fingerprint(before_writer) != changed.fingerprint(after_writer)
    tree[1]["stages"][1]["system_files"] = ["config/.env"]
    with pytest.raises(mod.ExperimentError, match="cannot be a model input"):
        save(tree)


def test_success_cost_reasoning_actual_model_and_resume(tree):
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    result = e.run_stage(v, s, mod.countries_key(), transport=fake_success)
    assert result["status"] == "success"
    receipt = mod.read_json(e.output_path(v, s).with_suffix(".receipt.json"))
    assert receipt["complete"] is True
    assert receipt["actual_provider"] == "DeepSeek"
    assert receipt["usage"]["completion_tokens_details"]["reasoning_tokens"] == 30
    assert e.usage_summary()["cost_usd"] == .012
    result = e.run_stage(v, s, mod.countries_key(), transport=lambda *a: pytest.fail("Valid receipt was ignored"))
    assert result["status"] == "resumed"
    assert e.usage_summary()["attempts"] == 1


@pytest.mark.parametrize("changed_field,value", [("model", "other/model"), ("provider", "OtherProvider")])
def test_unexpected_actual_route_fails_without_losing_cost(tree, changed_field, value):
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    def wrong_route(*args):
        status, response = fake_success(*args)
        response[changed_field] = value
        return status, response
    result = e.run_stage(v, s, mod.countries_key(), transport=wrong_route)
    assert result["status"] == "failed"
    assert not e.output_path(v, s).exists()
    assert e.usage_summary()["cost_usd"] == .012


def test_explicit_canonical_model_and_provider_display_names_accepted(tree):
    tree[1]["variants"][0].update(canonical_slug="deepseek/canonical-20261106", provider_names=["DeepSeek Official"])
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    def canonical(*args):
        status, response = fake_success(*args)
        response.update(model="deepseek/canonical-20261106", provider="DeepSeek Official")
        return status, response
    assert e.run_stage(v, s, mod.countries_key(), transport=canonical)["status"] == "success"


def test_changed_inputs_and_dependencies_invalidate_resume(tree):
    e = save(tree)
    v = e.variants[0]
    first, writer = e.stages(v)
    e.run_stage(v, first, mod.countries_key(), transport=fake_success)
    e.run_stage(v, writer, mod.countries_key(), transport=fake_success)
    (mod.ROOT / "topic.md").write_text("Changed topic")
    assert e.run_stage(v, first, mod.countries_key(), transport=fake_success)["status"] == "success"
    assert e.run_stage(v, writer, mod.countries_key(), transport=fake_success)["status"] == "success"
    assert e.usage_summary()["attempts"] == 4
    assert e.usage_summary()["cost_usd"] == .048


def test_changed_prior_output_invalidates_downstream(tree):
    e = save(tree)
    v = e.variants[0]
    first, writer = e.stages(v)
    e.run_stage(v, first, mod.countries_key(), transport=fake_success)
    e.run_stage(v, writer, mod.countries_key(), transport=fake_success)
    e.output_path(v, first).write_text("Different brief")
    assert e.run_stage(v, writer, mod.countries_key(), transport=fake_success)["status"] == "success"
    assert e.usage_summary()["attempts"] == 3


def test_length_failure_retains_paid_response_and_does_not_auto_retry(tree):
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    def truncated(*args):
        status, response = fake_success(*args)
        response["choices"][0]["finish_reason"] = "length"
        return status, response
    result = e.run_stage(v, s, mod.countries_key(), transport=truncated)
    assert result["status"] == "failed"
    assert not e.output_path(v, s).exists()
    assert e.usage_summary()["cost_usd"] == .012
    assert list(e.run_dir.glob("variants/*/attempts/*/partial.md"))
    with pytest.raises(mod.ExperimentError, match="inspect"):
        e.run_stage(v, s, mod.countries_key(), transport=fake_success)
    assert e.run_stage(v, s, mod.countries_key(), retry_failed=True, transport=fake_success)["status"] == "success"
    assert e.usage_summary()["cost_usd"] == .024


def test_timeout_is_uncertain_no_secret_and_blocks_new_cost(tree):
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    def failed(*args):
        raise TimeoutError("sk-or-countries_selected connection interrupted")
    assert e.run_stage(v, s, mod.countries_key(), transport=failed)["status"] == "uncertain"
    assert e.usage_summary()["unknown_cost_attempts"] == 1
    with pytest.raises(mod.ExperimentError, match="unknown cost"):
        e.run_stage(v, s, mod.countries_key(), retry_failed=True, transport=fake_success)
    for p in e.run_dir.rglob("*.json"):
        assert "sk-or-countries_selected" not in p.read_text()


def test_rejected_noncharged_error_retained_with_zero_cost(tree):
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    result = e.run_stage(v, s, mod.countries_key(), transport=lambda *a: (429, {"error": {"message": "Rate limit"}}))
    assert result["status"] == "rejected"
    assert e.usage_summary()["cost_usd"] == 0
    assert e.usage_summary()["unknown_cost_attempts"] == 0


def test_missing_api_cost_does_not_invent_zero_and_blocks_next_stage(tree):
    e = save(tree)
    v, first = e.variants[0], e.stages(e.variants[0])[0]
    def no_cost(*args):
        status, response = fake_success(*args)
        del response["usage"]["cost"]
        return status, response
    assert e.run_stage(v, first, mod.countries_key(), transport=no_cost)["status"] == "success"
    with pytest.raises(mod.ExperimentError, match="unknown cost"):
        e.run_stage(v, e.stages(v)[1], mod.countries_key(), transport=fake_success)


def test_budget_reserves_inflight_cost_and_counts_failed_paid_calls(tree):
    tree[1]["max_cost_usd"] = 1
    tree[1]["max_call_cost_usd"] = .6
    e = save(tree)
    e._reserve()
    with pytest.raises(mod.ExperimentError, match="reservation"):
        e._reserve()


def test_worker_default_and_explicit_recovery_bound(tree):
    assert save(tree).max_workers == 4
    tree[1]["max_workers"] = 8
    assert save(tree).max_workers == 8
    for workers in (0, 9):
        tree[1]["max_workers"] = workers
        with pytest.raises(mod.ExperimentError, match="between 1 and 8"):
            save(tree)


def test_credential_input_blocked_before_request(tree):
    e = save(tree)
    (mod.ROOT / "topic.md").write_text("Accidental secret sk-or-sensitive")
    with pytest.raises(mod.ExperimentError, match="Credential-shaped"):
        e.build_request(e.variants[0], e.stages(e.variants[0])[0])


def test_json_validation_failure_retains_cost_without_success_receipt(tree):
    tree[1]["stages"][0]["output_format"] = "json"
    e = save(tree)
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    assert e.run_stage(v, s, mod.countries_key(), transport=fake_success)["status"] == "failed"
    assert not e.output_path(v, s).exists()
    assert e.usage_summary()["cost_usd"] == .012


def test_interrupted_intent_blocks_execute_before_paid_calls(tree, monkeypatch):
    e = save(tree)
    p = e.run_dir / "variants/model-topic/attempts/brief-001/intent.json"
    mod.write_json(p, {"fingerprint": "some"})
    monkeypatch.setattr(mod, "post_json", lambda *a: pytest.fail("Ambiguous request replayed"))
    with pytest.raises(mod.ExperimentError, match="no receipt"):
        e.execute()
