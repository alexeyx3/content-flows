"""Word counter for a job's articles, so that editors and QA do not count by eye.

Agents have no shell, and their volume estimates systematically differ from the fact
by 300-500 words. The script writes the fact to <job>/wordcount.txt, from where an agent can
read it, and prints the same to stdout for the orchestrator.

Usage:
  python3 scripts/wordcount.py --job jobs/<job-dir>          # all files of the job
  python3 scripts/wordcount.py --file <path.md>              # one file
  python3 scripts/wordcount.py --job jobs/<job-dir> --quiet  # write only

Excluded from the count: the YAML/meta block at the start of the file, markdown tables,
code blocks and link lines. What is counted is what a human reads.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ["edited.md", "out/draft.md"]


def body_words(text: str) -> int:
    # meta block --- ... --- or > **Meta...** at the start
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"\A(?:>.*\n)+", "", text)
    # a draft sometimes arrives wrapped entirely in ```markdown ... ```: unwrap it,
    # otherwise the whole text would go into a "code block" and the count would be 0
    m = re.match(r"\A\s*```[a-zA-Z]*\n(.*)\n```\s*\Z", text, flags=re.S)
    if m:
        text = m.group(1)
    # code blocks
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    # markdown tables
    text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("|"))
    # link markup: keep the anchor, drop the url
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#*_>`]", " ", text)
    return len(text.split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--file")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if args.file:
        p = Path(args.file)
        print(f"{body_words(p.read_text(encoding='utf-8'))}\t{p}")
        return

    if not args.job:
        raise SystemExit("--job or --file is required")

    job = Path(args.job)
    if not job.is_absolute():
        job = ROOT / job
    lines = []
    for rel in TARGETS:
        p = job / rel
        if p.exists():
            lines.append(f"{rel}: {body_words(p.read_text(encoding='utf-8'))} words")
    if not lines:
        raise SystemExit(f"{job} has neither edited.md nor out/draft.md")

    out = "\n".join(lines) + "\n"
    (job / "wordcount.txt").write_text(out, encoding="utf-8")
    if not args.quiet:
        print(out, end="")


if __name__ == "__main__":
    main()
