#!/usr/bin/env python3
"""Run an isolated, resumable OpenRouter writing experiment (never publishes).

Only --execute makes paid requests. All input paths are repository-relative.
The selected model and exact provider are pinned; there is no model fallback.
An HTTP/transport ambiguity is retained and blocks automatic replay. Review it
before explicitly using --retry-failed. Existing attempts are never overwritten.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
KEY_RE = re.compile(r"sk-or-[A-Za-z0-9_-]+")
KEY_SOURCE = ROOT / "vendor/blog/config/.env"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


class ExperimentError(Exception):
    pass


def redact(value):
    """Defense in depth for API errors: credentials must never reach artifacts."""
    if isinstance(value, str):
        return KEY_RE.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes):
    return hashlib.sha256(value).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(redact(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: Path, value: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(redact(value), encoding="utf-8")
    os.replace(tmp, path)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def path_in_repo(value: str, *, exists=False):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ExperimentError("Expected a nonempty repository-relative path")
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ExperimentError("Path escapes repository")
    if exists and not path.is_file():
        raise ExperimentError(f"Missing input: {value}")
    return path


def countries_key(key_file=None):
    explicit = os.environ.get("OPENROUTER_GUIDES_API_KEY", "").strip()
    if explicit:
        if not KEY_RE.fullmatch(explicit):
            raise ExperimentError("Invalid countries key shape")
        return explicit
    source = Path(key_file) if key_file else KEY_SOURCE
    keys = []
    for line in source.read_text(encoding="utf-8").splitlines():
        label = KEY_RE.sub("[REDACTED]", line)
        if re.search(r"\bcountries\b|OPENROUTER_GUIDES_API_KEY", label, re.I):
            keys.extend(KEY_RE.findall(line))
    if len(keys) != 1:
        raise ExperimentError("Expected exactly one countries-labeled key; generic keys are never used")
    return keys[0]


def post_json(payload, key, timeout, *, endpoint=ENDPOINT, extra_headers=None):
    """No retries: an interrupted POST may already have incurred a charge."""
    request = urllib.request.Request(endpoint, data=encoded(payload), method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "X-Title": "Country guides local model experiment",
        **(extra_headers or {}),
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    try:
        body = json.loads(raw)
    except ValueError:
        body = {"unparsed_body": raw[:20000]}
    return status, redact(body)


class Experiment:
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path.resolve()
        self.manifest = read_json(self.manifest_path)
        m = self.manifest
        if m.get("schema_version") != 1 or not SAFE_ID.fullmatch(str(m.get("experiment_id", ""))):
            raise ExperimentError("Manifest requires schema_version=1 and safe experiment_id")
        if not isinstance(m.get("revision"), str) or not m["revision"]:
            raise ExperimentError("Manifest requires explicit revision")
        self.run_dir = path_in_repo(m["run_dir"])
        if not self.run_dir.is_relative_to((ROOT / "runs").resolve()) and not self.run_dir.is_relative_to((ROOT / "tmp").resolve()):
            raise ExperimentError("Experiment output must be isolated under runs/ or tmp/")
        self.system_files = self._files(m.get("system_files", []))
        if not isinstance(m.get("variants"), list) or not 1 <= len(m["variants"]) <= 24:
            raise ExperimentError("Manifest must contain 1 to 24 variants")
        self.variants = m["variants"]
        seen = set()
        for v in self.variants:
            if not SAFE_ID.fullmatch(str(v.get("id", ""))) or v["id"] in seen:
                raise ExperimentError("Variant IDs must be safe and unique")
            seen.add(v["id"])
            if not isinstance(v.get("model"), str) or "/" not in v["model"] or ":free" in v["model"]:
                raise ExperimentError("Every variant requires an exact paid model ID")
            if v["model"].split("/", 1)[0].lower() in {"openai", "anthropic", "google"}:
                raise ExperimentError("This experiment excludes OpenAI, Anthropic, and Google models")
            if not isinstance(v.get("provider"), str) or not v["provider"].strip():
                raise ExperimentError("Every variant requires one explicitly pinned provider")
            self._files(v.get("input_files", []))
            stages = v.get("stages", m.get("stages"))
            if not isinstance(stages, list) or not stages:
                raise ExperimentError("Every variant requires an ordered stages list")
            previous = set()
            for s in stages:
                sid = s.get("id", "")
                if not SAFE_ID.fullmatch(str(sid)) or sid in previous:
                    raise ExperimentError("Stage IDs must be safe and unique within variant")
                if any(dep not in previous for dep in s.get("input_stages", [])):
                    raise ExperimentError(f"Stage {sid} references an unknown or later input stage")
                self._files(s.get("input_files", []))
                self._files(s.get("system_files", []))
                self._input_path(s["prompt_file"])
                if type(s.get("max_tokens")) is not int or not 1 <= s["max_tokens"] <= 65536:
                    raise ExperimentError("Every stage requires explicit max_tokens between 1 and 65536")
                if s.get("output_format", "markdown") not in {"markdown", "json"}:
                    raise ExperimentError("output_format must be markdown or json")
                previous.add(sid)
        self.max_workers = int(m.get("max_workers", 4))
        if not 1 <= self.max_workers <= 8:
            raise ExperimentError("max_workers must be between 1 and 8")
        self.max_cost = float(m.get("max_cost_usd", 100))
        self.reservation = float(m.get("max_call_cost_usd", 5))
        if not 0 < self.reservation <= self.max_cost:
            raise ExperimentError("Require 0 < max_call_cost_usd <= max_cost_usd")
        self.lock = threading.Lock()
        self.reserved = 0.0

    def _input_path(self, value):
        path = path_in_repo(value, exists=True)
        key_path = Path(self.manifest.get("key_file", ROOT / "config/.env")).resolve()
        if (path == key_path or path.name == ".env" or path.name.startswith(".env.")
                or path.suffix.lower() in {".pem", ".key"} or path.name in {"credentials", "credentials.json"}):
            raise ExperimentError("Credential/configuration file cannot be a model input")
        return path

    def _files(self, paths):
        if not isinstance(paths, list):
            raise ExperimentError("input_files/system_files must be lists")
        return [self._input_path(p) for p in paths]

    def stages(self, variant):
        return variant.get("stages", self.manifest.get("stages"))

    def output_path(self, variant, stage):
        suffix = ".json" if stage.get("output_format") == "json" else ".md"
        return self.run_dir / "variants" / variant["id"] / (stage["id"] + suffix)

    def build_request(self, variant, stage):
        system_files = self.system_files + self._files(stage.get("system_files", []))
        system = "\n\n".join(f"SOURCE FILE: {p.relative_to(ROOT)}\n{p.read_text(encoding='utf-8')}" for p in system_files)
        if not system:
            system = "Produce the requested local research or article artifact. Follow the supplied sources and constraints."
        prompt_path = self._input_path(stage["prompt_file"])
        inputs = self._files(variant.get("input_files", [])) + self._files(stage.get("input_files", []))
        user = prompt_path.read_text(encoding="utf-8")
        for p in inputs:
            user += f"\n\nINPUT FILE: {p.relative_to(ROOT)}\n{p.read_text(encoding='utf-8')}"
        by_id = {s["id"]: s for s in self.stages(variant)}
        for dep in stage.get("input_stages", []):
            p = self.output_path(variant, by_id[dep])
            if not p.is_file():
                raise ExperimentError(f"Missing earlier output: {variant['id']}:{dep}")
            user += f"\n\nPRIOR STAGE: {dep}\n{p.read_text(encoding='utf-8')}"
        if KEY_RE.search(system + user):
            raise ExperimentError("Credential-shaped text found in model input; request blocked")
        request = {
            "model": variant["model"],
            "provider": {"only": [variant["provider"]], "allow_fallbacks": False, "require_parameters": True},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": stage["max_tokens"], "stream": False,
            "usage": {"include": True},
        }
        if "max_price" in variant:
            request["provider"]["max_price"] = variant["max_price"]
        if "reasoning" in variant:
            request["reasoning"] = variant["reasoning"]
        if "reasoning" in stage:
            request["reasoning"] = stage["reasoning"]
        if "temperature" in self.manifest:
            request["temperature"] = self.manifest["temperature"]
        if stage.get("output_format") == "json":
            request["response_format"] = {"type": "json_object"}
        return request

    def fingerprint(self, request):
        return sha(encoded({"revision": self.manifest["revision"], "request": request}))

    def attempts(self):
        return sorted((self.run_dir / "variants").glob("*/attempts/*/receipt.json"))

    def usage_summary(self):
        receipts = [read_json(p) for p in self.attempts()]
        costs = [r.get("cost_usd") for r in receipts]
        return {
            "attempts": len(receipts), "cost_usd": sum(c for c in costs if isinstance(c, (float, int))),
            "unknown_cost_attempts": sum(c is None and r.get("status") != "rejected" for c, r in zip(costs, receipts)),
            "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in receipts) if receipts and all(isinstance(r.get("usage", {}).get("prompt_tokens"), int) for r in receipts) else None,
            "completion_tokens": sum(r["usage"]["completion_tokens"] for r in receipts) if receipts and all(isinstance(r.get("usage", {}).get("completion_tokens"), int) for r in receipts) else None,
            "successes": sum(r.get("status") == "success" for r in receipts),
            "failed": sum(r.get("status") != "success" for r in receipts),
            "pending_intents": sum(not (p.parent / "receipt.json").is_file()
                                   for p in (self.run_dir / "variants").glob("*/attempts/*/intent.json")),
        }

    def dry_run(self):
        return {
            "experiment_id": self.manifest["experiment_id"], "revision": self.manifest["revision"],
            "variants": len(self.variants), "stages": sum(len(self.stages(v)) for v in self.variants),
            "models": sorted(set(v["model"] for v in self.variants)),
            "max_workers": self.max_workers, "max_cost_usd": self.max_cost,
            "max_call_cost_usd_reservation": self.reservation,
            "budget_note": "Reservation is an operator-selected upper bound per call, not a provider-enforced cap. Unknown cost blocks new calls.",
            "all_static_inputs_valid": True, "paid_requests_sent": 0,
        }

    def _resume(self, variant, stage, fp):
        p = self.output_path(variant, stage)
        receipt_path = p.with_suffix(".receipt.json")
        if not receipt_path.is_file() or not p.is_file():
            return False
        r = read_json(receipt_path)
        return r.get("status") == "success" and r.get("fingerprint") == fp and r.get("output_sha256") == sha(p.read_bytes())

    def _reserve(self, amount=None):
        amount = self.reservation if amount is None else amount
        with self.lock:
            summary = self.usage_summary()
            if summary["unknown_cost_attempts"]:
                raise ExperimentError("Prior charged/ambiguous request has unknown cost; reconcile before new paid calls")
            if summary["cost_usd"] + self.reserved + amount > self.max_cost:
                raise ExperimentError("Experiment cost reservation limit reached")
            self.reserved += amount

    def run_stage(self, variant, stage, key, *, retry_failed=False, transport=None):
        transport = transport or post_json
        request = self.build_request(variant, stage)
        fp = self.fingerprint(request)
        if self._resume(variant, stage, fp):
            return {"variant": variant["id"], "stage": stage["id"], "status": "resumed"}
        attempt_root = self.run_dir / "variants" / variant["id"] / "attempts"
        prior = sorted(attempt_root.glob(stage["id"] + "-*"))
        for p in prior:
            intent = read_json(p / "intent.json") if (p / "intent.json").is_file() else {}
            r = read_json(p / "receipt.json") if (p / "receipt.json").is_file() else {}
            if intent.get("fingerprint") == fp and r.get("status") != "success" and not retry_failed:
                raise ExperimentError(f"{variant['id']}:{stage['id']} has a failed/uncertain attempt; inspect it before explicit --retry-failed")
        reservation = self.reservation
        if "max_price" in variant:
            prices = variant["max_price"]
            # UTF-8 bytes conservatively bound tokenizer input, plus protocol overhead.
            input_bound = sum(len(m["content"].encode("utf-8")) for m in request["messages"]) + 4096
            charge_bound = (input_bound * float(prices["prompt"]) + request["max_tokens"] * float(prices["completion"])) / 1_000_000
            if charge_bound > self.reservation:
                raise ExperimentError("Conservative request cost exceeds per-call reservation")
            reservation = charge_bound
        self._reserve(reservation)
        attempt = attempt_root / f"{stage['id']}-{len(prior) + 1:03d}"
        attempt.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        intent = {"variant": variant["id"], "stage": stage["id"], "fingerprint": fp,
                  "requested_model": variant["model"], "requested_provider": variant["provider"],
                  "canonical_slug_from_catalog": variant.get("canonical_slug"), "requested_reasoning": request.get("reasoning"),
                  "reserved_cost_bound_usd": reservation, "started_at": now()}
        write_json(attempt / "request.json", request)
        write_json(attempt / "intent.json", intent)
        receipt = {**intent, "status": "uncertain", "complete": False, "cost_usd": None, "usage": {}}
        try:
            status_code, response = transport(request, key, float(self.manifest.get("timeout_seconds", 360)))
            write_json(attempt / "response.json", response)
            receipt.update(http_status=status_code, generation_id=response.get("id"),
                           actual_model=response.get("model"), actual_provider=response.get("provider"))
            usage = response.get("usage") or {}
            receipt["usage"] = usage
            cost = usage.get("cost")
            if isinstance(cost, (float, int)) and cost >= 0:
                receipt["cost_usd"] = float(cost)
            elif status_code in {400, 401, 402, 403, 404, 422, 429} and not response.get("choices"):
                receipt["cost_usd"] = 0.0
            if status_code != 200 or response.get("error"):
                receipt["status"] = "rejected" if receipt["cost_usd"] == 0 else "failed"
                receipt["error"] = response.get("error", f"HTTP {status_code}")
            else:
                expected_models = {variant["model"]}
                if variant.get("canonical_slug"):
                    expected_models.add(variant["canonical_slug"])
                expected_providers = variant.get("provider_names", [variant.get("provider_name", variant["provider"])])
                choices = response.get("choices", [])
                choice = choices[0] if choices else {}
                finish = choice.get("finish_reason")
                content = choice.get("message", {}).get("content")
                receipt["finish_reason"] = finish
                if response.get("model") not in expected_models:
                    receipt.update(status="failed", error="Response model differs from pinned model/canonical_slug")
                elif response.get("provider") not in expected_providers:
                    receipt.update(status="failed", error="Response provider differs from explicitly allowed provider_names")
                elif not isinstance(content, str) or not content.strip():
                    receipt.update(status="failed", error="No nonempty textual output")
                elif finish != "stop":
                    receipt.update(status="failed", error=f"Incomplete generation: finish_reason={finish}")
                    write_text(attempt / "partial.md", content)
                elif len(content.strip()) < int(stage.get("min_chars", 1)):
                    receipt.update(status="failed", error="Output below required min_chars")
                    write_text(attempt / "partial.md", content)
                else:
                    if stage.get("output_format") == "json":
                        parsed = json.loads(content)
                        content = json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"
                    p = self.output_path(variant, stage)
                    write_text(p, content)
                    receipt.update(status="success", complete=True, output_path=str(p.relative_to(ROOT)), output_sha256=sha(p.read_bytes()))
        except Exception as exc:
            # Avoid full tracebacks/request objects containing authorization.
            receipt["error"] = redact(f"{type(exc).__name__}: {exc}")
            if receipt.get("http_status") == 200:
                receipt["status"] = "failed"
        finally:
            receipt.update(finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 3))
            write_json(attempt / "receipt.json", receipt)
            with self.lock:
                self.reserved -= reservation
        if receipt["status"] == "success":
            write_json(self.output_path(variant, stage).with_suffix(".receipt.json"), receipt)
        return {"variant": variant["id"], "stage": stage["id"], "status": receipt["status"],
                "cost_usd": receipt["cost_usd"], "error": receipt.get("error")}

    def run_variant(self, variant, key, *, retry_failed=False):
        results = []
        for stage in self.stages(variant):
            try:
                result = self.run_stage(variant, stage, key, retry_failed=retry_failed)
            except ExperimentError as exc:
                result = {"variant": variant["id"], "stage": stage["id"], "status": "blocked", "error": str(exc)}
            results.append(result)
            print(json.dumps(redact(result), ensure_ascii=False), flush=True)
            if result["status"] not in {"success", "resumed"}:
                break
        return results

    def execute(self, *, selected=None, retry_failed=False):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with (self.run_dir / ".executor.lock").open("a") as lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ExperimentError("Another executor is already running this experiment") from exc
            key = countries_key(self.manifest.get("key_file"))
            if self.usage_summary()["pending_intents"]:
                raise ExperimentError("An earlier POST intent has no receipt; reconcile its charge before executing again")
            variants = [v for v in self.variants if not selected or v["id"] in selected]
            if selected and set(selected) - {v["id"] for v in variants}:
                raise ExperimentError("Unknown --variant")
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                futures = [pool.submit(self.run_variant, v, key, retry_failed=retry_failed) for v in variants]
                results = [future.result() for future in futures]
            report = {"experiment_id": self.manifest["experiment_id"], "at": now(), "results": results,
                      "usage": self.usage_summary()}
            write_json(self.run_dir / "execution-summary.json", report)
            return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--status-json", action="store_true")
    parser.add_argument("--variant", action="append")
    parser.add_argument("--retry-failed", action="store_true", help="Explicitly authorize another attempt after inspecting failed/uncertain POST")
    args = parser.parse_args(argv)
    try:
        experiment = Experiment(args.manifest)
        if args.execute:
            report = experiment.execute(selected=args.variant, retry_failed=args.retry_failed)
        elif args.status_json:
            report = {**experiment.dry_run(), "usage": experiment.usage_summary()}
        else:
            report = experiment.dry_run()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.execute and any(r["status"] not in {"success", "resumed"} for variant in report["results"] for r in variant):
            return 2
        return 0
    except (ExperimentError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": redact(str(exc))}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
