"""Validate the repository-local Codex skill and custom-agent wiring."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_NAMES = (
    "blog-coordinator",
    "blog-topic-research",
    "blog-research-map",
    "blog-primary-data-research",
    "blog-study-research",
    "blog-quote-scout",
    "blog-visual-planner",
    "blog-visual-qa",
    "blog-expert-quotes",
    "blog-strategy-brief",
    "blog-evidence",
    "blog-company-cards",
    "blog-section-writer",
    "blog-editor",
    "blog-qa-factcheck",
    "blog-translator",
    "blog-translation-editor",
    "blog-translation-qa",
)
REQUIRED_ENGLISH_SERP_GEOS = {"us", "gb", "de", "au"}


def main() -> None:
    problems: list[str] = []
    skill = ROOT / ".agents" / "skills" / "blog-article" / "SKILL.md"
    if not skill.exists():
        problems.append(f"missing repo skill: {skill}")
        skill_text = ""
    else:
        skill_text = skill.read_text(encoding="utf-8")
        if not re.search(r"^name:\s*blog-article\s*$", skill_text, re.M):
            problems.append("blog-article skill has invalid name")

    for name in AGENT_NAMES:
        path = ROOT / ".codex" / "agents" / f"{name}.toml"
        if not path.exists():
            problems.append(f"missing custom agent: {path}")
            continue
        try:
            config = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"invalid TOML {path}: {exc}")
            continue
        for field in ("name", "description", "developer_instructions"):
            if not str(config.get(field, "")).strip():
                problems.append(f"{path}: missing {field}")
        if config.get("name") != name:
            problems.append(f"{path}: name must be {name}")
        if name not in skill_text:
            problems.append(f"skill does not dispatch {name}")
        role = ROOT / "agents-src" / "agents" / f"{name}.md"
        if not role.exists():
            problems.append(f"missing role specification: {role}")

    routing_path = ROOT / "config" / "codex-model-routing.json"
    try:
        routing = json.loads(routing_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"invalid model routing {routing_path}: {exc}")
        routing = {}
    if routing.get("schema_version") != 1:
        problems.append("model routing schema_version must be 1")
    if routing.get("fork_turns") != "none":
        problems.append("model routing must isolate agents with fork_turns=none")
    routes = routing.get("agents", {})
    for name in AGENT_NAMES:
        route = routes.get(name, {}) if isinstance(routes, dict) else {}
        if not str(route.get("model", "")).strip():
            problems.append(f"model routing missing model for {name}")
        if route.get("reasoning_effort") != "medium":
            problems.append(f"model routing effort for {name} must be medium")
    unexpected = set(routes) - set(AGENT_NAMES) if isinstance(routes, dict) else set()
    if unexpected:
        problems.append("unexpected model routes: " + ", ".join(sorted(unexpected)))
    catalog_path = Path.home() / ".codex" / "models_cache.json"
    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            available = {
                str(row.get("slug")) for row in catalog.get("models", []) if row.get("slug")
            }
            for name in AGENT_NAMES:
                model = routes.get(name, {}).get("model") if isinstance(routes, dict) else None
                if model and model not in available:
                    problems.append(f"model routing for {name} is unavailable locally: {model}")
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"invalid local Codex model catalog {catalog_path}: {exc}")

    for name in ("copywriter", "humanizer"):
        path = ROOT / ".agents" / "skills" / name / "SKILL.md"
        if not path.exists():
            problems.append(f"missing repo skill: {path}")

    brief_validator = ROOT / "scripts" / "validate_article_brief.py"
    if not brief_validator.exists():
        problems.append(f"missing writer-facing brief validator: {brief_validator}")

    geos_path = ROOT / "config" / "geos.json"
    try:
        geos = json.loads(geos_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append(f"invalid SERP geo config {geos_path}: {exc}")
        geos = {}
    configured_geos = {
        str(row.get("geo_key", "")).lower()
        for row in geos
        if isinstance(row, dict)
    } if isinstance(geos, list) else set()
    missing_geos = REQUIRED_ENGLISH_SERP_GEOS - configured_geos
    if missing_geos:
        problems.append("missing required English SERP geos: " + ", ".join(sorted(missing_geos)))

    if problems:
        raise SystemExit("Codex setup invalid:\n- " + "\n- ".join(problems))
    print(
        "Codex setup: OK (1 root orchestrator skill, 17 active specialists, "
        "1 dormant coordinator, 2 editorial skills)"
    )


if __name__ == "__main__":
    main()
