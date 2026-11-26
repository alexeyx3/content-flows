"""Check that every Markdown link in the given files resolves.

Uses a browser User-Agent: many primary sources (weforum.org, dol.gov, pwc.com) return
403 to default clients. A 403 here means bot protection, not a dead link — a 404/410
does mean the citation is broken and must be replaced.

Usage:
  python3 scripts/check_links.py <file.md> [<file.md> ...]
Exit code 1 if any link returns 4xx other than 401/403/405, or 5xx.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
SOFT = {"401", "403", "405", "429"}


def status(url: str, timeout: int) -> str:
    proc = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-L",
         "--max-time", str(timeout), "-A", UA, url],
        capture_output=True, text=True)
    return proc.stdout.strip() or "000"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args()

    urls: "OrderedDict[str, set]" = OrderedDict()
    for name in args.files:
        text = Path(name).read_text(encoding="utf-8")
        for m in re.finditer(r"\]\((https?://[^)\s]+)\)", text):
            urls.setdefault(m.group(1), set()).add(Path(name).name)
        for m in re.finditer(r"(?<![(\[])\bhttps?://[^\s)>\]]+", text):
            urls.setdefault(m.group(0), set()).add(Path(name).name + " (bare URL!)")

    broken = 0
    for url, files in urls.items():
        code = status(url, args.timeout)
        flag = "OK  "
        if code in SOFT:
            flag = "SOFT"          # bot protection — verify by hand, not a broken link
        elif not code.startswith(("2", "3")):
            flag = "DEAD"
            broken += 1
        print(f"{flag} {code}  {url}  <- {', '.join(sorted(files))}")

    print(f"\n{len(urls)} links checked, {broken} dead")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
