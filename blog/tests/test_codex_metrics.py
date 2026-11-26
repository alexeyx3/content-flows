import importlib.util
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_metrics", ROOT / "scripts" / "codex_metrics.py")
METRICS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(METRICS)


def test_finish_parser_accepts_explicit_recovery_cutoff():
    args = METRICS.parser().parse_args([
        "finish", "--job", "jobs/example", "--finished-at", "2026-09-18T10:26:08Z"
    ])
    assert args.finished_at == "2026-09-18T10:26:08Z"


def test_recovery_can_close_stale_stage_and_phase_as_interrupted():
    stage = METRICS.parser().parse_args([
        "stage-stop", "--job", "jobs/example", "--id", "stage-1",
        "--status", "interrupted",
    ])
    phase = METRICS.parser().parse_args([
        "phase-stop", "--job", "jobs/example", "--id", "phase-1",
        "--status", "interrupted",
    ])
    assert stage.status == "interrupted"
    assert phase.status == "interrupted"


def write_rollout(root: Path, thread_id: str, records: list[dict]) -> None:
    path = root / "2026" / "09" / "15" / f"rollout-test-{thread_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in records) + "\n", encoding="utf-8")


def test_aggregate_uses_unique_provider_records_and_does_not_double_count_subsets(tmp_path):
    usage_a = {
        "input_tokens": 100,
        "cached_input_tokens": 80,
        "cache_write_input_tokens": 0,
        "output_tokens": 20,
        "reasoning_output_tokens": 7,
        "total_tokens": 120,
    }
    usage_b = {
        "input_tokens": 50,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 10,
        "reasoning_output_tokens": 3,
        "total_tokens": 60,
    }
    expected = {key: usage_a[key] + usage_b[key] for key in METRICS.TOKEN_KEYS}
    write_rollout(tmp_path, "thread-1", [
        {"type": "turn_context", "payload": {"model": "gpt-test", "effort": "high"}},
        {"type": "token_usage_record", "payload": {
            "response_id": "a", "usage": usage_a, "thread_token_usage": usage_a,
        }},
        {"type": "token_usage_record", "payload": {
            "response_id": "b", "usage": usage_b, "thread_token_usage": expected,
        }},
    ])

    result = METRICS.aggregate_thread("thread-1", sessions_root=tmp_path)

    assert result["usage"] == expected
    assert result["usage"]["total_tokens"] == 180
    assert result["integrity"]["status"] == "ok"


def test_root_measurement_is_limited_to_one_user_turn(tmp_path):
    def usage(value: int) -> dict:
        return {
            "input_tokens": value,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": 1,
            "reasoning_output_tokens": 0,
            "total_tokens": value + 1,
        }

    write_rollout(tmp_path, "root-thread", [
        {"type": "turn_context", "payload": {
            "root_turn_id": "old", "model": "gpt-test", "effort": "medium",
        }},
        {"type": "token_usage_record", "payload": {
            "root_turn_id": "old", "response_id": "old-response", "usage": usage(999),
            "turn_token_usage": usage(999),
        }},
        {"type": "turn_context", "payload": {
            "root_turn_id": "article", "model": "gpt-test", "effort": "high",
        }},
        {"type": "token_usage_record", "payload": {
            "root_turn_id": "article", "response_id": "article-response", "usage": usage(25),
            "turn_token_usage": usage(25),
        }},
    ])

    result = METRICS.aggregate_thread(
        "root-thread", root_turn_id="article", sessions_root=tmp_path
    )

    assert result["usage"]["total_tokens"] == 26
    assert result["reasoning_effort"] == "high"


