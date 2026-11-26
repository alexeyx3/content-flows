"""Shared contracts and checks for workflow v2. No network or mutations on import."""
from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = re.compile(r"\[\[VISUAL:([a-z0-9-]+)\]\]")
IMAGE_LINE = re.compile(r'^!\[([^\]\n]*)\]\((https?://[^\s)]+)(?:\s+"([^"\n]*)")?\)$')
PLACEHOLDERS = re.compile(
    r"\[\[(?:VISUAL|QUOTE):[^\]]+\]\]|\b(?-i:VISUAL|QUOTE):\s*[a-z0-9_-]+|"
    r"(?m:^\s*(?:VISUAL|QUOTE):\s*[a-z0-9_-]+)|"
    r"\[NEEDS EVIDENCE\]|\b(?:TODO|FIXME|TBD)\b|\{\{[^}]+\}\}|"
    r"\[(?:INSERT|ADD|ВСТАВИТЬ|ДОБАВИТЬ)\b[^\]]*\](?!\()", re.I)
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def digest(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: JSON object expected")
    return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def job_path(value: str) -> Path:
    p = Path(value)
    return p.resolve() if p.is_absolute() else (ROOT / p).resolve()


def is_v2(job: Path) -> bool:
    if not (job / "job.yaml").exists():
        return False
    return bool(re.search(r"^workflow_version:\s*2\s*(?:#.*)?$",
                          (job / "job.yaml").read_text(encoding="utf-8"), re.M))


def asset_path(job: Path, name: str) -> Path:
    path = (job / name).resolve()
    if not path.is_relative_to((job / "assets").resolve()):
        raise ValueError("the visual file must be inside this job's assets/")
    return path


def spec_digest(visual: dict) -> str:
    spec = {k: v for k, v in visual.items() if k not in {"asset", "inserted_markdown"}}
    return digest(json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def visual_qa_required(job: Path) -> bool:
    path = job / "job.yaml"
    return path.exists() and bool(re.search(r"^visual_qa_version:\s*1\s*(?:#.*)?$",
                                            path.read_text(encoding="utf-8"), re.M))


def primary_data_required(job: Path) -> bool:
    path = job / "job.yaml"
    return path.exists() and bool(re.search(r"^primary_data_research_version:\s*1\s*(?:#.*)?$",
                                            path.read_text(encoding="utf-8"), re.M))


def research_v3_required(job: Path) -> bool:
    path = job / "job.yaml"
    return path.exists() and bool(re.search(r"^research_v3_version:\s*1\s*(?:#.*)?$",
                                            path.read_text(encoding="utf-8"), re.M))


def refresh_required(job: Path) -> bool:
    path = job / "job.yaml"
    return path.exists() and bool(re.search(r"^article_refresh_version:\s*1\s*(?:#.*)?$",
                                            path.read_text(encoding="utf-8"), re.M))


def visual_render_sources_sha() -> str:
    """Invalidate visual review when renderer, logo, fonts, or palette changes."""
    paths = [ROOT / "scripts" / name for name in
             ("visual_renderer.mjs", "visual_geometry.mjs", "visual_mobile_preview.mjs")]
    paths += [ROOT / "config/site-brand-tokens.json"]
    paths += [ROOT / "tools/covers/assets" / name for name in
              ("logo.svg", "Exo2-SemiBold.ttf", "Manrope-Regular.ttf",
               "Manrope-SemiBold.ttf")]
    return digest(b"".join(path.read_bytes() for path in paths))


def visual_layout_errors(job: Path) -> list[str]:
    """Check rendered assets before drafting, independently of the human-style visual pass."""
    if not visual_qa_required(job):
        return []  # Existing jobs keep the contract they started with.
    try:
        manifest = read_json(job / "visuals.json")
        visuals = manifest["visuals"]
        report_path = job / "out/visual-layout-check.json"
        report = read_json(report_path)
    except (OSError, ValueError, KeyError) as exc:
        return [f"no visual layout check: {exc}"]
    problems = []
    rows = report.get("visuals")
    if report.get("version") != 1 or report.get("status") != "PASS" or not isinstance(rows, list):
        return ["visual layout check is not PASS"]
    if report.get("render_sources_sha256") != visual_render_sources_sha():
        problems.append("visual layout check is stale after a renderer or brand change")
    expected_ids = [v["id"] for v in visuals]
    if [row.get("id") for row in rows if isinstance(row, dict)] != expected_ids:
        return problems + ["visual layout check does not match visuals.json"]
    for visual, row in zip(visuals, rows):
        vid, asset = visual["id"], visual.get("asset", {})
        try:
            image = asset_path(job, asset["path"])
            body = image.read_bytes()
            if digest(body) != row["asset_sha256"] or asset.get("sha256") != row["asset_sha256"] or \
                    spec_digest(visual) != row["spec_sha256"] or asset.get("spec_sha256") != row["spec_sha256"]:
                problems.append(f"{vid}: visual QA is stale after a PNG or task change")
            if row.get("asset_path") != str(image.relative_to(job)) or \
                    row.get("current_render") != "PASS":
                problems.append(f"{vid}: no check of the current render")
            if visual["type"] in {"process", "decision"} and row.get("automatic_geometry") != "PASS":
                problems.append(f"{vid}: no automatic diagram geometry check")
            if not body.startswith(b"\x89PNG\r\n\x1a\n") or \
                    (int.from_bytes(body[16:20], "big"), int.from_bytes(body[20:24], "big")) != \
                    (row.get("width"), row.get("height")):
                problems.append(f"{vid}: PNG or dimensions do not match visual QA")
            mobile = (job / row["mobile_path"]).resolve()
            if not mobile.is_relative_to((job / "out/visual-qa").resolve()):
                raise ValueError("mobile preview outside out/visual-qa")
            mobile_bytes = mobile.read_bytes()
            if digest(mobile_bytes) != row["mobile_sha256"] or \
                    not mobile_bytes.startswith(b"\x89PNG\r\n\x1a\n") or \
                    int.from_bytes(mobile_bytes[16:20], "big") != 390:
                problems.append(f"{vid}: mobile preview changed or is not 390 px")
        except (KeyError, OSError, ValueError) as exc:
            problems.append(f"{vid}: no current visual QA ({exc})")
    return problems


def visual_qa_errors(job: Path) -> list[str]:
    """Require both the current deterministic report and independent visual verdict."""
    problems = visual_layout_errors(job)
    if problems or not visual_qa_required(job):
        return problems
    visuals = read_json(job / "visuals.json")["visuals"]
    if not visuals:
        return problems
    report_path = job / "out/visual-layout-check.json"
    rows = read_json(report_path)["visuals"]
    expected_ids = [visual["id"] for visual in visuals]
    try:
        verdict = read_json(job / "visual_qa.json")
    except (OSError, ValueError) as exc:
        return problems + [f"no visual_qa.json with an independent check: {exc}"]
    if verdict.get("version") != 1 or verdict.get("overall") != "PASS" or \
            verdict.get("layout_report_sha256") != digest(report_path.read_bytes()):
        problems.append("visual_qa.json: no PASS for the current layout report")
    checks = verdict.get("visuals")
    if not isinstance(checks, list) or [row.get("id") for row in checks if isinstance(row, dict)] != expected_ids:
        return problems + ["visual_qa.json: the list of diagrams does not match visuals.json"]
    for visual, row, checked in zip(visuals, rows, checks):
        if checked.get("verdict") != "PASS" or checked.get("viewed_full") is not True or \
                checked.get("viewed_mobile") is not True or not str(checked.get("notes", "")).strip() or \
                checked.get("asset_sha256") != row.get("asset_sha256") or \
                checked.get("mobile_sha256") != row.get("mobile_sha256"):
            problems.append(f"{visual['id']}: visual check is not PASS for the current PNG and 390 px preview")
    return problems


def writer_ready_errors(job: Path) -> list[str]:
    """Visual QA may run alongside the writer; render/geometry failures may not."""
    from check_research_links import evidence_table_errors
    from refresh_semantics import gate_errors as semantic_errors
    evidence = job / "evidence.md"
    table_errors = evidence_table_errors(evidence.read_text(encoding="utf-8")) if source_list_only(job) and evidence.is_file() else []
    return validate_inputs(job) + table_errors + visual_layout_errors(job) + semantic_errors(job, "writer")


def evidence_ids(job: Path) -> set[str]:
    from build_internal_package import CLAIM_ID
    ids = set()
    verdict_index = 7  # Standard evidence schema; older tables also end here.
    for line in (job / "evidence.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("*") for c in
                 re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if "entailment_verdict" in cells:
            verdict_index = cells.index("entailment_verdict")
            continue
        if len(cells) <= verdict_index or not CLAIM_ID.fullmatch(cells[0]):
            continue
        if re.match(r"^(supports|partial)\b", cells[verdict_index], re.I):
            ids.add(cells[0])
    return ids


def https(url: str) -> bool:
    return bool(re.fullmatch(r"https://[^\s<>\"()]+", str(url)))


def external_quote_in_scout(quote: dict, packet: dict) -> bool:
    """Only an exact excerpt verified in the outside-quote packet may ship."""
    return any(
        isinstance(candidate, dict)
        and candidate.get("status") == "verified_original"
        and candidate.get("source_url") == quote.get("source")
        and str(candidate.get("quote", "")).strip() == str(quote.get("text", "")).strip()
        for candidate in packet.get("candidates", [])
    )


def validate_inputs(job: Path) -> list[str]:
    """Before writing/rendering: all plans are linked to sections and recorded facts."""
    from delivery_contract import evidence_errors as delivery_evidence_errors
    errors = delivery_evidence_errors(job)
    if not is_v2(job):
        return errors
    required = ["research.md", "brief.md", "sections.json", "evidence.md",
                "visuals.json", "expert_quotes.json"]
    if primary_data_required(job):
        required.append("research.data.json")
    if research_v3_required(job):
        required.extend(("research_map.json", "research.studies.json", "research.quotes.json"))
    for name in required:
        if not (job / name).exists() or not (job / name).read_text(encoding="utf-8").strip():
            errors.append(f"missing {name}")
    if errors:
        return errors
    from answer_contract import evidence_errors as answer_evidence_errors
    errors.extend(answer_evidence_errors(job))
    if errors:
        return errors
    if research_v3_required(job):
        from validate_research_map import validate as validate_research_map
        from validate_primary_data_research import validate as validate_primary_data_research
        from validate_study_research import validate as validate_study_research
        from validate_quote_research import validate as validate_quote_research
        for validator in (validate_research_map, validate_primary_data_research,
                          validate_study_research, validate_quote_research):
            errors.extend(validator(job))
        if errors:
            return errors
    try:
        job_config = (job / "job.yaml").read_text(encoding="utf-8")
        sections = read_json(job / "sections.json")
        section_ids = {s["id"] for s in sections["sections"]}
        facts = evidence_ids(job)
        ig = sections.get("information_gain", [])
        if not ig:
            errors.append("sections.json: no information_gain")
        research_text = (job / "research.md").read_text(encoding="utf-8")
        known_research = set(re.findall(r"\bR-\d+\b", research_text))
        known_data: set[str] = set()
        if primary_data_required(job):
            packet = read_json(job / "research.data.json")
            known_data = {
                item.get("id") for item in packet.get("candidates", [])
                if isinstance(item, dict) and item.get("status") == "read_original"
            }
        known_studies: set[str] = set()
        if research_v3_required(job):
            studies_packet = read_json(job / "research.studies.json")
            known_studies = {
                item.get("id") for item in studies_packet.get("candidates", [])
                if isinstance(item, dict) and item.get("status") == "read_original"
                and item.get("transfer_status") == "usable"
            }
        for item in ig:
            if item.get("section_id") not in section_ids or not item.get("reader_value"):
                errors.append("information_gain: a section and a concrete reader benefit are required")
            if not item.get("research_ref"):
                errors.append("information_gain: no reference to a finding in research.md")
            else:
                refs = set(re.findall(r"\b[RDS]-\d+\b", str(item["research_ref"])))
                if not refs or refs - (known_research | known_data | known_studies):
                    errors.append("information_gain: the reference does not match the findings read from research.md, research.data.json or research.studies.json")
        manifest = read_json(job / "visuals.json")
        visuals = manifest["visuals"]
        if primary_data_required(job):
            audit = sections.get("visual_audit", {})
            selected = audit.get("selected_chart_ids", []) if isinstance(audit, dict) else []
            if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
                errors.append("visual_audit.selected_chart_ids must be a list of D-xx")
                selected = []
            selected_chart_ids = set(selected)
            planned_refs = {
                v.get("data_ref") for v in sections.get("visual_candidates", [])
                if isinstance(v, dict) and v.get("type") in {"bar", "line"}
            }
            actual_refs = {
                v.get("data_ref") for v in visuals
                if isinstance(v, dict) and v.get("type") in {"bar", "line"}
            }
            if None in actual_refs or not actual_refs <= selected_chart_ids:
                errors.append("numeric visual: data_ref must be a selected D-xx")
            omissions = manifest.get("data_omissions", {})
            if not isinstance(omissions, dict):
                errors.append("visuals.json data_omissions must be an object")
                omissions = {}
            for data_id in selected_chart_ids - actual_refs:
                if not str(omissions.get(data_id, "")).strip():
                    errors.append(f"{data_id}: the selected chart was not created and no reason is recorded")
            if actual_refs - planned_refs:
                errors.append("numeric visual: data_ref is missing from visual_candidates")
        quotes = read_json(job / "expert_quotes.json")["quotes"]
        if not isinstance(visuals, list) or not isinstance(quotes, list):
            raise ValueError("visuals and quotes must be arrays")
        if not visuals and not manifest.get("omission_reason"):
            errors.append("no visuals planned: omission_reason is required")
        quote_manifest = read_json(job / "expert_quotes.json")
        if not quotes and not quote_manifest.get("omission_reason"):
            errors.append("no expert comments prepared: omission_reason is required")
        caption_source_gate = re.search(r"^visual_caption_sources_version:\s*1\b", job_config, re.M)
        seen = set()
        for v in visuals:
            vid = v.get("id", "")
            if not ID.fullmatch(vid) or vid in seen:
                errors.append(f"visual: invalid or duplicate id {vid}")
            seen.add(vid)
            for field in ("purpose", "title", "alt", "caption"):
                value = v.get(field)
                if not isinstance(value, str) or not value.strip() or PLACEHOLDERS.search(value):
                    errors.append(f"{vid}: no ready {field}")
                if field in {"title", "alt", "caption"} and isinstance(value, str) and len(value) > 255:
                    errors.append(f"{vid}: {field} exceeds 255 characters of the Strapi media field")
            if v.get("section_id") not in section_ids:
                errors.append(f"{vid}: unknown section_id")
            if any('"' in str(v.get(k, "")) or '\n' in str(v.get(k, ""))
                   for k in ("alt", "title")) or "]" in str(v.get("alt", "")):
                errors.append(f"{vid}: alt/title must be single-line without quotes or ]")
            sources = v.get("sources", [])
            if not sources or any(not s.get("label") or not https(s.get("url", "")) for s in sources):
                errors.append(f"{vid}: sources with a label and an HTTPS url are required")
            if caption_source_gate and re.search(r"(?:^|[.!?]\s+|\n)\s*\*{0,2}(?:Sources?|Источники?):",
                                                 str(v.get("caption", "")), re.I):
                errors.append(f"{vid}: move the source list from caption to sources")
            refs = []
            kind = v.get("type")
            data = v.get("data", {})
            if kind in {"bar", "line"}:
                categories = data.get("categories", [])
                series = data.get("series", [])
                if not 2 <= len(categories) <= 8 or not 1 <= len(series) <= 3 or not data.get("unit"):
                    errors.append(f"{vid}: 2–8 categories, 1–3 series and a unit are required")
                for s in series:
                    values, ids = s.get("values", []), s.get("evidence_ids", [])
                    if not s.get("name") or len(values) != len(categories) or len(ids) != len(values):
                        errors.append(f"{vid}: series size and evidence_ids do not match the categories")
                    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or
                           not math.isfinite(x) or x < 0 for x in values):
                        errors.append(f"{vid}: values must be finite numbers >=0")
                    for group in ids:
                        if not isinstance(group, list) or not group:
                            errors.append(f"{vid}: every point needs evidence_ids")
                        elif any(not isinstance(x, str) for x in group):
                            errors.append(f"{vid}: evidence_ids must be strings")
                        else:
                            refs.extend(group)
                if kind == "line" and not data.get("x_label"):
                    errors.append(f"{vid}: a line chart needs an x_label axis caption")
                if kind == "line" and "x_values" in data:
                    xs = data["x_values"]
                    if len(xs) != len(categories) or any(isinstance(x, bool) or
                            not isinstance(x, (int, float)) or not math.isfinite(x) for x in xs) or \
                            any(a >= b for a, b in zip(xs, xs[1:])):
                        errors.append(f"{vid}: x_values must strictly increase and match the categories")
            elif kind in {"process", "decision"}:
                nodes, edges = data.get("nodes", []), data.get("edges", [])
                node_ids = {n.get("id") for n in nodes}
                if not 2 <= len(nodes) <= 8 or len(node_ids) != len(nodes):
                    errors.append(f"{vid}: 2–8 nodes with unique ids are required")
                for n in nodes:
                    if not n.get("label") or not n.get("evidence_ids"):
                        errors.append(f"{vid}: a node needs a label and evidence_ids")
                    refs.extend(n.get("evidence_ids", []))
                if not edges or any(e.get("from") not in node_ids or e.get("to") not in node_ids
                                    for e in edges):
                    errors.append(f"{vid}: invalid edges between nodes")
                if any(e.get("style", "solid") not in {"solid", "dashed"} for e in edges):
                    errors.append(f"{vid}: edge style must be solid or dashed")
                merge_layout = kind == "process" and data.get("layout") == "two-input-merge"
                if data.get("layout") and not merge_layout:
                    errors.append(f"{vid}: unknown layout scheme")
                if merge_layout:
                    ordered = [n.get("id") for n in nodes]
                    expected = ({(ordered[0], ordered[1]), (ordered[1], ordered[2]),
                                 (ordered[1], ordered[3]), (ordered[2], ordered[4]),
                                 (ordered[3], ordered[4]), (ordered[4], ordered[5]),
                                 (ordered[5], ordered[6])} if len(ordered) == 7 else set())
                    actual = {(e.get("from"), e.get("to")) for e in edges}
                    if len(ordered) != 7 or len(edges) != 7 or actual != expected or any(e.get("label") for e in edges):
                        errors.append(f"{vid}: two-input-merge requires seven nodes: a shared context, two separate inputs, their merge and two next steps; edge labels are not supported")
                # Ordinary process/decision diagrams remain rooted trees.
                incoming = {n: 0 for n in node_ids}
                children = {n: [] for n in node_ids}
                for e in edges:
                    if e.get("from") in node_ids and e.get("to") in node_ids:
                        incoming[e["to"]] += 1
                        children[e["from"]].append(e["to"])
                roots = [n for n in node_ids if incoming[n] == 0]
                visited = set()
                def visit(n):
                    if n in visited:
                        return
                    visited.add(n)
                    for child in children[n]:
                        visit(child)
                if len(roots) == 1:
                    visit(roots[0])
                if not merge_layout and (len(roots) != 1 or len(visited) != len(nodes) or any(x > 1 for x in incoming.values())):
                    errors.append(f"{vid}: edges must form a tree without cycles or merges")
                if not merge_layout and sum(not children[n] for n in node_ids) > 3:
                    errors.append(f"{vid}: more than three terminal branches; split the diagram")
            else:
                errors.append(f"{vid}: type {kind!r} is not part of v1; illustrations are discussed separately")
            if set(refs) - facts:
                errors.append(f"{vid}: unknown evidence_ids {sorted(set(refs) - facts)}")
        seen = set()
        author_match = re.search(r"^author:\s*(\S+)", job_config, re.M)
        author_ids = read_json(ROOT / 'config/blog-authors.json')
        speakers = {author_match.group(1).strip("\"\'") if author_match else "", author_ids['defaults']['editor']}
        profile_path = job / 'raw/speaker-profiles.json'
        profiles = read_json(profile_path) if quotes and profile_path.exists() else {}
        cms_names = {p['username']: p for p in profiles.get('profiles', [])}
        quote_research = read_json(job / "research.quotes.json") if research_v3_required(job) else {}
        staff_quotes = [q for q in quotes if q.get('speaker_kind', 'staff') == 'staff']
        if staff_quotes and (not profiles.get('source') or not profiles.get('checked_at')):
            errors.append('quotes: a Strapi names snapshot with source and checked_at is required')
        for q in quotes:
            qid = q.get("id", "")
            if not ID.fullmatch(qid) or qid in seen:
                errors.append(f"quote: invalid or duplicate id {qid}")
            seen.add(qid)
            speaker_kind = q.get('speaker_kind', 'staff')
            if speaker_kind == 'staff':
                if q.get("speaker") not in speakers:
                    errors.append(f"{qid}: speaker must be the author or editor of this article")
                profile = cms_names.get(q.get('speaker'), {})
                if profile.get('id') != author_ids.get(q.get('speaker')) or not profile.get('name'):
                    errors.append(f'{qid}: no name for the matching Strapi profile')
                elif q.get('attribution') != profile['name']:
                    errors.append(f'{qid}: attribution must match the Strapi name exactly')
            elif speaker_kind == 'external':
                if research_v3_required(job) and not external_quote_in_scout(q, quote_research):
                    errors.append(f'{qid}: the external quote is missing from the verified originals in research.quotes.json')
                if q.get('source_type') != 'verbatim':
                    errors.append(f'{qid}: the external quote must be verbatim')
                if not re.fullmatch(r'https://[^\s)]+', str(q.get('source', ''))):
                    errors.append(f'{qid}: a URL of a readable original of the external quote is required')
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(q.get('published_at', ''))):
                    errors.append(f'{qid}: the original publication date is required')
                if not str(q.get('source_location', '')).strip():
                    errors.append(f'{qid}: the location of the quote in the original is required')
                if len(str(q.get('text', '')).split()) > 25:
                    errors.append(f'{qid}: the external quote is longer than 25 words')
            else:
                errors.append(f'{qid}: unknown speaker_kind')
            for key in ("speaker", "attribution", "text"):
                if not isinstance(q.get(key), str) or not q[key].strip() or PLACEHOLDERS.search(q[key]):
                    errors.append(f"{qid}: no ready {key}")
            if q.get("section_id") not in section_ids:
                errors.append(f"{qid}: unknown section_id")
            if q.get("status") not in {"proposed", "approved", "rejected"}:
                errors.append(f"{qid}: unknown status")
            if q.get("source_type") not in {"editorial_draft", "verbatim"}:
                errors.append(f"{qid}: unknown source_type")
            if q.get("source_type") == "verbatim" and not q.get("source"):
                errors.append(f"{qid}: a real quote needs a source")
            if set(q.get("evidence_ids", [])) - facts:
                errors.append(f"{qid}: unknown evidence_ids")
            if q.get("status") == "approved":
                approval = q.get("approval", {})
                if not all(approval.get(k) for k in ("by", "reference", "at")) or \
                        approval.get("text_sha256") != digest(q["text"] + "\n" + q["attribution"]):
                    errors.append(f"{qid}: the current text and attribution are not approved")
    except (ValueError, KeyError, TypeError) as e:
        errors.append(f"contract error: {e}")
    return errors


def enrichment_block(job: Path) -> str:
    if not is_v2(job):
        return ""
    problems = validate_inputs(job)
    if problems:
        raise ValueError("materials are not ready:\n- " + "\n- ".join(problems))
    return ("# ENRICHMENT CONTRACT\n" + (ROOT / "knowledge" / "article-enrichment.md").read_text(encoding="utf-8")
            + "\n# VISUAL PLAN AND VERIFIED DATA\n" + (job / "visuals.json").read_text(encoding="utf-8")
            + "\n# EXPERT COMMENTS — INSERT EXACT TEXT AND ATTRIBUTION\n"
            + (job / "expert_quotes.json").read_text(encoding="utf-8"))


def source_list_only(job: Path) -> bool:
    path = job / "job.yaml"
    return path.exists() and bool(re.search(r"^source_policy_version:\s*1\b", path.read_text(encoding="utf-8"), re.M))


def visual_markdown(v: dict, *, sources_at_end: bool = False) -> str:
    title = v["title"]
    source_links = " · ".join(f'[{s["label"]}]({s["url"]})' if s.get("public", True) and not sources_at_end
                              else s["label"] for s in v["sources"])
    return (f'![{v["alt"]}]({v["asset"]["url"]} "{title}")\n\n'
            f'Caption: {v["caption"]} {source_links}')


def quote_markdown(q: dict, *, sources_at_end: bool = False) -> str:
    attribution = q["attribution"]
    if q.get("speaker_kind") == "external" and not sources_at_end:
        attribution = f'[{attribution}]({q["source"]})'
    return "> " + q["text"].replace("\n", "\n> ") + "\n>\n> — " + attribution


def normalized(text: str) -> str:
    return " ".join(text.replace("\r\n", "\n").split())


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            self.images.append(dict(attrs))


def fetch_remote_image(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "blog-material-check/2"})
    with urllib.request.urlopen(req, timeout=25) as response:
        if not response.geturl().startswith("https://"):
            raise ValueError("the image redirects to HTTP")
        body = response.read(5 * 1024 * 1024 + 1)
        if len(body) > 5 * 1024 * 1024:
            raise ValueError("the image exceeds 5 MB")
        if not (body.startswith(b"\x89PNG\r\n\x1a\n") or body.startswith(b"\xff\xd8\xff")):
            raise ValueError("Google Docs needs an accessible PNG or JPEG")
        return body


