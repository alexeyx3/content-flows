"""Report verbatim word overlap between texts (sibling-footprint check).

Editors and QA agents systematically report "no matches" where there are a dozen, so this
is a script, not a judgement call. Compares every pair of files and prints the longest
shared runs of words (default: runs built from shared 8-grams).

Usage:
  python3 scripts/text_overlap.py a.md b.md [c.md ...] [--n 8] [--top 10]
Exit code 1 if any pair shares a run of >= --fail-at words (default 20).
"""
from __future__ import annotations

import argparse
import re
import sys
from itertools import combinations
from pathlib import Path

WORD = re.compile(r"[a-zа-яё0-9$%']+", re.I)


def load(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)   # drop link targets
    text = text.replace("—", " ").replace("–", " ").replace("’", "'")
    return WORD.findall(text.lower())


def grams(words: list, n: int) -> dict:
    out = {}
    for i in range(len(words) - n + 1):
        out.setdefault(" ".join(words[i:i + n]), i)
    return out


def runs_for(idx: list) -> list:
    runs, cur = [], None
    for i in sorted(idx):
        if cur and i <= cur[1] + 1:
            cur[1] = i
        else:
            if cur:
                runs.append(cur)
            cur = [i, i]
    if cur:
        runs.append(cur)
    return runs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--fail-at", type=int, default=20)
    args = ap.parse_args()

    docs = {}
    for name in args.files:
        words = load(Path(name))
        docs[name] = (words, grams(words, args.n))

    worst = 0
    for a, b in combinations(docs, 2):
        shared = set(docs[a][1]) & set(docs[b][1])
        runs = runs_for([docs[a][1][g] for g in shared])
        runs.sort(key=lambda r: r[1] - r[0], reverse=True)
        longest = runs[0][1] - runs[0][0] + args.n if runs else 0
        worst = max(worst, longest)
        print(f"\n=== {Path(a).name} vs {Path(b).name}: "
              f"{len(shared)} shared {args.n}-grams, {len(runs)} runs, longest {longest}w ===")
        for start, end in runs[:args.top]:
            length = end - start + args.n
            print(f"  [{length}w] " + " ".join(docs[a][0][start:end + args.n]))

    print(f"\nlongest shared run overall: {worst} words (fail-at {args.fail_at})")
    return 1 if worst >= args.fail_at else 0


if __name__ == "__main__":
    sys.exit(main())
