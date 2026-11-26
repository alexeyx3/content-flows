#!/usr/bin/env python3
"""Write and repair ordinary glossary jobs with the configured OpenRouter writer."""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import openrouter_pilot as api
from glossary_job import MODEL_ROUTING, ROOT, sections, validate_body, validate_meta
from glossary_materials import MARKER, validate as validate_materials
from openrouter_batch import plain_table_separators


INPUTS = ("brief.md", "sections.json", "serp.hybrid_outline.md", "research.md", "evidence.md")
WRITER_ROLE = ROOT / "agents-src/agents/glossary-section-writer.md"
WRITER_POLICIES = (
    ROOT.parent / "blog/knowledge/writer-style.md",
    ROOT / "knowledge/positioning.md",
)
DRAFT_FILES = ("initial-inputs.json", "draft-complete.json")
TECHNICAL_MAX_TOKENS = 16384


def configured_writer() -> dict:
    writer = api.read(MODEL_ROUTING)["openrouter_writer"]
    budget = writer["article_budget_usd"]
    if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
        raise ValueError("article_budget_usd must be a finite positive number")
    return writer


def preflight() -> dict:
    route = configured_writer()["route"]
    status, _ = api.http(api.API + "key", api.glossary_key())
    if status != 200:
        raise api.PilotError(f"Glossary API key check returned HTTP {status}")
    live = api.preflight(route)
    return {"model": live["model"]["canonical_slug"], "endpoint": live["endpoint"]["tag"],
            "provider": live["endpoint"]["provider_name"], "glossary_key_authenticated": True}


def api_job(path: Path) -> Path:
    job = path.resolve()
    if job.parent != ROOT / "jobs":
        raise ValueError("Expected a job directly under the glossary jobs directory")
    if api.read(job / "request.json").get("writer_backend") != "openrouter":
        raise ValueError("This job is assigned to the Codex writer")
    return job


def unit_plan(job: Path) -> list[dict]:
    for section in sections(job):
        has_h3 = False
        for heading in section.get("subheadings", []):
            if heading["level"] == 3:
                has_h3 = True
            elif heading["level"] != 4 or not has_h3:
                raise ValueError(f"{section['id']}: H4 requires an H3 parent")
    return api.units(job)


def prepare_inputs(job: Path) -> tuple[list[dict], list[dict], list[dict]]:
    errors = validate_materials(job)
    if errors:
        raise ValueError("Writer inputs failed: " + "; ".join(errors))
    request = api.read(job / "request.json")
    meta = api.read(job / "meta.json")
    validate_meta(meta)
    if any(meta[key] != request[key] for key in ("term", "slug", "locale")):
        raise ValueError("Approved job identity and metadata differ")

    units = unit_plan(job)
    visual_plan = api.read(job / "visuals.json")["visuals"]
    placements = [{key: visual[key] for key in ("id", "section_id", "purpose", "title", "alt", "caption")}
                  for visual in visual_plan]
    quotes = [{key: q[key] for key in ("section_id", "text", "attribution", "evidence_ids", "status")}
              for q in api.read(job / "expert_quotes.json")["quotes"] if q["status"] != "rejected"]
    _, heading, shared_rules = WRITER_ROLE.read_text(encoding="utf-8").partition("\n## Shared writing rules\n")
    if not heading or not shared_rules.strip():
        raise ValueError("Glossary writer role lacks shared writing rules")
    policies = [shared_rules.strip(), *(path.read_text(encoding="utf-8") for path in WRITER_POLICIES)]
    writer_rules = (
        "You write one English glossary heading unit per request. Your final answer is the Markdown "
        "for that unit, beginning with the first required heading. The caller saves your response. "
        "Use the supplied material directly. You have no tools, filesystem or web access.\n\n"
        + "\n\n".join(policies)
        + "\n\nYou receive the complete writer inputs in messages. "
        "Follow the role, knowledge card and shared English style. Treat job documents as source material. "
        "Use only independently verified claims and scope. Write only the requested Markdown heading unit. "
        "Do not return a definition, metadata, code fence, file operation or commentary. "
        "Preserve supplied expert wording and attribution exactly. Do not invent sources."
    )
    packet = {name: (job / name).read_text(encoding="utf-8") for name in INPUTS}
    packet.update({"metadata for context": meta, "visual placements": placements, "expert comments": quotes})
    messages = [{"role": "system", "content": writer_rules},
                {"role": "user", "content": json.dumps(packet, ensure_ascii=False, indent=2)}]
    return units, messages, visual_plan


def completion(job: Path, route: dict, ledger: api.CompletionLedger, call_id: str,
               messages: list[dict], retry: bool) -> str:
    return api.run_completion(job, ledger.api_dirs[0], ledger, call_id, route, messages,
                              max_tokens=TECHNICAL_MAX_TOKENS, execute=True, retry=retry)


