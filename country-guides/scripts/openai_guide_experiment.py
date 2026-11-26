#!/usr/bin/env python3
"""Isolated Responses pilot. Dry-run by default; no automatic POST retry.

Reservations are conservative token-charge bounds, not invoice guarantees. Unknown
charges require external reconciliation before any further paid work. This runner
never publishes, invokes tools, or changes the country-guide production workflow.

Opt-in variant flags:
* cache_full_packet: explicit 30m breakpoint after all shared policies and inputs.
* writer_state_delta: section_id stages return exactly section_md and state_delta.
  Each append-only delta entry is {key, category, text}; key/category are safe IDs,
  text is nonempty and unabridged. Keys allow /:.- separators; categories use
  safe IDs. A key can only repeat with identical contents. Optional heading_title
  requires its exact single H2; empty heading_title identifies an H2-free opening.
  H1 headings are rejected in delta sections.
  Every section must depend on all previous section stages in manifest order.
  Materialized <stage>.state.json and lineage hashes accompany successful outputs.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request

import openrouter_experiment as router
from reconcile_openrouter_429 import digest, is_upstream_rejection, settled_rejections

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://api.openai.com/v1/responses"
OPENROUTER_RESPONSES = "https://openrouter.ai/api/v1/responses"
OPENROUTER_SNAPSHOTS = {
    "gpt-6.1-terra": "openai/gpt-6.1-terra-20261026",
    "gpt-6.2-sol": "openai/gpt-6.2-sol-20261117",
}
KEY_SOURCE = ROOT / "vendor/blog/config/openai-api-key"
KEY_RE = re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]+")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
STATE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:/.-]*")
RATES = {
    "gpt-6.1-terra": (1.0, .05, 5.0),
    "gpt-6.1-sol": (2.0, .10, 10.0),
    "gpt-6.2-sol": (2.0, .10, 10.0),
}
# Reserve long-context rates even for short inputs, plus 100% input allowance
# for cache writes. The API does not return an invoice or a cache-write price.
CACHE_WRITE_ALLOWANCE = 1.0


class ExperimentError(Exception):
    pass


def redact(value):
    if isinstance(value, str):
        return KEY_RE.sub("[REDACTED]", value)
    if isinstance(value, dict):
        return {redact(k): redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value, *, exclusive=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(redact(value), ensure_ascii=False, indent=2) + "\n"
    if exclusive:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(data)
    else:
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(data, encoding="utf-8")
        os.replace(temporary, path)


def path_in_repo(value, *, exists=False):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ExperimentError("Expected repository-relative path")
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ExperimentError("Path escapes repository")
    if exists and not path.is_file():
        raise ExperimentError("Missing input file")
    return path


def countries_key(key_file=None):
    explicit = os.environ.get("OPENAI_GUIDES_API_KEY", "").strip()
    if explicit:
        if not KEY_RE.fullmatch(explicit):
            raise ExperimentError("Invalid guides API key shape")
        return explicit
    try:
        raw = (Path(key_file) if key_file else KEY_SOURCE).read_text(encoding="utf-8")
    except OSError:
        raise ExperimentError("Unable to read guides API key file") from None
    keys = KEY_RE.findall(raw)
    if len(keys) != 1:
        raise ExperimentError("Expected exactly one API key token")
    return keys[0]


def post_json(payload, key, timeout):
    request = urllib.request.Request(ENDPOINT, data=encoded(payload), method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw, status = response.read().decode("utf-8", errors="replace"), response.status
    except urllib.error.HTTPError as exc:
        raw, status = exc.read().decode("utf-8", errors="replace"), exc.code
    try:
        body = json.loads(raw)
    except ValueError:
        body = {"unparsed_body": raw}
    return status, redact(body)


def count(value):
    return value if type(value) is int and value >= 0 else None


ACCOUNTING_REVISION = "cache-partition-v2"
ACCOUNTING_SOURCE = "https://developers.openai.com/api/docs/guides/prompt-caching"


def usage_estimate(model, usage):
    """Price disjoint ordinary/read/write input partitions, never an invoice.

    Missing counters stay null. A missing partition or lifetime uses the maximum
    supported 2.5x write rate as a conservative estimate, explicitly labeled.
    Invalid counters/partitions have no estimate and block future paid work.
    """
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    if not isinstance(details, dict) or not isinstance(output_details, dict):
        details, output_details = {}, {}
        malformed = True
    else:
        malformed = False
    ttl = details.get("cache_write_tokens_details") or {}
    if not isinstance(ttl, dict):
        ttl, malformed = {}, True
    inp, out = count(usage.get("input_tokens")), count(usage.get("output_tokens"))
    cached, writes = count(details.get("cached_tokens")), count(details.get("cache_write_tokens"))
    short, long = count(ttl.get("ttl_30m_tokens")), count(ttl.get("ttl_12h_tokens"))
    reasoning = count(output_details.get("reasoning_tokens"))
    result = {"input_tokens": inp, "output_tokens": out, "cached_tokens": cached,
              "reasoning_tokens": reasoning, "cache_write_tokens": writes,
              "cache_write_30m_tokens": short, "cache_write_12h_tokens": long,
              "ordinary_input_tokens": None, "token_charge_estimate_usd": None,
              "settled_cost_bound_usd": None, "invoice_cost_usd": None,
              "estimate_is_invoice": False, "accounting_revision": ACCOUNTING_REVISION,
              "accounting_source": ACCOUNTING_SOURCE, "estimate_basis": "Invalid or missing usage totals"}
    for obj, names in ((usage, ("input_tokens", "output_tokens")),
                       (details, ("cached_tokens", "cache_write_tokens")),
                       (ttl, ("ttl_30m_tokens", "ttl_12h_tokens")),
                       (output_details, ("reasoning_tokens",))):
        if any(name in obj and obj[name] is not None and count(obj[name]) is None for name in names):
            malformed = True
    if inp is None or out is None or model not in RATES or malformed:
        return result
    if (any(v is not None and v > inp for v in (cached, writes, short, long))
            or (cached is not None and writes is not None and cached + writes > inp)
            or (reasoning is not None and reasoning > out)
            or (writes is not None and short is not None and long is not None and short + long != writes)
            or (writes is not None and sum(v or 0 for v in (short, long)) > writes)):
        result["estimate_basis"] = "Invalid cache/usage partition; reconciliation required"
        return result
    ir, cr, outr = RATES[model]
    if inp > 272000:
        ir, cr, outr = ir * 2, cr * 2, outr * 1.5
    if cached is not None and writes is not None:
        ordinary = inp - cached - writes
        result["ordinary_input_tokens"] = ordinary
        if writes == 0 or (short is not None and long is not None):
            write_charge = (short or 0) * 1.25 * ir + (long or 0) * 2.5 * ir
            basis = "Disjoint ordinary/cache-read/30m-write/12h-write usage partitions at published rates"
        else:
            write_charge = writes * 2.5 * ir
            basis = "Conservative estimate: missing write lifetime priced at maximum 2.5x input rate"
        input_charge = ordinary * ir + cached * cr + write_charge
    else:
        hit = cached or 0
        input_charge = hit * cr + (inp - hit) * 2.5 * ir
        basis = "Conservative estimate: incomplete cache partition; unclassified input priced at maximum 2.5x write rate"
    charge = (input_charge + out * outr) / 1_000_000
    result.update(token_charge_estimate_usd=charge, settled_cost_bound_usd=charge, estimate_basis=basis)
    return result


class Experiment:
    def __init__(self, manifest_path):
        self.manifest_path = Path(manifest_path).resolve()
        if not self.manifest_path.is_relative_to(ROOT.resolve()):
            raise ExperimentError("Manifest must be inside repository")
        self.manifest = read_json(self.manifest_path)
        m = self.manifest
        self.openrouter = m.get("transport") == "openrouter"
        if m.get("transport", "openai_api") not in {"openai_api", "openrouter"}:
            raise ExperimentError("Unknown Responses transport")
        if KEY_RE.search(json.dumps(m)):
            raise ExperimentError("Credential-shaped text in manifest")
        if m.get("schema_version") != 1 or not SAFE_ID.fullmatch(str(m.get("experiment_id", ""))):
            raise ExperimentError("Require schema_version=1 and safe experiment_id")
        if not isinstance(m.get("revision"), str) or not m["revision"]:
            raise ExperimentError("Require explicit revision")
        self.run_dir = path_in_repo(m["run_dir"])
        if not any(self.run_dir.is_relative_to((ROOT / p).resolve()) and self.run_dir != (ROOT / p).resolve() for p in ("runs", "tmp")):
            raise ExperimentError("Run directory must be isolated under runs/ or tmp/")
        self.system_files = self._files(m.get("system_files", []))
        self.variants = m.get("variants")
        if not isinstance(self.variants, list) or not 1 <= len(self.variants) <= 24:
            raise ExperimentError("Require 1 to 24 variants")
        seen = set()
        for v in self.variants:
            if not SAFE_ID.fullmatch(str(v.get("id", ""))) or v["id"] in seen:
                raise ExperimentError("Variant IDs must be safe and unique")
            seen.add(v["id"])
            if v.get("model") not in RATES or v.get("reasoning") not in ("medium", {"effort": "medium"}):
                raise ExperimentError("Only pinned Terra/Sol with medium reasoning are permitted")
            for option in ("cache_full_packet", "writer_state_delta"):
                if option in v and type(v[option]) is not bool:
                    raise ExperimentError("Variant cache/state options must be booleans")
            self._files(v.get("input_files", []))
            stages = self.stages(v)
            if not isinstance(stages, list) or not stages:
                raise ExperimentError("Require ordered stages")
            previous = set()
            previous_sections = []
            for s in stages:
                sid = s.get("id", "")
                if not SAFE_ID.fullmatch(str(sid)) or sid in previous:
                    raise ExperimentError("Stage IDs must be safe and unique")
                deps = s.get("input_stages", [])
                if not isinstance(deps, list) or any(d not in previous for d in deps):
                    raise ExperimentError("Stage dependency must refer to an earlier stage")
                if "section_ids" in s or ("section_id" in s and (not isinstance(s["section_id"], str) or not SAFE_ID.fullmatch(s["section_id"]))):
                    raise ExperimentError("Writer stages must request exactly one scalar section_id, never section_ids")
                if v.get("writer_state_delta"):
                    section_deps = [d for d in deps if d in previous_sections]
                    if section_deps != previous_sections:
                        raise ExperimentError("State-delta stages must depend on all earlier sections in manifest order")
                    if "section_id" in s:
                        previous_sections.append(sid)
                if "heading_title" in s and (not isinstance(s["heading_title"], str) or "\n" in s["heading_title"] or "\r" in s["heading_title"]):
                    raise ExperimentError("heading_title must be a single-line string (empty for opening)")
                if s.get("reasoning", "medium") not in ("medium", {"effort": "medium"}):
                    raise ExperimentError("All stages require medium reasoning")
                self._files(s.get("input_files", [])); self._files(s.get("system_files", []))
                prompt = self._input_path(s["prompt_file"]).read_text(encoding="utf-8")
                if "json" not in prompt.lower():
                    raise ExperimentError("Prompt must explicitly request JSON")
                # Detect explicit multiple-section assignments in structured prompts.
                if re.search(r'"section_ids"\s*:', prompt) or len(set(re.findall(r'"section_id"\s*:\s*"([^"\n]+)"', prompt))) > 1:
                    raise ExperimentError("Writer prompt batches multiple section IDs")
                if type(s.get("max_tokens")) is not int or not 1 <= s["max_tokens"] <= 65536 or s.get("output_format") != "json":
                    raise ExperimentError("Require JSON and max_tokens between 1 and 65536")
                previous.add(sid)
        self.max_workers = m.get("max_workers", 1)
        if type(self.max_workers) is not int or not 1 <= self.max_workers <= 2:
            raise ExperimentError("max_workers must be 1 or 2")
        self.max_cost = self._limit(m.get("max_cost_usd", 15), 15)
        self.max_call_cost = self._limit(m.get("max_call_cost_usd", 2), 15)
        if self.max_call_cost > self.max_cost:
            raise ExperimentError("Per-call cap exceeds run cap")
        self.timeout = self._limit(m.get("timeout_seconds", 360), 3600)
        self.lock = threading.Lock()
        self.reserved = 0.0
        self.active_attempts = set()

    @staticmethod
    def _limit(value, ceiling):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= ceiling:
            raise ExperimentError("Invalid or excessive execution limit")
        return float(value)

    def _input_path(self, value):
        path = path_in_repo(value, exists=True)
        parts = [p.lower() for p in path.relative_to(ROOT.resolve()).parts]
        if (path == Path(self.manifest.get("key_file", KEY_SOURCE)).resolve()
                or any(p in {"config", "keys", "credentials", "secrets", ".git"} for p in parts)
                or path.name.lower().startswith(".env")
                or re.search(r"credential|secret|api.?key", path.name, re.I)
                or path.suffix.lower() in {".pem", ".key"}):
            raise ExperimentError("Credential/configuration files cannot be model inputs")
        if KEY_RE.search(path.read_text(encoding="utf-8")):
            raise ExperimentError("Credential-shaped text in input; blocked")
        return path

    def _files(self, values):
        if not isinstance(values, list):
            raise ExperimentError("File collections must be lists")
        return [self._input_path(v) for v in values]

    def stages(self, variant):
        return variant.get("stages", self.manifest.get("stages"))

    def output_path(self, variant, stage):
        return self.run_dir / "variants" / variant["id"] / (stage["id"] + ".json")

    @staticmethod
    def uses_delta(variant, stage):
        return bool(variant.get("writer_state_delta") and "section_id" in stage)

    def state_path(self, variant, stage):
        return self.output_path(variant, stage).with_suffix(".state.json")

    @staticmethod
    def merge_entries(base, delta):
        """Append in first-seen order; identical keys dedup, conflicts reject."""
        if not isinstance(base, list) or not isinstance(delta, list):
            raise ExperimentError("state_delta and materialized entries must be lists")
        merged, seen = [], {}
        for entry in base + delta:
            if (not isinstance(entry, dict) or set(entry) != {"key", "category", "text"}
                    or not isinstance(entry["key"], str) or not STATE_KEY.fullmatch(entry["key"])
                    or not isinstance(entry["category"], str) or not SAFE_ID.fullmatch(entry["category"])
                    or not isinstance(entry["text"], str) or not entry["text"].strip()):
                raise ExperimentError("Malformed state delta entry; require safe key/category and nonempty text")
            if KEY_RE.search(entry["text"]):
                raise ExperimentError("Credential-shaped state entry")
            key = entry["key"]
            if key in seen:
                if seen[key] != entry:
                    raise ExperimentError("Conflicting append-only state key: " + key)
                continue
            seen[key] = dict(entry)
            merged.append(dict(entry))
        return merged

    def validate_delta_output(self, parsed, stage):
        if (set(parsed) != {"section_md", "state_delta"}
                or not isinstance(parsed.get("section_md"), str) or not parsed["section_md"].strip()):
            raise ExperimentError("State-delta section output requires nonempty section_md and state_delta only")
        prose = parsed["section_md"]
        if re.search(r"^[ \t]{0,3}#[ \t]+", prose, re.M):
            raise ExperimentError("Section output must not contain an H1")
        headings = re.findall(r"^[ \t]{0,3}##[ \t]+([^\r\n]+)", prose, re.M)
        expected = stage.get("heading_title")
        if expected == "":
            valid = not headings
        else:
            valid = len(headings) == 1 and (expected is None or headings[0].strip() == expected)
        if not valid:
            raise ExperimentError("Section H2 count/title differs from heading_title (empty title requires H2-free opening)")
        self.merge_entries([], parsed["state_delta"])

    def _read_state(self, variant, stage):
        path = self.state_path(variant, stage)
        receipt = read_json(self.output_path(variant, stage).with_suffix(".receipt.json"))
        if (not path.is_file() or not path.resolve().is_relative_to(self.run_dir.resolve())
                or receipt.get("state_sha256") != sha(path.read_bytes())
                or receipt.get("state_path") != str(path.relative_to(ROOT))):
            raise ExperimentError("Materialized state hash/path mismatch")
        state = read_json(path)
        if (state.get("schema_version") != 1 or state.get("variant") != variant["id"]
                or state.get("stage") != stage["id"] or state.get("lineage") != receipt.get("state_lineage")
                or self.merge_entries([], state.get("entries")) != state.get("entries")):
            raise ExperimentError("Materialized state schema/lineage mismatch")
        return state

    def _state_base(self, variant, stage):
        entries, lineage = [], []
        by_id = {s["id"]: s for s in self.stages(variant)}
        for dep in stage.get("input_stages", []):
            prior = by_id[dep]
            if not self.uses_delta(variant, prior):
                continue
            state = self._read_state(variant, prior)
            receipt = read_json(self.output_path(variant, prior).with_suffix(".receipt.json"))
            lineage.append({"stage": dep, "section_id": prior["section_id"],
                            "output_sha256": receipt["output_sha256"], "state_sha256": receipt["state_sha256"]})
            # Each prior state was validated; only the latest cumulative state
            # is materialized or sent, never historical snapshots/delta JSON.
            entries = state["entries"]
        return entries, lineage

    def build_request(self, variant, stage, _cache=None):
        # Cache only within this construction: every new call re-reads sources and
        # rechecks receipts, while dense prior-section DAGs stay polynomial.
        cache = {} if _cache is None else _cache
        cache_key = (variant["id"], stage["id"])
        if cache_key in cache:
            return cache[cache_key]
        shared_system = [self._input_path(str(p.relative_to(ROOT))) for p in self.system_files]
        stage_system = self._files(stage.get("system_files", []))
        def contents(path):
            # Opt-in caching preserves source CRLF/trailing whitespace as well as
            # Unicode. Legacy text-mode behavior stays unchanged when absent.
            return path.read_bytes().decode("utf-8") if variant.get("cache_full_packet") else path.read_text(encoding="utf-8")
        def sources(paths):
            return "\n\n".join(f"SOURCE FILE: {p.relative_to(ROOT)}\n{contents(p)}" for p in paths)
        def inputs(paths):
            return "".join(f"\n\nINPUT FILE: {p.relative_to(ROOT)}\n{contents(p)}" for p in paths)
        system = sources(shared_system + stage_system)
        shared = inputs(self._files(variant.get("input_files", [])))
        dynamic = inputs(self._files(stage.get("input_files", [])))
        dynamic += "\n\nSTAGE PROMPT:\n" + contents(self._input_path(stage["prompt_file"]))
        by_id = {s["id"]: s for s in self.stages(variant)}
        for dep in stage.get("input_stages", []):
            prior = by_id[dep]
            p = self.output_path(variant, prior)
            if not self._resume(variant, prior, self.fingerprint(self.build_request(variant, prior, cache))):
                raise ExperimentError("Earlier stage lacks valid fingerprint and artifact hash")
            if self.uses_delta(variant, prior):
                parsed = read_json(p)
                self.validate_delta_output(parsed, prior)
                dynamic += f"\n\nPRIOR SECTION: {dep}\n{parsed['section_md']}"
            else:
                dynamic += f"\n\nPRIOR STAGE: {dep}\n{p.read_text(encoding='utf-8')}"
        if variant.get("writer_state_delta"):
            entries, _ = self._state_base(variant, stage)
            dynamic += "\n\nMERGED WRITER STATE:\n" + json.dumps(entries, ensure_ascii=False, sort_keys=True)
        user = shared + dynamic
        if KEY_RE.search(system + user):
            raise ExperimentError("Credential-shaped model input")
        request = {"model": variant["model"], "instructions": system or "Follow the supplied sources and return JSON.",
                "input": user, "max_output_tokens": stage["max_tokens"],
                "reasoning": {"effort": "medium"}, "store": False, "service_tier": "default",
                "text": {"format": {"type": "json_object"}}}
        if variant.get("cache_full_packet"):
            stable = [{"role": "developer", "content": [{"type": "input_text", "text": sources(shared_system) or "Follow the supplied sources and return JSON."}]}]
            if shared:
                stable.append({"role": "user", "content": [{"type": "input_text", "text": shared}]})
            stable[-1]["content"][-1]["prompt_cache_breakpoint"] = {"mode": "explicit"}
            messages = stable
            if stage_system:
                messages.append({"role": "developer", "content": [{"type": "input_text", "text": sources(stage_system)}]})
            messages.append({"role": "user", "content": [{"type": "input_text", "text": dynamic}]})
            del request["instructions"]
            request["input"] = messages
            request["prompt_cache_options"] = {"mode": "explicit", "ttl": "30m"}
        if self.openrouter:
            model = variant["model"]
            if model not in OPENROUTER_SNAPSHOTS:
                raise ExperimentError("OpenRouter model lacks a verified OpenAI snapshot")
            if router.KEY_RE.search(system + user):
                raise ExperimentError("Credential-shaped OpenRouter model input")
            ir, _, outr = RATES[model]
            request["model"] = "openai/" + model
            request.pop("service_tier")
            request["provider"] = {"only": ["openai"], "allow_fallbacks": False,
                                   "require_parameters": True, "data_collection": "deny",
                                   "max_price": {"prompt": ir * 2, "completion": outr * 1.5}}
        cache[cache_key] = request
        return request

    def post(self, request, key):
        if self.openrouter:
            return router.post_json(request, key, self.timeout, endpoint=OPENROUTER_RESPONSES,
                                    extra_headers={"X-OpenRouter-Metadata": "enabled"})
        return post_json(request, key, self.timeout)

    def route_matches(self, variant, response):
        model = variant["model"]
        if (response.get("reasoning") or {}).get("effort") != "medium":
            return False
        if not self.openrouter:
            return response.get("model") == model
        model_id = "openai/" + model
        meta = response.get("openrouter_metadata") or {}
        endpoints = (meta.get("endpoints") or {}).get("available") or []
        selected = [e for e in endpoints if e.get("selected") is True]
        return (response.get("model") in {model_id, OPENROUTER_SNAPSHOTS[model]}
                and meta.get("requested") == model_id and meta.get("attempt") == 1
                and meta.get("is_byok") is False and len(selected) == 1
                and selected[0].get("provider") == "OpenAI"
                and selected[0].get("model") == OPENROUTER_SNAPSHOTS[model])

    def charges(self, model, usage):
        if not self.openrouter:
            return usage_estimate(model, usage)
        usage = usage if isinstance(usage, dict) else {}
        model = model.removeprefix("openai/") if isinstance(model, str) else ""
        model = next((key for key, snapshot in OPENROUTER_SNAPSHOTS.items()
                      if snapshot == "openai/" + model), model)
        details = usage_estimate(model, usage)
        cost = usage.get("cost")
        valid_cost = type(cost) in {int, float} and math.isfinite(cost) and cost >= 0
        known = cost if valid_cost else None
        details.update(token_charge_estimate_usd=None, provider_reported_cost_usd=known,
                       settled_cost_bound_usd=known, accounting_revision="openrouter-reported-cost-v1",
                       accounting_source="https://openrouter.ai/docs/api/api-reference/responses/create-responses",
                       estimate_basis="OpenRouter response usage.cost" if valid_cost else "Missing OpenRouter usage.cost")
        return details

    def fingerprint(self, request):
        return sha(encoded({"experiment_id": self.manifest["experiment_id"], "revision": self.manifest["revision"], "request": request}))

    def attempts(self):
        return sorted((self.run_dir / "variants").glob("*/attempts/*/intent.json"))

    def usage_summary(self, *, exclude_active=False):
        receipts = []
        pending = 0
        reconciled = 0
        settled = set(settled_rejections(self.run_dir)) if self.openrouter else set()
        for p in self.attempts():
            if exclude_active and p.parent in self.active_attempts:
                continue
            receipt_path = p.with_name("receipt.json")
            if receipt_path.is_file():
                historical = read_json(receipt_path)
                # Recalculate in memory only: immutable receipts retain their
                # original accounting for audit, including pre-v2 estimates.
                model = historical.get("actual_model") or historical.get("requested_model")
                corrected = self.charges(model, historical.get("usage"))
                if (corrected["settled_cost_bound_usd"] is None and settled
                        and digest(receipt_path) in settled and is_upstream_rejection(p.parent, historical)):
                    corrected["settled_cost_bound_usd"] = 0
                    reconciled += 1
                receipts.append({**historical, "charges": corrected,
                                 "historical_charges": historical.get("charges", {})})
            else:
                pending += 1
        def total(field):
            vals = [r.get("charges", {}).get(field) for r in receipts]
            return sum(vals) if vals and all(v is not None for v in vals) else None
        return {"attempts": len(receipts), "pending_intents": pending,
                "reconciled_upstream_rejections": reconciled,
                "unknown_charge_attempts": sum(r.get("charges", {}).get("settled_cost_bound_usd") is None for r in receipts),
                "retained_cost_bound_usd": sum(r.get("charges", {}).get("settled_cost_bound_usd")
                    if r.get("charges", {}).get("settled_cost_bound_usd") is not None
                    else r["reserved_cost_bound_usd"] for r in receipts),
                "invoice_cost_usd": None,
                "accounting_revision": self.charges(None, {})["accounting_revision"],
                "accounting_source": self.charges(None, {})["accounting_source"],
                "accounting_basis": "Recalculated from immutable attempt receipt raw usage; historical receipts unchanged",
                "historical_receipt_estimate_usd": (sum(r["historical_charges"]["token_charge_estimate_usd"] for r in receipts)
                    if receipts and all(r["historical_charges"].get("token_charge_estimate_usd") is not None for r in receipts) else None),
                "token_charge_estimate_usd": total("token_charge_estimate_usd"),
                **({"provider_reported_cost_usd": total("provider_reported_cost_usd")} if self.openrouter else {}),
                "estimate_is_invoice": False,
                **{k: total(k) for k in ("input_tokens", "output_tokens", "cached_tokens", "reasoning_tokens", "cache_write_tokens", "cache_write_30m_tokens", "cache_write_12h_tokens", "ordinary_input_tokens")},
                "successes": sum(r.get("status") == "success" for r in receipts)}

    def cost_bound(self, request):
        body = request["input"]
        if not isinstance(body, (str, list)):
            raise ExperimentError("Request input must be text or structured message blocks")
        input_bytes = len(body.encode()) if isinstance(body, str) else len(encoded(body))
        input_bound = len(request.get("instructions", "").encode()) + input_bytes + 4096
        ir, _, outr = RATES[request["model"].removeprefix("openai/")]
        # OpenRouter Standard publishes a 1.25x write rate for this explicit
        # 30-minute TTL, including when long-context input rates apply.
        explicit_30m = request.get("prompt_cache_options") == {"mode": "explicit", "ttl": "30m"}
        input_multiplier = 1.25 if self.openrouter and explicit_30m else 1 + CACHE_WRITE_ALLOWANCE
        return (input_bound * ir * 2 * input_multiplier + request["max_output_tokens"] * outr * 1.5) / 1_000_000

    def dry_run(self, selected=None):
        variants = self._selected(selected)
        bounds = []
        for v in variants:
            for s in self.stages(v):
                if not s.get("input_stages"):
                    bound = self.cost_bound(self.build_request(v, s))
                    if bound > self.max_call_cost:
                        raise ExperimentError("Conservative cost bound exceeds per-call cap")
                    bounds.append(bound)
        return {"experiment_id": self.manifest["experiment_id"], "revision": self.manifest["revision"],
                "variants": len(variants), "stages": sum(len(self.stages(v)) for v in variants),
                "models": sorted({v["model"] for v in variants}), "max_workers": self.max_workers,
                "max_cost_usd": self.max_cost, "max_call_cost_usd": self.max_call_cost,
                "initial_call_cost_bounds_usd": bounds, "dependent_call_bounds": "checked after dependencies exist, before POST",
                "reservation_basis": ("UTF-8 bytes + 4096 tokens; long-context rates; explicit 30m OpenRouter Standard writes priced at 1.25x input, otherwise 100% allowance; output includes reasoning"
                                      if self.openrouter else "UTF-8 bytes + 4096 tokens; long-context rates; 100% input cache-write allowance; output includes reasoning"),
                "paid_requests_sent": 0}

    def _selected(self, selected):
        if selected and set(selected) - {v["id"] for v in self.variants}:
            raise ExperimentError("Unknown --variant")
        return [v for v in self.variants if not selected or v["id"] in selected]

    def _resume(self, variant, stage, fp):
        p = self.output_path(variant, stage)
        receipt = p.with_suffix(".receipt.json")
        if not p.is_file() or not receipt.is_file():
            return False
        r = read_json(receipt)
        attempt = self.run_dir / r.get("attempt_relative_path", "__missing__")
        if not attempt.is_relative_to(self.run_dir) or not (attempt / "receipt.json").is_file():
            return False
        immutable = read_json(attempt / "receipt.json")
        hashes_match = all((attempt / name).is_file() and sha((attempt / name).read_bytes()) == r.get(field)
                           for name, field in (("request.json", "request_sha256"), ("intent.json", "intent_sha256"),
                                               ("response.json", "response_sha256")))
        if self.uses_delta(variant, stage):
            try:
                self.validate_delta_output(read_json(p), stage)
                state = self._read_state(variant, stage)
                base, lineage = self._state_base(variant, stage)
                if state["lineage"] != lineage or state["entries"] != self.merge_entries(base, read_json(p)["state_delta"]):
                    return False
            except (ExperimentError, OSError, ValueError, KeyError, TypeError):
                return False
        return (hashes_match and r == immutable and r.get("status") == "success" and r.get("fingerprint") == fp
                and r.get("output_sha256") == sha(p.read_bytes()))

    def _reserve(self, amount, attempt):
        with self.lock:
            summary = self.usage_summary(exclude_active=True)
            if summary["pending_intents"] or summary["unknown_charge_attempts"]:
                raise ExperimentError("Unreconciled POST/unknown usage blocks further paid calls")
            if amount > self.max_call_cost or amount + self.reserved + summary["retained_cost_bound_usd"] > self.max_cost:
                raise ExperimentError("Conservative cost bound exceeds call/run cap")
            self.reserved += amount
            self.active_attempts.add(attempt)

    def run_stage(self, variant, stage, key, *, retry_failed=False, transport=None):
        request = self.build_request(variant, stage)
        fp = self.fingerprint(request)
        if self._resume(variant, stage, fp):
            return {"variant": variant["id"], "stage": stage["id"], "status": "resumed"}
        p = self.output_path(variant, stage)
        if p.exists() or p.with_suffix(".receipt.json").exists() or (self.uses_delta(variant, stage) and self.state_path(variant, stage).exists()):
            raise ExperimentError("Existing artifact differs from immutable receipt/fingerprint; use a new run revision/directory")
        attempt_root = self.run_dir / "variants" / variant["id"] / "attempts"
        prior = sorted(attempt_root.glob(stage["id"] + "-*"))
        if prior and not retry_failed:
            raise ExperimentError("Prior attempt exists; explicit --retry-failed required after inspection")
        state_base, state_lineage = self._state_base(variant, stage) if self.uses_delta(variant, stage) else ([], [])
        reservation = self.cost_bound(request)
        attempt = attempt_root / f"{stage['id']}-{len(prior) + 1:03d}"
        self._reserve(reservation, attempt)
        started = time.monotonic()
        intent = {"variant": variant["id"], "stage": stage["id"], "fingerprint": fp,
                  "requested_model": variant["model"], "requested_reasoning": "medium",
                  "reserved_cost_bound_usd": reservation, "started_at": now(),
                  "attempt_relative_path": str(attempt.relative_to(self.run_dir))}
        receipt = {**intent, "status": "uncertain", "complete": False, "usage": {},
                   "charges": self.charges(variant["model"], {})}
        try:
            attempt.mkdir(parents=True, exist_ok=False)
            write_json(attempt / "request.json", request)
            write_json(attempt / "intent.json", intent)
            receipt.update(request_sha256=sha((attempt / "request.json").read_bytes()),
                           intent_sha256=sha((attempt / "intent.json").read_bytes()))
            status, response = transport(request, key, self.timeout) if transport else self.post(request, key)
            response = redact(response)
            write_json(attempt / "response.json", response)
            receipt["response_sha256"] = sha((attempt / "response.json").read_bytes())
            receipt.update(http_status=status, generation_id=response.get("id"), actual_model=response.get("model"),
                           actual_reasoning=response.get("reasoning"))
            usage = response.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}
            actual_model = response.get("model")
            charges = self.charges(actual_model or variant["model"], usage)
            if not self.openrouter and actual_model not in RATES:
                charges["token_charge_estimate_usd"] = None
                charges["settled_cost_bound_usd"] = None
            receipt.update(usage=usage, charges=charges, status="failed")
            texts, refusal, unexpected = [], False, False
            for item in response.get("output") or []:
                if item.get("type") not in {"message", "reasoning"}:
                    unexpected = True
                if item.get("type") == "message" and item.get("status", "completed") != "completed":
                    unexpected = True
                for content in item.get("content") or []:
                    if content.get("type") == "refusal":
                        refusal = True
                    if item.get("type") == "message" and content.get("type") == "output_text" and isinstance(content.get("text"), str):
                        texts.append(content["text"])
            text = "".join(texts)
            if text:
                write_json(attempt / "partial.json", {"output_text": text})
            if status != 200 or response.get("error"):
                raise ExperimentError("HTTP/API failure; charge retained")
            if not self.route_matches(variant, response):
                raise ExperimentError("Missing or mismatched model/reasoning routing proof")
            if response.get("status") != "completed" or response.get("incomplete_details") or refusal or unexpected:
                raise ExperimentError("Incomplete/refused/unexpected-tool response")
            if not text.strip():
                raise ExperimentError("Missing nonempty message output_text")
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ExperimentError("Expected JSON object output")
            if receipt["charges"]["settled_cost_bound_usd"] is None:
                raise ExperimentError("Missing/invalid usage; reconcile before further paid work")
            if self.uses_delta(variant, stage):
                self.validate_delta_output(parsed, stage)
                state = {"schema_version": 1, "variant": variant["id"], "stage": stage["id"],
                         "entries": self.merge_entries(state_base, parsed["state_delta"]), "lineage": state_lineage}
                state_path = self.state_path(variant, stage)
                write_json(state_path, state)
                receipt.update(state_path=str(state_path.relative_to(ROOT)), state_sha256=sha(state_path.read_bytes()),
                               state_lineage=state_lineage, state_delta_schema="append-only-key-v1")
            write_json(p, parsed)
            receipt.update(status="success", complete=True, output_path=str(p.relative_to(ROOT)), output_sha256=sha(p.read_bytes()))
        except Exception as exc:
            receipt["error"] = redact(f"{type(exc).__name__}: {exc}")
        finally:
            receipt.update(finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 3))
            if attempt.is_dir() and (attempt / "intent.json").exists():
                write_json(attempt / "receipt.json", receipt)
            with self.lock:
                self.reserved -= reservation
                self.active_attempts.discard(attempt)
        if receipt["status"] == "success":
            write_json(p.with_suffix(".receipt.json"), receipt)
        return {"variant": variant["id"], "stage": stage["id"], "status": receipt["status"],
                "token_charge_estimate_usd": receipt["charges"]["token_charge_estimate_usd"],
                **({"provider_reported_cost_usd": receipt["charges"]["provider_reported_cost_usd"]}
                   if self.openrouter else {}), "error": receipt.get("error")}

    def run_variant(self, variant, key, *, retry_failed=False):
        results = []
        for stage in self.stages(variant):
            try:
                result = self.run_stage(variant, stage, key, retry_failed=retry_failed)
            except ExperimentError as exc:
                result = {"variant": variant["id"], "stage": stage["id"], "status": "blocked", "error": redact(str(exc))}
            results.append(result)
            if result["status"] not in {"success", "resumed"}:
                break
        return results

    def execute(self, *, selected=None, retry_failed=False):
        variants = self._selected(selected)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with (self.run_dir / ".executor.lock").open("a") as lock_file:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ExperimentError("Another executor holds this run lock") from None
            summary = self.usage_summary()
            if summary["pending_intents"] or summary["unknown_charge_attempts"]:
                raise ExperimentError("Unreconciled POST/unknown usage blocks paid work, including retry")
            key = (router.countries_key if self.openrouter else countries_key)(self.manifest.get("key_file"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                results = list(pool.map(lambda v: self.run_variant(v, key, retry_failed=retry_failed), variants))
            report = {"experiment_id": self.manifest["experiment_id"], "at": now(), "results": results, "usage": self.usage_summary()}
            write_json(self.run_dir / "execution-summary.json", report, exclusive=False)
            return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--status-json", action="store_true")
    parser.add_argument("--variant", action="append")
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args(argv)
    try:
        experiment = Experiment(args.manifest)
        if args.execute:
            report = experiment.execute(selected=args.variant, retry_failed=args.retry_failed)
        else:
            report = experiment.dry_run(args.variant)
            if args.status_json:
                report["usage"] = experiment.usage_summary()
        print(json.dumps(redact(report), ensure_ascii=False, indent=2))
        return 2 if args.execute and any(r["status"] not in {"success", "resumed"} for rs in report["results"] for r in rs) else 0
    except (ExperimentError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": redact(str(exc))}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
