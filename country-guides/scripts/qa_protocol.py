"""Versioned QA findings and explicit reconsiderations. No model or network calls.

Validation proves artifact consistency, not factual truth or editorial judgment.
History contains immutable article/review/report snapshots; packets bind a claim
to one parent, so sealing a review never changes that claim's fingerprint.
"""
from __future__ import annotations

import argparse
import difflib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from contextlib import contextmanager


class ProtocolError(ValueError):
    pass


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> dict:
    if path.is_symlink():
        raise ProtocolError(f"Symlink is not a QA artifact: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProtocolError(f"Expected QA object: {path}")
    return value


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ProtocolError(f"Symlink is not a QA artifact: {path}")
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stream.write(data)
        temporary = Path(stream.name)
    temporary.replace(path)


def version(job: Path) -> str:
    text = (job / "job.yaml").read_text(encoding="utf-8")
    values = re.findall(r"^qa_protocol\s*:\s*([^#\n]*)", text, re.M)
    if len(values) > 1:
        raise ProtocolError("Duplicate qa_protocol setting")
    value = values[0].strip().strip("\"'") if values else ""
    if values and value != "v1":
        raise ProtocolError(f"Unsupported qa_protocol: {value!r}")
    return value


@contextmanager
def locked(history: Path):
    history.mkdir(parents=True, exist_ok=True)
    with (history / ".lock").open("a") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        yield


def _text(obj: dict, name: str) -> str:
    value = obj.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"Missing nonempty {name}")
    return value


def _items(value, field: str) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
        raise ProtocolError(f"{field} must be a list of objects")
    return value


def _by_id(items: list[dict], pattern: str) -> dict:
    result = {}
    for item in items:
        identifier = item.get("id", "")
        if not isinstance(identifier, str) or not re.fullmatch(pattern, identifier) or identifier in result:
            raise ProtocolError(f"Invalid/duplicate QA ID: {identifier!r}")
        result[identifier] = item
    return result


def _anchor(passage: str, article: str) -> None:
    if not passage or passage not in article:
        raise ProtocolError("QA passage must occur exactly in current article")