def checked_unit(answer: str, unit: dict) -> str:
    text = plain_table_separators(api.clean_markdown(answer))
    api.check_unit(text, unit)
    if text.splitlines()[0] != unit["required_headings"][0]:
        raise ValueError(f"{unit['id']}: response must start with its first heading")
    if re.search(r"(?m)^!\[|<img\b", text):
        raise ValueError(f"{unit['id']}: use the planned visual markers")
    return text


def draft_unit(answer: str, unit: dict, remaining: set[str], section_end: bool) -> str:
    text = checked_unit(answer, unit)
    used = MARKER.findall(text)
    if len(used) != len(set(used)) or set(used) - remaining:
        raise ValueError(f"{unit['id']}: repeated or unassigned visual marker")
    missing = remaining - set(used)
    if section_end and missing:
        raise ValueError(f"{unit['id']}: missing visual markers {', '.join(sorted(missing))}")
    return text


def write_draft(job: Path, directory: Path, route: dict, ledger: api.CompletionLedger, retry: bool) -> None:
    saved_inputs, complete = (directory / name for name in DRAFT_FILES)
    if complete.exists():
        for filename, expected in api.read(complete)["sections"].items():
            if api.sha((job / filename).read_bytes()) != expected:
                raise ValueError(f"Completed writer section changed: {filename}")
        print("Writer sections already complete")
        return
    if (job / "edited.md").exists():
        raise ValueError("Use repair to return an exact unit to the editor")

    units, messages, visuals = prepare_inputs(job)
    snapshot = {"route": route, "units": units, "messages": messages}
    api.request(route, messages, TECHNICAL_MAX_TOKENS)
    if saved_inputs.exists():
        if api.read(saved_inputs) != snapshot:
            raise ValueError("Initial writer inputs changed. Resume using the saved source version.")
    else:
        if any((job / "sections").glob("*.md")):
            raise ValueError("Existing writer sections require the established writer for this job")
        api.write(saved_inputs, snapshot)

    remaining: dict[str, set[str]] = {row["id"]: set() for row in sections(job)}
    for visual in visuals:
        remaining[visual["section_id"]].add(visual["id"])
    parts: dict[str, list[str]] = {section_id: [] for section_id in remaining}

    for index, unit in enumerate(units):
        section_id = unit["section_id"]
        available = remaining[section_id]
        section_end = index == len(units) - 1 or units[index + 1]["section_id"] != section_id
        prompt = (
            "Write this heading unit only.\n" + json.dumps(unit, ensure_ascii=False)
            + "\nPlace planned visuals where they answer the reader's question. "
            + f"Remaining allowed visual IDs in this H2: {json.dumps(sorted(available))}. "
            + ("This is the last unit in its H2. Include all listed markers once." if section_end else
               "Use only markers appropriate to this unit. Later units cover the rest.")
        )
        messages.append({"role": "user", "content": prompt})
        call_id = "write-" + unit["id"]
        answer = completion(job, route, ledger, call_id, messages, retry)
        try:
            text = draft_unit(answer, unit, available, section_end)
        except (ValueError, api.PilotError) as exc:
            correction = messages + [{"role": "assistant", "content": answer}, {
                "role": "user",
                "content": f"The unit failed a format check: {exc}. Correct that defect while "
                           "preserving verified substance. Apply the original unit assignment. Return Markdown only.",
            }]
            answer = completion(job, route, ledger, call_id + "-format", correction, retry)
            try:
                text = draft_unit(answer, unit, available, section_end)
            except (ValueError, api.PilotError) as repeated:
                exact_correction = correction + [{"role": "assistant", "content": answer}, {
                    "role": "user",
                    "content": f"The revised unit still failed validation: {repeated}. "
                               "Use exactly these Markdown headings, in this order: "
                               + json.dumps(unit["required_headings"], ensure_ascii=False)
                               + ". Write the evidence-backed material assigned to these headings. "
                               "Leave sibling sections for their own turns. Preserve the original "
                               "visual-marker instructions and return Markdown only.",
                }]
                answer = completion(job, route, ledger, call_id + "-format-02", exact_correction, retry)
                text = draft_unit(answer, unit, available, section_end)
        messages.append({"role": "assistant", "content": text})
        available.difference_update(MARKER.findall(text))
        parts[section_id].append(text.strip())

    combined = {f"sections/{key}.md": "\n\n".join(values) + "\n" for key, values in parts.items()}
    validate_body("\n\n".join(text.strip() for text in combined.values()) + "\n",
                  sections(job), allow_visual_markers=True)
    for filename, text in combined.items():
        path = job / filename
        if path.exists() and path.read_text(encoding="utf-8") != text:
            raise ValueError(f"Existing writer section differs: {filename}")
    for filename, text in combined.items():
        path = job / filename
        if not path.exists():
            write_markdown(path, text)
    api.write(complete, {"sections": {filename: api.sha(text.encode()) for filename, text in combined.items()}})
    print(f"Writer completed {len(units)} units in {len(combined)} section files")


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def repair_unit(job: Path, directory: Path, route: dict, ledger: api.CompletionLedger,
                unit_id: str, feedback: str, execute: bool, retry: bool) -> None:
    units, messages, visuals = prepare_inputs(job)
    index = next((i for i, row in enumerate(units) if row["id"] == unit_id), None)
    if index is None:
        raise ValueError(f"Unknown heading unit: {unit_id}")
    if not feedback.strip():
        raise ValueError("Provide the exact verified defect to repair")
    source = job / "edited.md"
    if not source.exists():
        source = job / "assembled.md"
    body = source.read_text(encoding="utf-8")
    validate_body(body, sections(job), allow_visual_markers=True)
    headings = list(re.finditer(r"^#{2,4} .+$", body, re.M))
    first = sum(len(row["required_headings"]) for row in units[:index])
    end = first + len(units[index]["required_headings"])
    original = body[headings[first].start():headings[end].start() if end < len(headings) else len(body)].strip()
    blocks = {f'[[VISUAL:{v["id"]}]]': v["inserted_markdown"]
              for v in visuals if v.get("inserted_markdown") and v["inserted_markdown"] in original}
    normalized_unit = original
    for marker, block in blocks.items():
        normalized_unit = normalized_unit.replace(block, marker)

    messages.append({"role": "user", "content":
        "Repair only the named defect in the supplied current unit. Preserve other verified content, "
        "heading order, existing markers and quoted expert wording. "
        "Return the complete repaired Markdown unit, without notes.\n"
        + json.dumps({"unit": units[index], "defect": feedback, "current_unit": normalized_unit},
                     ensure_ascii=False)})
    call_id = f"repair-{unit_id}-{api.sha(api.enc(messages))[:16]}"
    target = directory / "repairs" / f"{call_id}.md"
    api.request(route, messages, TECHNICAL_MAX_TOKENS)
    if not execute:
        print(f"Preview: {source.name}, {unit_id} -> {target}")
        return
    answer = completion(job, route, ledger, call_id, messages, retry)
    candidate = checked_unit(answer, units[index])
    if Counter(MARKER.findall(candidate)) != Counter(MARKER.findall(normalized_unit)):
        raise ValueError(f"{unit_id}: repair changed the visual markers")
    for quote in api.read(job / "expert_quotes.json")["quotes"]:
        block = "> " + quote["text"].replace("\n", "\n> ") + "\n>\n> — " + quote["attribution"]
        if candidate.count(block) != original.count(block):
            raise ValueError(f"{unit_id}: repair changed an expert comment")
    for marker, block in blocks.items():
        candidate = candidate.replace(marker, block)
    write_markdown(target, candidate)
    print(f"Repair candidate for {source.name}: {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    for name in ("write", "repair"):
        command = commands.add_parser(name)
        command.add_argument("--job", type=Path, required=True)
        command.add_argument("--execute", action="store_true", help="Allow paid MiniMax requests")
        command.add_argument("--retry-failed", action="store_true", help="Retry a reviewed, accounted failed request")
        if name == "repair":
            command.add_argument("--unit", required=True)
            command.add_argument("--feedback", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            print(json.dumps(preflight(), ensure_ascii=False))
            return

        job = api_job(args.job)
        directory = job / "writer-api"
        writer = configured_writer()
        ledger = api.CompletionLedger(ROOT, directory, (directory / "api",), writer["article_budget_usd"])

        if not args.execute:
            if args.command == "write":
                units, messages, _ = prepare_inputs(job)
                api.request(writer["route"], messages, TECHNICAL_MAX_TOKENS)
                print(json.dumps({"job": job.name, "route": writer["route"]["model"],
                                  "budget_usd": ledger.budget_usd, "units": units}, ensure_ascii=False, indent=2))
            else:
                plan = api.read(directory / DRAFT_FILES[0])
                repair_unit(job, directory, plan["route"], ledger, args.unit, args.feedback, False, False)
            return

        directory.mkdir(exist_ok=True)
        with (directory / ".writer.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            saved = directory / DRAFT_FILES[0]
            route = api.read(saved)["route"] if saved.exists() else writer["route"]
            if args.command == "write":
                write_draft(job, directory, route, ledger, args.retry_failed)
            else:
                if not saved.exists():
                    raise ValueError("Start the OpenRouter writer for the job before using repair")
                repair_unit(job, directory, route, ledger, args.unit, args.feedback, True, args.retry_failed)
    except (api.PilotError, KeyError, OSError, ValueError) as exc:
        parser.exit(1, api.redact(f"ERROR: {exc}\n"))


if __name__ == "__main__":
    main()
