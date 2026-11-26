"""Checks and materialization for the optional glossary enrichment contract."""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG_V2 = ROOT.parent / "blog"
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MARKER = re.compile(r"\[\[VISUAL:([a-z0-9-]+)\]\]")
IMAGE = re.compile(r'^!\[([^\]\n]+)\]\((https://[^\s)]+) "([^"\n]+)"\)$', re.M)


def read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: expected object")
    return value


def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def enriched(job: Path) -> bool:
    return read(job / "request.json").get("workflow_version", 1) >= 2


def humanization_errors(job: Path) -> list[str]:
    if not read(job / "request.json").get("humanization_required"):
        return []
    report_path = job / "humanization_report.md"
    body_path = job / "edited.md"
    if not report_path.is_file() or not body_path.is_file():
        return ["humanization_report.md and edited.md required before QA"]
    report = report_path.read_text(encoding="utf-8")
    expected = digest(body_path.read_bytes())
    errors = []
    if not re.search(r"(?m)^Scope: whole page\s*$", report):
        errors.append("humanization_report.md: whole-page scope required")
    if not re.search(rf"(?m)^edited\.md SHA256: {expected}\s*$", report):
        errors.append("humanization_report.md: stale or missing edited.md checksum")
    return errors


def evidence_ids(text: str) -> set[str]:
    return set(evidence_claims(text))


def evidence_claims(text: str) -> dict[str, dict]:
    found = {}
    blocks = re.split(r"(?=^### Claim [A-Z][A-Z0-9-]+\b)", text, flags=re.M)
    for block in blocks:
        match = re.match(r"### Claim ([A-Z][A-Z0-9-]+)\b", block)
        if not match:
            continue
        verdict = re.search(r"(?im)^-\s*\*\*Verdict:\*\*\s*\*{0,2}(supports|partial)\b", block)
        if verdict:
            source_part = block.split("**Article link", 1)[0]
            urls = [value.rstrip(".,;") for value in re.findall(r"https://[^\s)]+", source_part)]
            link = re.search(r"\*\*Article link:\*\*\s*\*{0,2}(required|optional|forbidden)\b|"
                             r"\*\*Article link:\s*(required|optional|forbidden)\*\*", block, re.I)
            decision = next((group for group in link.groups() if group), "") if link else ""
            found[match.group(1)] = {"urls": urls, "link": decision.lower()}
    return found


