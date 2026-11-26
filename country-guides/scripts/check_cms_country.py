"""Read-only live CMS compatibility check before starting a country's content job.

No probe records, schema changes or paid model requests. A failed schema lookup
blocks selection rather than treating unavailable compatibility as a pass.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import urllib.error

from common import ROOT, queue, write_json
from strapi_publish import api

COUNTRY_UID = "api::country-guide.country-guide"
SUBPAGE_UID = "api::guide-subpage.guide-subpage"
HEADER_STRINGS = ("minimumWage", "averageSalary", "incomeTax", "paidLeave",
                  "publicHolidays", "probation", "noticePeriod")


def check_country(iso: str, slug: str = "") -> dict:
    report = {
        "schema_version": 1,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "iso": iso, "slug": slug, "status": "BLOCK", "errors": [],
        "mode": "live read-only schema check; no probe records or CMS changes",
        "scope": "Country identity and current exporter field compatibility. Later article, "
                 "QA, authorization and publication-time validations still apply.",
    }
    errors = report["errors"]
    if not isinstance(iso, str) or not re.fullmatch(r"[A-Z]{2}", iso):
        errors.append("Expected the country's actual two-letter uppercase ISO code")
        return report
    if slug and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        errors.append("Invalid country slug")
        return report
    attributes = {}
    for uid in (COUNTRY_UID, SUBPAGE_UID):
        path = "/content-type-builder/content-types/" + uid
        try:
            data = api(path).get("data", {})
            fields = data.get("schema", {}).get("attributes")
            if data.get("uid") != uid or not isinstance(fields, dict):
                raise ValueError("Missing or unexpected schema")
            attributes[uid] = fields
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            # Do not persist full account/server responses, headers or credentials.
            status = f" HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else ""
            errors.append(f"Cannot verify live CMS schema {uid}:{status} {type(exc).__name__}")
    if errors:
        return report

    country, subpage = attributes[COUNTRY_UID], attributes[SUBPAGE_UID]
    code = country.get("code", {})
    allowed = code.get("enum")
    report["country_code_required"] = code.get("required")
    report["allowed_country_codes"] = allowed if isinstance(allowed, list) else None
    if code.get("type") != "enumeration" or not isinstance(allowed, list):
        errors.append("Cannot verify the CMS country-code enumeration")
    elif iso not in allowed:
        errors.append(f"CMS country code {iso} is unsupported; choose another country. "
                      "Do not substitute another country's code or change the CMS schema.")

    required_types = {"name": {"string"}, "slug": {"string", "uid"},
                      "employerContributions": {"decimal", "float", "integer"},
                      "contentHtml": {"richtext", "text"},
                      **{name: {"string"} for name in HEADER_STRINGS}}
    for name, types in required_types.items():
        field = country.get(name)
        if not isinstance(field, dict) or field.get("type") not in types:
            errors.append(f"Country field {name} is incompatible with the current exporter")
    report["country_field_limits"] = {name: country.get(name, {}).get("maxLength")
                                      for name in HEADER_STRINGS}
    kind = subpage.get("kind", {})
    kinds = kind.get("enum")
    if kind.get("type") != "enumeration" or not isinstance(kinds, list) or not {"eor", "contractors"} <= set(kinds):
        errors.append("CMS must support both EOR and contractors subpage kinds")
    relation = subpage.get("country", {})
    if relation.get("type") != "relation" or relation.get("target") != COUNTRY_UID:
        errors.append("Subpages cannot be linked to the country-guide collection")
    if subpage.get("contentHtml", {}).get("type") not in {"richtext", "text"}:
        errors.append("Subpage contentHtml is incompatible with the current exporter")
    report["status"] = "BLOCK" if errors else "PASS"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--slug", help="Country slug from config/queue.json")
    choice.add_argument("--iso", help="Actual uppercase ISO code, e.g. NZ")
    parser.add_argument("--output", help="Optional sanitized local JSON receipt")
    args = parser.parse_args()
    iso = args.iso
    if args.slug:
        entry = next((c for c in queue()["countries"] if c["slug"] == args.slug), None)
        if entry is None:
            parser.error("Country is not in config/queue.json")
        iso = entry["iso"]
    report = check_country(iso, args.slug or "")
    if args.output:
        from pathlib import Path
        dest = Path(args.output)
        write_json(dest if dest.is_absolute() else ROOT / dest, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