def test_root_measurement_stops_at_article_finish_time(tmp_path):
    def usage(value: int) -> dict:
        return {
            "input_tokens": value,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": 1,
            "reasoning_output_tokens": 0,
            "total_tokens": value + 1,
        }

    first = usage(20)
    cumulative = {key: first[key] * 2 for key in METRICS.TOKEN_KEYS}
    write_rollout(tmp_path, "root-cutoff", [
        {"timestamp": "2026-09-15T10:00:00Z", "type": "turn_context", "payload": {
            "root_turn_id": "article", "model": "gpt-test", "effort": "high",
        }},
        {"timestamp": "2026-09-15T10:01:00Z", "type": "token_usage_record", "payload": {
            "root_turn_id": "article", "response_id": "in-article", "usage": first,
            "turn_token_usage": first,
        }},
        {"timestamp": "2026-09-15T10:03:00Z", "type": "token_usage_record", "payload": {
            "root_turn_id": "article", "response_id": "after-article", "usage": first,
            "turn_token_usage": cumulative,
        }},
    ])

    result = METRICS.aggregate_thread(
        "root-cutoff",
        root_turn_id="article",
        ended_at="2026-09-15T10:02:00Z",
        sessions_root=tmp_path,
    )

    assert result["usage"] == first
    assert result["integrity"]["status"] == "ok"


def test_integrity_fails_when_provider_cumulative_total_does_not_match(tmp_path):
    usage = {
        "input_tokens": 10,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 2,
        "reasoning_output_tokens": 1,
        "total_tokens": 12,
    }
    wrong = dict(usage, total_tokens=13)
    write_rollout(tmp_path, "thread-2", [
        {"type": "turn_context", "payload": {"model": "gpt-test", "effort": "medium"}},
        {"type": "token_usage_record", "payload": {
            "response_id": "a", "usage": usage, "thread_token_usage": wrong,
        }},
    ])

    result = METRICS.aggregate_thread("thread-2", sessions_root=tmp_path)

    assert result["integrity"]["status"] == "incomplete"


def test_malformed_non_usage_record_is_ignored_but_reported(tmp_path):
    usage = {
        "input_tokens": 10,
        "cached_input_tokens": 5,
        "cache_write_input_tokens": 0,
        "output_tokens": 2,
        "reasoning_output_tokens": 1,
        "total_tokens": 12,
    }
    path = tmp_path / "2026" / "09" / "15" / "rollout-test-thread-3.jsonl"
    path.parent.mkdir(parents=True)
    rows = [
        {"type": "turn_context", "payload": {"model": "gpt-test", "effort": "medium"}},
        {"type": "token_usage_record", "payload": {
            "response_id": "a", "usage": usage, "thread_token_usage": usage,
        }},
    ]
    path.write_text(
        json.dumps(rows[0]) + "\n"
        + '{"type":"response_item","payload":{"broken":"unterminated}}\n'
        + 'continuation of the broken tool output\n'
        + json.dumps(rows[1]) + "\n",
        encoding="utf-8",
    )

    result = METRICS.aggregate_thread("thread-3", sessions_root=tmp_path)

    assert result["integrity"]["status"] == "ok"
    assert result["integrity"]["ignored_malformed_irrelevant_records"] == 2


@pytest.mark.parametrize("window_start", ["2026-09-15T10:01:30Z", "2026-09-15T10:02:30Z"])
def test_same_thread_stage_window_uses_provider_cumulative_delta(tmp_path, window_start):
    def usage(input_tokens: int, output_tokens: int) -> dict:
        return {
            "input_tokens": input_tokens,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": output_tokens,
            "reasoning_output_tokens": 0,
            "total_tokens": input_tokens + output_tokens,
        }

    first = usage(10, 2)
    second = usage(20, 3)
    cumulative = {
        key: first[key] + second[key] for key in METRICS.TOKEN_KEYS
    }
    write_rollout(tmp_path, "continued-agent", [
        {"timestamp": "2026-09-15T10:00:00Z", "type": "turn_context", "payload": {
            "root_turn_id": "first", "model": "gpt-5.6-sol", "effort": "medium",
        }},
        {"timestamp": "2026-09-15T10:01:00Z", "type": "token_usage_record", "payload": {
            "root_turn_id": "first", "response_id": "first-response", "usage": first,
            "thread_token_usage": first, "turn_token_usage": first,
        }},
        {"timestamp": "2026-09-15T10:02:00Z", "type": "turn_context", "payload": {
            "root_turn_id": "recheck", "model": "gpt-5.6-sol", "effort": "medium",
        }},
        {"timestamp": "2026-09-15T10:03:00Z", "type": "token_usage_record", "payload": {
            "root_turn_id": "recheck", "response_id": "recheck-response", "usage": second,
            "thread_token_usage": cumulative, "turn_token_usage": second,
        }},
    ])

    result = METRICS.aggregate_thread(
        "continued-agent",
        started_at=window_start,
        ended_at="2026-09-15T10:03:30Z",
        sessions_root=tmp_path,
    )

    assert result["usage"] == second
    assert result["integrity"]["status"] == "ok"
    assert result["integrity"]["compared_with"] == "thread_token_usage_delta"


