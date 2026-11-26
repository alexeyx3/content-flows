"""Report repeated visual-type choices across a batch of article jobs."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit(jobs: list[Path]) -> dict:
    articles = []
    totals: Counter[str] = Counter()
    for job in jobs:
        path = job / "visuals.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        visuals = data.get("visuals")
        if not isinstance(visuals, list):
            raise ValueError(f"{path}: visuals must be a list")
        types = [v.get("type") for v in visuals if isinstance(v, dict)]
        if len(types) != len(visuals) or any(not isinstance(t, str) or not t for t in types):
            raise ValueError(f"{path}: every visual needs a type")
        totals.update(types)
        articles.append({"job": str(job), "types": types, "signature": sorted(types)})
    signatures = [tuple(row["signature"]) for row in articles]
    repeated = len(articles) >= 3 and len(set(signatures)) == 1 and bool(signatures[0])
    return {
        "version": 1,
        "articles": articles,
        "type_totals": dict(sorted(totals.items())),
        "needs_editorial_review": repeated,
        "reason": (
            "Every article has the same visual-type set; review data candidates and rejected charts."
            if repeated else "Visual-type sets are not identical across the batch."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", nargs="+", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    jobs = [Path(x) if Path(x).is_absolute() else ROOT / x for x in args.jobs]
    report = audit(jobs)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output) if Path(args.output).is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