def check_remote_image(url: str, expected_hash: str | None = None) -> None:
    body = fetch_remote_image(url)
    if expected_hash and digest(body) != expected_hash:
        raise ValueError("the remote image differs from the verified file")


def article_errors(job: Path, target: str, remote: bool = False) -> list[str]:
    """Validate article inputs/materialization, before an independent QA verdict exists."""
    from md_to_strapi_html import convert
    problems = []
    edited = job / "edited.md"
    if not edited.exists():
        return ["no edited.md"]
    text = edited.read_text(encoding="utf-8")
    from refresh_semantics import gate_errors as semantic_errors
    problems.extend(semantic_errors(job, "writer"))
    problems.extend(semantic_errors(job, "after"))
    if source_list_only(job):
        from check_research_links import evidence_reference_errors, evidence_table_errors, source_policy_errors
        evidence = job / "evidence.md"
        if not evidence.exists():
            problems.append("no evidence.md to check Sources")
        else:
            evidence_text = evidence.read_text(encoding="utf-8")
            problems.extend(evidence_table_errors(evidence_text))
            problems.extend(evidence_reference_errors(evidence_text, text))
            problems.extend(source_policy_errors(job, evidence_text, text))
    for match in PLACEHOLDERS.finditer(text):
        problems.append(f"service placeholder: {match.group(0)}")
    title, expected_html = convert(text)
    parser = Images()
    parser.feed(expected_html)
    for img in parser.images:
        if not https(img.get("src", "")) or not img.get("alt", "").strip():
            problems.append("image: an absolute HTTPS src and alt are required")
    if not is_v2(job):
        # Existing jobs keep their contract, but placeholders and stale body are always rejected.
        if target == "strapi":
            path = job / "out" / "article.html"
            if not path.exists() or path.read_text(encoding="utf-8") != expected_html:
                problems.append("out/article.html does not match edited.md; repackage the article")
        if remote:
            for img in parser.images:
                if https(img.get("src", "")):
                    try:
                        check_remote_image(img["src"])
                    except Exception as e:
                        problems.append(f"image unavailable: {e}")
        return problems
    problems.extend(validate_inputs(job))
    if problems:
        return problems
    problems.extend(visual_qa_errors(job))
    visuals = read_json(job / "visuals.json")["visuals"]
    expected_urls = []
    for v in visuals:
        vid, asset = v["id"], v.get("asset", {})
        try:
            data = asset_path(job, asset["path"]).read_bytes()
            if digest(data) != asset["sha256"] or asset.get("spec_sha256") != spec_digest(v):
                problems.append(f"{vid}: the file or task changed after rendering")
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                problems.append(f"{vid}: PNG expected")
            if not https(asset.get("url", "")) or not asset.get("media_id"):
                problems.append(f"{vid}: no public image for the article")
                continue
            if target == "strapi" and str(asset["media_id"]).startswith("drive:"):
                problems.append(f"{vid}: the image is hosted for Google Docs only; a separate upload to Strapi is required")
            expected_urls.append(asset["url"])
            if text.count(visual_markdown(v, sources_at_end=source_list_only(job))) != 1:
                problems.append(f"{vid}: there is no single ready image with a caption and sources")
            if not asset.get("remote_path") or not asset.get("remote_sha256"):
                problems.append(f"{vid}: no saved PNG from the CMS for QA")
            if asset.get("remote_path") and asset.get("remote_sha256"):
                delivered = asset_path(job, asset["remote_path"]).read_bytes()
                if digest(delivered) != asset["remote_sha256"]:
                    problems.append(f"{vid}: the file for QA differs from the uploaded PNG")
            if remote:
                check_remote_image(asset["url"], asset.get("remote_sha256", asset["sha256"]))
        except (KeyError, ValueError, OSError) as e:
            problems.append(f"{vid}: no ready current image ({e})")
        except Exception as e:
            problems.append(f"{vid}: remote image unavailable ({e})")
    if sorted(img.get("src", "") for img in parser.images) != sorted(expected_urls):
        problems.append("images in the article do not match visuals.json")
    for img in parser.images:
        if not img.get("title", "").strip():
            problems.append("image: title is missing")
    quotes = read_json(job / "expert_quotes.json")["quotes"]
    for q in quotes:
        block = quote_markdown(q, sources_at_end=source_list_only(job))
        if q["status"] == "rejected":
            if normalized(block) in normalized(text):
                problems.append(f'{q["id"]}: a rejected quote remained in the article')
        elif normalized(text).count(normalized(block)) != 1:
            problems.append(f'{q["id"]}: the quote or attribution was changed or not inserted exactly once')
        elif target == "strapi" and q["status"] != "approved":
            problems.append(f'{q["id"]}: quote not approved')
    for name, expected in (("out/article.md", text), ("out/article.html", cms_image_html(expected_html))):
        p = job / name
        if not p.exists() or p.read_text(encoding="utf-8") != expected:
            problems.append(f"{name} does not match edited.md; repackage the article")
    from strapi_publish import read_meta, stop_brand_errors, validate_meta
    try:
        meta = read_meta(job)
        config = (job / "job.yaml").read_text(encoding="utf-8") if (job / "job.yaml").exists() else ""
        article_type_match = re.search(r"^article_type:\s*([^\s#]+)", config, re.M)
        article_type = article_type_match.group(1).strip("\"'").lower() if article_type_match else None
        problems.extend(validate_meta(meta, article_type))
        problems.extend(stop_brand_errors(meta, expected_html))
        if meta.get("title") != title:
            problems.append("title in out/meta.md does not match the final H1")
    except OSError:
        problems.append("no out/meta.md")
    return problems


