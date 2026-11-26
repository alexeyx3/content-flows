#!/usr/bin/env python3
"""Create, cover, publish, and verify a packaged glossary term in Strapi."""

from __future__ import annotations

import argparse
import json
import hashlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from glossary_materials import validate as validate_materials

ROOT = Path(__file__).resolve().parents[1]
API = "https://cms.example.com/api"
TOKEN_FILE = ROOT.parent / "blog" / "config" / "strapi-api-token"
AUTHORS_FILE = ROOT.parent / "blog" / "config" / "blog-authors.json"
EDITOR_USERNAME = json.loads(AUTHORS_FILE.read_text(encoding="utf-8"))["defaults"]["editor"]

# Brands that must never reach the CMS: config/stop-brands.json holds a list of names (empty by default).
_STOP_NAMES = json.loads((ROOT / "config" / "stop-brands.json").read_text(encoding="utf-8"))["brands"]
STOP_BRANDS = re.compile("|".join(rf"\b{re.escape(name)}\b" for name in _STOP_NAMES) or r"(?!)", re.I)


def token() -> str:
    value = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("Strapi token file is empty")
    return value


def call(path: str, method: str = "GET", data: dict | None = None, files=None) -> dict:
    headers = {"Authorization": f"Bearer {token()}"}
    response = requests.request(method, API + path, headers=headers, json=data if files is None else None,
                                files=files, timeout=45)
    if not response.ok:
        raise RuntimeError(f"Strapi {method} {path}: HTTP {response.status_code}: {response.text[:700]}")
    return response.json()


def paths(job: Path) -> tuple[Path, Path]:
    return job / "out" / "strapi-payload.json", job / "out" / "strapi-record.json"


def load_payload(job: Path) -> dict:
    errors = validate_materials(job, for_cms=True)
    if errors:
        raise ValueError("CMS materials blocked: " + "; ".join(errors))
    subprocess.run([sys.executable, str(ROOT / "scripts" / "glossary_job.py"), "package", "--job", str(job)],
                   check=True, capture_output=True, text=True)
    payload_file, _ = paths(job)
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    author, editor = people(job)
    payload["data"]["author"] = author["id"]
    payload["data"]["editors"] = [editor["id"]]
    found = sorted({m.group(0) for m in STOP_BRANDS.finditer(json.dumps(payload["data"], ensure_ascii=False))}, key=str.lower)
    if found:
        raise ValueError(f"CMS materials blocked: {', '.join(found)} — listed in config/stop-brands.json")
    return payload


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def people(job: Path) -> tuple[dict, dict]:
    request = json.loads((job / "request.json").read_text(encoding="utf-8"))
    mapping = json.loads(AUTHORS_FILE.read_text(encoding="utf-8"))
    author_username = request.get("author")
    editor_username = request.get("editor")
    if not author_username or editor_username != EDITOR_USERNAME:
        raise ValueError(f"{job.name}: author and blog editor must be assigned in request.json")
    result = []
    for username in (author_username, editor_username):
        user_id = mapping.get(username)
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError(f"{job.name}: no Strapi user ID for {username!r}")
        result.append({"username": username, "id": user_id})
    return result[0], result[1]


def record(job: Path) -> dict:
    _, state_path = paths(job)
    return json.loads(state_path.read_text(encoding="utf-8"))


def save(job: Path, value: dict) -> None:
    _, state_path = paths(job)
    state_path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dry_run(job: Path) -> None:
    payload = load_payload(job)["data"]
    cover = job / "out" / "cover.webp"
    if not cover.is_file():
        raise ValueError("cover.webp is missing")
    print(json.dumps({
        "term": payload["term"], "slug": payload["slug"], "locale": payload["locale"],
        "definition_chars": len(payload["definition"]), "body_html_chars": len(payload["contentHtml"]),
        "cover_bytes": cover.stat().st_size, "author_id": payload["author"],
        "editor_ids": payload["editors"], "draft_publishedAt": None,
    }, ensure_ascii=False, indent=2))


