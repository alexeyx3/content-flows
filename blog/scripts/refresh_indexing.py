"""Read-only Google URL Inspection preflight, before selecting refresh pages."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

if __package__:
    from scripts.collect_refresh_baseline import google_client, retry
else:
    from collect_refresh_baseline import google_client, retry

ROOT = Path(__file__).resolve().parents[1]
PROPERTY = "sc-domain:example.com"


def inspect(url: str, *, service=None) -> dict:
    if not re.fullmatch(r"https://example\.com/blog/[a-z0-9-]+/", url):
        raise ValueError("expected an exact canonical Example Co blog URL")
    receipt = {"url": url, "property": PROPERTY,
               "checked_at": datetime.now(timezone.utc).isoformat(),
               "ready_for_semantic_refresh": False}
    try:
        svc = service if service is not None else google_client()
        response = retry(lambda: svc.urlInspection().index().inspect(body={
            "inspectionUrl": url, "siteUrl": PROPERTY, "languageCode": "en-US"}).execute())
        result = response.get("inspectionResult", {}).get("indexStatusResult", {})
        receipt["index_status"] = result
        if result.get("verdict") == "PASS" and result.get("googleCanonical") == url:
            receipt.update(status="indexed", ready_for_semantic_refresh=True)
        elif result.get("verdict") == "PASS" and result.get("googleCanonical"):
            receipt["status"] = "canonical_mismatch"
        elif result.get("verdict") in {"FAIL", "NEUTRAL"}:
            receipt["status"] = "index_problem"
        else:
            receipt["status"] = "unknown"
    except Exception as exc:
        # API/auth failures are not evidence of exclusion. Never log credentials
        # or raw exception messages that can include request/auth information.
        receipt.update(status="unavailable", error_type=type(exc).__name__)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cluster-id", help="disambiguate one evaluated temnik row")
    parser.add_argument("--sync-temnik", action="store_true")
    parser.add_argument("--apply", action="store_true", help="apply the requested temnik sync")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error("output must be a new receipt inside this repository")
    if any(not re.fullmatch(r"https://example\.com/blog/[a-z0-9-]+/", url) for url in args.url):
        parser.error("expected exact canonical Example Co blog URLs")
    if args.cluster_id and len(set(args.url)) != 1:
        parser.error("--cluster-id requires exactly one URL")
    pages = [inspect(url) for url in dict.fromkeys(args.url)]
    if args.cluster_id:
        pages[0]["cluster_id"] = args.cluster_id
    ready = all(page["ready_for_semantic_refresh"] for page in pages)
    receipt = {"version": 1, "status": "PASS" if ready else "HOLD", "pages": pages,
               "limitation": "Google's stored index inspection, not a live crawl test; no indexing submission."}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if args.sync_temnik:
        if __package__:
            from scripts.blog_monitor import sync
        else:
            from blog_monitor import sync
        print(json.dumps(sync(receipt, apply=args.apply), ensure_ascii=False, indent=2))
    raise SystemExit(0 if ready else 2)


if __name__ == "__main__":
    main()