QA_FILES = ("job.yaml", "edited.md", "visuals.json", "expert_quotes.json", "evidence.md", "sections.json",
            "research.md", "out/meta.md", "qa_report.md", "raw/speaker-profiles.json")


def qa_fingerprint(job: Path) -> dict:
    # Approval status is a later human decision; QA binds the exact quote text, speaker and facts.
    hashes = {name: digest((job / name).read_bytes()) for name in QA_FILES
              if name != "expert_quotes.json" and
              (name != 'raw/speaker-profiles.json' or (job / name).exists())}
    quotes = read_json(job / "expert_quotes.json")
    content = [{k: v for k, v in q.items() if k not in {"status", "approval"}} for q in quotes["quotes"]]
    hashes["expert_quotes.json"] = digest(json.dumps(content, sort_keys=True, ensure_ascii=False))
    from delivery_contract import enabled as delivery_enabled
    if delivery_enabled(job):
        for name in ("brief.md", "qa_delivery.json"):
            hashes[name] = digest((job / name).read_bytes())
    if refresh_required(job):
        for name in ("refresh_plan.json", "refresh_evidence.md", "baseline/article.md"):
            path = job / name
            body = path.read_bytes() if path.is_file() else b""
            if not body:
                raise ValueError(f"required refresh material is missing: {name}")
            hashes[name] = digest(body)
        from refresh_semantics import required as semantic_required
        if semantic_required(job):
            for name in ("raw/semantic-queries.json", "semantics_plan.json",
                         "metrics/semantics-before/coverage.json", "metrics/semantics-after/coverage.json"):
                hashes[name] = digest((job / name).read_bytes())
    if research_v3_required(job):
        for name in ("research_map.json", "research.data.json", "research.studies.json", "research.quotes.json"):
            if (job / name).exists():
                hashes[name] = digest((job / name).read_bytes())
    if visual_qa_required(job):
        for name in ("out/visual-layout-check.json", "visual_qa.json"):
            if (job / name).exists():
                hashes[name] = digest((job / name).read_bytes())
    return hashes


