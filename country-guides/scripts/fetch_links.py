"""Internal link map for the guides -> config/site-links.json (English pages of Example Co).

Source: the production sitemap index. Pages under a language prefix (/ru/, /de/, …) are left out:
the guides are English. The guides' own URLs are allowed by check_guide.py separately.

Usage: python3 scripts/fetch_links.py
"""
from __future__ import annotations

import argparse
import re
import urllib.request
from datetime import date

from common import ROOT, write_json

INDEX = "https://example.com/sitemap-index.xml"
# Any two-letter locale prefix (/de/, /pt-br/). If your site has two-letter sections that are
# not locales (for example /hr/), list your locales here instead.
LANG = re.compile(r"^https://example\.com/[a-z]{2}(?:-[a-z]{2})?/")


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "country-guides-links/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    maps = re.findall(r"<loc>([^<]+)</loc>", get(INDEX))
    urls = set()
    for m in maps:
        urls |= set(re.findall(r"<loc>([^<]+)</loc>", get(m)))
    english = sorted(u for u in urls if not LANG.match(u))
    write_json(ROOT / "config" / "site-links.json", {"fetched": date.today().isoformat(), "source": INDEX,
                                                     "urls": english})
    print(f"{len(english)} English URLs from {len(maps)} sitemaps")


if __name__ == "__main__":
    main()