def create_draft(job: Path) -> None:
    payload = load_payload(job)
    _, state_path = paths(job)
    if state_path.exists():
        raise ValueError(f"Existing Strapi state at {state_path}; refusing duplicate creation")
    payload["data"]["publishedAt"] = None
    result = call("/glossary-terms", "POST", payload)
    entry = result.get("data") or {}
    if not entry.get("id"):
        raise RuntimeError("Strapi returned no glossary term ID")
    attributes = entry.get("attributes", entry)
    if attributes.get("publishedAt"):
        call(f"/glossary-terms/{entry['id']}", "PUT", {"data": {"publishedAt": None}})
        raise RuntimeError("Strapi unexpectedly published the draft; it was immediately unpublished")
    author, editor = people(job)
    value = {"id": entry["id"], "slug": payload["data"]["slug"], "locale": payload["data"]["locale"],
             "status": "draft", "coverMediaId": None, "author": author, "editor": editor,
             "payloadSha256": payload_hash(payload)}
    save(job, value)
    print(json.dumps(value, ensure_ascii=False))


def attach_cover(job: Path) -> None:
    value = record(job)
    if value["status"] != "draft":
        raise ValueError("Cover must be attached before publication")
    if value.get("coverMediaId"):
        print(f"cover already attached: media id {value['coverMediaId']}")
        return
    cover = job / "out" / "cover.webp"
    with cover.open("rb") as image:
        response = call("/upload", "POST", files={"files": (f"glossary-{value['slug']}.webp", image, "image/webp")})
    if not isinstance(response, list) or not response or not response[0].get("id"):
        raise RuntimeError("Strapi upload returned no media ID")
    media_id = response[0]["id"]
    call(f"/glossary-terms/{value['id']}", "PUT", {"data": {"cover": media_id}})
    value["coverMediaId"] = media_id
    save(job, value)
    print(f"cover attached: media id {media_id}")


def publish(job: Path) -> None:
    value = record(job)
    if value["status"] != "draft" or not value.get("coverMediaId"):
        raise ValueError("Publication requires a draft with an attached cover")
    current = load_payload(job)
    current["data"]["publishedAt"] = None
    if value.get("payloadSha256") and value["payloadSha256"] != payload_hash(current):
        raise ValueError("Current reviewed payload differs from the Strapi draft; update and recheck before publication")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    call(f"/glossary-terms/{value['id']}", "PUT", {"data": {"publishedAt": now}})
    value["status"] = "published"
    value["publishedAt"] = now
    save(job, value)
    print(f"published: {value['slug']} (id {value['id']})")


def verify(job: Path) -> None:
    value = record(job)
    result = call(f"/glossary-terms/{value['slug']}/findBySlug?locale={value['locale']}")
    entry = result.get("data") or {}
    attrs = entry.get("attributes", entry)
    payload = load_payload(job)["data"]
    if entry.get("id") != value["id"]:
        raise RuntimeError("Public glossary entry ID does not match the created record")
    for name in ("term", "slug", "locale", "definition", "metaTitle", "metaDescription", "indexable"):
        if attrs.get(name) != payload[name]:
            raise RuntimeError(f"Public glossary {name} does not match the packaged value")
    if attrs.get("content") != payload["contentHtml"]:
        raise RuntimeError("Public glossary body does not match the packaged HTML")
    if not attrs.get("publishedAt") or not attrs.get("content") or not attrs.get("cover"):
        raise RuntimeError("Public glossary entry lacks publication date, content, or cover")
    author, editor = people(job)
    actual_author = attrs.get("author") or {}
    actual_editors = attrs.get("editors") or []
    if actual_author.get("id") != author["id"] or actual_author.get("username") != author["username"]:
        raise RuntimeError("Public glossary author does not match the assigned author")
    if not any(person.get("id") == editor["id"] and person.get("username") == editor["username"]
               for person in actual_editors):
        raise RuntimeError("Public glossary editor does not match the assigned editor")
    print(f"public API verified: {value['slug']}, cover, author and editor present")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["dry-run", "create-draft", "attach-cover", "publish", "verify"])
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    try:
        {"dry-run": dry_run, "create-draft": create_draft, "attach-cover": attach_cover,
         "publish": publish, "verify": verify}[args.command](Path(args.job).resolve())
    except (OSError, ValueError, RuntimeError, requests.RequestException, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
