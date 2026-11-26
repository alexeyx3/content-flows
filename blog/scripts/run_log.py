"""Run log: how much time and how many tokens each stage cost.

The agent track was not measured at all at first, and all savings estimates were arithmetic.
Now every stage writes a line here, and the next pipeline change is checked by a number, not
by feel. The file lives in the run folder: `jobs/<job>/run_log.jsonl`.

Usage:
  python3 scripts/run_log.py --job jobs/<job> --stage brief --seconds 651 --tokens 225051 \
      --note "blog-strategy-brief, one call"
  python3 scripts/run_log.py --job jobs/<job> --report
  python3 scripts/run_log.py --job jobs/<job> --report --compare jobs/<other-run>
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def job_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / value


def add(job: Path, stage: str, seconds: float | None, tokens: int | None, note: str) -> None:
    row = {
        "stage": stage,
        "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "seconds": round(seconds) if seconds is not None else None,
        "tokens": tokens,
        "note": note,
    }
    path = job / "run_log.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read(job: Path) -> list[dict]:
    path = job / "run_log.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def totals(rows: list[dict]) -> tuple[int, int]:
    return (sum(r["seconds"] or 0 for r in rows), sum(r["tokens"] or 0 for r in rows))


def report(job: Path, compare: Path | None) -> None:
    rows = read(job)
    if not rows:
        print(f"{job.name}: log is empty")
        return
    base = {r["stage"]: r for r in read(compare)} if compare else {}
    print(f"# {job.name}\n")
    head = f"{'stage':22} {'time':>9} {'tokens':>11}"
    if base:
        head += f" {'was time':>11} {'was tokens':>13}"
    print(head)
    for r in rows:
        line = (f"{r['stage'][:22]:22} {fmt_time(r['seconds']):>9} "
                f"{fmt_tok(r['tokens']):>11}")
        if base:
            b = base.get(r["stage"])
            line += (f" {fmt_time(b['seconds'] if b else None):>11} "
                     f"{fmt_tok(b['tokens'] if b else None):>13}")
        print(line)
    sec, tok = totals(rows)
    line = f"{'TOTAL':22} {fmt_time(sec):>9} {fmt_tok(tok):>11}"
    if base:
        bsec, btok = totals(list(base.values()))
        line += f" {fmt_time(bsec):>11} {fmt_tok(btok):>13}"
    print(line)
    if base:
        bsec, btok = totals(list(base.values()))
        if bsec and btok:
            print(f"\ntime {sec/bsec:.2f}× of the previous, tokens {tok/btok:.2f}×")


def fmt_time(seconds: int | None) -> str:
    if not seconds:
        return "—"
    return f"{seconds // 60}:{seconds % 60:02d}"


def fmt_tok(tokens: int | None) -> str:
    if not tokens:
        return "—"
    return f"{tokens/1000:.0f}k" if tokens < 1_000_000 else f"{tokens/1e6:.2f}M"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--stage")
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--tokens", type=int)
    ap.add_argument("--note", default="")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--compare", help="folder of another run to compare with")
    args = ap.parse_args()

    job = job_path(args.job)
    if args.report:
        report(job, job_path(args.compare) if args.compare else None)
        return
    if not args.stage:
        raise SystemExit("--stage or --report is required")
    job.mkdir(parents=True, exist_ok=True)
    add(job, args.stage, args.seconds, args.tokens, args.note)
    print(f"{job.name}: stage '{args.stage}' recorded — {fmt_time(args.seconds and round(args.seconds))}, "
          f"{fmt_tok(args.tokens)}")


if __name__ == "__main__":
    main()
