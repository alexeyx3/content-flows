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
    r"\[\[(?:VISUAL|QUOTE):[^\]]+\]\]|(?-i:\b(?:VISUAL|QUOTE):)\s*[a-z0-9_-]+|"
    r"\[NEEDS EVIDENCE\]|\b(?:TODO|FIXME|TBD)\b|\{\{[^}]+\}\}|"
    r"\[(?:INSERT|ADD|ВСТАВИТЬ|ДОБАВИТЬ)\b[^\]]*\]", re.I)
# In this verified Spanish source, “todo trabajador” means “every worker”.
# Preserve its exact bibliography title/URL without exempting draft markers
# elsewhere in the article or even elsewhere on the same Sources line.
SPANISH_WORKER_SOURCE_TITLE = (
    "Sunafil: El sueldo de todo trabajador no puede ser inferior a una "
    "remuneración mínima vital y debe estar en planilla")
SPANISH_WORKER_SOURCE_URL = (
    "https://www.gob.pe/institucion/sunafil/noticias/1364909-"
    "sunafil-el-sueldo-de-todo-trabajador-no-puede-ser-inferior-a-una-"
    "remuneracion-minima-vital-y-debe-estar-en-planilla")
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def placeholder_matches(text: str):
    source_heading = re.search(r"^## Sources\s*$", text, re.M)
    literal = f"[{SPANISH_WORKER_SOURCE_TITLE}]({SPANISH_WORKER_SOURCE_URL})"
    allowed = ([m.span() for m in re.finditer(re.escape(literal), text)
                if m.start() > source_heading.end()] if source_heading else [])
    for match in PLACEHOLDERS.finditer(text):
        if match.group().lower() == "todo" and any(
                start <= match.start() and match.end() <= end for start, end in allowed):
            continue
        yield match


