"""Verify actual provider turn contexts against a country-guide role's route."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect_rollout(path: Path, expected: dict, since: str | None = None) -> dict:
    contexts = []
    for line in path.open(encoding="utf-8"):
        if '"turn_context"' not in line:
            continue
        row = json.loads(line)
        if row.get("type") != "turn_context":
            continue
        if since and datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")) < datetime.fromisoformat(since.replace("Z", "+00:00")):
            continue
        payload = row["payload"]
        contexts.append({"timestamp": row["timestamp"], "turn_id": payload.get("turn_id"),
                         "model": payload.get("model"), "reasoning_effort": payload.get("effort")})
    mismatches = [row for row in contexts if any(row[k] != expected[k]
                  for k in ("model", "reasoning_effort"))]
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "rollout": str(path),
            "expected": expected, "contexts": contexts, "mismatches": mismatches,
            "status": "FAIL" if mismatches else "PASS" if contexts else "PENDING"}


def find_rollout(sessions: Path, thread_id: str | None, agent_path: str | None) -> Path:
    if thread_id:
        files = list(sessions.rglob(f"*{thread_id}.jsonl"))
    else:
        files = []
        for path in sessions.rglob("*.jsonl"):
            with path.open(encoding="utf-8") as handle:
                try:
                    row = json.loads(next(handle))
                except (StopIteration, ValueError):
                    continue
            source = row.get("payload", {}).get("source", {})
            spawn = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) else {}
            if spawn.get("agent_path") == agent_path:
                files.append(path)
    if len(files) != 1:
        raise ValueError(f"Expected one rollout, found {len(files)}; use exact thread ID when agent names repeat")
    return files[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True)
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument("--thread-id")
    identity.add_argument("--agent-path")
    parser.add_argument("--since", help="ISO UTC boundary, useful for the switched parent chat")
    parser.add_argument("--sessions-root", type=Path, default=Path.home() / ".codex/sessions")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    routing = json.loads((ROOT / "config/codex-model-routing.json").read_text())
    expected = routing["orchestrator"] if args.role == "orchestrator" else routing["agents"][args.role]
    try:
        rollout = find_rollout(args.sessions_root, args.thread_id, args.agent_path)
        receipt = inspect_rollout(rollout, expected, args.since)
    except (OSError, ValueError) as exc:
        receipt = {"status": "PENDING", "expected": expected, "error": str(exc)}
    receipt.update(role=args.role, agent_path=args.agent_path, thread_id=args.thread_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "role": args.role, "expected": expected,
                      "contexts": len(receipt.get("contexts", [])), "receipt": str(args.output)}))
    raise SystemExit(0 if receipt["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
