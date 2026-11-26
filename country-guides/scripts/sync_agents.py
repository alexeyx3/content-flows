"""Sync project-local Codex skill/profiles; optionally install its user entrypoint."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync(install_user_skill: bool = False) -> None:
    src = ROOT / "agents-src/skills/country-guide"
    local = ROOT / ".agents/skills/country-guide"
    shutil.copytree(src, local, dirs_exist_ok=True)
    profiles = ROOT / ".codex/agents"
    profiles.mkdir(parents=True, exist_ok=True)
    roles = sorted((ROOT / "agents-src/agents").glob("guide-*.md"))
    routes = json.loads((ROOT / "config/codex-model-routing.json").read_text())["agents"]
    for role in roles:
        route = routes[role.stem]
        if route.get("reasoning_effort") != "medium":
            raise ValueError(f"{role.stem}: reasoning effort must be medium")
        description = next(line.removeprefix("description: ") for line in
                           role.read_text().splitlines() if line.startswith("description: "))
        instructions = (f"Read {role.relative_to(ROOT)} completely and follow it for the assigned job and scope. "
                        "Use only available tools. Do not spawn or message other agents. "
                        "Save role-defined output files and return a compact status.")
        (profiles / f"{role.stem}.toml").write_text(
            f"name = {json.dumps(role.stem)}\n"
            f"model = {json.dumps(route['model'])}\n"
            f"model_reasoning_effort = {json.dumps(route['reasoning_effort'])}\n"
            f"description = {json.dumps(description)}\n"
            f"developer_instructions = {json.dumps(instructions)}\n", encoding="utf-8")
    print(f"Synced local country-guide skill and {len(roles)} role profiles.")
    if install_user_skill:
        codex_dir = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
        dest = codex_dir / "skills/country-guide"
        marker = f"Project: `{ROOT}`"
        if dest.exists():
            manifest = dest / "SKILL.md"
            if not manifest.is_file() or marker not in manifest.read_text():
                raise SystemExit(f"Refusing to overwrite another skill: {dest}")
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "SKILL.md").write_text(
            "---\nname: country-guide\n"
            "description: Create, continue, edit or review the three Example Co guide pages for a country using the local Codex country-guide project.\n"
            "---\n\n# Example Co country guides\n\n" + marker + "\n\n"
            f"Read `{ROOT / 'AGENTS.md'}` and `{local / 'SKILL.md'}` before executing the workflow. "
            "Use this project's roles, scripts and job folders. The local skill is the maintained "
            "source of truth; this entrypoint grants no additional external-write permissions.\n",
            encoding="utf-8")
        print(f"Installed project entrypoint: {dest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-user-skill", action="store_true")
    sync(parser.parse_args().install_user_skill)