def qa_is_pass(job: Path) -> bool:
    """Accept a reported PASS only with every enabled current native QA audit."""
    try:
        report = (job / "qa_report.md").read_text(encoding="utf-8")
    except OSError:
        return False
    verdicts = re.findall(r"^overall:[ \t]*(PASS|BLOCK)[ \t]*$", report, re.M | re.I)
    if not verdicts or any(v.upper() != "PASS" for v in verdicts) or re.search(
            r"Gate\s+\d+[^\n:]*:\s*(?:\*\*)?BLOCK\b", report, re.I):
        return False
    from answer_contract import qa_errors as answer_qa_errors
    from delivery_contract import qa_errors as delivery_qa_errors
    return not (answer_qa_errors(job) or delivery_qa_errors(job))


def export_errors(job: Path, target: str, remote: bool = True) -> list[str]:
    # Translation has a distinct fidelity/review contract; never fall through to
    # new-article evidence or let fidelity PASS authorize a CMS write.
    config = job / "job.yaml"
    if config.exists() and re.search(r"^article_translation_version:\s*1\b", config.read_text(), re.M):
        if __package__:
            from .blog_translation import export_errors as translation_export_errors
        else:
            from blog_translation import export_errors as translation_export_errors
        return translation_export_errors(job, target, remote)
    problems = article_errors(job, target, remote)
    from delivery_contract import qa_errors as delivery_qa_errors
    problems.extend(delivery_qa_errors(job))
    if not is_v2(job) or problems:
        return problems
    from answer_contract import qa_errors as answer_qa_errors
    problems.extend(answer_qa_errors(job))
    try:
        receipt = read_json(job / "qa_receipt.json")
        if not qa_is_pass(job) or receipt.get("hashes") != qa_fingerprint(job):
            problems.append("QA is not PASS or the verified materials changed; repeat QA and seal-qa")
    except (OSError, ValueError, KeyError):
        problems.append("no current qa_receipt.json; QA PASS and seal-qa are required")
    if target == "strapi":
        try:
            approval = read_json(job / "review_approval.json")
            if not all(approval.get(k) for k in ("by", "reference", "at")) or \
                    approval.get("article_sha256") != digest((job / "edited.md").read_bytes()):
                problems.append("the current version of the article is not approved")
        except (OSError, ValueError):
            problems.append("no review_approval.json: proofreading and approval of the article come first")
    return problems


