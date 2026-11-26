"""Offline contract tests: no credentials or external APIs are touched."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("openai_guide_experiment", Path(__file__).resolve().parents[1] / "scripts/openai_guide_experiment.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    (tmp_path / "prompt.txt").write_text('Return JSON for exactly one H2. {"section_id":"intro"}\n')
    (tmp_path / "facts.txt").write_text("Full country facts\nEOR and contractor evidence\n")
    m = {"schema_version": 1, "experiment_id": "offline", "revision": "v1", "run_dir": "runs/offline",
         "system_files": [], "max_workers": 2, "max_cost_usd": 15, "max_call_cost_usd": 2,
         "variants": [{"id": "terra", "model": "gpt-6.1-terra", "reasoning": "medium", "input_files": ["facts.txt"],
                       "stages": [{"id": "write", "prompt_file": "prompt.txt", "max_tokens": 100, "output_format": "json", "section_id": "intro"}]}]}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(m))
    return runner.Experiment(path)


def response(**changes):
    r = {"id": "resp_offline", "model": "gpt-6.1-terra", "reasoning": {"effort": "medium"}, "status": "completed",
         "usage": {"input_tokens": 100, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 10},
                   "output_tokens_details": {"reasoning_tokens": 5}},
         "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"body":"one H2"}'}]}]}
    r.update(changes)
    return r


def run(e, reply=None, **kw):
    return e.run_stage(e.variants[0], e.stages(e.variants[0])[0], "dummy", transport=lambda *_: (200, reply or response()), **kw)


def reload(e):
    return runner.Experiment(e.manifest_path)


def save_manifest(e):
    e.manifest_path.write_text(json.dumps(e.manifest))
    return reload(e)


def test_default_dry_run_no_key_no_writes(experiment, monkeypatch, capsys):
    e = experiment
    monkeypatch.setattr(runner, "countries_key", lambda *_: pytest.fail("Must not read key"))
    monkeypatch.setattr(runner, "post_json", lambda *_: pytest.fail("Must not POST"))
    before = set(runner.ROOT.rglob("*"))
    assert runner.main(["--manifest", str(e.manifest_path)]) == 0
    assert set(runner.ROOT.rglob("*")) == before
    assert json.loads(capsys.readouterr().out)["paid_requests_sent"] == 0
    assert not e.run_dir.exists()


def test_request_contract_and_full_inputs(experiment):
    e = experiment
    req = e.build_request(e.variants[0], e.stages(e.variants[0])[0])
    assert req["model"] == "gpt-6.1-terra"
    assert req["reasoning"] == {"effort": "medium"}
    assert req["store"] is False and req["service_tier"] == "default"
    assert req["text"]["format"]["type"] == "json_object"
    assert "tools" not in req and "previous_response_id" not in req
    assert (runner.ROOT / "facts.txt").read_text() in req["input"]


def test_success_resume_and_tampered_artifact(experiment):
    e = experiment
    assert run(e)["status"] == "success"
    assert run(e)["status"] == "resumed"
    p = e.output_path(e.variants[0], e.stages(e.variants[0])[0])
    p.write_text('{"changed":true}')
    with pytest.raises(runner.ExperimentError, match="differs"):
        run(e)


def test_changed_inputs_do_not_resume(experiment):
    e = experiment
    assert run(e)["status"] == "success"
    (runner.ROOT / "facts.txt").write_text("Changed facts")
    with pytest.raises(runner.ExperimentError, match="differs"):
        run(e)


@pytest.mark.parametrize("change", [{"model": "gpt-6.1-sol"}, {"reasoning": None}, {"reasoning": {"effort": "high"}},
                                  {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}},
                                  {"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "no"}]}]},
                                  {"output": [{"type": "function_call", "name": "bad"}]},
                                  {"output": [{"type": "message", "content": [{"type": "output_text", "text": '{"broken"'}]}]}])
def test_invalid_response_never_success(experiment, change):
    assert run(experiment, response(**change))["status"] == "failed"
    assert not experiment.output_path(experiment.variants[0], experiment.stages(experiment.variants[0])[0]).exists()
    assert list(experiment.run_dir.rglob("response.json"))


def test_http_failure_with_usage_retained_and_explicit_retry(experiment):
    e = experiment
    s = e.stages(e.variants[0])[0]
    result = e.run_stage(e.variants[0], s, "dummy", transport=lambda *_: (500, response(error={"message": "server"})))
    assert result["status"] == "failed"
    assert e.usage_summary()["retained_cost_bound_usd"] > 0
    with pytest.raises(runner.ExperimentError, match="retry-failed"):
        run(e)
    assert run(e, retry_failed=True)["status"] == "success"
    assert len(e.attempts()) == 2


def test_unknown_transport_no_replay_even_explicit_retry(experiment):
    e = experiment
    calls = []
    def interrupted(*_):
        calls.append(1)
        raise TimeoutError("POST may have completed sk-offlineFAKE")
    assert e.run_stage(e.variants[0], e.stages(e.variants[0])[0], "dummy", transport=interrupted)["status"] == "uncertain"
    with pytest.raises(runner.ExperimentError, match="Unreconciled"):
        run(e, retry_failed=True)
    assert len(calls) == 1
    assert "sk-offlineFAKE" not in "".join(p.read_text() for p in e.run_dir.rglob("*.json"))
    assert e.usage_summary()["input_tokens"] is None


def test_missing_usage_blocks(experiment):
    assert run(experiment, response(usage=None))["status"] == "failed"
    with pytest.raises(runner.ExperimentError, match="Unreconciled"):
        run(experiment, retry_failed=True)


def test_call_and_run_caps_prevent_transport(experiment):
    e = experiment
    e.max_call_cost = .00001
    with pytest.raises(runner.ExperimentError, match="cap"):
        run(e)
    assert not e.run_dir.exists()
    e.max_call_cost = 2
    e.max_cost = .00001
    with pytest.raises(runner.ExperimentError, match="cap"):
        run(e)


@pytest.mark.parametrize("field,value", [("max_cost_usd", 16), ("max_call_cost_usd", 16), ("max_workers", 3), ("max_cost_usd", float("nan"))])
def test_hard_limits(experiment, field, value):
    experiment.manifest[field] = value
    with pytest.raises(runner.ExperimentError):
        save_manifest(experiment)


@pytest.mark.parametrize("path", ["../outside.txt", "/tmp/outside.txt", "config/facts.txt", ".env", "credentials.json"])
def test_protected_input_paths(experiment, path):
    e = experiment
    if not path.startswith(("/", "..")):
        p = runner.ROOT / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("public data")
    e.manifest["variants"][0]["input_files"] = [path]
    with pytest.raises(runner.ExperimentError):
        save_manifest(e)


def test_symlink_escape_and_secret_content(experiment, tmp_path):
    e = experiment
    p = runner.ROOT / "linked.txt"
    p.symlink_to("/etc/hosts")
    e.manifest["variants"][0]["input_files"] = ["linked.txt"]
    with pytest.raises(runner.ExperimentError, match="escapes"):
        save_manifest(e)
    (runner.ROOT / "facts.txt").write_text("sk-FAKEcredential")
    e.manifest["variants"][0]["input_files"] = ["facts.txt"]
    with pytest.raises(runner.ExperimentError, match="Credential-shaped"):
        save_manifest(e)


def test_prior_stage_exact_json_and_independent_request(experiment):
    e = experiment
    assert run(e)["status"] == "success"
    stage2 = {"id": "edit", "prompt_file": "prompt.txt", "max_tokens": 100, "output_format": "json", "input_stages": ["write"]}
    e.manifest["variants"][0]["stages"].append(stage2)
    e = save_manifest(e)
    req = e.build_request(e.variants[0], stage2)
    prior = e.output_path(e.variants[0], e.stages(e.variants[0])[0]).read_text()
    assert req["input"].endswith(prior)
    assert "previous_response_id" not in req
    assert e.build_request(e.variants[0], e.stages(e.variants[0])[0])["input"].count("PRIOR STAGE") == 0


@pytest.mark.parametrize("change", [{"section_ids": ["one", "two"]}, {"section_id": ["one", "two"]}])
def test_writer_multiple_sections_blocked(experiment, change):
    experiment.manifest["variants"][0]["stages"][0].update(change)
    with pytest.raises(runner.ExperimentError, match="section"):
        save_manifest(experiment)


def test_prompt_multiple_section_ids_blocked(experiment):
    (runner.ROOT / "prompt.txt").write_text('Return JSON: {"section_id":"one"}, {"section_id":"two"}')
    with pytest.raises(runner.ExperimentError, match="multiple"):
        reload(experiment)


def test_usage_estimates_are_not_invoice_or_cache_write_zero():
    v = runner.usage_estimate("gpt-6.1-terra", {"input_tokens": 100, "output_tokens": 20})
    assert v["token_charge_estimate_usd"] == pytest.approx(.00035)
    assert v["cached_tokens"] is None and v["cache_write_tokens"] is None
    assert v["estimate_is_invoice"] is False
    assert runner.usage_estimate("gpt-6.1-sol", {})["token_charge_estimate_usd"] is None


def test_key_parser_exactly_one_and_redaction(experiment, monkeypatch):
    monkeypatch.delenv("OPENAI_GUIDES_API_KEY", raising=False)
    p = runner.ROOT / "unread-fake-key.txt"
    p.write_text("label sk-testFAKE")
    assert runner.countries_key(p) == "sk-testFAKE"
    p.write_text("sk-oneFAKE sk-twoFAKE")
    with pytest.raises(runner.ExperimentError, match="exactly one"):
        runner.countries_key(p)
    assert runner.redact({"sk-fakeKEY": ["sk-fakeVALUE"]}) == {"[REDACTED]": ["[REDACTED]"]}


def test_known_usage_settles_reservation_without_cache_write_underpricing(experiment):
    e = experiment
    v, stage = e.variants[0], e.stages(e.variants[0])[0]
    reserved = e.cost_bound(e.build_request(v, stage))
    assert run(e)["status"] == "success"
    retained = e.usage_summary()["retained_cost_bound_usd"]
    assert retained < reserved
    # Cache writes missing: 90 non-read tokens conservatively priced at 2.5x.
    # Actual output includes reasoning, never added twice.
    assert retained == pytest.approx((90 * 2.5 + 10 * .05 + 20 * 5) / 1_000_000)
    assert e.usage_summary()["invoice_cost_usd"] is None
    e.max_cost = retained + reserved + .000001
    assert e.run_stage(v, {**stage, "id": "second"}, "dummy", transport=lambda *_: (200, response()))["status"] == "success"


def test_resume_verifies_immutable_request_and_response(experiment):
    e = experiment
    assert run(e)["status"] == "success"
    attempt = e.attempts()[0].parent
    (attempt / "request.json").write_text('{}')
    with pytest.raises(runner.ExperimentError, match="differs"):
        run(e)


def test_two_inflight_requests_share_budget_without_blocking_each_other(experiment):
    import concurrent.futures
    import threading
    e = experiment
    barrier = threading.Barrier(2)
    def transport(*_):
        barrier.wait(timeout=2)
        return 200, response()
    base = e.stages(e.variants[0])[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(e.run_stage, e.variants[0], {**base, "id": sid}, "dummy", transport=transport)
                   for sid in ("first", "second")]
        assert [f.result()["status"] for f in futures] == ["success", "success"]
    assert e.reserved == 0
    assert e.active_attempts == set()


def test_stable_full_input_prefix_precedes_changing_prompt(experiment):
    e = experiment
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    first = e.build_request(v, s)["input"]
    (runner.ROOT / "prompt.txt").write_text('Return JSON for next single section.')
    second = e.build_request(v, s)["input"]
    prefix = first.split("STAGE PROMPT:")[0]
    assert prefix == second.split("STAGE PROMPT:")[0]
    assert (runner.ROOT / "facts.txt").read_text() in prefix


def test_dense_prior_section_dag_is_bounded_and_revalidates_sources(experiment, monkeypatch):
    e = experiment
    base = e.stages(e.variants[0])[0]
    stages = [{**base, "id": f"section{i}", "input_stages": [f"section{j}" for j in range(i)]} for i in range(14)]
    e.manifest["variants"][0]["stages"] = stages
    e = save_manifest(e)
    v = e.variants[0]
    for stage in stages:
        assert e.run_stage(v, stage, "dummy", transport=lambda *_: (200, response()))["status"] == "success"
    calls = []
    original = e._input_path
    def counted(path):
        calls.append(path)
        return original(path)
    monkeypatch.setattr(e, "_input_path", counted)
    request = e.build_request(v, stages[-1])
    assert request["input"].count("PRIOR STAGE:") == 13
    assert len(calls) < 100  # Without local memoization this exceeds 16,000 reads.
    (runner.ROOT / "facts.txt").write_text("Modified country fact packet")
    with pytest.raises(runner.ExperimentError, match="Earlier stage"):
        e.build_request(v, stages[-1])


def test_explicit_larger_call_reservation_stays_within_run_cap(experiment):
    e = experiment
    e.manifest["max_call_cost_usd"] = 6
    e = save_manifest(e)
    assert e.max_call_cost == 6 and e.max_cost == 15
    assert run(e)["status"] == "success"
    e.manifest["max_cost_usd"] = 5
    with pytest.raises(runner.ExperimentError, match="Per-call cap exceeds run cap"):
        save_manifest(e)


def test_default_call_cap_remains_two(experiment):
    del experiment.manifest["max_call_cost_usd"]
    assert save_manifest(experiment).max_call_cost == 2


def cache_usage(inp=135457, cached=0, writes=135454, short=135454, long=0, out=706):
    return {"input_tokens": inp, "output_tokens": out,
            "input_tokens_details": {"cached_tokens": cached, "cache_write_tokens": writes,
                                     "cache_write_tokens_details": {"ttl_30m_tokens": short, "ttl_12h_tokens": long}},
            "output_tokens_details": {"reasoning_tokens": 143}}


def test_actual_cache_write_partition_nonadditive():
    c = runner.usage_estimate("gpt-6.1-terra", cache_usage())
    assert c["ordinary_input_tokens"] == 3
    assert c["cache_write_tokens"] == 135454
    assert c["token_charge_estimate_usd"] == pytest.approx((3 + 135454 * 1.25 + 706 * 5) / 1_000_000)
    assert c["cache_write_12h_tokens"] == 0
    assert c["invoice_cost_usd"] is None


def test_mixed_ttl_cache_partitions_and_long_context_rates():
    usage = cache_usage(inp=300000, cached=10000, writes=200000, short=120000, long=80000, out=1000)
    c = runner.usage_estimate("gpt-6.1-sol", usage)
    expected = (90000 * 4 + 10000 * .2 + 120000 * 1.25 * 4 + 80000 * 2.5 * 4 + 1000 * 15) / 1_000_000
    assert c["token_charge_estimate_usd"] == pytest.approx(expected)


@pytest.mark.parametrize("change", [{"cache_write_tokens": 140000}, {"cached_tokens": 100},
                                  {"cache_write_tokens": -1}, {"cache_write_tokens": True},
                                  {"cache_write_tokens_details": {"ttl_30m_tokens": 1, "ttl_12h_tokens": 1}}])
def test_invalid_cache_partitions_require_reconciliation(change):
    usage = cache_usage()
    usage["input_tokens_details"].update(change)
    assert runner.usage_estimate("gpt-6.1-terra", usage)["token_charge_estimate_usd"] is None


def test_missing_ttl_preserves_null_and_uses_conservative_write_price():
    usage = cache_usage()
    del usage["input_tokens_details"]["cache_write_tokens_details"]
    c = runner.usage_estimate("gpt-6.1-terra", usage)
    assert c["cache_write_30m_tokens"] is None and c["cache_write_12h_tokens"] is None
    assert c["token_charge_estimate_usd"] == pytest.approx((3 + 135454 * 2.5 + 706 * 5) / 1_000_000)
    assert "Conservative" in c["estimate_basis"]


def test_summary_recalculates_historical_receipts_without_mutation(experiment):
    e = experiment
    assert run(e, response(usage=cache_usage()))["status"] == "success"
    receipt_path = e.attempts()[0].with_name("receipt.json")
    receipt = runner.read_json(receipt_path)
    receipt["charges"]["token_charge_estimate_usd"] = .138987  # old estimate excluded write premium
    receipt["charges"]["cache_write_tokens"] = None
    receipt_path.write_text(json.dumps(receipt))
    before = {p: p.read_bytes() for p in e.run_dir.rglob("*") if p.is_file()}
    summary = e.usage_summary()
    expected = (3 + 135454 * 1.25 + 706 * 5) / 1_000_000
    assert summary["token_charge_estimate_usd"] == pytest.approx(expected)
    assert summary["token_charge_estimate_usd"] > summary["historical_receipt_estimate_usd"]
    assert summary["cache_write_tokens"] == 135454
    assert summary["accounting_revision"] == "cache-partition-v2"
    assert "immutable" in summary["accounting_basis"]
    assert before == {p: p.read_bytes() for p in e.run_dir.rglob("*") if p.is_file()}


def configure_options(e, *, cache=False, delta=False, stages=1):
    v = e.manifest["variants"][0]
    v["cache_full_packet"] = cache
    v["writer_state_delta"] = delta
    base = v["stages"][0]
    v["stages"] = [{**base, "id": f"s{i}", "section_id": f"h2-{i}", "input_stages": [f"s{j}" for j in range(i)]}
                   for i in range(stages)]
    return save_manifest(e)


def delta_response(section, entries):
    r = response()
    r["output"][0]["content"][0]["text"] = json.dumps({"section_md": f"## Section {section}\nFull prose {section}.", "state_delta": entries})
    return r


def entry(key, text=None, category="facts"):
    return {"key": key, "category": category, "text": text or f"Unabridged fact {key}"}


def run_at(e, index, reply):
    v = e.variants[0]
    return e.run_stage(v, e.stages(v)[index], "dummy", transport=lambda *_: (200, reply))


def test_cache_option_absent_and_false_preserve_exact_legacy_request(experiment):
    e = experiment
    v, s = e.variants[0], e.stages(e.variants[0])[0]
    expected = {"model": "gpt-6.1-terra", "instructions": "Follow the supplied sources and return JSON.",
                "input": "\n\nINPUT FILE: facts.txt\n" + (runner.ROOT / "facts.txt").read_text()
                         + "\n\nSTAGE PROMPT:\n" + (runner.ROOT / "prompt.txt").read_text(),
                "max_output_tokens": 100, "reasoning": {"effort": "medium"}, "store": False,
                "service_tier": "default", "text": {"format": {"type": "json_object"}}}
    req = e.build_request(v, s)
    assert runner.encoded(req) == runner.encoded(expected)
    old_fp = e.fingerprint(req)
    v.update(cache_full_packet=False, writer_state_delta=False)
    assert e.fingerprint(e.build_request(v, s)) == old_fp
    assert "prompt_cache_options" not in req


def test_explicit_cache_prefix_identity_full_raw_packet_dynamic_suffix(experiment):
    e = experiment
    (runner.ROOT / "policy.txt").write_bytes("Policy α\r\nFull system rules.  \r\n".encode())
    (runner.ROOT / "facts.txt").write_bytes("All country EOR contractor facts.\r\nEvidence β.  \r\n".encode())
    (runner.ROOT / "stage-input.txt").write_text("Dynamic section data")
    (runner.ROOT / "stage-policy.txt").write_text("Dynamic stage rules")
    e.manifest["system_files"] = ["policy.txt"]
    e = configure_options(e, cache=True, stages=2)
    v = e.variants[0]
    s0, s1 = e.stages(v)
    s0.update(input_files=["stage-input.txt"], system_files=["stage-policy.txt"])
    req0 = e.build_request(v, s0)
    assert req0["prompt_cache_options"] == {"mode": "explicit", "ttl": "30m"}
    assert "instructions" not in req0
    assert req0["input"][1]["content"][0]["prompt_cache_breakpoint"] == {"mode": "explicit"}
    assert (runner.ROOT / "policy.txt").read_bytes().decode() in req0["input"][0]["content"][0]["text"]
    assert (runner.ROOT / "facts.txt").read_bytes().decode() in req0["input"][1]["content"][0]["text"]
    assert "Dynamic" not in json.dumps(req0["input"][:2])
    assert "Dynamic stage rules" in req0["input"][2]["content"][0]["text"]
    assert run_at(e, 0, response())["status"] == "success"
    req1 = e.build_request(v, s1)
    assert runner.encoded(req0["input"][:2]) == runner.encoded(req1["input"][:2])
    assert req0["input"][2:] != req1["input"][2:]
    assert e.cost_bound(req1) > 0
    assert runner.encoded(req1)[-1:] == b"}"


def test_cache_budget_counts_large_structured_packet_before_transport(experiment):
    e = configure_options(experiment, cache=True)
    (runner.ROOT / "facts.txt").write_text("x" * 100000)
    e.max_call_cost = .01
    with pytest.raises(runner.ExperimentError, match="cap"):
        run_at(e, 0, response())
    assert not e.run_dir.exists()


def test_delta_three_turns_keep_all_prose_and_full_merged_state_once(experiment):
    e = configure_options(experiment, cache=True, delta=True, stages=3)
    first = entry("h2-0/facts/one", "First detailed state fact.\nWith its original qualification.")
    second = entry("h2-1/coverage/two", "Second fact retained verbatim.", "coverage")
    assert run_at(e, 0, delta_response(0, [first]))["status"] == "success"
    assert run_at(e, 1, delta_response(1, [first, second]))["status"] == "success"
    v = e.variants[0]
    req = e.build_request(v, e.stages(v)[2])
    dynamic = req["input"][-1]["content"][0]["text"]
    assert "## Section 0\nFull prose 0." in dynamic
    assert "## Section 1\nFull prose 1." in dynamic
    assert "state_delta" not in dynamic
    assert dynamic.count("MERGED WRITER STATE:") == 1
    assert dynamic.count("First detailed state fact.") == 1
    assert json.loads(dynamic.split("MERGED WRITER STATE:\n")[1]) == [first, second]
    assert run_at(e, 2, delta_response(2, [entry("h2-2/decisions/three", category="decisions")]))["status"] == "success"
    state = runner.read_json(e.state_path(v, e.stages(v)[2]))
    assert len(state["entries"]) == 3
    assert state["entries"][:2] == [first, second]
    assert [p["stage"] for p in state["lineage"]] == ["s0", "s1"]
    r = runner.read_json(e.output_path(v, e.stages(v)[2]).with_suffix(".receipt.json"))
    assert r["state_sha256"] == runner.sha(e.state_path(v, e.stages(v)[2]).read_bytes())
    assert r["state_lineage"] == state["lineage"]
    assert r["started_at"] and r["finished_at"] and r["elapsed_seconds"] >= 0
    assert run_at(e, 2, response())["status"] == "resumed"


def test_delta_identical_dedup_conflicting_text_or_category_rejects():
    a = entry("h2-1/facts/one")
    assert runner.Experiment.merge_entries([a], [a, a]) == [a]
    for b in ({**a, "text": "Changed"}, {**a, "category": "coverage"}):
        with pytest.raises(runner.ExperimentError, match="Conflicting"):
            runner.Experiment.merge_entries([a], [b])


@pytest.mark.parametrize("delta", [None, {}, ["fact"], [{"key": "a", "category": "facts"}],
                                   [entry("bad key")], [entry("good", " ")],
                                   [{**entry("a"), "replace": True}],
                                   [entry("a"), entry("a", "Conflict")]])
def test_malformed_delta_retains_response_and_charges_blocks_downstream(experiment, delta):
    e = configure_options(experiment, delta=True, stages=2)
    result = run_at(e, 0, delta_response(0, delta))
    assert result["status"] == "failed"
    assert result["token_charge_estimate_usd"] > 0
    assert list(e.run_dir.rglob("response.json"))
    assert not e.state_path(e.variants[0], e.stages(e.variants[0])[0]).exists()
    with pytest.raises(runner.ExperimentError, match="Earlier stage"):
        e.build_request(e.variants[0], e.stages(e.variants[0])[1])


def test_delta_cross_turn_conflict_fails_without_publishing_state(experiment):
    e = configure_options(experiment, delta=True, stages=2)
    assert run_at(e, 0, delta_response(0, [entry("shared")]))["status"] == "success"
    r = run_at(e, 1, delta_response(1, [entry("shared", "Different fact")]))
    assert r["status"] == "failed" and "Conflicting" in r["error"]
    assert not e.state_path(e.variants[0], e.stages(e.variants[0])[1]).exists()


def test_delta_state_tamper_invalidates_resume_and_future_request(experiment):
    e = configure_options(experiment, delta=True, stages=2)
    assert run_at(e, 0, delta_response(0, [entry("fact")]))["status"] == "success"
    v = e.variants[0]
    e.state_path(v, e.stages(v)[0]).write_text('{"entries":[]}')
    with pytest.raises(runner.ExperimentError, match="differs"):
        run_at(e, 0, response())
    with pytest.raises(runner.ExperimentError, match="Earlier stage"):
        e.build_request(v, e.stages(v)[1])


def test_delta_missing_past_or_future_dependency_rejected(experiment):
    e = configure_options(experiment, delta=True, stages=3)
    e.manifest["variants"][0]["stages"][2]["input_stages"] = ["s1"]
    with pytest.raises(runner.ExperimentError, match="all earlier"):
        save_manifest(e)
    e.manifest["variants"][0]["stages"][0]["input_stages"] = ["s2"]
    with pytest.raises(runner.ExperimentError, match="earlier"):
        save_manifest(e)


def test_delta_opening_empty_title_no_h2_is_preserved(experiment):
    e = configure_options(experiment, delta=True, stages=2)
    v = e.variants[0]
    e.stages(v)[0]["heading_title"] = ""
    e.stages(v)[1]["heading_title"] = "Section 1"
    opening = {"section_md": "Finland opening paragraph, with all qualifications.\n\nAnother opening paragraph.",
               "state_delta": [entry("opening/facts/one")]}
    r = response()
    r["output"][0]["content"][0]["text"] = json.dumps(opening)
    assert run_at(e, 0, r)["status"] == "success"
    assert runner.read_json(e.output_path(v, e.stages(v)[0]))["section_md"] == opening["section_md"]
    assert "##" not in opening["section_md"]
    req = e.build_request(v, e.stages(v)[1])
    assert opening["section_md"] in req["input"]
    assert run_at(e, 1, delta_response(1, []))["status"] == "success"
    assert run_at(e, 0, response())["status"] == "resumed"


@pytest.mark.parametrize("title,prose", [("", "## Unexpected H2\nBody"),
                                         ("Expected", "## Wrong title\nBody"),
                                         ("Expected", "No heading body"),
                                         ("Expected", "# Disallowed H1\n## Expected\nBody"),
                                         ("Expected", "## Expected\nBody\n## Second H2\nBody")])
def test_delta_heading_contract_rejects_wrong_count_title_or_h1(experiment, title, prose):
    e = configure_options(experiment, delta=True)
    e.stages(e.variants[0])[0]["heading_title"] = title
    r = response()
    r["output"][0]["content"][0]["text"] = json.dumps({"section_md": prose, "state_delta": []})
    assert run_at(e, 0, r)["status"] == "failed"