def test_stage_model_mismatch_fails_closed(tmp_path):
    usage = {
        "input_tokens": 10,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 2,
        "reasoning_output_tokens": 0,
        "total_tokens": 12,
    }
    write_rollout(tmp_path, "wrong-model", [
        {"timestamp": "2026-09-15T10:00:00Z", "type": "turn_context", "payload": {
            "model": "gpt-5.6-luna", "effort": "medium",
        }},
        {"timestamp": "2026-09-15T10:01:00Z", "type": "token_usage_record", "payload": {
            "response_id": "response", "usage": usage, "thread_token_usage": usage,
        }},
    ])
    row = {
        "stage": "qa-1",
        "agent": "blog-qa-factcheck",
        "attempt": 1,
        "kind": "agent",
        "thread_id": "wrong-model",
        "root_turn_id": None,
        "expected_model": "gpt-5.6-sol",
        "expected_reasoning_effort": "medium",
        "started_at": "2026-09-15T09:59:00Z",
        "ended_at": "2026-09-15T10:02:00Z",
        "status": "complete",
        "note": "",
    }

    measured = METRICS.measured_row(row, tmp_path)

    assert measured["integrity"]["status"] == "incomplete"
    assert "model mismatch" in measured["integrity"]["routing_errors"][0]


def test_weekly_after_does_not_move_finished_at(tmp_path, monkeypatch):
    job = tmp_path / "job"
    metrics = job / "metrics"
    metrics.mkdir(parents=True)
    finished_at = "2026-09-15T10:00:00Z"
    (metrics / "manifest.json").write_text(json.dumps({
        "finished_at": finished_at,
        "subscription_limit": {
            "weekly_remaining_before_percent": 97.0,
            "weekly_remaining_after_percent": None,
        },
    }), encoding="utf-8")
    monkeypatch.setattr(METRICS, "command_report", lambda _args: None)

    METRICS.command_weekly_after(Namespace(job=str(job), remaining=93.0))

    manifest = json.loads((metrics / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["finished_at"] == finished_at
    assert manifest["subscription_limit"]["weekly_remaining_after_percent"] == 93.0


def test_post_production_phase_is_included_without_counting_user_wait_time(tmp_path):
    def usage(input_tokens: int, output_tokens: int) -> dict:
        return {
            "input_tokens": input_tokens,
            "cached_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "output_tokens": output_tokens,
            "reasoning_output_tokens": 0,
            "total_tokens": input_tokens + output_tokens,
        }

    production = usage(20, 2)
    review = usage(7, 3)
    write_rollout(tmp_path, "production-thread", [
        {"timestamp": "2026-09-15T10:00:00Z", "type": "turn_context", "payload": {
            "root_turn_id": "production", "model": "gpt-5.6-luna", "effort": "medium",
        }},
        {"timestamp": "2026-09-15T10:05:00Z", "type": "token_usage_record", "payload": {
            "root_turn_id": "production", "response_id": "p", "usage": production,
            "turn_token_usage": production, "thread_token_usage": production,
        }},
    ])
    write_rollout(tmp_path, "review-thread", [
        {"timestamp": "2026-09-16T12:00:00Z", "type": "turn_context", "payload": {
            "root_turn_id": "review", "model": "gpt-test", "effort": "medium",
        }},
        {"timestamp": "2026-09-16T12:04:00Z", "type": "token_usage_record", "payload": {
            "root_turn_id": "review", "response_id": "r", "usage": review,
            "turn_token_usage": review, "thread_token_usage": review,
        }},
    ])

    manifest = {
        "run_id": "run",
        "job": "jobs/test",
        "started_at": "2026-09-15T10:00:00Z",
        "finished_at": "2026-09-15T10:10:00Z",
        "codex_version": "test",
        "subscription_limit": {},
        "root": {
            "thread_id": "production-thread", "root_turn_id": "production",
        },
        "stages": [],
        "phases": [{
            "id": "phase-1", "name": "google-docs-review",
            "started_at": "2026-09-16T12:00:00Z", "ended_at": "2026-09-16T12:05:00Z",
            "status": "complete",
            "root": {"thread_id": "review-thread", "root_turn_id": "review"},
            "subscription_limit": {}, "stages": [],
        }],
    }

    report = METRICS.build_report(tmp_path, manifest, tmp_path)

    assert report["status"] == "complete"
    assert report["production_total_usage"] == production
    assert report["article_total_usage"]["total_tokens"] == 32
    assert report["wall_seconds"] == 600
    assert report["active_lifecycle_seconds"] == 900
    assert report["phases"][0]["name"] == "google-docs-review"


@pytest.mark.parametrize("operation", ["start", "bind-stop"])
def test_concurrent_processes_preserve_all_manifest_updates(tmp_path, operation):
    job = tmp_path / "job"
    stages = [] if operation == "start" else [
        {"id": str(i), "stage": f"stage-{i}", "thread_id": None, "status": "running"}
        for i in range(20)]
    METRICS.save_manifest(job, {"stages": stages, "phases": [], "sentinel": "keep"})
    # Delay reads to reproduce the previously observed read/modify/write race.
    code = '''
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location("metrics", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
original = m.load_manifest
def slow_load(job):
    data = original(job); time.sleep(0.02); return data
m.load_manifest = slow_load
job, i, operation = sys.argv[2:]
if operation == "start":
    m.main_args = m.parser().parse_args(["stage-start", "--job", job, "--stage", "same-stage", "--kind", "script"])
    m.main_args.func(m.main_args)
else:
    args = m.parser().parse_args(["stage-bind", "--job", job, "--id", i, "--thread-id", "thread-" + i])
    args.func(args)
    args = m.parser().parse_args(["stage-stop", "--job", job, "--id", i])
    args.func(args)
'''
    processes = [subprocess.Popen([sys.executable, "-c", code, str(ROOT / "scripts/codex_metrics.py"),
                                   str(job), str(i), operation], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for i in range(20)]
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            assert process.returncode == 0, stdout + stderr
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
    manifest = METRICS.load_manifest(job)
    assert manifest["sentinel"] == "keep"
    assert len(manifest["stages"]) == 20
    if operation == "start":
        assert sorted(row["attempt"] for row in manifest["stages"]) == list(range(1, 21))
        assert len({row["id"] for row in manifest["stages"]}) == 20
    else:
        assert all(row["thread_id"] == "thread-" + row["id"] and row["status"] == "complete"
                   for row in manifest["stages"])


def test_writer_stage_timing_separates_execution_and_handoff_delays(tmp_path):
    write_rollout(tmp_path, "writer", [
        {"timestamp": "2026-09-15T10:00:20Z", "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "first", "duration_ms": 10000}},
        {"timestamp": "2026-09-15T10:00:20Z", "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "first", "duration_ms": 10000}},
        {"timestamp": "2026-09-15T10:01:40Z", "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "second", "duration_ms": 20000}},
    ])
    timing = METRICS.stage_timing({"thread_id": "writer", "started_at": "2026-09-15T10:00:00Z",
                                   "ended_at": "2026-09-15T10:02:00Z"}, tmp_path)
    assert timing["completed_turns"] == 2
    assert timing["execution_seconds"] == 30
    assert timing["dispatch_wait_seconds"] == 10
    assert timing["between_turns_seconds"] == 60
    assert timing["closing_delay_seconds"] == 20
    assert timing["non_execution_seconds"] == 90


@pytest.mark.parametrize("partial", [False, True])
def test_missing_or_partial_task_events_do_not_invent_zero_execution(tmp_path, partial):
    rows = [{"timestamp": "2026-09-15T10:01:30Z", "type": "token_usage_record", "payload": {}}]
    if partial:
        rows.insert(0, {"timestamp": "2026-09-15T10:00:30Z", "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "first", "duration_ms": 10000}})
    write_rollout(tmp_path, "partial", rows)
    timing = METRICS.stage_timing({"thread_id": "partial", "started_at": "2026-09-15T10:00:00Z",
                                   "ended_at": "2026-09-15T10:02:00Z"}, tmp_path)
    assert timing["execution_seconds"] is None
    assert timing["non_execution_seconds"] is None


def test_active_stage_does_not_label_unfinished_turn_as_closing_delay(tmp_path):
    timing = METRICS.stage_timing({"thread_id": "not-scanned", "status": "running",
                                  "started_at": "2026-09-15T10:00:00Z"}, tmp_path)
    assert timing["closing_delay_seconds"] is None


def test_missing_middle_turn_completion_does_not_count_work_as_handoff(tmp_path):
    write_rollout(tmp_path, "middle", [
        {"timestamp": "2026-09-15T10:00:20Z", "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "first", "duration_ms": 10000}},
        {"timestamp": "2026-09-15T10:00:40Z", "type": "token_usage_record", "payload": {}},
        {"timestamp": "2026-09-15T10:01:40Z", "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "last", "duration_ms": 20000}},
    ])
    timing = METRICS.stage_timing({"thread_id": "middle", "started_at": "2026-09-15T10:00:00Z",
        "ended_at": "2026-09-15T10:02:00Z"}, tmp_path)
    assert timing["execution_seconds"] is None
    assert timing["between_turns_seconds"] is None


def test_stage_overlapping_partial_turn_has_unknown_execution(tmp_path):
    write_rollout(tmp_path, "overlap", [
        {"timestamp": "2026-09-15T10:00:10Z", "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "overlap", "duration_ms": 20000}},
        {"timestamp": "2026-09-15T10:00:40Z", "type": "event_msg", "payload": {
            "type": "task_complete", "turn_id": "complete", "duration_ms": 10000}},
    ])
    timing = METRICS.stage_timing({"thread_id": "overlap", "started_at": "2026-09-15T10:00:00Z",
                                   "ended_at": "2026-09-15T10:02:00Z"}, tmp_path)
    assert timing["execution_seconds"] is None


def test_missing_serp_stage_makes_report_incomplete(tmp_path, monkeypatch):
    (tmp_path / "job.yaml").write_text("workflow_version: 2\nresearch_v3_version: 1\n")
    monkeypatch.setattr(METRICS, "aggregate_thread", lambda thread_id, **kwargs: {
        "thread_id": thread_id, "root_turn_id": kwargs.get("root_turn_id"),
        "model": "test", "reasoning_effort": "medium", "requests": 1,
        "usage": METRICS.empty_usage(), "integrity": {"status": "ok"}})
    required = METRICS.planned_stages(tmp_path, "full")
    manifest = {"run_id": "test", "job": str(tmp_path), "root": {
        "thread_id": "root", "root_turn_id": "turn"}, "subscription_limit": {},
        "started_at": "2026-09-15T10:00:00Z", "finished_at": "2026-09-15T10:02:00Z",
        "required_stages": required, "stages": [{
            "stage": name, "kind": "script", "started_at": "2026-09-15T10:00:00Z",
            "ended_at": "2026-09-15T10:01:00Z", "status": "complete"}
            for name in required if name != "serp"]}
    report = METRICS.build_report(tmp_path, manifest, tmp_path)
    assert report["status"] == "incomplete"
    assert report["stage_coverage"]["missing"] == ["serp"]
    assert "missing: serp" in METRICS.render_markdown(report)
    manifest["stages"].append(dict(manifest["stages"][0], stage="serp"))
    assert METRICS.build_report(tmp_path, manifest, tmp_path)["status"] == "complete"


def test_preflight_and_production_have_separate_expected_plans(tmp_path):
    (tmp_path / "job.yaml").write_text(
        "workflow_version: 2\nresearch_v3_version: 1\nprimary_data_research_version: 1\nvisual_qa_version: 1\n")
    preflight = METRICS.planned_stages(tmp_path, "preflight")
    production = METRICS.planned_stages(tmp_path, "production")
    assert {"serp", "research-map", "document-research", "study-research", "quote-research"} <= set(preflight)
    assert "writer" not in preflight
    assert {"writer", "visual-render", "visual-layout", "visual-qa", "gdoc-review-push"} <= set(production)
    assert "serp" not in production
    assert METRICS.stage_coverage(tmp_path, {"scope": "preflight"}, [{"stage": s} for s in preflight])["missing"] == []


def test_refresh_scope_registers_only_refresh_work(tmp_path):
    (tmp_path / "job.yaml").write_text("workflow_version: 2\narticle_refresh_version: 1\n")
    preflight = METRICS.planned_stages(tmp_path, "preflight")
    production = METRICS.planned_stages(tmp_path, "production")
    assert preflight == ["refresh-baseline", "strategy-brief"]
    assert production == ["evidence", "writer", "assemble", "editor", "editor-delta",
                          "article-qa", "pre-qa-package", "gdoc-review-push", "refresh-temnik-sync"]
    assert METRICS.planned_stages(tmp_path, "full") == preflight + production


def test_hybrid_critic_and_unregistered_stages_continue_without_double_counting(tmp_path, monkeypatch):
    (tmp_path / "job.yaml").write_text("workflow_version: 2\nproduction_text_backend: openrouter_hybrid\n")
    plan = METRICS.planned_stages(tmp_path, "production")
    assert plan.index("assemble") < plan.index("openrouter-critic") < plan.index("editor")
    monkeypatch.setenv("CODEX_THREAD_ID", "root-thread")
    monkeypatch.setattr(METRICS, "read_rollout", lambda *_: [])
    def turn(turn_id):
        monkeypatch.setattr(METRICS, "last_turn_context", lambda _: {
            "timestamp": "2026-09-22T10:00:00Z", "payload": {"root_turn_id": turn_id},
        })
    turn("same-turn")
    initial = {"root": {"thread_id": "root-thread", "root_turn_id": "same-turn"},
               "finished_at": "2026-09-21T11:00:00Z", "required_stages": ["openrouter-critic", "gdoc-review-push"],
               "stages": [{"stage": "openrouter-critic", "status": "complete"}], "phases": []}
    METRICS.save_manifest(tmp_path, initial)
    args = Namespace(job=str(tmp_path), sessions_root=str(tmp_path), name="publication", started_at=None,
                     weekly_remaining=None, scope="manual", continue_phase="initial")
    with pytest.raises(SystemExit, match="parent turn already has metrics"):
        METRICS.command_phase_start(args)
    assert METRICS.load_manifest(tmp_path) == initial
    turn("next-turn")
    METRICS.command_phase_start(args)
    manifest = METRICS.load_manifest(tmp_path)
    assert manifest["required_stages"] == ["openrouter-critic"]
    assert manifest["phases"][0]["required_stages"] == ["gdoc-review-push"]
    assert manifest["phases"][0]["continued_from"] == "initial"


def test_documented_empty_visual_plan_waives_only_visual_agent_and_upload(tmp_path):
    (tmp_path / "visuals.json").write_text(json.dumps({"visuals": [], "omission_reason": "No useful visual"}))
    owner = {"required_stages": ["visual-render", "visual-layout", "visual-qa", "review-visual-upload", "writer"]}
    coverage = METRICS.stage_coverage(tmp_path, owner, [{"stage": "visual-render"}, {"stage": "visual-layout"}])
    assert coverage["missing"] == ["writer"]


def test_finished_production_requires_phase_for_new_stage():
    with pytest.raises(SystemExit, match="lifecycle phase"):
        METRICS.stage_collection({"finished_at": "2026-09-15T10:00:00Z", "stages": []}, None)
