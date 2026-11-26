"""Measure a Codex article run from provider-recorded local session usage.

This intentionally keeps subscription-limit observations separate from tokens.
Token values are never accepted from the command line: they are read from the
Codex rollout JSONL that owns the registered thread id.
"""
from __future__ import annotations

import argparse
import fcntl
import functools
import json
import os
import re
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSIONS = Path.home() / ".codex" / "sessions"
MODEL_ROUTING = ROOT / "config" / "codex-model-routing.json"
TOKEN_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def job_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def manifest_path(job: Path) -> Path:
    return job / "metrics" / "manifest.json"


def load_manifest(job: Path) -> dict[str, Any]:
    path = manifest_path(job)
    if not path.exists():
        raise SystemExit(f"metrics manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(job: Path, manifest: dict[str, Any]) -> None:
    path = manifest_path(job)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def atomic_write(path: Path, text: str) -> None:
    """Readers see either the previous complete document or the new one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def manifest_lock(job: Path, name: str = ".manifest.lock"):
    """Lock the whole read/modify/write transaction, independently for each job."""
    directory = job / "metrics"
    directory.mkdir(parents=True, exist_ok=True)
    # Keep the lock inode: unlinking it would let concurrent writers lock different files.
    with (directory / name).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def locked_mutation(command=None, *, report_after: bool = False):
    if command is None:
        return lambda command: locked_mutation(command, report_after=report_after)
    @functools.wraps(command)
    def wrapped(args):
        with manifest_lock(job_path(args.job)):
            result = command(args)
        # Rollout scanning/report generation must not hold the write lock.
        if report_after:
            command_report(args)
        return result
    return wrapped


def planned_stages(job: Path, scope: str) -> list[str]:
    """Record the expected workflow before stage registration can lose an entry."""
    config = job / "job.yaml"
    if scope == "manual" or not config.exists():
        return []
    text = config.read_text(encoding="utf-8")
    enabled = lambda key: bool(re.search(rf"^{key}:\s*[12]\b", text, re.M))
    if not enabled("workflow_version"):
        return []
    if enabled("article_translation_version"):
        preflight = ["translation-source"]
        production = ["translator", "translation-editor", "translation-check",
                      "translation-qa", "translation-source-drift", "translation-package",
                      "translation-seal", "gdoc-review-push"]
        if enabled("translation_units_version"):
            production.insert(1, "translation-assemble")
        return preflight if scope == "preflight" else production if scope == "production" else preflight + production
    if enabled("article_refresh_version"):
        preflight = ["refresh-baseline", "strategy-brief"]
        production = ["evidence", "writer", "assemble", "editor", "editor-delta",
                      "article-qa", "pre-qa-package", "gdoc-review-push", "refresh-temnik-sync"]
        if enabled("semantic_refresh_version"):
            preflight += ["semantic-collect", "semantic-before", "semantic-plan-check"]
            production += ["semantic-after"]
        return preflight if scope == "preflight" else production if scope == "production" else preflight + production
    preflight = ["serp", "reddit", "topic-research", "strategy-brief"]
    if enabled("primary_data_research_version"):
        preflight.append("document-research")
    if enabled("research_v3_version"):
        preflight += ["research-map", "study-research", "quote-research"]
    production = ["evidence", "writer", "assemble", "editor", "editor-delta",
                  "article-qa", "gdoc-review-push"]
    if re.search(r"^production_text_backend:\s*openrouter_hybrid\b", text, re.M):
        production.insert(production.index("editor"), "openrouter-critic")
    if re.search(r"^workflow_version:\s*2\b", text, re.M):
        production += ["visual-plan", "expert-quotes", "visual-render", "pre-qa-package",
                       "review-visual-upload"]
        if enabled("visual_qa_version"):
            production += ["visual-layout", "visual-qa"]
    return preflight if scope == "preflight" else production if scope == "production" else preflight + production


def stage_coverage(job: Path, owner: dict, stages: list[dict]) -> dict:
    required = owner.get("required_stages")
    source = "registered_at_start"
    if required is None:
        required = planned_stages(job, owner.get("scope", "full"))
        source = "inferred_from_job"
    required = list(required)
    try:
        visuals = json.loads((job / "visuals.json").read_text(encoding="utf-8"))
        if visuals.get("visuals") == [] and str(visuals.get("omission_reason", "")).strip():
            required = [s for s in required if s not in {"visual-qa", "review-visual-upload"}]
    except (OSError, ValueError, AttributeError):
        pass  # Missing or invalid plans cannot waive an expected stage.
    registered = {row["stage"] for row in stages}
    missing = sorted(set(required) - registered)
    return {"status": "incomplete" if missing else "ok", "required": required,
            "missing": missing, "source": source}


def find_rollout(thread_id: str, sessions_root: Path = DEFAULT_SESSIONS) -> Path:
    matches = list(sessions_root.rglob(f"*{thread_id}.jsonl"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one rollout for {thread_id}, found {len(matches)}")
    return matches[0]


def read_rollout(thread_id: str, sessions_root: Path = DEFAULT_SESSIONS) -> list[dict[str, Any]]:
    path = find_rollout(thread_id, sessions_root)
    rows = []
    skipping_irrelevant_continuation = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
            skipping_irrelevant_continuation = False
        except json.JSONDecodeError as exc:
            # Rollouts can contain malformed tool-output records (for example, a
            # fetched page with an unescaped control character). Those records
            # are not usage. Ignore them only when the top-level type proves
            # that they are irrelevant; a damaged usage/context record remains
            # a hard failure so token totals are never guessed.
            match = re.search(r'"type"\s*:\s*"([^"]+)"', line[:512])
            record_type = match.group(1) if match else None
            is_top_level = line.lstrip().startswith('{"timestamp"')
            if record_type in {"token_usage_record", "turn_context"}:
                raise RuntimeError(f"invalid JSON in {path}:{number}: {exc}") from exc
            if record_type is None and (is_top_level or not skipping_irrelevant_continuation):
                raise RuntimeError(f"invalid JSON in {path}:{number}: {exc}") from exc
            rows.append({
                "type": "_malformed_irrelevant",
                "payload": {"line": number, "original_type": record_type},
            })
            skipping_irrelevant_continuation = True
    return rows


def last_turn_context(rows: list[dict[str, Any]]) -> dict[str, Any]:
    contexts = [row for row in rows if row.get("type") == "turn_context"]
    if not contexts:
        raise RuntimeError("rollout has no turn_context")
    return contexts[-1]


def empty_usage() -> dict[str, int]:
    return {key: 0 for key in TOKEN_KEYS}


def add_usage(total: dict[str, int], usage: dict[str, Any]) -> None:
    for key in TOKEN_KEYS:
        total[key] += int(usage.get(key) or 0)


def subtract_usage(later: dict[str, Any], earlier: dict[str, Any]) -> dict[str, int]:
    delta = {
        key: int(later.get(key) or 0) - int(earlier.get(key) or 0)
        for key in TOKEN_KEYS
    }
    if any(value < 0 for value in delta.values()):
        raise RuntimeError("provider cumulative usage decreased inside a measured window")
    return delta


def load_model_routing(path: Path = MODEL_ROUTING) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"model routing not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("agents"), dict):
        raise RuntimeError(f"invalid model routing: {path}")
    return data


def row_time(row: dict[str, Any]) -> datetime | None:
    value = row.get("timestamp")
    return parse_time(value) if value else None


def within_window(
    row: dict[str, Any],
    *,
    started_at: str | None,
    ended_at: str | None,
) -> bool:
    if started_at is None and ended_at is None:
        return True
    stamp = row_time(row)
    if stamp is None:
        raise RuntimeError("timestamp missing from a record used for window attribution")
    if started_at is not None and stamp < parse_time(started_at):
        return False
    if ended_at is not None and stamp > parse_time(ended_at):
        return False
    return True


def aggregate_thread(
    thread_id: str,
    *,
    root_turn_id: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    sessions_root: Path = DEFAULT_SESSIONS,
) -> dict[str, Any]:
    rows = read_rollout(thread_id, sessions_root)
    all_contexts = [row for row in rows if row.get("type") == "turn_context"]
    contexts = list(all_contexts)
    if root_turn_id is not None:
        contexts = [
            row for row in contexts
            if row.get("payload", {}).get("root_turn_id") == root_turn_id
        ]
    elif started_at is not None or ended_at is not None:
        contexts = [
            row for row in contexts
            if within_window(row, started_at=started_at, ended_at=ended_at)
        ]
        # A window may begin during an existing turn. Its model/effort remain
        # active until the next context; only usage records inside the window
        # are counted below. Do not require a new turn just to measure a slice.
        if started_at is not None:
            preceding_contexts = [row for row in all_contexts
                                  if row_time(row) is not None
                                  and row_time(row) < parse_time(started_at)]
            if preceding_contexts:
                contexts.insert(0, preceding_contexts[-1])
    if not contexts:
        raise RuntimeError(f"no matching turn_context in {thread_id}")

    all_records = [row for row in rows if row.get("type") == "token_usage_record"]
    records = list(all_records)
    if root_turn_id is not None:
        records = [
            row for row in records
            if row.get("payload", {}).get("root_turn_id") == root_turn_id
        ]
        if ended_at is not None:
            cutoff = parse_time(ended_at)
            records = [
                row for row in records
                if row.get("timestamp") and parse_time(row["timestamp"]) <= cutoff
            ]
    elif started_at is not None or ended_at is not None:
        records = [
            row for row in records
            if within_window(row, started_at=started_at, ended_at=ended_at)
        ]
    if not records:
        raise RuntimeError(f"no matching token_usage_record in {thread_id}")

    unique: dict[str, dict[str, Any]] = {}
    for row in records:
        payload = row.get("payload", {})
        response_id = payload.get("response_id")
        if not response_id:
            raise RuntimeError(f"token record without response_id in {thread_id}")
        if response_id in unique and unique[response_id].get("usage") != payload.get("usage"):
            raise RuntimeError(f"conflicting duplicate response_id {response_id}")
        unique[response_id] = payload

    measured = empty_usage()
    for payload in unique.values():
        add_usage(measured, payload.get("usage") or {})

    last_payload = records[-1].get("payload", {})
    if root_turn_id is not None:
        expected_key = "turn_token_usage"
        expected = {
            key: int((last_payload.get(expected_key) or {}).get(key) or 0)
            for key in TOKEN_KEYS
        }
    elif started_at is not None or ended_at is not None:
        expected_key = "thread_token_usage_delta"
        baseline_payload: dict[str, Any] = {}
        first_stamp = row_time(records[0])
        if first_stamp is None:
            raise RuntimeError("timestamp missing from first window usage record")
        preceding = [
            row for row in all_records
            if row_time(row) is not None and row_time(row) < first_stamp
        ]
        if preceding:
            baseline_payload = preceding[-1].get("payload", {}).get("thread_token_usage") or {}
        latest = last_payload.get("thread_token_usage") or {}
        if not latest:
            raise RuntimeError("thread_token_usage missing from measured window")
        expected = subtract_usage(latest, baseline_payload)
    else:
        expected_key = "thread_token_usage"
        expected = {
            key: int((last_payload.get(expected_key) or {}).get(key) or 0)
            for key in TOKEN_KEYS
        }
    consistent = measured == expected
    ignored_malformed = sum(row.get("type") == "_malformed_irrelevant" for row in rows)

    models = sorted({str(row.get("payload", {}).get("model")) for row in contexts})
    efforts = sorted({str(row.get("payload", {}).get("effort")) for row in contexts})
    if len(models) != 1 or len(efforts) != 1:
        raise RuntimeError(f"model or effort changed inside measured thread {thread_id}")

    return {
        "thread_id": thread_id,
        "root_turn_id": root_turn_id,
        "model": models[0],
        "reasoning_effort": efforts[0],
        "requests": len(unique),
        "usage": measured,
        "integrity": {
            "status": "ok" if consistent else "incomplete",
            "compared_with": expected_key,
            "expected": expected,
            "window_started_at": started_at,
            "window_ended_at": ended_at,
            "ignored_malformed_irrelevant_records": ignored_malformed,
        },
    }


@locked_mutation
def command_start(args: argparse.Namespace) -> None:
    job = job_path(args.job)
    if manifest_path(job).exists():
        raise SystemExit(f"metrics already started: {manifest_path(job)}")
    thread_id = os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID")
    if not thread_id:
        raise SystemExit("CODEX_THREAD_ID/CODEX_SESSION_ID is not set")
    rollout = read_rollout(thread_id, Path(args.sessions_root))
    context = last_turn_context(rollout)
    payload = context.get("payload", {})
    started_at = args.started_at or context.get("timestamp")
    manifest = {
        "schema_version": 2,
        "scope": getattr(args, "scope", "full"),
        "required_stages": planned_stages(job, getattr(args, "scope", "full")),
        "run_id": str(uuid.uuid4()),
        "job": str(job.relative_to(ROOT) if job.is_relative_to(ROOT) else job),
        "started_at": started_at,
        "finished_at": None,
        "codex_version": os.environ.get("CODEX_VERSION"),
        "root": {
            "agent": "parent-orchestrator",
            "thread_id": thread_id,
            "root_turn_id": payload.get("root_turn_id") or payload.get("turn_id"),
        },
        "subscription_limit": {
            "weekly_remaining_before_percent": args.weekly_remaining,
            "weekly_remaining_after_percent": None,
            "source": "user_observed",
            "precision": "coarse_not_attributable",
        },
        "stages": [],
        "phases": [],
    }
    save_manifest(job, manifest)
    print(f"metrics started: {manifest['run_id']} ({started_at})")


def find_phase(manifest: dict[str, Any], phase_id: str) -> dict[str, Any]:
    for phase in manifest.get("phases", []):
        if phase["id"] == phase_id:
            return phase
    raise SystemExit(f"unknown phase id: {phase_id}")


def stage_collection(manifest: dict[str, Any], phase_id: str | None) -> list[dict[str, Any]]:
    if phase_id is None:
        if manifest.get("finished_at") is not None:
            raise SystemExit("production run is finished; start a lifecycle phase for new work")
        return manifest["stages"]
    phase = find_phase(manifest, phase_id)
    if phase.get("ended_at") is not None:
        raise SystemExit(f"phase is already stopped: {phase_id}")
    return phase["stages"]


@locked_mutation
def command_phase_start(args: argparse.Namespace) -> None:
    """Start one active post-production turn without counting user waiting time."""
    job = job_path(args.job)
    manifest = load_manifest(job)
    thread_id = os.environ.get("CODEX_THREAD_ID") or os.environ.get("CODEX_SESSION_ID")
    if not thread_id:
        raise SystemExit("CODEX_THREAD_ID/CODEX_SESSION_ID is not set")
    rollout = read_rollout(thread_id, Path(args.sessions_root))
    context = last_turn_context(rollout)
    payload = context.get("payload", {})
    turn_id = payload.get("root_turn_id") or payload.get("turn_id")
    for owner in [manifest, *manifest.get("phases", [])]:
        root = owner.get("root", {})
        if turn_id and (root.get("thread_id"), root.get("root_turn_id")) == (thread_id, turn_id):
            existing = owner.get("id", "initial run")
            raise SystemExit(f"this parent turn already has metrics in {existing}; use its stages")
    scope = getattr(args, "scope", "manual")
    required = planned_stages(job, scope)
    continuation = getattr(args, "continue_phase", None)
    if continuation:
        previous = manifest if continuation == "initial" else find_phase(manifest, continuation)
        if not (previous.get("ended_at") or previous.get("finished_at")):
            raise SystemExit("stop the previous metrics scope before continuing it")
        if scope != "manual":
            raise SystemExit("continuing a phase transfers coverage; omit --scope")
        registered = {row["stage"] for row in previous["stages"]}
        old_required = previous.get("required_stages")
        if old_required is None:
            old_required = planned_stages(job, previous.get("scope", "full"))
        # Transfer only still-unregistered work. Completed and failed attempts stay on the original turn.
        required = [stage for stage in old_required if stage not in registered]
        previous["required_stages"] = [stage for stage in old_required if stage in registered]
    phase = {
        "id": str(uuid.uuid4()),
        "scope": scope,
        "required_stages": required,
        "name": args.name,
        "started_at": args.started_at or context.get("timestamp") or now(),
        "ended_at": None,
        "status": "running",
        "root": {
            "agent": "parent-orchestrator",
            "thread_id": thread_id,
            "root_turn_id": turn_id,
        },
        "subscription_limit": {
            "weekly_remaining_before_percent": args.weekly_remaining,
            "weekly_remaining_after_percent": None,
            "source": "user_observed",
            "precision": "coarse_not_attributable",
        },
        "stages": [],
    }
    if continuation:
        phase["continued_from"] = continuation
    manifest.setdefault("phases", []).append(phase)
    save_manifest(job, manifest)
    print(phase["id"])


@locked_mutation(report_after=True)
def command_phase_stop(args: argparse.Namespace) -> None:
    job = job_path(args.job)
    manifest = load_manifest(job)
    phase = find_phase(manifest, args.id)
    running = [row["stage"] for row in phase["stages"] if row.get("status") == "running"]
    if running:
        raise SystemExit("cannot stop phase with running stages: " + ", ".join(running))
    phase["ended_at"] = now()
    phase["status"] = args.status
    if args.weekly_remaining is not None:
        phase["subscription_limit"]["weekly_remaining_after_percent"] = args.weekly_remaining
    save_manifest(job, manifest)


@locked_mutation
def command_stage_start(args: argparse.Namespace) -> None:
    job = job_path(args.job)
    manifest = load_manifest(job)
    rows = stage_collection(manifest, args.phase_id)
    attempt = args.attempt or 1 + sum(row["stage"] == args.stage for row in rows)
    route = None
    if args.kind == "agent" and args.agent:
        route = load_model_routing()["agents"].get(args.agent)
        if route is None:
            raise SystemExit(f"agent is missing from model routing: {args.agent}")
    row = {
        "id": str(uuid.uuid4()),
        "stage": args.stage,
        "agent": args.agent,
        "attempt": attempt,
        "kind": args.kind,
        "thread_id": None,
        "root_turn_id": None,
        "expected_model": route.get("model") if route else None,
        "expected_reasoning_effort": route.get("reasoning_effort") if route else None,
        "started_at": now(),
        "ended_at": None,
        "status": "running",
        "note": args.note,
        "phase_id": args.phase_id,
    }
    rows.append(row)
    save_manifest(job, manifest)
    print(row["id"])


def find_stage(manifest: dict[str, Any], stage_id: str) -> dict[str, Any]:
    for row in manifest["stages"]:
        if row["id"] == stage_id:
            return row
    for phase in manifest.get("phases", []):
        for row in phase.get("stages", []):
            if row["id"] == stage_id:
                return row
    raise SystemExit(f"unknown stage id: {stage_id}")


@locked_mutation
def command_stage_bind(args: argparse.Namespace) -> None:
    job = job_path(args.job)
    manifest = load_manifest(job)
    row = find_stage(manifest, args.id)
    row["thread_id"] = args.thread_id
    row["root_turn_id"] = args.root_turn_id
    save_manifest(job, manifest)
    print(f"bound {row['stage']} to {args.thread_id}")


@locked_mutation
def command_stage_stop(args: argparse.Namespace) -> None:
    job = job_path(args.job)
    manifest = load_manifest(job)
    row = find_stage(manifest, args.id)
    row["ended_at"] = now()
    row["status"] = args.status
    save_manifest(job, manifest)
    print(f"stopped {row['stage']}: {args.status}")


def duration_seconds(started_at: str, ended_at: str) -> float:
    return round((parse_time(ended_at) - parse_time(started_at)).total_seconds(), 3)


def stage_timing(row: dict, sessions_root: Path) -> dict:
    """Separate observed agent execution from dispatch, handoff and closing delays."""
    result = {"source": "task_events_unavailable", "completed_turns": 0,
              "execution_seconds": None, "dispatch_wait_seconds": None,
              "between_turns_seconds": None, "closing_delay_seconds": None,
              "non_execution_seconds": None}
    if not row.get("thread_id") or not row.get("ended_at") or row.get("status") == "running":
        return result
    rows = read_rollout(row["thread_id"], sessions_root)
    start, end = parse_time(row["started_at"]), parse_time(row.get("ended_at") or now())
    allowed_turns = None
    if row.get("root_turn_id"):
        allowed_turns = {r.get("payload", {}).get("turn_id") for r in rows
                         if r.get("type") == "turn_context" and
                         r.get("payload", {}).get("root_turn_id") == row["root_turn_id"]}
    intervals = {}
    completed = set()
    partial_turn = False
    for event in rows:
        payload = event.get("payload", {})
        if event.get("type") != "event_msg" or payload.get("type") != "task_complete":
            continue
        if allowed_turns is not None and payload.get("turn_id") not in allowed_turns:
            continue
        milliseconds = payload.get("duration_ms")
        if not isinstance(milliseconds, (int, float)) or milliseconds < 0 or not event.get("timestamp"):
            continue
        finished = parse_time(event["timestamp"])
        began = finished - timedelta(milliseconds=milliseconds)
        if began < start or finished > end:
            if began < end and finished > start:
                partial_turn = True
            continue  # A partial turn is not a fully measured execution interval.
        key = payload.get("turn_id") or event["timestamp"]
        intervals[key] = (began, finished)
        completed.add(key)
    if not intervals or partial_turn:
        return result
    # A missing completion anywhere in the window must not turn observed work into
    # handoff time, including an unfinished turn between two completed turns.
    usage_records = [r for r in rows if r.get("type") == "token_usage_record" and
                     r.get("timestamp") and start <= parse_time(r["timestamp"]) <= end and
                     (not row.get("root_turn_id") or
                      r.get("payload", {}).get("root_turn_id") == row["root_turn_id"])]
    if any(not any(began <= parse_time(usage["timestamp"]) <= finished
                   for began, finished in intervals.values()) for usage in usage_records):
        return dict(result, completed_turns=len(completed))
    merged = []
    for began, finished in sorted(intervals.values()):
        if merged and began <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], finished))
        else:
            merged.append((began, finished))
    execution = sum((b - a).total_seconds() for a, b in merged)
    dispatch = (merged[0][0] - start).total_seconds()
    closing = (end - merged[-1][1]).total_seconds()
    between = sum((right[0] - left[1]).total_seconds() for left, right in zip(merged, merged[1:]))
    return {"source": "rollout_task_complete", "completed_turns": len(completed),
            "execution_seconds": round(execution, 3),
            "dispatch_wait_seconds": round(dispatch, 3),
            "between_turns_seconds": round(between, 3),
            "closing_delay_seconds": round(closing, 3),
            "non_execution_seconds": round(dispatch + between + closing, 3)}


def measured_row(row: dict[str, Any], sessions_root: Path) -> dict[str, Any]:
    result = dict(row)
    end = row.get("ended_at") or now()
    result["duration_seconds"] = duration_seconds(row["started_at"], end)
    if row["kind"] == "script":
        result.update({
            "model": None,
            "reasoning_effort": None,
            "requests": 0,
            "usage": empty_usage(),
            "integrity": {"status": "ok", "compared_with": "not_applicable"},
        })
        return result
    if not row.get("thread_id"):
        result.update({
            "model": None,
            "reasoning_effort": None,
            "requests": 0,
            "usage": empty_usage(),
            "integrity": {"status": "incomplete", "error": "agent thread not bound"},
        })
        return result
    try:
        result.update(aggregate_thread(
            row["thread_id"],
            root_turn_id=row.get("root_turn_id"),
            started_at=None if row.get("root_turn_id") else row.get("started_at"),
            ended_at=row.get("ended_at"),
            sessions_root=sessions_root,
        ))
        result["timing"] = stage_timing(row, sessions_root)
        route_errors = []
        if row.get("expected_model") and result.get("model") != row["expected_model"]:
            route_errors.append(
                f"model mismatch: expected {row['expected_model']}, got {result.get('model')}"
            )
        if (
            row.get("expected_reasoning_effort")
            and result.get("reasoning_effort") != row["expected_reasoning_effort"]
        ):
            route_errors.append(
                "reasoning effort mismatch: expected "
                f"{row['expected_reasoning_effort']}, got {result.get('reasoning_effort')}"
            )
        if route_errors:
            result["integrity"]["status"] = "incomplete"
            result["integrity"]["routing_errors"] = route_errors
    except RuntimeError as exc:
        result.update({
            "model": None,
            "reasoning_effort": None,
            "requests": 0,
            "usage": empty_usage(),
            "integrity": {"status": "incomplete", "error": str(exc)},
        })
    return result


def mark_overlapping_windows(stages: list[dict[str, Any]]) -> None:
    """Fail closed when the same agent thread is attributed twice for overlapping time."""
    for index, left in enumerate(stages):
        if left.get("kind") != "agent" or not left.get("thread_id"):
            continue
        for right in stages[index + 1:]:
            if right.get("kind") != "agent" or right.get("thread_id") != left["thread_id"]:
                continue
            left_start = parse_time(left["started_at"])
            left_end = parse_time(left.get("ended_at") or now())
            right_start = parse_time(right["started_at"])
            right_end = parse_time(right.get("ended_at") or now())
            if left_start < right_end and right_start < left_end:
                message = f"overlapping attribution windows with stage {right['stage']}"
                left["integrity"]["status"] = "incomplete"
                left["integrity"]["error"] = message
                right["integrity"]["status"] = "incomplete"
                right["integrity"]["error"] = (
                    f"overlapping attribution windows with stage {left['stage']}"
                )


def build_report(job: Path, manifest: dict[str, Any], sessions_root: Path) -> dict[str, Any]:
    root = aggregate_thread(
        manifest["root"]["thread_id"],
        root_turn_id=manifest["root"]["root_turn_id"],
        ended_at=manifest.get("finished_at"),
        sessions_root=sessions_root,
    )
    root_agent = manifest.get("root", {}).get("agent")
    if root_agent == "blog-coordinator":
        coordinator_route = load_model_routing()["agents"]["blog-coordinator"]
        if (
            root["model"] != coordinator_route["model"]
            or root["reasoning_effort"] != coordinator_route["reasoning_effort"]
        ):
            root["integrity"]["status"] = "incomplete"
            root["integrity"]["routing_errors"] = [
                "coordinator route mismatch: expected "
                f"{coordinator_route['model']}/{coordinator_route['reasoning_effort']}, got "
                f"{root['model']}/{root['reasoning_effort']}"
            ]
    stages = [measured_row(row, sessions_root) for row in manifest["stages"]]
    phases: list[dict[str, Any]] = []
    all_stages = list(stages)
    root_keys = {(root["thread_id"], root.get("root_turn_id"))}
    for phase in manifest.get("phases", []):
        ended_at = phase.get("ended_at") or now()
        phase_root = aggregate_thread(
            phase["root"]["thread_id"],
            root_turn_id=phase["root"].get("root_turn_id"),
            started_at=None if phase["root"].get("root_turn_id") else phase["started_at"],
            ended_at=ended_at,
            sessions_root=sessions_root,
        )
        key = (phase_root["thread_id"], phase_root.get("root_turn_id"))
        if key in root_keys:
            phase_root["integrity"]["status"] = "incomplete"
            phase_root["integrity"]["error"] = "root thread/turn is attributed more than once"
        root_keys.add(key)
        phase_stages = [measured_row(row, sessions_root) for row in phase.get("stages", [])]
        all_stages.extend(phase_stages)
        phase_total = empty_usage()
        add_usage(phase_total, phase_root["usage"])
        for row in phase_stages:
            add_usage(phase_total, row["usage"])
        phase_complete = (
            phase.get("status") != "running"
            and phase_root["integrity"]["status"] == "ok"
            and all(
                row["integrity"]["status"] == "ok" and row["status"] != "running"
                for row in phase_stages
            )
        )
        phases.append({
            **phase,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds(phase["started_at"], ended_at),
            "root": phase_root,
            "stages": phase_stages,
            "total_usage": phase_total,
            "stage_coverage": stage_coverage(job, {"scope": "manual", **phase}, phase_stages),
            "integrity": {"status": "ok" if phase_complete else "incomplete"},
        })
    mark_overlapping_windows(all_stages)
    for phase in phases:
        phase["integrity"]["status"] = "ok" if (
            phase.get("status") != "running"
            and phase["stage_coverage"]["status"] == "ok"
            and phase["root"]["integrity"]["status"] == "ok"
            and all(
                row["integrity"]["status"] == "ok" and row["status"] != "running"
                for row in phase["stages"]
            )
        ) else "incomplete"
    production_total = empty_usage()
    add_usage(production_total, root["usage"])
    for row in stages:
        add_usage(production_total, row["usage"])
    total = dict(production_total)
    for phase in phases:
        add_usage(total, phase["total_usage"])
    finished_at = manifest.get("finished_at") or now()
    # Feedback stages cannot hide a missing original production stage.
    coverage_stages = list(stages)
    for phase in phases:
        if phase.get("scope") == "production":
            coverage_stages.extend(phase["stages"])
    coverage = stage_coverage(job, manifest, coverage_stages)
    complete = (
        manifest.get("finished_at") is not None
        and coverage["status"] == "ok"
        and root["integrity"]["status"] == "ok"
        and all(row["integrity"]["status"] == "ok" and row["status"] != "running" for row in stages)
        and all(phase["integrity"]["status"] == "ok" for phase in phases)
    )
    return {
        "schema_version": 2,
        "run_id": manifest["run_id"],
        "job": manifest["job"],
        "started_at": manifest["started_at"],
        "finished_at": finished_at,
        "wall_seconds": duration_seconds(manifest["started_at"], finished_at),
        "active_lifecycle_seconds": (
            duration_seconds(manifest["started_at"], finished_at)
            + sum(phase["duration_seconds"] for phase in phases)
        ),
        "status": "complete" if complete else "incomplete",
        "stage_coverage": coverage,
        "codex_version": manifest.get("codex_version"),
        "subscription_limit": manifest["subscription_limit"],
        "root_agent": root_agent or "parent-orchestrator",
        "orchestrator": root,
        "stages": stages,
        "production_total_usage": production_total,
        "phases": phases,
        "article_total_usage": total,
        "token_semantics": {
            "cached_input_is_subset_of_input": True,
            "reasoning_output_is_subset_of_output": True,
            "uncached_input_formula": "input_tokens - cached_input_tokens",
            "measurement_boundary": (
                "production orchestrator turn plus bound production stages, followed by every "
                "registered review/publication phase root turn and its bound stages"
            ),
            "source": "Codex rollout token_usage_record",
        },
    }


def fmt_seconds(value: float) -> str:
    seconds = int(round(value))
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def fmt_tokens(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def render_markdown(report: dict[str, Any]) -> str:
    limit = report["subscription_limit"]
    before = limit.get("weekly_remaining_before_percent")
    after = limit.get("weekly_remaining_after_percent")
    observed = None if before is None or after is None else after - before
    lines = [
        f"# Codex metrics — {Path(report['job']).name}",
        "",
        f"Status: **{report['status'].upper()}**  ",
        f"Production wall time: **{fmt_seconds(report['wall_seconds'])}**  ",
        f"Measured active lifecycle time: **{fmt_seconds(report['active_lifecycle_seconds'])}**  ",
        f"Codex version: `{report.get('codex_version') or 'unknown'}`",
        "",
        "| Phase | Stage | Agent | Attempt | Model | Effort | Time | Requests | Input | Cached | Uncached | Output | Reasoning | Total | Integrity |",
        "|---|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    root = report["orchestrator"]
    rows = [{
        "phase": "production",
        "stage": "orchestrator",
        "agent": report.get("root_agent") or "parent-orchestrator",
        "attempt": 1,
        "duration_seconds": report["wall_seconds"],
        **root,
    }, *({**row, "phase": "production"} for row in report["stages"])]
    for phase in report.get("phases", []):
        rows.append({
            "phase": phase["name"],
            "stage": "orchestrator",
            "agent": "parent-orchestrator",
            "attempt": 1,
            "duration_seconds": phase["duration_seconds"],
            **phase["root"],
        })
        rows.extend({**row, "phase": phase["name"]} for row in phase["stages"])
    for row in rows:
        usage = row["usage"]
        lines.append(
            "| {phase} | {stage} | {agent} | {attempt} | {model} | {effort} | {time} | {requests} | {input} | {cached} | {uncached} | {output} | {reasoning} | {total} | {integrity} |".format(
                phase=row["phase"],
                stage=row["stage"],
                agent=row.get("agent") or "—",
                attempt=row.get("attempt", 1),
                model=row.get("model") or "—",
                effort=row.get("reasoning_effort") or "—",
                time=fmt_seconds(row["duration_seconds"]),
                requests=row["requests"],
                input=fmt_tokens(usage["input_tokens"]),
                cached=fmt_tokens(usage["cached_input_tokens"]),
                uncached=fmt_tokens(max(
                    usage["input_tokens"] - usage["cached_input_tokens"], 0
                )),
                output=fmt_tokens(usage["output_tokens"]),
                reasoning=fmt_tokens(usage["reasoning_output_tokens"]),
                total=fmt_tokens(usage["total_tokens"]),
                integrity=row["integrity"]["status"],
            )
        )
    lines.extend(["", "## Stage coverage", ""])
    owners = [("production", report.get("stage_coverage", {}))] + [
        (phase["name"], phase.get("stage_coverage", {})) for phase in report.get("phases", [])]
    for name, coverage in owners:
        lines.append(f"- {name}: {coverage.get('status', 'not recorded')}; "
                     f"missing: {', '.join(coverage.get('missing', [])) or 'none'}")
    lines.extend(["", "## Agent execution and handoff time", "",
                  "| Phase | Stage | Turns | Execution | Dispatch wait | Between turns | Closing delay |",
                  "|---|---|---:|---:|---:|---:|---:|---:|"])
    for row in rows:
        if row.get("kind") != "agent":
            continue
        timing = row.get("timing", {})
        values = [fmt_seconds(timing[key]) if timing.get(key) is not None else "unknown"
                  for key in ("execution_seconds", "dispatch_wait_seconds",
                              "between_turns_seconds", "closing_delay_seconds")]
        lines.append(f"| {row['phase']} | {row['stage']} | {timing.get('completed_turns', 0)} | "
                     + " | ".join(values) + " |")
    lines.extend(["", "Execution is elapsed time inside completed agent turns, including tools. "
                  "Other intervals are handoff/dispatch/closing time; they do not identify the cause "
                  "of a delay. Missing task events are unknown, never inferred as zero."])
    production = report["production_total_usage"]
    has_phases = bool(report.get("phases"))
    total = report["article_total_usage"]
    lines.extend([
        "",
        "## Production subtotal",
        "",
        f"- Input: {fmt_tokens(production['input_tokens'])}",
        f"- Cached input: {fmt_tokens(production['cached_input_tokens'])}",
        f"- Uncached input: {fmt_tokens(max(production['input_tokens'] - production['cached_input_tokens'], 0))}",
        f"- Output: {fmt_tokens(production['output_tokens'])}",
        f"- Reasoning output: {fmt_tokens(production['reasoning_output_tokens'])}",
        f"- Total: {fmt_tokens(production['total_tokens'])}",
        "",
        "## Whole lifecycle total" if has_phases else "## Measured total (production only)",
        "",
        f"- Input: {fmt_tokens(total['input_tokens'])}",
        f"- Cached input: {fmt_tokens(total['cached_input_tokens'])}",
        f"- Uncached input: {fmt_tokens(max(total['input_tokens'] - total['cached_input_tokens'], 0))}",
        f"- Cache-write input: {fmt_tokens(total['cache_write_input_tokens'])}",
        f"- Output: {fmt_tokens(total['output_tokens'])}",
        f"- Reasoning output: {fmt_tokens(total['reasoning_output_tokens'])}",
        f"- Total: {fmt_tokens(total['total_tokens'])}",
        "",
        "`cached input` is included in `input`; `uncached input = input - cached input`; "
        "`reasoning output` is included in `output`.",
        (
            "The measured article boundary includes production and every explicitly registered "
            "Google Docs, feedback-rework, and publication phase. Time waiting for user feedback "
            "between phases is excluded."
            if has_phases else
            "No post-production lifecycle phases were registered for this run; this report is a "
            "production-only measurement."
        ),
    ])
    if report.get("phases"):
        lines.extend(["", "## Lifecycle phases", ""])
        for phase in report["phases"]:
            phase_limit = phase.get("subscription_limit", {})
            phase_before = phase_limit.get("weekly_remaining_before_percent")
            phase_after = phase_limit.get("weekly_remaining_after_percent")
            phase_change = (
                None if phase_before is None or phase_after is None
                else phase_after - phase_before
            )
            observation = (
                "not recorded"
                if phase_change is None
                else f"{phase_change:+g} percentage points"
            )
            lines.append(
                f"- `{phase['name']}`: {fmt_seconds(phase['duration_seconds'])}; "
                f"weekly observation {observation}; integrity {phase['integrity']['status']}"
            )
    lines.extend([
        "",
        "## Weekly subscription limit observation",
        "",
        f"- Remaining before: {before}%" if before is not None else "- Remaining before: not recorded",
        f"- Remaining after: {after}%" if after is not None else "- Remaining after: not recorded",
        (
            f"- Observed change: {observed:+g} percentage points"
            if observed is not None else "- Observed change: not available"
        ),
        "- This is a coarse user-observed account snapshot, not exact per-article attribution.",
        "",
    ])
    return "\n".join(lines)


def command_report(args: argparse.Namespace) -> None:
    job = job_path(args.job)
    with manifest_lock(job, ".report.lock"):
        manifest = load_manifest(job)
        report = build_report(job, manifest, Path(args.sessions_root))
        metrics = job / "metrics"
        atomic_write(metrics / "report.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        atomic_write(metrics / "report.md", render_markdown(report))
    print(render_markdown(report))
    if report["status"] != "complete":
        raise SystemExit(2)


@locked_mutation(report_after=True)
def command_finish(args: argparse.Namespace) -> None:
    job = job_path(args.job)
    manifest = load_manifest(job)
    manifest["finished_at"] = args.finished_at or now()
    if args.weekly_remaining is not None:
        manifest["subscription_limit"]["weekly_remaining_after_percent"] = args.weekly_remaining
    save_manifest(job, manifest)


@locked_mutation(report_after=True)
def command_weekly_after(args: argparse.Namespace) -> None:
    """Attach the user's later UI observation without moving the run boundary."""
    job = job_path(args.job)
    manifest = load_manifest(job)
    if manifest.get("finished_at") is None:
        raise SystemExit("metrics run is not finished")
    manifest["subscription_limit"]["weekly_remaining_after_percent"] = args.remaining
    save_manifest(job, manifest)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions-root", default=str(DEFAULT_SESSIONS))
    sub = ap.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--job", required=True)
    start.add_argument("--weekly-remaining", type=float)
    start.add_argument("--started-at")
    start.add_argument("--scope", choices=("full", "preflight", "production", "manual"), default="full",
                       help="Expected article stages; preflight ends at the brief checkpoint.")
    start.set_defaults(func=command_start)

    phase_start = sub.add_parser("phase-start")
    phase_start.add_argument("--job", required=True)
    phase_start.add_argument("--name", required=True)
    phase_start.add_argument("--weekly-remaining", type=float)
    phase_start.add_argument("--started-at")
    phase_start.add_argument("--scope", choices=("production", "manual"), default="manual",
                             help="Use production for the post-approval article continuation.")
    phase_start.add_argument("--continue-phase", metavar="ID",
                             help="Move unregistered planned stages from a stopped phase or 'initial'.")
    phase_start.set_defaults(func=command_phase_start)

    phase_stop = sub.add_parser("phase-stop")
    phase_stop.add_argument("--job", required=True)
    phase_stop.add_argument("--id", required=True)
    phase_stop.add_argument(
        "--status", choices=("complete", "failed", "blocked", "interrupted"),
        default="complete",
    )
    phase_stop.add_argument("--weekly-remaining", type=float)
    phase_stop.set_defaults(func=command_phase_stop)

    stage_start = sub.add_parser("stage-start")
    stage_start.add_argument("--job", required=True)
    stage_start.add_argument("--stage", required=True)
    stage_start.add_argument("--agent")
    stage_start.add_argument("--attempt", type=int)
    stage_start.add_argument("--kind", choices=("agent", "script"), default="agent")
    stage_start.add_argument("--note", default="")
    stage_start.add_argument("--phase-id")
    stage_start.set_defaults(func=command_stage_start)

    bind = sub.add_parser("stage-bind")
    bind.add_argument("--job", required=True)
    bind.add_argument("--id", required=True)
    bind.add_argument("--thread-id", required=True)
    bind.add_argument("--root-turn-id")
    bind.set_defaults(func=command_stage_bind)

    stop = sub.add_parser("stage-stop")
    stop.add_argument("--job", required=True)
    stop.add_argument("--id", required=True)
    stop.add_argument(
        "--status", choices=("complete", "failed", "blocked", "interrupted"),
        default="complete",
    )
    stop.set_defaults(func=command_stage_stop)

    report = sub.add_parser("report")
    report.add_argument("--job", required=True)
    report.set_defaults(func=command_report)

    finish = sub.add_parser("finish")
    finish.add_argument("--job", required=True)
    finish.add_argument("--weekly-remaining", type=float)
    finish.add_argument(
        "--finished-at",
        help="Explicit ISO-8601 cutoff for recovery when a completed turn was not closed promptly.",
    )
    finish.set_defaults(func=command_finish)

    weekly_after = sub.add_parser("weekly-after")
    weekly_after.add_argument("--job", required=True)
    weekly_after.add_argument("--remaining", type=float, required=True)
    weekly_after.set_defaults(func=command_weekly_after)
    return ap


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