def cms_image_html(html: str) -> str:
    """Match CMS image-attribute normalization before sanitizer comparison."""
    return re.sub(r"<img\b[^>]*>",
                  lambda match: re.sub(r'\s+title="[^"]*"', '', match.group(0))
                  .replace('&#x27;', "'").replace('&#39;', "'"), html)


def bind_article_visuals(job: Path) -> None:
    bind_visuals = True
    text = (job / "edited.md").read_text(encoding="utf-8")
    if is_v2(job):
        problems = validate_inputs(job)
        if problems:
            raise ValueError("\n".join(problems))
        manifest = read_json(job / "visuals.json")
        if bind_visuals:
            for v in manifest["visuals"]:
                asset = v.get("asset", {})
                if not asset.get("url") or asset.get("spec_sha256") != spec_digest(v) or \
                        digest(asset_path(job, asset["path"]).read_bytes()) != asset.get("sha256"):
                    raise ValueError(f'{v["id"]}: render and upload the current image first')
                marker = f'[[VISUAL:{v["id"]}]]'
                block = visual_markdown(v, sources_at_end=source_list_only(job))
                previous = v.get("inserted_markdown")
                if text.count(marker) == 1:
                    text = text.replace(marker, block)
                elif previous and text.count(previous) == 1:
                    text = text.replace(previous, block)
                elif text.count(block) != 1:
                    raise ValueError(f'{v["id"]}: no single marker or previous block; restore the insertion point')
                v["inserted_markdown"] = block
            if MARKER.search(text):
                raise ValueError("an unknown or duplicate VISUAL marker remained")
            write_json(job / "visuals.json", manifest)
            (job / "edited.md").write_text(text, encoding="utf-8")