def visual_spec_hash(visual: dict) -> str:
    value = {k: v for k, v in visual.items() if k not in {"asset", "inserted_markdown"}}
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def validate(job: Path, *, for_qa: bool = False, for_cms: bool = False) -> list[str]:
    if not enriched(job):
        return []
    errors = []
    if for_qa or for_cms:
        errors.extend(humanization_errors(job))
    for name in ("research.md", "evidence.md", "sections.json", "visuals.json", "expert_quotes.json"):
        if not (job / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        return errors
    research = (job / "research.md").read_text(encoding="utf-8")
    evidence = (job / "evidence.md").read_text(encoding="utf-8")
    refs = set(re.findall(r"^### (R-\d+)\b", research, re.M))
    claims = evidence_claims(evidence)
    facts = set(claims)
    sections = read(job / "sections.json")
    section_ids = {s["id"] for s in sections["sections"]}
    ig = sections.get("information_gain", [])
    if not ig:
        errors.append("sections.json: information_gain required")
    for item in ig:
        if item.get("section_id") not in section_ids or not item.get("reader_value"):
            errors.append("information_gain: section_id and reader_value required")
        item_refs = set(re.findall(r"R-\d+", str(item.get("research_ref", ""))))
        if not item_refs or item_refs - refs:
            errors.append("information_gain: unknown research_ref")
        if item_refs - set(re.findall(r"\bR-\d+\b", evidence)):
            errors.append("information_gain: research finding lacks evidence mapping")
    visuals = read(job / "visuals.json")
    quotes = read(job / "expert_quotes.json")
    if not isinstance(visuals.get("visuals"), list) or not isinstance(quotes.get("quotes"), list):
        return errors + ["visuals/quotes must be lists"]
    if not visuals["visuals"] and not visuals.get("omission_reason"):
        errors.append("visuals.json: omission_reason required for no visual")
    if not quotes["quotes"] and not quotes.get("omission_reason"):
        errors.append("expert_quotes.json: omission_reason required for no comment")
    seen = set()
    for v in visuals["visuals"]:
        vid = v.get("id", "")
        if not ID.fullmatch(vid) or vid in seen:
            errors.append(f"visual {vid}: invalid or duplicate id")
        seen.add(vid)
        if v.get("section_id") not in section_ids or v.get("type") not in {"bar", "line", "process", "decision"}:
            errors.append(f"visual {vid}: invalid section or type")
        for key in ("purpose", "title", "alt", "caption"):
            value = v.get(key)
            if not isinstance(value, str) or not value.strip() or (key != "purpose" and len(value) > 255):
                errors.append(f"visual {vid}: invalid {key}")
        if any('"' in str(v.get(k, "")) or "\n" in str(v.get(k, "")) for k in ("alt", "title")) or "]" in str(v.get("alt", "")):
            errors.append(f"visual {vid}: alt/title cannot contain quotes, newline or ]")
        if any(not s.get("label") or not re.fullmatch(r"https://[^\s]+", s.get("url", "")) for s in v.get("sources", [])) or not v.get("sources"):
            errors.append(f"visual {vid}: labelled HTTPS sources required")
        data = v.get("data", {})
        if v.get("type") in {"bar", "line"}:
            categories = data.get("categories", [])
            series_rows = data.get("series", [])
            if not 2 <= len(categories) <= 8 or not 1 <= len(series_rows) <= 3 or not data.get("unit"):
                errors.append(f"visual {vid}: chart needs 2–8 categories, 1–3 series and unit")
            if v.get("type") == "line" and not data.get("x_label"):
                errors.append(f"visual {vid}: line chart needs x_label")
            if "x_values" in data:
                xs = data["x_values"]
                if len(xs) != len(categories) or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in xs) or any(a >= b for a, b in zip(xs, xs[1:])):
                    errors.append(f"visual {vid}: x_values must rise strictly")
            for series in series_rows:
                if len(series.get("values", [])) != len(categories) or len(series.get("evidence_ids", [])) != len(categories):
                    errors.append(f"visual {vid}: chart series length mismatch")
                if not series.get("name") or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 for x in series.get("values", [])):
                    errors.append(f"visual {vid}: series name or finite nonnegative values missing")
                for ids in series.get("evidence_ids", []):
                    if not ids or set(ids) - facts:
                        errors.append(f"visual {vid}: chart point lacks verified evidence IDs")
        else:
            nodes = data.get("nodes", [])
            if not 2 <= len(nodes) <= 8 or not data.get("edges"):
                errors.append(f"visual {vid}: diagram needs nodes and edges")
            node_ids = {n.get("id") for n in nodes}
            if len(node_ids) != len(nodes) or any(not n.get("label") for n in nodes):
                errors.append(f"visual {vid}: diagram node IDs and labels must be unique and present")
            for node in nodes:
                if not node.get("evidence_ids") or set(node["evidence_ids"]) - facts:
                    errors.append(f"visual {vid}: diagram node lacks verified evidence IDs")
            edges = data.get("edges", [])
            if any(e.get("from") not in node_ids or e.get("to") not in node_ids for e in edges):
                errors.append(f"visual {vid}: diagram edge references unknown node")
            else:
                incoming = {node: 0 for node in node_ids}
                children = {node: [] for node in node_ids}
                for edge in edges:
                    incoming[edge["to"]] += 1
                    children[edge["from"]].append(edge["to"])
                roots = [node for node in node_ids if incoming[node] == 0]
                seen_nodes = set()
                def walk(node):
                    if node in seen_nodes:
                        return
                    seen_nodes.add(node)
                    for child in children[node]:
                        walk(child)
                if len(roots) == 1:
                    walk(roots[0])
                if len(roots) != 1 or len(seen_nodes) != len(nodes) or any(count > 1 for count in incoming.values()) or sum(not children[node] for node in node_ids) > 3:
                    errors.append(f"visual {vid}: diagram must be a rooted tree with at most three leaves")
        if for_qa:
            asset = v.get("asset", {})
            path = (job / asset.get("path", "")).resolve()
            if not path.is_relative_to((job / "assets").resolve()) or not path.is_file():
                errors.append(f"visual {vid}: rendered asset missing")
            elif digest(path.read_bytes()) != asset.get("sha256") or visual_spec_hash(v) != asset.get("spec_sha256"):
                errors.append(f"visual {vid}: rendered asset stale")
            if not re.fullmatch(r"https://[^\s]+", asset.get("url", "")) or not asset.get("media_id"):
                errors.append(f"visual {vid}: verified CMS media URL missing")
            remote = (job / asset.get("remote_path", "")).resolve()
            if not remote.is_relative_to((job / "assets").resolve()) or not remote.is_file() or digest(remote.read_bytes()) != asset.get("remote_sha256"):
                errors.append(f"visual {vid}: verified CMS image copy missing or stale")
    request = read(job / "request.json")
    profiles_path = job / "raw" / "speaker-profiles.json"
    profiles = read(profiles_path) if quotes["quotes"] and profiles_path.is_file() else {}
    profile_rows = {p.get("username"): p for p in profiles.get("profiles", [])}
    names = {key: value.get("name") for key, value in profile_rows.items()}
    if quotes["quotes"] and (not profiles.get("source") or not profiles.get("checked_at")):
        errors.append("expert comments: current Strapi speaker profile snapshot required")
    for q in quotes["quotes"]:
        qid = q.get("id", "")
        if not ID.fullmatch(qid) or qid in seen:
            errors.append(f"comment {qid}: invalid or duplicate id")
        seen.add(qid)
        if q.get("section_id") not in section_ids or q.get("speaker") not in {request.get("author"), request.get("editor")}:
            errors.append(f"comment {qid}: invalid section or speaker")
        if not q.get("text") or not q.get("attribution") or q.get("source_type") not in {"verbatim", "editorial_draft"}:
            errors.append(f"comment {qid}: text, attribution and source_type required")
        if q.get("attribution") != names.get(q.get("speaker")):
            errors.append(f"comment {qid}: attribution must match Strapi profile name")
        mapping = read(ROOT.parent / "blog" / "config" / "blog-authors.json")
        if profile_rows.get(q.get("speaker"), {}).get("id") != mapping.get(q.get("speaker")):
            errors.append(f"comment {qid}: speaker profile ID does not match CMS mapping")
        if q.get("source_type") == "verbatim" and not q.get("source"):
            errors.append(f"comment {qid}: verbatim source required")
        if q.get("status") not in {"proposed", "approved", "rejected"} or set(q.get("evidence_ids", [])) - facts:
            errors.append(f"comment {qid}: invalid status or evidence IDs")
        if q.get("status") == "approved":
            approval = q.get("approval", {})
            if not all(approval.get(k) for k in ("by", "reference", "at")) or approval.get("text_sha256") != digest(q["text"] + "\n" + q["attribution"]):
                errors.append(f"comment {qid}: current wording lacks approval")
        if for_cms and q.get("status") == "proposed":
            errors.append(f"comment {qid}: publisher approval required before CMS")
    if for_qa:
        body = (job / "edited.md").read_text(encoding="utf-8")
        if len(re.findall(r"^!\[", body, re.M)) != len(visuals["visuals"]) or re.search(r"<img\b", body, re.I):
            errors.append("edited.md: unmanaged or malformed image")
        for claim_id, claim in claims.items():
            if not claim["link"]:
                errors.append(f"claim {claim_id}: Article link decision missing")
            if claim["link"] == "required" and (not claim["urls"] or not any(url in body for url in claim["urls"])):
                errors.append(f"claim {claim_id}: required primary-source link missing from article")
        images = IMAGE.findall(body)
        if len(images) != len(visuals["visuals"]):
            errors.append("edited.md: image count differs from visual manifest")
        for v in visuals["visuals"]:
            a = v.get("asset", {})
            if (v.get("alt"), a.get("url"), v.get("title")) not in images or not v.get("inserted_markdown") or v["inserted_markdown"] not in body:
                errors.append(f"visual {v['id']}: exact image/caption/source block missing from edited.md")
        for q in quotes["quotes"]:
            block = "> " + q["text"].replace("\n", "\n> ") + "\n>\n> — " + q["attribution"]
            if q["status"] != "rejected" and block not in body:
                errors.append(f"comment {q['id']}: exact block missing")
            if q["status"] == "rejected" and block in body:
                errors.append(f"comment {q['id']}: rejected block remains")
    return errors