def advance(packet: dict, review: dict, article: str) -> tuple[dict, dict]:
    """Validate current decisions against a frozen parent and return merged state."""
    if review.get("schema_version") != 1 or packet.get("schema_version") != 1:
        raise ProtocolError("Unsupported QA protocol schema")
    for key in ("article_sha256", "parent_review_sha256", "policy_sha256"):
        if review.get(key) != packet.get(key):
            raise ProtocolError(f"QA {key} does not match claimed context")
    if review.get("article_sha256") != sha(article.encode("utf-8")):
        raise ProtocolError("QA article hash is stale")
    if review.get("whole_article_coverage_checked") is not True:
        raise ProtocolError("Whole-article coverage must be checked in every QA")
    _text(review, "scope")
    if review.get("overall") not in {"PASS", "BLOCK"}:
        raise ProtocolError("QA overall must be PASS or BLOCK")
    old = packet["prior_findings"]
    decisions = _by_id(_items(review.get("decisions"), "decisions"), r"Q-\d{4,}")
    if set(decisions) != set(old):
        raise ProtocolError("Every previous finding ID requires exactly one decision")
    current = {}
    for identifier, prior in old.items():
        decision = decisions[identifier]
        if any(key in decision for key in ("rule_id", "acceptance_condition", "description", "severity", "category")):
            raise ProtocolError("A decision cannot redefine the original finding")
        status = decision.get("status")
        if status not in {"open", "resolved", "withdrawn", "reopened"}:
            raise ProtocolError(f"Invalid finding status: {identifier}")
        _text(decision, "reason")
        if prior["status"] in {"resolved", "withdrawn"} and status == "open":
            raise ProtocolError("Use reopened with an explicit reversal_reason")
        if (status == "reopened" or status == "withdrawn" and prior["status"] != status
                or prior["status"] in {"resolved", "withdrawn"} and status != prior["status"]):
            _text(decision, "reversal_reason")
        if status in {"open", "reopened"}:
            _anchor(_text(decision, "passage"), article)
        elif decision.get("passage"):
            _anchor(_text(decision, "passage"), article)
        current[identifier] = {**prior, "status": status, "current_passage": decision.get("passage", ""),
                               "decision_reason": decision["reason"]}
    added = _by_id(_items(review.get("new_findings"), "new_findings"), r"Q-\d{4,}")
    if set(added) & set(old):
        raise ProtocolError("Existing finding cannot be resubmitted as new")
    identities = {(p["rule_id"], passage) for p in old.values()
                  for passage in (p["original_passage"], p.get("current_passage", "")) if passage}
    for identifier, finding in added.items():
        for key in ("rule_id", "section", "passage", "description", "acceptance_condition"):
            _text(finding, key)
        _anchor(finding["passage"], article)
        if finding.get("severity") not in {"critical", "major", "minor"}:
            raise ProtocolError("Finding severity must be critical, major or minor")
        if finding.get("category") not in {"factual", "coverage", "editorial", "style"}:
            raise ProtocolError("Invalid finding category")
        if not isinstance(finding.get("evidence_ids"), list) or any(not isinstance(v, str) or not v for v in finding["evidence_ids"]):
            raise ProtocolError("evidence_ids must be a list of nonempty strings")
        if finding["category"] in {"factual", "coverage"} and not finding["evidence_ids"]:
            raise ProtocolError("Factual/coverage finding needs evidence IDs")
        identity = (finding["rule_id"], finding["passage"])
        if identity in identities:
            raise ProtocolError("Same rule/passage must retain its existing finding ID")
        identities.add(identity)
        current[identifier] = {**finding, "original_passage": finding["passage"],
                               "current_passage": finding["passage"], "status": "open",
                               "first_seen_article_sha256": review["article_sha256"]}
    previous = packet["prior_adjudications"]
    audits = _by_id(_items(review.get("contrast_audit"), "contrast_audit"), r"C-\d{4,}")
    if not set(previous) <= set(audits):
        raise ProtocolError("Every previous contrast adjudication requires a current entry")
    old_passages = {v["passage"]: k for k, v in previous.items()}
    for identifier, item in audits.items():
        passage = _text(item, "passage")
        decision = item.get("decision")
        if decision not in {"count", "exclude", "absent"}:
            raise ProtocolError("Contrast decision must be count, exclude or absent")
        _text(item, "reason")
        prior = previous.get(identifier)
        if prior:
            if passage != prior["passage"]:
                raise ProtocolError("A contrast ID cannot change its original passage")
            if decision != prior["decision"] and decision != "absent":
                _text(item, "reversal_reason")
        elif passage in old_passages or decision == "absent":
            raise ProtocolError("Existing contrast passage must keep its original ID")
        if decision == "absent":
            if passage in article:
                raise ProtocolError("Contrast marked absent still occurs in current article")
        else:
            _anchor(passage, article)
        if decision == "count":
            for key in ("rejected", "affirmed", "slot"):
                _text(item, key)
            if item["rejected"] not in passage or item["affirmed"] not in passage:
                raise ProtocolError("Counted contrast must quote both components within its passage")
        if not prior and passage in {a["passage"] for k, a in audits.items() if k != identifier}:
            raise ProtocolError("Duplicate contrast passage")
    quotes = review.get("quote_pair_count")
    if type(quotes) is not int or quotes < 0:
        raise ProtocolError("quote_pair_count must be a nonnegative integer")
    has_blocker = any(f["status"] in {"open", "reopened"} and f["severity"] in {"critical", "major"}
                      for f in current.values())
    if review["overall"] == "PASS" and has_blocker:
        raise ProtocolError("PASS contradicts open major/critical blockers")
    if review["overall"] == "BLOCK" and not has_blocker:
        raise ProtocolError("BLOCK requires a specific active major/critical defect")
    return current, audits


