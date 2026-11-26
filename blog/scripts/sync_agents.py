"""Compatibility entry point for the old Claude sync command.

Codex discovers this repository's agents and skills in place, so nothing is copied into a
user-level directory. Keeping this script as a validator prevents an old documented command from
writing into ~/.claude while preserving a familiar maintenance entry point.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sync() -> None:
    validator = ROOT / "scripts" / "validate_codex_setup.py"
    result = subprocess.run([sys.executable, str(validator)], cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)
    print("Codex uses repo-local .codex/agents and .agents/skills; no sync needed.")


if __name__ == "__main__":
    sync()
