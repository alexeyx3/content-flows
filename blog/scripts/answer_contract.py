"""Check answer-plan references, not semantic truth. No network calls or writes."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_ID = re.compile(r"A-\d{2,}")


def enabled(job: Path) -> bool:
    path = job / "job.yaml"
    config = path.read_text(encoding="utf-8") if path.exists() else ""
    return bool(re.search(r"^answer_contract_version:\s*1\s*(?:#.*)?$", config, re.M)) and not bool(
        re.search(r"^article_(?:refresh|translation)_version:\s*1\b", config, re.M))


def tables(text: str, header: str) -> list[dict[str, str]]:
    """Read named Markdown tables, including escaped pipes in exact excerpts."""
    def cells(line):
        return [v.strip().replace(r"\|", "|")
                for v in re.split(r"(?<!\\)\|", line.strip().strip("|"))]

    rows, columns = [], None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            columns = None
            continue
        values = cells(line)
        if header in values and index + 1 < len(lines):
            sep = cells(lines[index + 1])
            if len(sep) == len(values) and all(re.fullmatch(r":?-{3,}:?", v) for v in sep):
                columns = values
                continue
        if columns and len(values) == len(columns) and not all(
                re.fullmatch(r":?-{3,}:?", v) for v in values):
            rows.append(dict(zip(columns, values, strict=True)))
    return rows


def ids(value: str) -> set[str]:
    return {x.strip().strip("`") for x in value.split(",") if x.strip() not in {"", "-", "—"}}


def plan_errors(job: Path) -> list[str]:
    if not enabled(job):
        return []
    try:
        plan = json.loads((job / "sections.json").read_text(encoding="utf-8"))
        sections, checks = plan["sections"], plan["answer_checks"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"answer contract: sections.json needs sections and answer_checks ({exc})"]
    if not isinstance(sections, list) or not isinstance(checks, list) or not checks:
        return ["answer contract: needs a nonempty answer_checks list and a sections list"]
    known = {s.get("id") for s in sections if isinstance(s, dict) and isinstance(s.get("id"), str)}
    errors, seen = [], set()
    for index, row in enumerate(checks, 1):
        if not isinstance(row, dict):
            errors.append(f"answer check {index}: expected an object")
            continue
        aid = row.get("id")
        if not isinstance(aid, str) or not CHECK_ID.fullmatch(aid):
            errors.append(f"answer check {index}: needs A-xx id")
        elif aid in seen:
            errors.append(f"answer contract: duplicate {aid}")
        else:
            seen.add(aid)
        if not isinstance(row.get("section_id"), str) or row["section_id"] not in known:
            errors.append(f"{aid}: unknown section_id")
        for name in ("question", "answer_needed"):
            if not isinstance(row.get(name), str) or not row[name].strip():
                errors.append(f"{aid}: needs {name}")
        qualifiers = row.get("qualifiers")
        if not isinstance(qualifiers, list) or any(not isinstance(q, str) or not q.strip() for q in qualifiers):
            errors.append(f"{aid}: qualifiers must be a string list (may be empty)")
    return errors


def evidence_errors(job: Path) -> list[str]:
    if not enabled(job):
        return []
    errors = plan_errors(job)
    if errors:
        return errors
    checks = {c["id"] for c in json.loads((job / "sections.json").read_text())["answer_checks"]}
    try:
        rows = tables((job / "evidence.md").read_text(encoding="utf-8"), "claim_id")
    except OSError as exc:
        return [f"answer contract: missing evidence ({exc})"]
    supported = set()
    claim_ids = set()
    for row in rows:
        mapped = ids(row.get("answer_check_ids", ""))
        if not mapped:
            continue
        cid = row.get("claim_id", "")
        if not cid or cid in claim_ids:
            errors.append(f"answer contract: missing or duplicate claim_id {cid}")
        claim_ids.add(cid)
        if mapped - checks:
            errors.append(f"{cid}: unknown answer_check_ids {sorted(mapped - checks)}")
        # Rejected evidence remains audit trail; it cannot fulfil an answer.
        if not re.match(r"^(?:supports|partial)\b", row.get("entailment_verdict", ""), re.I):
            continue
        if not re.search(r"https?://[^\s<>]+", row.get("source_url", "")) or \
                not row.get("supporting_quote", "").strip(" -—") or not row.get("claim", "").strip(" -—"):
            errors.append(f"{cid}: mapped evidence needs claim, source_url and supporting_quote")
            continue
        supported.update(mapped & checks)
    for aid in sorted(checks - supported):
        errors.append(f"{aid}: no supported scoped evidence mapping; resolve before writing")
    return errors


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def excerpt_in_heading(text: str, heading: str, excerpt: str) -> bool:
    headings = list(re.finditer(r"^(#{1,4})\s+(.+?)\s*$", text, re.M))
    for index, match in enumerate(headings):
        if match.group(2) != heading:
            continue
        end = next((h.start() for h in headings[index + 1:]
                    if len(h.group(1)) <= len(match.group(1))), len(text))
        if normalized(excerpt) in normalized(text[match.end():end]):
            return True
    return False


def qa_errors(job: Path) -> list[str]:
    if not enabled(job):
        return []
    errors = evidence_errors(job)
    if errors:
        return errors
    try:
        report = (job / "qa_report.md").read_text(encoding="utf-8")
        text = (job / "edited.md").read_text(encoding="utf-8")
        evidence = tables((job / "evidence.md").read_text(encoding="utf-8"), "claim_id")
        checks = json.loads((job / "sections.json").read_text())["answer_checks"]
    except (OSError, ValueError) as exc:
        return [f"answer contract: missing final review materials ({exc})"]
    known = {c["id"] for c in checks}
    seen = set()
    for row in tables(report, "answer_check_id"):
        aid = row.get("answer_check_id")
        if aid not in known or aid in seen:
            errors.append(f"answer QA: unknown or duplicate answer_check_id {aid}")
            continue
        seen.add(aid)
        allowed = {e["claim_id"] for e in evidence if aid in ids(e.get("answer_check_ids", ""))
                   and re.match(r"^(?:supports|partial)\b", e.get("entailment_verdict", ""), re.I)}
        used = ids(row.get("evidence_ids", ""))
        if not used or not used <= allowed:
            errors.append(f"{aid}: QA evidence_ids do not match its supported evidence")
        if row.get("verdict") not in {"PASS", "NOTE"} or not row.get("note", "").strip():
            errors.append(f"{aid}: answer QA needs PASS/NOTE with semantic-review note")
        excerpt = row.get("article_excerpt", "")
        if not excerpt or not excerpt_in_heading(text, row.get("article_heading", ""), excerpt):
            errors.append(f"{aid}: QA excerpt is absent from its actual article_heading")
    for aid in sorted(known - seen):
        errors.append(f"{aid}: missing answer QA row")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--target", choices=("brief", "inputs", "qa"), default="inputs")
    args = ap.parse_args()
    job = Path(args.job).resolve()
    errors = {"brief": plan_errors, "inputs": evidence_errors, "qa": qa_errors}[args.target](job)
    if errors:
        raise SystemExit("BLOCK:\n- " + "\n- ".join(errors))
    print("Answer contract references: OK; semantic truth and completeness still require independent QA")


if __name__ == "__main__":
    main()
