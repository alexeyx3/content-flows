"""Validate a writer-facing blog brief and section contract before drafting."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from article_materials import is_v2
from answer_contract import plan_errors as answer_plan_errors
from delivery_contract import plan_errors as delivery_plan_errors
from package_article import extract_metadata, validate as validate_metadata
from validate_research_discovery import validate as validate_research_discovery
from validate_primary_data_research import (
    enabled as primary_data_enabled,
    validate as validate_primary_data_research,
)
from validate_research_map import validate as validate_research_map
from validate_study_research import validate as validate_study_research
from validate_quote_research import validate as validate_quote_research
from topic_overlap import decision_errors, resolved_query

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"[a-z0-9-]+")
LENGTH_HEADING = re.compile(
    r"^#{1,6}\s+(?:\d+[a-z]?\.\s*)?(?:length|word count|target length|объ[её]м)\b",
    re.I | re.M,
)
WORD_TARGET = re.compile(
    r"\b(?:word budget|target length|word-count target|word count target)\b"
    r"|\b(?:budget|target|aim|write|about|around|approximately)?\s*"
    r"\d[\d,]*(?:\s*(?:-|–|—|to)\s*\d[\d,]*)?\s+words?\b",
    re.I,
)


def validate(job: Path) -> list[str]:
    problems: list[str] = []
    problems.extend(answer_plan_errors(job))
    problems.extend(delivery_plan_errors(job))
    problems.extend(validate_research_discovery(job))
    problems.extend(validate_primary_data_research(job))
    problems.extend(validate_research_map(job))
    problems.extend(validate_study_research(job))
    problems.extend(validate_quote_research(job))
    brief_path = job / "brief.md"
    sections_path = job / "sections.json"
    if not brief_path.exists():
        problems.append("missing brief.md")
    if not sections_path.exists():
        problems.append("missing sections.json")
    if problems:
        return problems

    brief = brief_path.read_text(encoding="utf-8")
    config_text = (job / "job.yaml").read_text(encoding="utf-8") if (job / "job.yaml").exists() else ""
    if re.search(r"^duplicate_preflight_version:\s*1\b", config_text, re.M):
        cluster = re.search(r'^temnik_cluster_id:\s*["\']?([^\s"\']+)', config_text, re.M)
        topic = re.search(r'^topic:\s*["\']?(.*?)["\']?\s*(?:#.*)?$', config_text, re.M)
        query = resolved_query(brief)
        if not cluster or not topic or not query:
            problems.append("overlap preflight needs temnik cluster, topic and brief primary query")
        else:
            problems.extend(decision_errors(cluster.group(1), "resolved", topic.group(1).strip().strip('"\''), query))
    if LENGTH_HEADING.search(brief) or WORD_TARGET.search(brief):
        problems.append("brief.md exposes a word-count or length target to the writer")

    try:
        payload = json.loads(sections_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return problems + [f"sections.json is invalid JSON: {exc}"]
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list) or not sections:
        problems.append("sections.json must contain at least one section")
        return problems
    metadata = extract_metadata(brief)
    if metadata:
        metadata["title"] = str(payload.get("title", ""))
        article_type_match = re.search(r"^article_type:\s*([^\s#]+)", config_text, re.M)
        article_type = article_type_match.group(1).strip("\"'").lower() if article_type_match else None
        problems.extend(validate_metadata(metadata, article_type))

    if is_v2(job):
        research = job / "research.md"
        if not research.exists() or not research.read_text(encoding="utf-8").strip():
            problems.append("workflow v2 requires research.md before the brief")
        gains = payload.get("information_gain", [])
        ids = {s.get("id") for s in sections if isinstance(s, dict)}
        if not gains:
            problems.append("workflow v2 requires information_gain")
        for gain in gains:
            if gain.get("section_id") not in ids or not gain.get("reader_value") or not gain.get("research_ref"):
                problems.append("information_gain needs section_id, reader_value and research_ref")
        for name in ("visual_candidates", "expert_questions"):
            if not isinstance(payload.get(name), list):
                problems.append(f"workflow v2 requires {name} list (may be empty with an explanation in the brief)")

        config = (job / "job.yaml").read_text(encoding="utf-8")
        if re.search(r"^geographic_audit_version:\s*1\b", config, re.M):
            geo = payload.get("geographic_audit")
            if not isinstance(geo, dict) or not all(
                isinstance(geo.get(key), str) and geo[key].strip()
                for key in ("intended_scope", "jurisdiction_selection", "source_scope_risk")
            ):
                problems.append("geographic_audit needs intended_scope, jurisdiction_selection and source_scope_risk")

        if primary_data_enabled(job) and (job / "research.data.json").exists():
            data = json.loads((job / "research.data.json").read_text(encoding="utf-8"))
            read_ids = {
                c.get("id") for c in data.get("candidates", [])
                if isinstance(c, dict) and c.get("status") == "read_original"
            }
            chart_ids = {
                c.get("id") for c in data.get("candidates", [])
                if isinstance(c, dict) and c.get("status") == "read_original"
                and c.get("chart_status") == "chartable"
            }
            audit = payload.get("visual_audit")
            if not isinstance(audit, dict):
                problems.append("primary data jobs need sections.json visual_audit")
            else:
                considered = audit.get("considered_data_ids")
                selected = audit.get("selected_chart_ids")
                if (not isinstance(considered, list) or
                        not all(isinstance(x, str) for x in considered) or
                        set(considered) != read_ids):
                    problems.append("visual_audit must consider every read_original data candidate")
                if (not isinstance(selected, list) or
                        not all(isinstance(x, str) for x in selected) or
                        not set(selected) <= chart_ids):
                    problems.append("visual_audit selected_chart_ids must refer to chartable originals")
                if not str(audit.get("decision", "")).strip():
                    problems.append("visual_audit needs a chart selection or omission reason")
                visuals = payload.get("visual_candidates", [])
                if (isinstance(visuals, list) and isinstance(selected, list) and
                        all(isinstance(x, str) for x in selected)):
                    planned = {
                        v.get("data_ref") for v in visuals
                        if isinstance(v, dict) and v.get("type") in {"bar", "line"}
                    }
                    if planned != set(selected):
                        problems.append("numeric visual_candidates must match selected_chart_ids")

    seen: set[str] = set()
    for index, section in enumerate(sections, 1):
        if not isinstance(section, dict):
            problems.append(f"section {index} is not an object")
            continue
        for field in ("id", "title"):
            if not str(section.get(field, "")).strip():
                problems.append(f"section {index} is missing {field}")
        section_id = str(section.get("id", ""))
        if section_id and not ID.fullmatch(section_id):
            problems.append(f"section {index} has invalid id: {section_id}")
        if section_id in seen:
            problems.append(f"duplicate section id: {section_id}")
        seen.add(section_id)
        if WORD_TARGET.search(str(section.get("instruction", ""))):
            problems.append(f"section {index} exposes a word-count target")
        subheadings = section.get("subheadings", [])
        if subheadings is None:
            subheadings = []
        if not isinstance(subheadings, list):
            problems.append(f"section {index} subheadings is not a list")
            continue
        for subindex, subheading in enumerate(subheadings, 1):
            if not isinstance(subheading, dict):
                problems.append(f"section {index} subheading {subindex} is not an object")
                continue
            if subheading.get("level") not in (3, 4):
                problems.append(
                    f"section {index} subheading {subindex} has invalid level: "
                    f"{subheading.get('level')}"
                )
            if not str(subheading.get("title", "")).strip():
                problems.append(f"section {index} subheading {subindex} is missing title")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    problems = validate(job)
    if problems:
        raise SystemExit("brief contract invalid:\n- " + "\n- ".join(problems))
    print(f"brief contract: OK ({job})")


if __name__ == "__main__":
    main()