def digest(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a JSON object")
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
        raise ValueError("the visual file must be inside assets/ of this job")
    return path


def spec_digest(visual: dict) -> str:
    spec = {k: v for k, v in visual.items() if k not in {"asset", "inserted_markdown"}}
    return digest(json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def evidence_ids(job: Path) -> set[str]:
    ids = set()
    for line in (job / "evidence.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*([A-Z][A-Z0-9-]*-\d+)\s*\|", line)
        verdict = line.strip().strip("|").split("|")[-1].strip().strip("*").lower()
        if match and re.match(r"^(supports|partial)\b", verdict):
            ids.add(match.group(1))
    return ids


def https(url: str) -> bool:
    return bool(re.fullmatch(r"https://[^\s<>\"()]+", str(url)))


def validate_inputs(job: Path) -> list[str]:
    """Before writing/rendering: all plans are linked to sections and recorded facts."""
    if not is_v2(job):
        return []
    errors = []
    for name in ("research.md", "brief.md", "sections.json", "evidence.md",
                 "visuals.json", "expert_quotes.json"):
        if not (job / name).exists() or not (job / name).read_text(encoding="utf-8").strip():
            errors.append(f"missing {name}")
    if errors:
        return errors
    try:
        sections = read_json(job / "sections.json")
        section_ids = {s["id"] for s in sections["sections"]}
        facts = evidence_ids(job)
        ig = sections.get("information_gain", [])
        if not ig:
            errors.append("sections.json: no information_gain")
        for item in ig:
            if item.get("section_id") not in section_ids or not item.get("reader_value"):
                errors.append("information_gain: a section and a concrete reader value are required")
            if not item.get("research_ref"):
                errors.append("information_gain: no reference to a finding in research.md")
        manifest = read_json(job / "visuals.json")
        visuals = manifest["visuals"]
        quotes = read_json(job / "expert_quotes.json")["quotes"]
        if not isinstance(visuals, list) or not isinstance(quotes, list):
            raise ValueError("visuals and quotes must be arrays")
        if not visuals and not manifest.get("omission_reason"):
            errors.append("no visuals are planned: omission_reason is required")
        quote_manifest = read_json(job / "expert_quotes.json")
        if not quotes and not quote_manifest.get("omission_reason"):
            errors.append("expert comments are not prepared: omission_reason is required")
        seen = set()
        for v in visuals:
            vid = v.get("id", "")
            if not ID.fullmatch(vid) or vid in seen:
                errors.append(f"visual: invalid or repeated id {vid}")
            seen.add(vid)
            for field in ("purpose", "title", "alt", "caption"):
                value = v.get(field)
                if not isinstance(value, str) or not value.strip() or PLACEHOLDERS.search(value):
                    errors.append(f"{vid}: no ready {field}")
                elif field in {"title", "alt", "caption"} and len(value) > 255:
                    errors.append(f"{vid}: {field} is longer than 255 characters ({len(value)})")
            if v.get("section_id") not in section_ids:
                errors.append(f"{vid}: unknown section_id")
            if any('"' in str(v.get(k, "")) or '\n' in str(v.get(k, ""))
                   for k in ("alt", "title")) or "]" in str(v.get("alt", "")):
                errors.append(f"{vid}: alt/title must be single-line, without quotation marks and ]")
            sources = v.get("sources", [])
            if not sources or any(not s.get("label") or not https(s.get("url", "")) for s in sources):
                errors.append(f"{vid}: sources with a label and an HTTPS url are required")
            refs = []
            kind = v.get("type")
            data = v.get("data", {})
            if kind in {"bar", "line"}:
                categories = data.get("categories", [])
                series = data.get("series", [])
                if not 2 <= len(categories) <= 8 or not 1 <= len(series) <= 3 or not data.get("unit"):
                    errors.append(f"{vid}: 2–8 categories, 1–3 series and a unit are required")
                if "future_rate_label" in data:
                    label = data["future_rate_label"]
                    if kind != "line" or not isinstance(label, str) or not label.strip() or len(label) > 80:
                        errors.append(f"{vid}: future_rate_label must be non-empty line text of up to 80 characters")
                if "value_decimals" in data:
                    decimals = data["value_decimals"]
                    if (kind != "bar" or isinstance(decimals, bool) or
                            not isinstance(decimals, int) or not 0 <= decimals <= 6):
                        errors.append(f"{vid}: value_decimals must be an integer bar precision from 0 to 6")
                for s in series:
                    values, ids = s.get("values", []), s.get("evidence_ids", [])
                    if "announced_from_index" in s:
                        announced = s["announced_from_index"]
                        if (kind != "line" or isinstance(announced, bool) or
                                not isinstance(announced, int) or not 1 <= announced < len(categories)):
                            errors.append(f"{vid}: announced_from_index must be an integer line index from 1 to the number of categories minus 1")
                    if not s.get("name") or len(values) != len(categories) or len(ids) != len(values):
                        errors.append(f"{vid}: the sizes of the series and evidence_ids do not match the categories")
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
                    errors.append(f"{vid}: a line needs the axis label x_label")
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
                    errors.append(f"{vid}: invalid links between nodes")
                # Supported layout is a rooted tree; fail rather than hide arrows/cycles.
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
                if len(roots) != 1 or len(visited) != len(nodes) or any(x > 1 for x in incoming.values()):
                    errors.append(f"{vid}: links must form a tree without cycles or merges")
                if sum(not children[n] for n in node_ids) > 3:
                    errors.append(f"{vid}: more than three leaf branches; split the diagram")
            else:
                errors.append(f"{vid}: type {kind!r} is not part of v1; illustrations are discussed separately")
            if set(refs) - facts:
                errors.append(f"{vid}: unknown evidence_ids {sorted(set(refs) - facts)}")
        seen = set()
        author_match = re.search(r"^author:\s*(\S+)", (job / "job.yaml").read_text(encoding="utf-8"), re.M)
        editor = read_json(ROOT / "config" / "blog-authors.json")["defaults"]["editor"]
        speakers = {author_match.group(1) if author_match else "", editor}
        for q in quotes:
            qid = q.get("id", "")
            if not ID.fullmatch(qid) or qid in seen:
                errors.append(f"quote: invalid or repeated id {qid}")
            seen.add(qid)
            if q.get("speaker") not in speakers:
                errors.append(f"{qid}: speaker must be the author or the editor of this article")
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


def guide_source_numbers(text, sources):
    """Resolve every visual original to its existing numbered Sources entry."""
    block = re.split(r"^##\s+Sources\s*$", text, flags=re.M)
    if len(block) != 2:
        raise ValueError("guide visuals require one Sources section")
    lookup = {}
    for line in block[1].splitlines():
        item = re.match(r"^(\d+)\.\s", line)
        if item:
            for url in re.findall(r"\]\((https?://[^)\s]+)\)", line):
                lookup.setdefault(url, int(item.group(1)))
    numbers = []
    for source in sources:
        if source["url"] not in lookup:
            raise ValueError("visual original missing from linked Sources: " + source["url"])
        number = lookup[source["url"]]
        if number not in numbers:
            numbers.append(number)
    return sorted(numbers)


def visual_markdown(v: dict) -> str:
    title = v["title"]
    numbers = v.get("asset", {}).get("source_numbers")
    if numbers:
        source_links = 'Sources: [' + ", ".join(str(n) for n in numbers) + '](#sources).'
    else:
        source_links = " · ".join(f'[{s["label"]}]({s["url"]})' if s.get("public", True)
                                  else s["label"] for s in v["sources"])
    return (f'![{v["alt"]}]({v["asset"]["url"]} "{title}")\n\n'
            f'Caption: {v["caption"]} {source_links}')


def quote_markdown(q: dict) -> str:
    return "> " + q["text"].replace("\n", "\n> ") + "\n>\n> — " + q["attribution"]


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
            raise ValueError("the image is larger than 5 MB")
        if not (body.startswith(b"\x89PNG\r\n\x1a\n") or body.startswith(b"\xff\xd8\xff")):
            raise ValueError("Google Docs needs a reachable PNG or JPEG")
        return body


def check_remote_image(url: str, expected_hash: str | None = None) -> None:
    body = fetch_remote_image(url)
    if expected_hash and digest(body) != expected_hash:
        raise ValueError("the remote image differs from the verified file")


def article_errors(job: Path, target: str, remote: bool = False) -> list[str]:
    from md_to_strapi_html import convert
    problems = []
    edited = job / "edited.md"
    if not edited.exists():
        return ["no edited.md"]
    text = edited.read_text(encoding="utf-8")
    for match in placeholder_matches(text):
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
                        problems.append(f"image is unreachable: {e}")
        return problems
    problems.extend(validate_inputs(job))
    if problems:
        return problems
    visuals = read_json(job / "visuals.json")["visuals"]
    expected_urls = []
    for v in visuals:
        vid, asset = v["id"], v.get("asset", {})
        try:
            data = asset_path(job, asset["path"]).read_bytes()
            if digest(data) != asset["sha256"] or asset.get("spec_sha256") != spec_digest(v):
                problems.append(f"{vid}: the file or the spec changed after rendering")
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                problems.append(f"{vid}: a PNG is expected")
            if not https(asset.get("url", "")) or not asset.get("media_id"):
                problems.append(f"{vid}: the visual is not uploaded to Strapi")
                continue
            expected_urls.append(asset["url"])
            if asset.get("source_numbers") is not None and asset["source_numbers"] != guide_source_numbers(text, v["sources"]):
                problems.append(f"{vid}: source numbers are stale; renumber Sources and bind visuals again")
            if text.count(visual_markdown(v)) != 1:
                problems.append(f"{vid}: no single ready image with a caption and sources")
            if asset.get("remote_sha256"):
                delivered = asset_path(job, asset["remote_path"]).read_bytes()
                if digest(delivered) != asset["remote_sha256"]:
                    problems.append(f"{vid}: the file for QA differs from the uploaded PNG")
            if remote:
                check_remote_image(asset["url"], asset.get("remote_sha256", asset["sha256"]))
        except (KeyError, ValueError, OSError) as e:
            problems.append(f"{vid}: no ready current image ({e})")
        except Exception as e:
            problems.append(f"{vid}: the remote image is unreachable ({e})")
    if sorted(img.get("src", "") for img in parser.images) != sorted(expected_urls):
        problems.append("the images in the article do not match visuals.json")
    for img in parser.images:
        if not img.get("title", "").strip():
            problems.append("image: title is missing")
    quotes = read_json(job / "expert_quotes.json")["quotes"]
    for q in quotes:
        block = quote_markdown(q)
        if q["status"] == "rejected":
            if normalized(block) in normalized(text):
                problems.append(f'{q["id"]}: a rejected quote is still in the article')
        elif normalized(text).count(normalized(block)) != 1:
            problems.append(f'{q["id"]}: the quote or attribution is changed or not inserted exactly once')
        elif target == "strapi" and q["status"] != "approved":
            problems.append(f'{q["id"]}: the quote is not approved')
    for name, expected in (("out/article.md", text), ("out/article.html", expected_html)):
        p = job / name
        if not p.exists() or p.read_text(encoding="utf-8") != expected:
            problems.append(f"{name} does not match edited.md; repackage the article")
    from strapi_publish import read_meta, validate_meta
    try:
        meta = read_meta(job)
        problems.extend(validate_meta(meta))
        if meta.get("title") != title:
            problems.append("title in out/meta.md does not match the final H1")
    except OSError:
        problems.append("no out/meta.md")
    return problems


QA_FILES = ("job.yaml", "edited.md", "visuals.json", "expert_quotes.json", "evidence.md", "sections.json",
            "research.md", "out/meta.md", "qa_report.md")


def qa_fingerprint(job: Path) -> dict:
    # Approval status is a later human decision; QA binds the exact quote text, speaker and facts.
    hashes = {name: digest((job / name).read_bytes()) for name in QA_FILES if name != "expert_quotes.json"}
    quotes = read_json(job / "expert_quotes.json")
    content = [{k: v for k, v in q.items() if k not in {"status", "approval"}} for q in quotes["quotes"]]
    hashes["expert_quotes.json"] = digest(json.dumps(content, sort_keys=True, ensure_ascii=False))
    return hashes


def qa_is_pass(job: Path) -> bool:
    report = (job / "qa_report.md").read_text(encoding="utf-8")
    return bool(re.search(r"^overall:\s*PASS\s*$", report, re.M | re.I)) and not bool(
        re.search(r"Gate\s+\d+[^\n:]*:\s*(?:\*\*)?BLOCK\b", report, re.I))


def export_errors(job: Path, target: str, remote: bool = True) -> list[str]:
    problems = article_errors(job, target, remote)
    if not is_v2(job) or problems:
        return problems
    try:
        receipt = read_json(job / "qa_receipt.json")
        if not qa_is_pass(job) or receipt.get("hashes") != qa_fingerprint(job):
            problems.append("QA is not PASS or the checked materials changed; repeat QA and seal-qa")
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