def state(history: Path) -> dict:
    """Read and verify the complete immutable parent chain, never old live outputs."""
    if not (history / "latest.json").exists():
        if history.exists() and any(re.fullmatch(r"[a-f0-9]{64}", p.name) for p in history.iterdir()):
            raise ProtocolError("QA history has snapshots without a latest pointer")
        return {"parent": None, "findings": {}, "adjudications": {}, "references": {}}
    latest = load(history / "latest.json").get("review_sha256")
    chain = []; seen = set(); cursor = latest
    while cursor is not None:
        if not isinstance(cursor, str) or not re.fullmatch(r"[a-f0-9]{64}", cursor) or cursor in seen:
            raise ProtocolError("Invalid/cyclic QA history pointer")
        seen.add(cursor);directory = history / cursor
        if directory.is_symlink():
            raise ProtocolError("Symlink in QA history")
        manifest = load(directory / "snapshot.json")
        for name in ("article.md", "review.json", "report.md"):
            path = directory / name
            if path.is_symlink() or sha(path.read_bytes()) != manifest.get(name):
                raise ProtocolError("QA history snapshot hash mismatch")
        if manifest["review.json"] != cursor:
            raise ProtocolError("QA history review hash mismatch")
        review = load(directory / "review.json")
        chain.append((directory, review));cursor = review.get("parent_review_sha256")
    actual = {p.name for p in history.iterdir() if re.fullmatch(r"[a-f0-9]{64}", p.name)}
    if actual != seen:
        raise ProtocolError("QA history has an orphan/fork; reconcile explicitly")
    findings = {};adjudications = {};refs = {}
    for directory, review in reversed(chain):
        article = (directory / "article.md").read_bytes().decode("utf-8")
        packet = {"schema_version": 1, "article_sha256": sha(article.encode()),
                  "parent_review_sha256": review.get("parent_review_sha256"),
                  "policy_sha256": review.get("policy_sha256"),
                  "prior_findings": findings, "prior_adjudications": adjudications}
        findings, adjudications = advance(packet, review, article)
        for name in ("article.md", "review.json", "report.md", "snapshot.json"):
            p = (directory / name).resolve();refs[str(p)] = sha(p.read_bytes())
    directory = chain[0][0]
    return {"parent": latest, "findings": findings, "adjudications": adjudications, "references": refs,
            "previous_article": str((directory / "article.md").resolve()),
            "previous_report": str((directory / "report.md").resolve()),
            "previous_review": str((directory / "review.json").resolve())}


def prepare(article: Path, history: Path, packet_path: Path, policy: Path, *, mode: str = "qa") -> dict:
    if mode not in {"qa", "editor"}:
        raise ProtocolError("Unknown QA context mode")
    with locked(history):
        prior = state(history)
        if article.is_symlink() or policy.is_symlink():
            raise ProtocolError("Symlink input is not allowed")
        if mode == "qa" and not article.is_file():
            raise ProtocolError("QA requires current article")
        now = article.read_bytes() if article.exists() else b""
        delta = packet_path.with_suffix(".diff")
        before = Path(prior["previous_article"]).read_bytes() if prior["parent"] else b""
        delta.parent.mkdir(parents=True, exist_ok=True)
        if delta.is_symlink():
            raise ProtocolError("Symlink QA diff is not allowed")
        delta.write_text("".join(difflib.unified_diff(before.decode().splitlines(keepends=True),
                         now.decode().splitlines(keepends=True), fromfile="previous-qa/article.md", tofile="current/article.md")))
        refs = {**prior["references"], str(delta.resolve()): sha(delta.read_bytes())}
        packet = {"schema_version": 1, "mode": mode, "article_sha256": sha(now),
                  "parent_review_sha256": prior["parent"], "policy_sha256": sha(policy.read_bytes()),
                  "prior_findings": prior["findings"], "prior_adjudications": prior["adjudications"],
                  "previous_article": prior.get("previous_article"), "previous_report": prior.get("previous_report"),
                  "previous_review": prior.get("previous_review"), "diff": str(delta.resolve()), "references": refs}
        if mode == "qa":
            packet["review_template"] = {
                "schema_version": 1, **{k: packet[k] for k in ("article_sha256", "parent_review_sha256", "policy_sha256")},
                "overall": None, "scope": "", "whole_article_coverage_checked": False,
                "quote_pair_count": None,
                "decisions": [{"id": k, "status": None, "passage": "", "reason": ""} for k in prior["findings"]],
                "new_findings": [],
                "contrast_audit": [{"id": k, "passage": v["passage"], "decision": None, "reason": ""}
                                   for k, v in prior["adjudications"].items()],
            }
        write(packet_path, packet)
        return packet