def bind_visuals(job: Path) -> None:
    errors = validate(job)
    if errors:
        raise ValueError("; ".join(errors))
    body_path = job / "edited.md"
    body = body_path.read_text(encoding="utf-8")
    manifest = read(job / "visuals.json")
    expected = {v["id"] for v in manifest["visuals"]}
    found = set(MARKER.findall(body))
    if found - expected or len(MARKER.findall(body)) != len(found):
        raise ValueError(f"unexpected or duplicate visual markers: {sorted(found - expected)}")
    for v in manifest["visuals"]:
        marker = f'[[VISUAL:{v["id"]}]]'
        previous = v.get("inserted_markdown", "")
        if body.count(marker) + (body.count(previous) if previous else 0) != 1:
            raise ValueError(f"visual {v['id']}: expected one marker or exact previous image block")
        a = v.get("asset", {})
        path = (job / a.get("path", "")).resolve()
        if not path.is_relative_to((job / "assets").resolve()) or not path.is_file() or digest(path.read_bytes()) != a.get("sha256") or visual_spec_hash(v) != a.get("spec_sha256"):
            raise ValueError(f"visual {v['id']}: render is missing or stale")
        if not re.fullmatch(r"https://[^\s]+", a.get("url", "")) or not a.get("media_id"):
            raise ValueError(f"visual {v['id']}: CMS media has not been verified")
        sources = " · ".join(f'[{s["label"]}]({s["url"]})' for s in v["sources"] if s.get("public", True))
        inserted = f'![{v["alt"]}]({a["url"]} "{v["title"]}")\n\nCaption: {v["caption"]}'
        if sources:
            inserted += " " + sources
        body = body.replace(marker if marker in body else previous, inserted)
        v["inserted_markdown"] = inserted
    body_path.write_text(body, encoding="utf-8")
    (job / "visuals.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_visuals(job: Path) -> None:
    errors = validate(job)
    if errors:
        raise ValueError("; ".join(errors))
    data = read(job / "visuals.json")
    (job / "assets").mkdir(exist_ok=True)
    for visual in data["visuals"]:
        path = job / "assets" / f'{visual["id"]}.png'
        result = subprocess.run(["node", str(BLOG_V2 / "scripts" / "visual_renderer.mjs"), str(path)],
                                input=json.dumps(dict(visual, language="en"), ensure_ascii=False),
                                text=True, capture_output=True)
        if result.returncode:
            raise ValueError(f'{visual["id"]}: {result.stderr.strip()}')
        dimensions = json.loads(result.stdout)
        sha = digest(path.read_bytes())
        asset = {"path": str(path.relative_to(job)), "sha256": sha,
                 "spec_sha256": visual_spec_hash(visual), **dimensions}
        previous = visual.get("asset", {})
        if previous.get("sha256") == sha and previous.get("spec_sha256") == asset["spec_sha256"]:
            asset.update({k: previous[k] for k in ("url", "media_id", "delivery_url", "remote_sha256", "remote_path", "pixels_identical") if k in previous})
        visual["asset"] = asset
        print(f'{visual["id"]}: {dimensions["width"]}×{dimensions["height"]}')
    (job / "visuals.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_blog_visual_script(job: Path, command: str, dry_run: bool = False) -> None:
    errors = validate(job)
    if errors:
        raise ValueError("; ".join(errors))
    if command == "render_visuals.py":
        render_visuals(job)
        return
    script = BLOG_V2 / "scripts" / command
    if not script.is_file():
        raise ValueError(f"shared blog visual tool missing: {script}")
    args = [sys.executable, str(script), "--job", str(job)]
    if dry_run:
        args.append("--dry-run")
    subprocess.run(args, check=True)
