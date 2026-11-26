"""Legacy utility of the former numeric paragraph-length rule.

The active pipeline does not call it: paragraphs are now split by meaning without a numeric threshold.
The file is kept only to reproduce old runs and their tests.

Usage:
  python3 scripts/split_walls.py --file jobs/<job>/edited.md
  python3 scripts/split_walls.py --file <path> --limit 32 --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint_article as lint  # noqa: E402

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
SKIP_PREFIX = ("|", "#", ">")


def split_paragraph(text: str, limit: int) -> list[str]:
    """Paragraph -> several paragraphs. Each accumulates up to the limit and breaks at a phrase boundary."""
    out: list[str] = []
    buf = ""
    for sentence in SENTENCE_END.split(text.strip()):
        candidate = f"{buf} {sentence}".strip()
        if buf and len(candidate.split()) > limit:
            out.append(buf)
            buf = sentence
        else:
            buf = candidate
    if buf:
        out.append(buf)
    return out


def process(text: str, limit: int = 32) -> tuple[str, int]:
    lines = text.split("\n")
    walls = {n for n, _ in lint.walls(text)}
    out: list[str] = []
    changed = 0
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if i in walls and not stripped.startswith(SKIP_PREFIX) and not lint.LIST_START.match(stripped):
            pieces = split_paragraph(line, limit)
            if len(pieces) > 1:
                changed += 1
                for k, piece in enumerate(pieces):
                    out.append(piece)
                    if k < len(pieces) - 1:
                        out.append("")
                continue
        out.append(line)
    return "\n".join(out), changed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--limit", type=int, default=32,
                    help="target paragraph length in words (default 32)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = Path(args.file)
    before = path.read_text(encoding="utf-8")
    after, changed = process(before, args.limit)
    was = len(lint.walls(before))
    now = len(lint.walls(after))
    print(f"{path.name}: paragraphs longer than 40 words {was} -> {now}, split {changed}, "
          f"words {len(before.split())} -> {len(after.split())}")
    if not args.dry_run:
        path.write_text(after, encoding="utf-8")


if __name__ == "__main__":
    main()
