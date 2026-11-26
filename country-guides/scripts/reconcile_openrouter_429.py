"""Reconcile rejected guide requests against the dedicated OpenRouter key ledger.

The starting point must be a previously reconciled cumulative /key observation.
Run while writers using the key are stopped. This performs a GET, never a POST.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from openrouter_experiment import countries_key

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://openrouter.ai/api/v1/key"
MIN_AGE = timedelta(minutes=2)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("Invalid OpenRouter cost")
    return amount


def is_upstream_rejection(attempt, receipt):
    """Only the pinned OpenAI upstream 429 with a complete rejection envelope."""
    if (receipt.get("status") != "failed" or receipt.get("http_status") != 429
            or receipt.get("complete") is not False or receipt.get("generation_id")
            or receipt.get("usage") != {} or (attempt / "partial.json").exists()):
        return False
    for name, field in (("request", "request_sha256"), ("intent", "intent_sha256"),
                        ("response", "response_sha256")):
        artifact = attempt / (name + ".json")
        if not artifact.is_file() or digest(artifact) != receipt.get(field):
            return False
    response = read(attempt / "response.json")
    request = read(attempt / "request.json")
    provider = request.get("provider") or {}
    error = response.get("error") or {}
    return (not any(response.get(k) for k in ("id", "output", "choices", "usage"))
            and request.get("model") == "openai/gpt-6.1-terra"
            and provider.get("only") == ["openai"] and provider.get("allow_fallbacks") is False
            and request.get("reasoning") == {"effort": "medium"}
            and error.get("code") == 429
            and (error.get("metadata") or {}).get("provider_name") == "OpenAI"
            and "temporarily rate-limited upstream" in error.get("message", ""))


def settled_rejections(run_dir):
    """Return receipt digests covered by immutable, equal-total observations."""
    for path in (run_dir / "reconciliations").glob("*.json"):
        try:
            audit = read(path)
            if (path.stem == digest(path) and audit["schema_version"] == 1
                    and audit["source"] == SOURCE
                    and money(audit["current_usage_usd"]) - money(audit["baseline_usage_usd"])
                    == money(audit["reported_usage_usd"])):
                yield from audit["rejected_receipts"]
        except (OSError, ValueError, KeyError, TypeError, InvalidOperation):
            continue


def reconcile(baseline_path):
    baseline = read(baseline_path)
    if (baseline.get("exact_match") is not True
            or baseline.get("source") != "OpenRouter GET /api/v1/key, countries key aggregates"):
        raise ValueError("Baseline must be a previously exact dedicated-key observation")
    cutoff = datetime.fromisoformat(baseline["utc"])
    before = money(baseline["usage"])
    intents = sorted((ROOT / "runs/guide-api").glob("*/*/execution/variants/*/attempts/*/intent.json"))
    known = Decimal(0)
    rejected = {}
    now = datetime.now(timezone.utc)
    for intent in intents:
        if datetime.fromisoformat(read(intent)["started_at"]) < cutoff:
            continue
        run_dir = intent.parents[4]
        profile = read(run_dir.parent / "profile.json")
        if profile.get("explicit_transport", profile["default_backend"]) != "openrouter":
            continue
        receipt_path = intent.with_name("receipt.json")
        if not receipt_path.is_file():
            raise ValueError("OpenRouter POST still has an unresolved intent")
        receipt = read(receipt_path)
        if now - datetime.fromisoformat(receipt["finished_at"]) < MIN_AGE:
            raise ValueError("Wait at least two minutes after the latest OpenRouter response")
        cost = (receipt.get("usage") or {}).get("cost")
        if cost is not None:
            known += money(cost)
        elif is_upstream_rejection(intent.parent, receipt):
            rejected.setdefault(run_dir, []).append(digest(receipt_path))
        else:
            raise ValueError("An unknown response is not an eligible upstream rejection")
    request = Request(SOURCE, headers={"Authorization": "Bearer " + countries_key()})
    with urlopen(request, timeout=15) as response:
        key = json.loads(response.read(), parse_float=Decimal)["data"]
    if intents != sorted((ROOT / "runs/guide-api").glob("*/*/execution/variants/*/attempts/*/intent.json")):
        raise ValueError("Attempts changed during reconciliation")
    current = money(key["usage"])
    if money(key["limit"]) != money(baseline["limit"]) or current - before != known:
        raise ValueError("Dedicated-key usage does not match the recorded charges")
    for run, receipts in rejected.items():
        audit = {"schema_version": 1, "source": SOURCE, "observed_at_utc": now.isoformat(),
                 "baseline_at_utc": cutoff.isoformat(), "baseline_usage_usd": str(before),
                 "current_usage_usd": str(current), "reported_usage_usd": str(known),
                 "rejected_receipts": receipts}
        data = (json.dumps(audit, indent=2) + "\n").encode()
        path = run / "reconciliations" / (hashlib.sha256(data).hexdigest() + ".json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(data)
    return known, sum(map(len, rejected.values()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    args = parser.parse_args()
    try:
        recorded, count = reconcile(args.baseline)
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation) as exc:
        parser.exit(2, f"Reconciliation blocked: {exc}\n")
    print(f"Dedicated-key delta matches USD {recorded}. Reconciled upstream rejections: {count}.")
