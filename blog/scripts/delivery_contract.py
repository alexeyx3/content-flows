"""Validate selected delivery references and reviewer records, not semantic delivery.

No network, generation or writes. Only batch_delivery_contract_version: 1 opts in;
refresh and translation contracts are never migrated by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from answer_contract import excerpt_in_heading, ids, tables

CHECK_ID = re.compile(r"DLV-\d{2,}")
KINDS = {"table", "internal_link", "source_qualifier", "wording", "other"}
AUDIT_INPUTS = ("brief.md", "sections.json", "evidence.md", "qa_report.md")


def enabled(job: Path) -> bool:
    path = job / "job.yaml"
    config = path.read_text(encoding="utf-8") if path.exists() else ""
    return bool(re.search(r"^batch_delivery_contract_version:\s*1\s*(?:#.*)?$", config, re.M)) and not bool(
        re.search(r"^article_(?:refresh|translation)_version:\s*1\b", config, re.M))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_plan(job: Path):
    return json.loads((job / "sections.json").read_text(encoding="utf-8"))


def plan_errors(job: Path) -> list[str]:
    if not enabled(job):
        return []
    try:
        plan = load_plan(job)
        brief = (job / "brief.md").read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        return [f"delivery contract: missing/invalid brief plan ({exc})"]
    if not isinstance(plan, dict) or not isinstance(plan.get("sections"), list) or not isinstance(plan.get("delivery_checks"), list):
        return ["delivery contract: sections.json needs sections and delivery_checks lists"]
    sections = {s.get("id"): s for s in plan["sections"]
                if isinstance(s, dict) and nonempty(s.get("id"))}
    errors, seen = [], set()
    for section in plan["sections"]:
        if not isinstance(section, dict) or not nonempty(section.get("id")) or not nonempty(section.get("title")):
            errors.append("delivery contract: approved sections need string id and title")
            continue
        subheadings = section.get("subheadings") or []
        if not isinstance(subheadings, list) or any(
                not isinstance(h, dict) or not nonempty(h.get("title")) for h in subheadings):
            errors.append("delivery contract: approved subheadings need a title list")
    if not plan["delivery_checks"]:
        review = plan.get("delivery_review")
        if not isinstance(review, dict) or not all(nonempty(review.get(k)) for k in ("reviewer", "no_additional_obligations")):
            errors.append("delivery contract: empty checks need delivery_review.reviewer and explicit no_additional_obligations explanation")
    for number, check in enumerate(plan["delivery_checks"], 1):
        if not isinstance(check, dict):
            errors.append(f"delivery check {number}: expected an object")
            continue
        cid = check.get("id")
        if not isinstance(cid, str) or not CHECK_ID.fullmatch(cid):
            errors.append(f"delivery check {number}: needs stable DLV-xx id")
        elif cid in seen:
            errors.append(f"delivery contract: duplicate {cid}")
        else:
            seen.add(cid)
        sid = check.get("section_id")
        if not isinstance(sid, str) or sid not in sections:
            errors.append(f"{cid}: unknown section_id")
        if not isinstance(check.get("kind"), str) or check["kind"] not in KINDS:
            errors.append(f"{cid}: invalid delivery kind")
        if not nonempty(check.get("requirement")):
            errors.append(f"{cid}: needs a concrete requirement")
        if type(check.get("evidence_required")) is not bool or (check.get("kind") == "source_qualifier" and check.get("evidence_required") is not True):
            errors.append(f"{cid}: needs evidence_required boolean; source_qualifier must require evidence")
        basis = check.get("basis")
        if (not isinstance(basis, dict) or not nonempty(basis.get("brief_heading"))
                or not nonempty(basis.get("brief_excerpt"))
                or not excerpt_in_heading(brief, basis["brief_heading"], basis["brief_excerpt"])):
            errors.append(f"{cid}: selected-brief basis excerpt is absent from its brief_heading")
    return errors


def mapped_evidence(job: Path):
    return tables((job / "evidence.md").read_text(encoding="utf-8"), "claim_id")


def evidence_errors(job: Path) -> list[str]:
    if not enabled(job):
        return []
    errors = plan_errors(job)
    if errors:
        return errors
    checks = {c["id"]: c for c in load_plan(job)["delivery_checks"]}
    try:
        rows = mapped_evidence(job)
    except OSError as exc:
        return [f"delivery contract: missing evidence ({exc})"]
    supported, seen_claims = set(), set()
    for row in rows:
        mapped = ids(row.get("delivery_check_ids", ""))
        if not mapped:
            continue
        claim = row.get("claim_id", "")
        if not claim or claim in seen_claims:
            errors.append(f"delivery evidence: missing/duplicate claim_id {claim}")
        seen_claims.add(claim)
        if mapped - checks.keys():
            errors.append(f"{claim}: unknown delivery_check_ids {sorted(mapped - checks.keys())}")
        if not re.match(r"^(?:supports|partial)\b", row.get("entailment_verdict", ""), re.I):
            continue
        if (not re.search(r"https?://[^\s<>]+", row.get("source_url", ""))
                or not row.get("claim", "").strip(" -—") or not row.get("supporting_quote", "").strip(" -—")):
            errors.append(f"{claim}: delivery evidence needs claim, source_url and supporting_quote")
            continue
        supported.update(mapped & checks.keys())
    for cid, check in checks.items():
        if check["evidence_required"] and cid not in supported:
            errors.append(f"{cid}: no supported delivery evidence mapping; resolve before writing")
    return errors


def qa_errors(job: Path) -> list[str]:
    if not enabled(job):
        return []
    errors = evidence_errors(job)
    if errors:
        return errors
    try:
        audit = json.loads((job / "qa_delivery.json").read_text(encoding="utf-8"))
        text = (job / "edited.md").read_text(encoding="utf-8")
        report = (job / "qa_report.md").read_text(encoding="utf-8")
        current = {name: digest(job / name) for name in AUDIT_INPUTS}
    except (OSError, ValueError) as exc:
        return [f"delivery QA: missing/invalid current audit materials ({exc})"]
    if not isinstance(audit, dict):
        return ["delivery QA: qa_delivery.json must be an object"]
    if type(audit.get("schema_version")) is not int or audit["schema_version"] != 1 or audit.get("article_sha256") != digest(job / "edited.md") or audit.get("input_sha256") != current:
        errors.append("delivery QA: stale audit hash/schema; review the exact current article and inputs")
    reviewers = re.findall(r"^delivery_reviewer:[ \t]*(\S.*?)[ \t]*$", report, re.M)
    if not nonempty(audit.get("reviewer")) or reviewers != [audit.get("reviewer")]:
        errors.append("delivery QA: reviewer must match the single delivery_reviewer in qa_report.md")
    if not nonempty(audit.get("summary")):
        errors.append("delivery QA: needs semantic-review summary, including any reviewed empty selection")
    rows = audit.get("checks")
    if not isinstance(rows, list):
        return errors + ["delivery QA: needs complete checks list"]
    plan = load_plan(job)
    checks = {c["id"]: c for c in plan["delivery_checks"]}
    sections = {s["id"]: s for s in plan["sections"] if isinstance(s, dict) and "id" in s}
    evidence = mapped_evidence(job)
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] not in checks:
            errors.append("delivery QA: unknown/invalid check row")
            continue
        cid = row["id"]
        if cid in seen:
            errors.append(f"delivery QA: duplicate {cid}")
        seen.add(cid)
        if row.get("verdict") != "PASS" or not nonempty(row.get("reason")):
            errors.append(f"{cid}: unresolved delivery requirement; needs PASS and substantive reason")
        check = checks[cid]
        section = sections[check["section_id"]]
        allowed_headings = {section.get("title", "")} | {
            h.get("title", "") for h in (section.get("subheadings") or []) if isinstance(h, dict)}
        heading, excerpt = row.get("article_heading"), row.get("article_excerpt")
        if (not nonempty(heading) or heading not in allowed_headings or not nonempty(excerpt)
                or not excerpt_in_heading(text, heading, excerpt)
                or not excerpt_in_heading(text, section.get("title", ""), excerpt)):
            errors.append(f"{cid}: actual excerpt/heading is absent from its approved section")
        used = row.get("evidence_ids")
        allowed = {r["claim_id"] for r in evidence if cid in ids(r.get("delivery_check_ids", ""))
                   and re.match(r"^(?:supports|partial)\b", r.get("entailment_verdict", ""), re.I)}
        if (not isinstance(used, list) or any(not isinstance(e, str) for e in used)
                or not set(used) <= allowed or (check["evidence_required"] and not used)):
            errors.append(f"{cid}: QA evidence_ids must reference its supported delivery evidence")
    for cid in sorted(checks.keys() - seen):
        errors.append(f"{cid}: missing delivery QA row")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", type=Path, required=True)
    ap.add_argument("--target", choices=("brief", "inputs", "qa"), default="inputs")
    args = ap.parse_args()
    errors = {"brief": plan_errors, "inputs": evidence_errors, "qa": qa_errors}[args.target](args.job.resolve())
    if errors:
        raise SystemExit("BLOCK:\n- " + "\n- ".join(errors))
    print("Delivery references: OK; semantic fulfilment and source qualifications require native QA")


if __name__ == "__main__":
    main()