def packet_digest(packet_path: Path) -> str:
    packet = load(packet_path)
    for filename, expected in packet.get("references", {}).items():
        path = Path(filename)
        if path.is_symlink() or sha(path.read_bytes()) != expected:
            raise ProtocolError("QA context reference hash mismatch")
    return sha(packet_path.read_bytes())


def validate(article: Path, review_path: Path, report: Path, packet_path: Path) -> tuple[dict, dict]:
    packet_digest(packet_path)
    if article.is_symlink():
        raise ProtocolError("Symlink article is not allowed")
    packet = load(packet_path)
    if packet.get("mode") != "qa":
        raise ProtocolError("Review requires a QA-mode context")
    review = load(review_path)
    result = advance(packet, review, article.read_bytes().decode("utf-8"))
    if report.is_symlink() or report.read_text(encoding="utf-8").splitlines()[0].strip() != f"Overall: {review['overall']}":
        raise ProtocolError("QA report first line disagrees with structured review")
    return result


def seal(article: Path, review: Path, report: Path, packet: Path, history: Path) -> str:
    with locked(history):
        validate(article, review, report, packet)
        latest = state(history)["parent"];data = review.read_bytes();key = sha(data)
        if latest == key:  # complete(BLOCK) followed by block(), same immutable round
            if (history / key / "article.md").read_bytes() != article.read_bytes() or (history / key / "report.md").read_bytes() != report.read_bytes():
                raise ProtocolError("Cannot replace an already sealed QA snapshot")
            return key
        if latest != load(packet).get("parent_review_sha256"):
            raise ProtocolError("QA history advanced after claim")
        directory = history / key
        temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=history))
        try:
            for source, name in [(article, "article.md"), (review, "review.json"), (report, "report.md")]:
                shutil.copyfile(source, temporary / name)
            write(temporary / "snapshot.json", {n: sha((temporary / n).read_bytes()) for n in ("article.md", "review.json", "report.md")})
            temporary.rename(directory)
            write(history / "latest.json", {"review_sha256": key})
        finally:
            if temporary.exists():shutil.rmtree(temporary)
        return key


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "validate", "seal"])
    parser.add_argument("--article", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--mode", choices=["qa", "editor"], default="qa")
    args = parser.parse_args(argv)
    try:
        if args.action == "prepare":
            if not args.history or not args.policy:raise ProtocolError("prepare needs --history and --policy")
            prepare(args.article, args.history, args.context, args.policy, mode=args.mode)
        else:
            if not args.review or not args.report:raise ProtocolError("validate/seal need --review and --report")
            if args.action == "seal":
                if not args.history:raise ProtocolError("seal needs --history")
                seal(args.article, args.review, args.report, args.context, args.history)
            else:validate(args.article, args.review, args.report, args.context)
    except (OSError, ValueError, KeyError, IndexError) as exc:
        print(f"BLOCK: {exc}")
        return 2
    print("PASS: QA artifact consistency (semantic review remains required)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
