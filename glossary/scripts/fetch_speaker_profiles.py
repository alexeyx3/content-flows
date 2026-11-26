#!/usr/bin/env python3
"""Save exact public Strapi names for a glossary job's author and editor."""
from __future__ import annotations

import argparse
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from strapi_glossary import API, call, people


def fetch(job: Path) -> Path:
    author, editor = people(job)
    expected = {author["username"]: author["id"], editor["username"]: editor["id"]}
    query = urllib.parse.urlencode({
        "filters[author][id][$eq]": author["id"], "sort": "id:desc",
        "pagination[pageSize]": 5, "populate[author]": "*", "populate[editors]": "*",
    })
    response = call("/articles?" + query)
    rows = response.get("data", response) if isinstance(response, dict) else response
    found = {}
    for row in rows:
        fields = row.get("attributes", row)
        for relation in ("author", "editors"):
            linked = fields.get(relation, [])
            linked = linked.get("data", linked) if isinstance(linked, dict) else linked
            for person in linked if isinstance(linked, list) else [linked]:
                if not isinstance(person, dict):
                    continue
                details = person.get("attributes", person)
                for username, user_id in expected.items():
                    if person.get("id") == user_id and details.get("name"):
                        if details.get("username") and details["username"] != username:
                            raise ValueError("CMS profile ID/username mismatch")
                        record = {"id": user_id, "username": username, "name": details["name"]}
                        if username in found and found[username] != record:
                            raise ValueError("conflicting CMS speaker names")
                        found[username] = record
    if set(found) != set(expected):
        raise ValueError("CMS speaker profiles missing: " + ", ".join(sorted(set(expected) - set(found))))
    target = job / "raw" / "speaker-profiles.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"source": API + "/articles?" + query,
                                  "checked_at": datetime.now(timezone.utc).isoformat(),
                                  "profiles": [found[name] for name in expected]},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    print(fetch(Path(args.job).resolve()))
