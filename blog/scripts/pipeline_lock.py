"""Atomic, owner-checked locks for article-pipeline shared writes."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK_ROOT = ROOT / "var" / "locks"
LOCK_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def lock_path(lock_root: Path, name: str) -> Path:
    if not LOCK_NAME.fullmatch(name):
        raise ValueError("lock name must use lowercase letters, digits, and hyphens")
    return lock_root / f"{name}.lock"


def read_owner(path: Path) -> dict[str, str]:
    metadata = path / "owner.json"
    if not metadata.exists():
        return {"owner": "unknown", "acquired_at": "unknown"}
    return json.loads(metadata.read_text(encoding="utf-8"))


def acquire(lock_root: Path, name: str, owner: str) -> Path:
    if not owner.strip():
        raise ValueError("owner must not be empty")
    lock_root.mkdir(parents=True, exist_ok=True)
    path = lock_path(lock_root, name)
    try:
        path.mkdir()
    except FileExistsError as exc:
        held = read_owner(path)
        raise RuntimeError(
            f"lock {name} is held by {held.get('owner')} since {held.get('acquired_at')}"
        ) from exc
    (path / "owner.json").write_text(
        json.dumps({"owner": owner, "acquired_at": timestamp()}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def release(lock_root: Path, name: str, owner: str) -> None:
    path = lock_path(lock_root, name)
    if not path.exists():
        raise RuntimeError(f"lock {name} does not exist")
    held = read_owner(path)
    if held.get("owner") != owner:
        raise RuntimeError(f"lock {name} belongs to {held.get('owner')}, not {owner}")
    metadata = path / "owner.json"
    if metadata.exists():
        metadata.unlink()
    path.rmdir()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock-root", default=str(DEFAULT_LOCK_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    for command_name in ("acquire", "release"):
        command = sub.add_parser(command_name)
        command.add_argument("--name", required=True)
        command.add_argument("--owner", required=True)
    status = sub.add_parser("status")
    status.add_argument("--name", required=True)
    args = parser.parse_args()
    lock_root = Path(args.lock_root)
    try:
        if args.command == "acquire":
            print(acquire(lock_root, args.name, args.owner))
        elif args.command == "release":
            release(lock_root, args.name, args.owner)
            print(f"released {args.name}")
        else:
            path = lock_path(lock_root, args.name)
            if not path.exists():
                print(f"{args.name}: free")
            else:
                held = read_owner(path)
                print(f"{args.name}: held by {held.get('owner')} since {held.get('acquired_at')}")
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
