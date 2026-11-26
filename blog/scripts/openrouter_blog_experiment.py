#!/usr/bin/env python3
"""Run an authorized isolated blog model benchmark (never publishes).

Only --execute makes paid requests. All input paths are repository-relative.
The selected model and exact provider are pinned; there is no model fallback.
An HTTP/transport ambiguity is retained and blocks automatic replay. Review it
before explicitly using --retry-failed. Existing attempts are never overwritten.

The default request_mode is "legacy". Opt in to "stable_conversation_v1"
to retain full verified earlier turns and place shared sources before unit prompts.
Only explicitly registered batches can exceed USD 3: batch_authorization must
name the batch's exact receipt and current approval_sha256, use its shared run
directory, and declare approved cluster IDs. Each batch has a separate capped
attempt ledger and executor lock.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
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

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
KEY_RE = re.compile(r"sk-or-[A-Za-z0-9_-]+")
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
SHARED_KEY_FILE = ROOT / 'config' / 'openrouter.env'
ALLOWED_MODELS = {
    'minimax/minimax-m3.1-flash', 'moonshotai/kimi-k3.1-pro',
    'deepseek/deepseek-v4-pro-0813', 'deepseek/deepseek-v4.1-flash-1017',
    'xiaomi/mimo-v2.6-pro', 'z-ai/glm-5.3',
}
# Registered batches (example values). Each entry binds an approval receipt to its
# shared run directory, approval date, API budget and number of approved clusters.
APPROVED_BATCH = 'example-batch'
BATCH_APPROVAL_FILE = f'docs/workflow-v2/batches/{APPROVED_BATCH}/approval.json'
BATCH_RUN_DIR = f'runs/{APPROVED_BATCH}'
APPROVED_BATCH_SCOPES = {
    BATCH_APPROVAL_FILE: {'run_dir': BATCH_RUN_DIR, 'date': '2026-01-15',
                          'budget': 8, 'count': 12},
    'docs/workflow-v2/batches/example-batch-two/approval.json': {
        'run_dir': 'runs/example-batch-two', 'date': '2026-01-22',
        'budget': 4, 'count': 6},
}
# Run directories that share one provider key; a charge reconciliation covers all of them.
RECONCILIATION_LEDGERS = ('runs/example-pilot', BATCH_RUN_DIR)
UNBATCHED_BUDGET_USD = 3
RECONCILIATION_TOLERANCE = Decimal('0.00000001')
DEFAULT_SYSTEM = 'Produce the requested local research or article artifact. Follow the supplied sources and constraints.'


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


def _require(condition, message):
    if not condition:
        raise ExperimentError('Charge reconciliation: ' + message)


def _instant(value):
    stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    _require(stamp.tzinfo is not None, 'timestamps require timezone')
    return stamp


def _amount(value):
    _require(type(value) in {float, int}, 'usage/cost must be a numeric provider value')
    result = Decimal(str(value))
    _require(result.is_finite() and result >= 0, 'usage/cost must be finite and nonnegative')
    return result


def _ledger_files():
    receipts, intents = {}, {}
    for root in RECONCILIATION_LEDGERS:
        directory = path_in_repo(root)
        for p in directory.glob('variants/*/attempts/*/receipt.json'):
            receipts[str(p.relative_to(ROOT))] = sha(p.read_bytes())
        for p in directory.glob('variants/*/attempts/*/intent.json'):
            intents[str(p.relative_to(ROOT))] = sha(p.read_bytes())
    return receipts, intents


def validate_charge_reconciliation(receipt_path, proof, *, expected_key_sha256=None):
    """Verify a zero residual at counter precision; never repair generation state.

    Later paid attempts are allowed only after this append-only audit's seal.
    Original frozen attempts and both provider snapshots must remain unchanged.
    """
    _require(isinstance(proof, dict) and proof.get('schema_version') == 1
             and proof.get('method') == 'provider-key-total-zero-v1'
             and type(proof.get('cost_usd')) in {int, float} and proof['cost_usd'] == 0,
             'only an audited zero-residual proof is supported')
    _require(proof.get('ledger_roots') == list(RECONCILIATION_LEDGERS), 'declared ledger scope differs')
    target = str(receipt_path.resolve().relative_to(ROOT.resolve()))
    _require(proof.get('target_receipt') == target, 'target receipt differs')
    _require(all(isinstance(proof.get(k), str) and proof[k].strip() for k in ('audited_by', 'audit_reference')),
             'named technical audit and collection provenance required')
    identity = proof.get('authenticated_key_sha256', '')
    _require(isinstance(identity, str) and re.fullmatch(r'[0-9a-f]{64}', identity), 'missing authenticated key identity')
    _require(expected_key_sha256 is None or identity == expected_key_sha256, 'execution BLOG key differs from audited key')
    sealed = _instant(proof['sealed_at'])
    _require(sealed <= _instant(now()), 'audit seal is in the future')
    ledger = proof['ledger_sha256']
    _require(isinstance(ledger, dict) and target in ledger, 'target absent from frozen receipts')
    current, current_intents = _ledger_files()
    _require(all(current.get(p) == digest for p, digest in ledger.items()), 'original receipt inventory changed')
    attempt_hashes = proof['attempt_files_sha256']
    _require(isinstance(attempt_hashes, dict), 'missing original intent/request hashes')
    known, unknown, latest = Decimal(0), [], None
    for name, digest in ledger.items():
        path = path_in_repo(name, exists=True)
        _require(name in current and sha(path.read_bytes()) == digest, 'source receipt hash differs')
        receipt = read_json(path)
        for filename in ('intent.json', 'request.json'):
            source = path.parent / filename
            relative = str(source.relative_to(ROOT))
            _require(attempt_hashes.get(relative) == sha(source.read_bytes()), 'original intent/request changed')
        intent = read_json(path.parent / 'intent.json')
        _require(receipt.get('fingerprint') == intent.get('fingerprint') and receipt.get('started_at') == intent.get('started_at'),
                 'receipt/intent provenance differs')
        finished = _instant(receipt['finished_at'])
        _require(_instant(receipt['started_at']) <= finished, 'attempt times are inconsistent')
        latest = max(latest, finished) if latest else finished
        if receipt.get('cost_usd') is None:
            unknown.append(name)
        else:
            known += _amount(receipt['cost_usd'])
    _require(unknown == [target] or (len(unknown) == 1 and unknown[0] == target), 'must have exactly one frozen unresolved attempt')
    target_data = read_json(receipt_path)
    _require(target_data.get('status') != 'success' and not target_data.get('generation_id')
             and not target_data.get('complete') and not target_data.get('output_sha256'), 'target generation is not an unresolved transport attempt')
    snapshots = proof['snapshots']
    _require(isinstance(snapshots, list) and len(snapshots) == 2 and snapshots[0]['path'] != snapshots[1]['path'],
             'two separate provider snapshots required')
    observed, totals = [], []
    for source in snapshots:
        path = path_in_repo(source['path'], exists=True)
        _require(sha(path.read_bytes()) == source['sha256'], 'provider snapshot hash differs')
        snapshot = read_json(path)
        _require(snapshot.get('endpoint') == 'https://openrouter.ai/api/v1/key'
                 and snapshot.get('authenticated_key_sha256') == identity
                 and snapshot.get('ledger_sha256') == ledger, 'provider source/key/frozen inventory differs')
        stamp = _instant(snapshot['observed_at'])
        server = parsedate_to_datetime(snapshot['provider_http_date'])
        _require(server.tzinfo is not None and abs((stamp - server).total_seconds()) <= 120, 'provider/client observation times disagree')
        _require(snapshot['data'].get('is_management_key') is False, 'snapshot must be the authenticated inference BLOG key')
        total = _amount(snapshot['data']['usage'])
        _require(abs(total - known) <= RECONCILIATION_TOLERANCE, 'lifetime provider total does not equal ALL known charges')
        observed.append(stamp); totals.append(total)
    _require(latest is not None and (observed[0] - latest).total_seconds() >= 300
             and (observed[1] - observed[0]).total_seconds() >= 60, 'snapshots are not sufficiently later/separated')
    _require(observed[1] <= sealed and (sealed - observed[1]).total_seconds() <= 900,
             'snapshots were stale or in the future when audited')
    _require(abs(totals[1] - totals[0]) <= RECONCILIATION_TOLERANCE, 'provider counters do not agree')
    frozen_intents = {str(Path(p).parent / 'intent.json') for p in ledger}
    _require(set(attempt_hashes) == {str(Path(p).parent / filename) for p in ledger for filename in ('intent.json', 'request.json')},
             'frozen attempt inventory is incomplete')
    # No unrecorded/pending request between either snapshot and the audit seal.
    # After sealing, new charged or uncertain attempts retain their own receipts
    # and are accounted normally; they cannot retroactively erase this proof.
    for name in set(current_intents) - frozen_intents:
        intent = read_json(path_in_repo(name, exists=True))
        _require(_instant(intent['started_at']) >= sealed, 'new paid intent appeared before the audit seal')
    for name in set(current) - set(ledger):
        _require(str(Path(name).parent / 'intent.json') in current_intents, 'new receipt has no POST intent')
    return 0.0


def build_charge_reconciliation(receipt_path, snapshots, *, audited_by, audit_reference):
    ledger, intents = _ledger_files()
    _require(set(intents) == {str(Path(p).parent / 'intent.json') for p in ledger}, 'pending/unrecorded POST intent blocks audit')
    records = [read_json(path_in_repo(p, exists=True)) for p in snapshots]
    proof = {'schema_version': 1, 'method': 'provider-key-total-zero-v1', 'cost_usd': 0.0,
             'sealed_at': now(), 'audited_by': audited_by, 'audit_reference': audit_reference,
             'authenticated_key_sha256': records[0]['authenticated_key_sha256'],
             'ledger_roots': list(RECONCILIATION_LEDGERS), 'ledger_sha256': ledger,
             'target_receipt': str(receipt_path.resolve().relative_to(ROOT.resolve())),
             'attempt_files_sha256': {str((path_in_repo(p).parent / f).relative_to(ROOT)): sha((path_in_repo(p).parent / f).read_bytes())
                                      for p in ledger for f in ('intent.json', 'request.json')},
             'snapshots': [{'path': p, 'sha256': sha(path_in_repo(p, exists=True).read_bytes())} for p in snapshots]}
    validate_charge_reconciliation(receipt_path, proof)
    return proof


def path_in_repo(value: str, *, exists=False):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ExperimentError("Expected a nonempty repository-relative path")
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ExperimentError("Path escapes repository")
    if exists and not path.is_file():
        raise ExperimentError(f"Missing input: {value}")
    return path


def blog_key(key_file=None):
    explicit = os.environ.get("OPENROUTER_BLOG_API_KEY", "").strip()
    if explicit:
        if not KEY_RE.fullmatch(explicit):
            raise ExperimentError("OPENROUTER_BLOG_API_KEY is not a valid key shape")
        return explicit
    source = Path(key_file).resolve() if key_file else SHARED_KEY_FILE.resolve()
    if source not in {SHARED_KEY_FILE.resolve(), (ROOT / 'config/.env').resolve()}:
        raise ExperimentError('Credential source is not an explicitly allowed BLOG/shared config')
    keys, context = [], ''
    for line in source.read_text(encoding="utf-8").splitlines():
        label = KEY_RE.sub("[REDACTED]", line)
        if line.lstrip().startswith('#') and not KEY_RE.search(line):
            context = label
            continue
        if KEY_RE.search(line):
            full_label = context + ' ' + label
            if re.search(r"\bblog\b|блог|OPENROUTER_BLOG_API_KEY", full_label, re.I) and not re.search(
                    r"\bgeo\b|гео|глоссар|glossary|country|гайд", full_label, re.I):
                keys.extend(KEY_RE.findall(line))
            context = ''
    if len(keys) != 1:
        raise ExperimentError("Expected exactly one explicitly BLOG-labeled key; GEO/generic keys are never used")
    return keys[0]


def post_json(payload, key, timeout):
    """No retries: an interrupted POST may already have incurred a charge."""
    request = urllib.request.Request(ENDPOINT, data=encoded(payload), method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "X-Title": "Blog isolated model benchmark",
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
        self.input_hashes = m.get('input_sha256', {})
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
        self.request_mode = m.get('request_mode', 'legacy')
        if self.request_mode not in {'legacy', 'stable_conversation_v1'}:
            raise ExperimentError('Unknown request_mode')
        seen = set()
        for v in self.variants:
            if not SAFE_ID.fullmatch(str(v.get("id", ""))) or v["id"] in seen:
                raise ExperimentError("Variant IDs must be safe and unique")
            seen.add(v["id"])
            if not isinstance(v.get("model"), str) or "/" not in v["model"] or ":free" in v["model"]:
                raise ExperimentError("Every variant requires an exact paid model ID")
            if v["model"].split("/", 1)[0].lower() in {"openai", "anthropic", "google"}:
                raise ExperimentError("This experiment excludes OpenAI, Anthropic, and Google models")
            if v['model'] not in ALLOWED_MODELS or not v.get('canonical_slug'):
                raise ExperimentError('Exact approved model and canonical_slug are required')
            if not isinstance(v.get('price_cap'), dict) or not all(
                    isinstance(v['price_cap'].get(k), (int, float)) and v['price_cap'][k] > 0
                    for k in ['prompt', 'completion']):
                raise ExperimentError('Explicit positive per-million prompt/completion price caps required')
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
            if self.request_mode == 'stable_conversation_v1':
                systems = {self._system(s) for s in stages}
                if len(systems) != 1:
                    raise ExperimentError('Stable conversation requires identical system rules at every stage')
        self.max_workers = int(m.get("max_workers", 4))
        if not 1 <= self.max_workers <= 8:
            raise ExperimentError("max_workers must be between 1 and 8")
        self.max_cost = float(m.get("max_cost_usd", 100))
        self.reservation = float(m.get("max_call_cost_usd", 5))
        if not (math.isfinite(self.max_cost) and math.isfinite(self.reservation)
                and 0 < self.reservation <= self.max_cost):
            raise ExperimentError("Require 0 < max_call_cost_usd <= max_cost_usd")
        self.batch_authorization = m.get('batch_authorization')
        if self.batch_authorization is not None:
            self._validate_batch_authorization()
        elif self.max_cost > UNBATCHED_BUDGET_USD:
            raise ExperimentError(f'Without batch_authorization the API budget is at most USD {UNBATCHED_BUDGET_USD}')
        elif any(self.run_dir == path_in_repo(scope['run_dir'])
                 for scope in APPROVED_BATCH_SCOPES.values()):
            raise ExperimentError('The shared batch run directory requires batch_authorization')
        self.lock = threading.Lock()
        self.reserved = 0.0
        self.active_key_sha256 = None

    def _validate_batch_authorization(self):
        """Accept only an explicitly registered receipt and its exact batch scope."""
        auth = self.batch_authorization
        scope = APPROVED_BATCH_SCOPES.get(auth.get('approval_file')) if isinstance(auth, dict) else None
        if scope is None:
            self._validate_production_authorization(auth)
            return
        if self.run_dir != path_in_repo(scope['run_dir']):
            raise ExperimentError('Batch authorization requires the exact approved receipt and shared run directory')
        path = path_in_repo(auth['approval_file'], exists=True)
        if auth.get('approval_sha256') != sha(path.read_bytes()):
            raise ExperimentError('Missing or stale batch authorization hash')
        receipt = read_json(path)
        if not isinstance(receipt, dict):
            raise ExperimentError('Batch approval receipt must be an object')
        ids = receipt.get('selected_cluster_ids')
        if (receipt.get('status') != 'approved_topics_and_batch_plan'
                or receipt.get('publisher') != 'the publisher' or receipt.get('date') != scope['date']
                or type(receipt.get('api_budget_usd')) not in {int, float}
                or receipt['api_budget_usd'] != scope['budget'] or self.max_cost > scope['budget']
                or not isinstance(ids, list) or len(ids) != scope['count']
                or any(not isinstance(cid, str) or not re.fullmatch(r'b-[0-9]{4}', cid) for cid in ids)
                or len(set(ids)) != scope['count']):
            raise ExperimentError('Batch receipt must retain the approved publisher, status, date, budget and cluster IDs')
        if any(v.get('cluster_id') not in ids for v in self.variants):
            raise ExperimentError('Every batch variant requires an explicitly approved cluster_id')

    def _validate_production_authorization(self, auth):
        approval_file = auth.get('approval_file', '') if isinstance(auth, dict) else ''
        match = re.fullmatch(r'docs/workflow-v2/batches/([A-Za-z0-9][A-Za-z0-9_-]*)/brief-approval\.json',
                             approval_file) if isinstance(approval_file, str) else None
        if not match or self.run_dir != path_in_repo(f'runs/{match[1]}'):
            raise ExperimentError('Batch authorization requires the exact approved receipt and shared run directory')
        path = path_in_repo(approval_file, exists=True)
        if auth.get('approval_sha256') != sha(path.read_bytes()):
            raise ExperimentError('Missing or stale batch authorization hash')
        approval = read_json(path)
        proposal = path.with_name('publisher-proposal.json')
        if not isinstance(approval, dict) or not proposal.is_file():
            raise ExperimentError('Exact approved briefs and a batch API budget are required')
        budget = approval.get('api_budget_usd')
        if (approval.get('status') != 'approved' or not str(approval.get('publisher') or '').strip()
                or type(budget) not in {int, float} or not math.isfinite(budget) or not 0 < self.max_cost <= budget
                or approval.get('publisher_proposal_sha256') != sha(proposal.read_bytes())
                or approval.get('items') != read_json(proposal)):
            raise ExperimentError('Exact approved briefs and a batch API budget are required')
        items = approval.get('items')
        if not isinstance(items, list) or not items or any(not isinstance(item, dict) for item in items):
            raise ExperimentError('Approved brief items must be a nonempty list')
        ids = [item.get('cluster_id') for item in items]
        if (any(not isinstance(cid, str) or not re.fullmatch(r'b-[0-9]{4}', cid) for cid in ids)
                or len(ids) != len(set(ids)) or any(v.get('cluster_id') not in ids for v in self.variants)):
            raise ExperimentError('Every batch variant requires an explicitly approved cluster_id')

    def _input_path(self, value):
        path = path_in_repo(value, exists=True)
        if (path == SHARED_KEY_FILE.resolve() or path.name == ".env" or path.name.startswith(".env.")
                or path.suffix.lower() in {".pem", ".key"} or path.name in {"credentials", "credentials.json"}):
            raise ExperimentError("Credential/configuration file cannot be a model input")
        expected = self.input_hashes.get(str(path.relative_to(ROOT)))
        if not expected or sha(path.read_bytes()) != expected:
            raise ExperimentError('Missing or stale frozen input hash: ' + str(path.relative_to(ROOT)))
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

    def _system(self, stage):
        system_files = self.system_files + self._files(stage.get("system_files", []))
        system = "\n\n".join(f"SOURCE FILE: {p.relative_to(ROOT)}\n{p.read_text(encoding='utf-8')}" for p in system_files)
        # Recheck the top-level system inputs too when the executor is reused.
        for p in self.system_files:
            self._input_path(str(p.relative_to(ROOT)))
        return system or DEFAULT_SYSTEM

    def _legacy_messages(self, variant, stage):
        system = self._system(stage)
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
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _verified_prior_output(self, variant, stage, request):
        path = self.output_path(variant, stage)
        fp = self.fingerprint(request)
        if not self._resume(variant, stage, fp):
            raise ExperimentError(f"Missing, stale or altered prior-stage receipt/output: {variant['id']}:{stage['id']}")
        sidecar = read_json(path.with_suffix('.receipt.json'))
        # A sidecar alone is not a paid-generation record. Keep the original
        # attempt and request as the authority when replaying conversational turns.
        for receipt_path in (self.run_dir / 'variants' / variant['id'] / 'attempts').glob(stage['id'] + '-*/receipt.json'):
            if read_json(receipt_path) != sidecar:
                continue
            request_path = receipt_path.parent / 'request.json'
            if request_path.is_file() and read_json(request_path) == request:
                return path.read_text(encoding='utf-8')
        raise ExperimentError(f"Prior-stage attempt receipt/request verification failed: {variant['id']}:{stage['id']}")

    def _conversation_messages(self, variant, stage):
        stages = self.stages(variant)
        if stage not in stages:
            raise ExperimentError('Stable conversation stage must belong to the variant')
        system = self._system(stage)
        if any(self._system(s) != system for s in stages):
            raise ExperimentError('Stable conversation requires identical system rules at every stage')
        messages = [{'role': 'system', 'content': system}]
        sources = self._files(variant.get('input_files', []))
        if sources:
            messages.append({'role': 'user', 'content': '\n\n'.join(
                f"INPUT FILE: {p.relative_to(ROOT)}\n{p.read_text(encoding='utf-8')}" for p in sources)})
        for unit in stages:
            # Unit-specific context also precedes its prompt. Nothing is clipped
            # or summarized, including earlier outputs and qualifications.
            parts = [f"INPUT FILE: {p.relative_to(ROOT)}\n{p.read_text(encoding='utf-8')}"
                     for p in self._files(unit.get('input_files', []))]
            parts.append(self._input_path(unit['prompt_file']).read_text(encoding='utf-8'))
            messages.append({'role': 'user', 'content': '\n\n'.join(parts)})
            if unit == stage:
                return messages
            prior_request = self._request(variant, unit, list(messages))
            content = self._verified_prior_output(variant, unit, prior_request)
            messages.append({'role': 'assistant', 'content': content})

    def build_request(self, variant, stage):
        messages = (self._conversation_messages(variant, stage) if self.request_mode == 'stable_conversation_v1'
                    else self._legacy_messages(variant, stage))
        return self._request(variant, stage, messages)

    def _request(self, variant, stage, messages):
        if KEY_RE.search(''.join(message['content'] for message in messages)):
            raise ExperimentError("Credential-shaped text found in model input; request blocked")
        request = {
            "model": variant["model"],
            "provider": {"only": [variant["provider"]], "allow_fallbacks": False,
                         "require_parameters": True, "max_price": variant['price_cap']},
            "messages": messages,
            "max_tokens": stage["max_tokens"], "stream": False,
            "usage": {"include": True},
        }
        if "reasoning" in variant:
            request["reasoning"] = variant["reasoning"]
        if "reasoning" in stage:
            request["reasoning"] = stage["reasoning"]
        if "temperature" in self.manifest:
            request["temperature"] = self.manifest["temperature"]
        if stage.get("output_format") == "json":
            request["response_format"] = {"type": "json_object"}
        # UTF-8 byte length is a deliberately loose token upper bound; include
        # framing overhead. Refuse a call whose conservative cap exceeds reserve.
        input_bound = len(encoded(request['messages'])) + 4096
        upper = (input_bound * variant['price_cap']['prompt'] +
                 stage['max_tokens'] * variant['price_cap']['completion']) / 1_000_000
        if upper > self.reservation:
            raise ExperimentError(f'Per-call price upper bound {upper:.4f} exceeds reservation')
        return request

    def fingerprint(self, request):
        return sha(encoded({"revision": self.manifest["revision"], "request": request}))

    def attempts(self):
        return sorted((self.run_dir / "variants").glob("*/attempts/*/receipt.json"))

    def usage_summary(self):
        paths = self.attempts()
        receipts = [read_json(p) for p in paths]
        costs = [r.get("cost_usd") for r in receipts]
        reconciled, invalid = [], []
        for index, (path, cost) in enumerate(zip(paths, costs)):
            sidecar = path.parent / 'cost-reconciliation.json'
            if cost is not None or not sidecar.is_file():
                continue
            try:
                costs[index] = validate_charge_reconciliation(path, read_json(sidecar), expected_key_sha256=self.active_key_sha256)
                reconciled.append({'receipt': str(path.relative_to(ROOT)), 'cost_usd': costs[index],
                                   'proof_sha256': sha(sidecar.read_bytes())})
            except (ExperimentError, OSError, ValueError, KeyError, TypeError, AttributeError, InvalidOperation) as exc:
                invalid.append({'receipt': str(path.relative_to(ROOT)), 'error': redact(str(exc))})
        summary = {
            "attempts": len(receipts), "cost_usd": sum(c for c in costs if isinstance(c, (float, int))),
            "unknown_cost_attempts": sum(c is None and r.get("status") != "rejected" for c, r in zip(costs, receipts)),
            "prompt_tokens": sum(r.get("usage", {}).get("prompt_tokens", 0) or 0 for r in receipts),
            "completion_tokens": sum(r.get("usage", {}).get("completion_tokens", 0) or 0 for r in receipts),
            "successes": sum(r.get("status") == "success" for r in receipts),
            "failed": sum(r.get("status") != "success" for r in receipts),
            "pending_intents": sum(not (p.parent / "receipt.json").is_file()
                                   for p in (self.run_dir / "variants").glob("*/attempts/*/intent.json")),
        }
        if reconciled:
            summary['charge_reconciliations'] = reconciled
        if invalid:
            summary['invalid_charge_reconciliations'] = invalid
        return summary

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

    def _reserve(self):
        with self.lock:
            if self.batch_authorization is not None:
                self._validate_batch_authorization()
            summary = self.usage_summary()
            if summary["unknown_cost_attempts"]:
                raise ExperimentError("Prior charged/ambiguous request has unknown cost; reconcile before new paid calls")
            if summary["cost_usd"] + self.reserved + self.reservation > self.max_cost:
                raise ExperimentError("Experiment cost reservation limit reached")
            self.reserved += self.reservation

    def run_stage(self, variant, stage, key, *, retry_failed=False, transport=None):
        transport = transport or post_json
        self.active_key_sha256 = sha(key.encode())
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
        self._reserve()
        attempt = attempt_root / f"{stage['id']}-{len(prior) + 1:03d}"
        attempt.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        intent = {"variant": variant["id"], "stage": stage["id"], "fingerprint": fp,
                  "requested_model": variant["model"], "requested_provider": variant["provider"], "started_at": now()}
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
                self.reserved -= self.reservation
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
            key = blog_key(self.manifest.get("key_file"))
            self.active_key_sha256 = sha(key.encode())
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
