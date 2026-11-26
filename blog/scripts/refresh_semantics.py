"""Collect page-only GSC queries, audit literal/morphological coverage, enforce a plan.

No prose is written. Existing jobs can be audited to an explicit external output
directory; only semantic_refresh_version: 1 jobs acquire the mandatory gates.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta
import hashlib
import html
import io
import json
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

if __package__:
    from scripts import md_to_gdoc as md, semantic_morphology as morphology
else:
    import md_to_gdoc as md
    import semantic_morphology as morphology

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = {"covered", "expand", "link", "separate_topic", "irrelevant"}
LIMITATION = "All returned page-query rows, not all possible queries: GSC may omit/anonymize rows. Missing rows are unknown, not zero."


def sha(value: bytes | str) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def normalize(text: str) -> str:
    # Case and technical whitespace are immaterial. Punctuation/word order remain.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", html.unescape(text))).strip().casefold()


def query_id(text: str) -> str:
    return "Q-" + sha(text)[:16]


def required(job: Path) -> bool:
    path = job / "job.yaml"
    if not path.exists():
        return False
    text = path.read_text()
    return all(re.search(rf"^{key}:\s*1\s*(?:#.*)?$", text, re.M)
               for key in ('article_refresh_version', 'semantic_refresh_version'))


def resolve_job(value: str) -> Path:
    job = (ROOT / value).resolve()
    if not job.is_relative_to(ROOT / "jobs") or not (job / "refresh.json").is_file():
        raise ValueError("job must be a refresh cycle under jobs/")
    return job


def registry(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("version") != 1 or data.get("source") != "google_search_console" or data.get("dataState") != "final":
        raise ValueError("expected a version-1 final-data GSC query registry")
    if date.fromisoformat(data["startDate"]) > date.fromisoformat(data["endDate"]):
        raise ValueError("invalid semantic date window")
    rows = data["queries"]
    if not isinstance(rows, list):
        raise ValueError("queries must be a list")
    seen = set()
    for row in rows:
        text = row.get("query")
        if not isinstance(text, str) or not normalize(text):
            raise ValueError("empty or invalid query")
        if row.get("id") != query_id(text) or row["id"] in seen:
            raise ValueError("query ID mismatch or duplicate query")
        seen.add(row["id"])
    return data


def collect(job: Path, *, end: date | None = None, service=None) -> dict:
    if __package__:
        from scripts.collect_refresh_baseline import google_client, query
    else:
        from collect_refresh_baseline import google_client, query
    manifest = json.loads((job / "refresh.json").read_text())
    url = manifest["source_url"]
    if not re.fullmatch(r"https://example\.com/blog/[a-z0-9-]+/", url):
        raise ValueError("expected the exact canonical Example Co blog URL")
    prop = manifest.get("gsc_property", "sc-domain:example.com")
    service = service or google_client()
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    basis = "explicit final-data end date"
    if end is None:
        available = query(service, prop, today - timedelta(days=14), today, ["date"], [])
        dates = [date.fromisoformat(row["keys"][0]) for row in available if row.get("keys")]
        if not dates:
            raise ValueError("cannot establish the property's last final-data date; supply --end-date")
        end, basis = max(dates), "latest returned property date with dataState=final (GSC Pacific dates)"
    if end > today:
        raise ValueError("end date is in the future")
    record = json.loads((job / "baseline/cms-record.json").read_text())
    published_at = record.get("publishedAt")
    if not published_at:
        raise ValueError("published baseline needs the original publishedAt")
    published = datetime.fromisoformat(published_at.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles")).date()
    days = json.loads(morphology.CONFIG.read_text())["history_days"]
    start = max(published, end - timedelta(days=days - 1))
    if start > end:
        raise ValueError("query window ends before publication")
    rows = query(service, prop, start, end, ["query"],
                 [{"dimension": "page", "operator": "equals", "expression": url}])
    result = {"version": 1, "source": "google_search_console", "property": prop,
              "source_url": url, "startDate": str(start), "endDate": str(end),
              "publication_date": str(published), "history_days": days, "date_basis": basis,
              "dataState": "final", "collected_at": datetime.now().astimezone().isoformat(),
              "limitations": LIMITATION, "queries": []}
    seen = set()
    for row in rows:
        text = row["keys"][0]
        if text in seen:
            raise ValueError("duplicate query across API pages; retry collection")
        seen.add(text)
        result["queries"].append({"id": query_id(text), "query": text,
                                  **{k: row.get(k) for k in ("clicks", "impressions", "ctr", "position")}})
    return result


def blocks(markdown: str) -> list[dict]:
    """Visible main-article blocks; no URL targets, image alt, code, or metadata."""
    markdown = re.sub(r"```.*?```|<!--.*?-->", "", markdown, flags=re.S)
    out, section, subsection, sources = [], "Introduction", "", False
    for i, block in enumerate(md.parse(markdown)):
        kind = block[0]
        if kind == "image":
            continue
        if kind == "heading":
            if block[1] == 2:
                section, subsection = md.inline(block[2])[0], ""
                sources = normalize(section) in {"sources", "источники", "references"}
            elif block[1] > 2:
                subsection = md.inline(block[2])[0]
        entries = [("table-cell", f"{i}:r{r}:c{c}", md.inline(cell)[0])
                   for r, row in enumerate(block[1]) for c, cell in enumerate(row)] if kind == "table" else [
                       (kind, str(i), md.inline(block[-1])[0])]
        for block_kind, location, text in entries:
            text = normalize(text)
            if text and not sources:
                out.append({"kind": block_kind, "location": location, "section": section,
                            "subsection": subsection, "text": text})
    return out


def morphology_index(content: list[dict], annotations: list[list[dict]], requested: set[tuple]) -> dict:
    """Scan each requested length once, instead of once per query/term."""
    result = {key: [] for key in requested if key}
    lengths = sorted({len(key) for key in result})
    for block, tokens in zip(content, annotations, strict=True):
        sequence = tuple(t['lemma'] for t in tokens)
        for size in lengths:
            for i in range(len(tokens) - size + 1):
                key = sequence[i:i + size]
                if key not in result or tokens[i]['segment'] != tokens[i + size - 1]['segment']:
                    continue
                begin, finish = tokens[i]['start'], tokens[i + size - 1]['end']
                result[key].append({**{k: block[k] for k in ('location', 'kind', 'section', 'subsection')},
                                    'start': begin, 'end': finish,
                                    'excerpt': block['text'][max(0, begin - 65):finish + 65]})
    return result


def occurrences(variants: list[str], lemmas: list[str], content: list[dict], annotations: list[list[dict]], index: dict | None = None) -> dict:
    exact, morph = [], []
    patterns = [re.compile(r"(?<!\w)" + re.escape(normalize(v)) + r"(?!\w)") for v in variants if normalize(v)]
    for block, tokens in zip(content, annotations, strict=True):
        spans = {m.span() for pattern in patterns for m in pattern.finditer(block["text"])}
        base = {k: block[k] for k in ("location", "kind", "section", "subsection")}
        for begin, finish in sorted(spans):
            exact.append({**base, "start": begin, "end": finish,
                          "excerpt": block["text"][max(0, begin - 65):finish + 65]})
        size = len(lemmas)
        if size and index is None:
            for i in range(len(tokens) - size + 1):
                chunk = tokens[i:i + size]
                if chunk[0]["segment"] == chunk[-1]["segment"] and [t["lemma"] for t in chunk] == lemmas:
                    begin, finish = chunk[0]["start"], chunk[-1]["end"]
                    morph.append({**base, "start": begin, "end": finish,
                                  "excerpt": block["text"][max(0, begin - 65):finish + 65]})
    if index is not None:
        morph = index.get(tuple(lemmas), [])
    # An identical phrase is already a match, even if short-query POS differs
    # from the same literal phrase's POS in the sentence. Never double count it.
    morph = list({(loc['location'], loc['start'], loc['end']): loc for loc in morph + exact}.values())
    return {"exact": len(exact), "morph": len(morph), "exact_locations": exact, "morph_locations": morph}


def analyze(dataset: dict, before: str, after: str, language: str, *, annotator=morphology.annotate,
            before_metadata: dict | None = None, after_metadata: dict | None = None) -> dict:
    left, right = blocks(before), blocks(after)
    meta_blocks = lambda values: [{"kind": "metadata", "location": key, "section": "Metadata", "subsection": "", "text": normalize(value)}
                                  for key, value in (values or {}).items() if key in {"metaTitle", "metaDescription", "summary"} and value]
    meta_left, meta_right = meta_blocks(before_metadata), meta_blocks(after_metadata)
    queries = dataset["queries"]
    texts = [normalize(q["query"]) for q in queries] + [b["text"] for b in left + right + meta_left + meta_right]
    annotations, engine = annotator(texts, language)
    q_tokens = annotations[:len(queries)]
    l_tokens = annotations[len(queries):len(queries) + len(left)]
    r_start = len(queries) + len(left)
    r_tokens = annotations[r_start:r_start + len(right)]
    meta_start = r_start + len(right)
    ml_tokens = annotations[meta_start:meta_start + len(meta_left)]
    mr_tokens = annotations[meta_start + len(meta_left):]
    requested = set()
    for tokens in q_tokens:
        if tokens and tokens[0]['segment'] == tokens[-1]['segment']:
            requested.add(tuple(t['lemma'] for t in tokens))
        for size in (1, 2):
            for i in range(len(tokens) - size + 1):
                chunk = tokens[i:i + size]
                if chunk[0]['segment'] == chunk[-1]['segment']:
                    requested.add(tuple(t['lemma'] for t in chunk))
    left_index = morphology_index(left, l_tokens, requested)
    right_index = morphology_index(right, r_tokens, requested)
    ml_index = morphology_index(meta_left, ml_tokens, requested)
    mr_index = morphology_index(meta_right, mr_tokens, requested)
    rows, terms = [], {}
    for query, tokens in zip(queries, q_tokens, strict=True):
        lemmas = [t["lemma"] for t in tokens]
        # A multi-sentence/punctuated query has no single contiguous morphological span.
        match_lemmas = lemmas if tokens and tokens[0]["segment"] == tokens[-1]["segment"] else []
        rows.append({"id": query["id"], "type": "query", "text": query["query"], "variants": [query["query"]],
                     "lemmas": lemmas, "query_ids": [query["id"]], "impressions": query.get("impressions"),
                     "before": occurrences([query["query"]], match_lemmas, left, l_tokens, left_index),
                     "after": occurrences([query["query"]], match_lemmas, right, r_tokens, right_index)})
        for size in (1, 2):
            for i in range(len(tokens) - size + 1):
                chunk = tokens[i:i + size]
                if chunk[0]["segment"] != chunk[-1]["segment"]:
                    continue
                key = tuple(t["lemma"] for t in chunk)
                item = terms.setdefault(key, {"id": "T-" + sha(json.dumps(key, ensure_ascii=False))[:16],
                                              "type": "unigram" if size == 1 else "bigram", "text": " ".join(key),
                                              "lemmas": list(key), "variants": set(), "query_ids": set(),
                                              "all_stopwords": all(t["stop"] for t in chunk)})
                item["variants"].add(normalize(query["query"])[chunk[0]["start"]:chunk[-1]["end"]])
                item["query_ids"].add(query["id"])
    for item in terms.values():
        item["variants"], item["query_ids"] = sorted(item["variants"]), sorted(item["query_ids"])
        item["before"] = occurrences(item["variants"], item["lemmas"], left, l_tokens, left_index)
        item["after"] = occurrences(item["variants"], item["lemmas"], right, r_tokens, right_index)
        rows.append(item)
    for row in rows:
        row['metadata_before'] = occurrences(row['variants'], row['lemmas'], meta_left, ml_tokens, ml_index)
        row['metadata_after'] = occurrences(row['variants'], row['lemmas'], meta_right, mr_tokens, mr_index)
    summary = {"queries": len(queries), "unigrams": sum(r["type"] == "unigram" for r in rows),
               "bigrams": sum(r["type"] == "bigram" for r in rows)}
    for period in ("before", "after"):
        for mode in ("exact", "morph"):
            summary[f"queries_{mode}_{period}"] = sum(r["type"] == "query" and r[period][mode] > 0 for r in rows)
    summary["new_query_exact"] = sum(r["type"] == "query" and not r["before"]["exact"] and bool(r["after"]["exact"]) for r in rows)
    summary["lost_query_exact"] = sum(r["type"] == "query" and r["before"]["exact"] > 0 and not r["after"]["exact"] for r in rows)
    return {"version": 1, "engine": engine, "language": language, "summary": summary, "rows": rows,
            "definitions": {"exact": "Same contiguous literal words/punctuation, ignoring case and technical whitespace; word boundaries required.",
                            "morph": "Exact occurrences plus the same ordered adjacent lemma sequence in one segment; unique spans, no synonyms/reordering/gaps. Inclusive, not an extra count to add to exact.",
                            "terms": "Unigrams and adjacent bigrams; stopwords/negation are retained and labelled. No invented adjacency after stopword removal.",
                            "scope": "Article headings/body/lists/quotes/table cells; no cross-block or cross-cell matches. Sources, URL targets, code and image alt excluded. Metadata not added to body counts."}}


def plan_errors(report: dict, plan: dict, *, final: bool) -> list[str]:
    errors, seen = [], set()
    if not isinstance(plan, dict) or any(not isinstance(plan.get(key, []), list) or
                                       any(not isinstance(row, dict) for row in plan.get(key, []))
                                       for key in ('queries', 'targets', 'loss_exceptions')):
        return ['semantic plan needs lists of query decisions, targets and loss exceptions']
    rows = {r["id"]: r for r in report["rows"]}
    expected = {k for k, r in rows.items() if r["type"] == "query"}
    if plan.get("version") != 1:
        errors.append("semantics_plan.json needs version: 1")
    for decision in plan.get("queries", []):
        qid = decision.get("query_id")
        if qid not in expected or qid in seen:
            errors.append(f"unknown/duplicate query decision: {qid}")
        seen.add(qid)
        if decision.get("action") not in ACTIONS or not str(decision.get("reason", "")).strip():
            errors.append(f"query {qid}: action and reason required")
        if decision.get("action") in {"expand", "link"} and not str(decision.get("section", "")).strip():
            errors.append(f"query {qid}: affected section required")
    if expected - seen:
        errors.append(f"missing decisions for {len(expected - seen)} queries")
    target_ids = set()
    target_queries = set()
    for target in plan.get("targets", []):
        tid, mode = target.get("id"), target.get("match")
        if tid not in rows or tid in target_ids or mode not in {"exact", "morph"}:
            errors.append(f"invalid/duplicate semantic target: {tid}")
            continue
        target_ids.add(tid)
        target_queries.update(rows[tid]["query_ids"])
        minimum = target.get("min_count")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1 or not str(target.get("section", "")).strip():
            errors.append(f"target {tid}: positive min_count and section required")
            continue
        if final:
            locations = rows[tid]["after"][mode + "_locations"]
            actual = sum(loc["section"] == target["section"] for loc in locations)
            if actual < minimum:
                errors.append(f"target {tid}: {mode} {actual} < {minimum} in {target['section']}")
    for decision in plan.get("queries", []):
        if decision.get("action") == "expand" and decision.get("query_id") not in target_queries:
            errors.append(f"expanded query needs an exact/morph target: {decision.get('query_id')}")
    exceptions = {}
    for item in plan.get("loss_exceptions", []):
        key = (item.get("id"), item.get("match"))
        if key in exceptions or key[0] not in rows or key[1] not in {"exact", "morph"} or not str(item.get("reason", "")).strip():
            errors.append(f"invalid loss exception: {key}")
        exceptions[key] = item.get("reason")
    protected = set(plan.get("protect_ids", []))
    if protected - rows.keys():
        errors.append("protect_ids contains unknown IDs")
    if final:
        for row in rows.values():
            if row["type"] != "query" and row["id"] not in protected:
                continue  # Other term losses remain visible advisories, not forced stuffing.
            for mode in ("exact", "morph"):
                if row["before"][mode] and not row["after"][mode] and (row["id"], mode) not in exceptions:
                    errors.append(f"unexplained lost {mode} occurrence: {row['id']} {row['text']}")
    return errors


def gate_errors(job: Path, stage: str) -> list[str]:
    if not required(job):
        return []
    try:
        queries = job / "raw/semantic-queries.json"
        data = registry(queries)
        manifest = json.loads((job / "refresh.json").read_text())
        if data.get("source_url") != manifest.get("source_url"):
            return ["semantic query registry belongs to another URL"]
        plan_path = job / "semantics_plan.json"
        plan = json.loads(plan_path.read_text())
        phase = "before" if stage == "writer" else "after"
        report = json.loads((job / f"metrics/semantics-{phase}/coverage.json").read_text())
        config = json.loads(morphology.CONFIG.read_text())
        lang = re.search(r'^language:\s*[\"\x27]?(en|ru)\b', (job / 'job.yaml').read_text(), re.I | re.M)
        if not lang or report.get('language') != lang[1].lower():
            return ['semantic report language differs from job language']
        engine = report.get('engine', {})
        if any(engine.get(k) != value for k, value in {
                'spacy': config['spacy_version'], 'model': config['models'][lang[1].lower()],
                'model_version': config['model_version']}.items()):
            return ['semantic report has an unpinned morphology engine']
        if {r['id'] for r in report['rows'] if r['type'] == 'query'} != {q['id'] for q in data['queries']}:
            return ["semantic report does not contain every source query"]
        expected = {"queries": sha(queries.read_bytes()), "baseline": sha((job / "baseline/article.md").read_bytes())}
        if phase == "after":
            expected.update(article=sha((job / "edited.md").read_bytes()), plan=sha(plan_path.read_bytes()))
        else:
            expected["article"] = expected["baseline"]
        metadata_inputs = [("baseline_metadata", job / 'baseline/cms-record.json')]
        if phase == 'after':
            metadata_inputs.append(("brief", job / 'brief.md'))
        for key, path in metadata_inputs:
            if path.exists():
                expected[key] = sha(path.read_bytes())
        if any(report.get("hashes", {}).get(k) != v for k, v in expected.items()) or report.get("engine", {}).get("sources_sha256") != morphology.source_hash():
            return ["semantic coverage report is stale; rerun refresh_semantics.py analyze"]
        return plan_errors(report, plan, final=phase == "after")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"semantic stage incomplete: {exc}"]


def save_report(output: Path, report: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    with (output / "coverage.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "type", "text", "variants", "query_ids", "stopwords_only", "query_impressions", "exact_before", "exact_after", "morph_before", "morph_after",
                         "metadata_exact_before", "metadata_exact_after", "metadata_morph_before", "metadata_morph_after", "locations_after"])
        for row in report["rows"]:
            writer.writerow([row["id"], row["type"], row["text"], json.dumps(row["variants"], ensure_ascii=False),
                             " ".join(row["query_ids"]), row.get('all_stopwords', False), row.get('impressions'), row["before"]["exact"], row["after"]["exact"],
                             row["before"]["morph"], row["after"]["morph"],
                             row['metadata_before']['exact'], row['metadata_after']['exact'],
                             row['metadata_before']['morph'], row['metadata_after']['morph'],
                             json.dumps(row["after"]["morph_locations"], ensure_ascii=False)])
    lines = ["# Semantic coverage audit", "", "Counts describe textual presence, not relevance or a duty to insert every phrase.", "",
             "```json", json.dumps(report["summary"], ensure_ascii=False, indent=2), "```", "",
             "Full queries, lemma unigrams/bigrams, source-query links, original forms and every match location are in coverage.csv / coverage.json.", "",
             "## Changed full-query presence", ""]
    for row in report["rows"]:
        if row["type"] == "query" and any(bool(row["before"][m]) != bool(row["after"][m]) for m in ("exact", "morph")):
            lines.append(f"- {row['id']} {row['text']}: exact {row['before']['exact']} → {row['after']['exact']}; morphology {row['before']['morph']} → {row['after']['morph']}.")
    (output / "report.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    col = sub.add_parser("collect")
    col.add_argument("--job", required=True)
    col.add_argument("--end-date")
    col.add_argument("--output", type=Path)
    audit = sub.add_parser("analyze")
    audit.add_argument("--job", required=True)
    audit.add_argument("--queries", type=Path)
    audit.add_argument("--stage", choices=["before", "after"], default="after")
    audit.add_argument("--output-dir", type=Path)
    check = sub.add_parser("check")
    check.add_argument("--job", required=True)
    check.add_argument("--stage", choices=["writer", "after"], default="after")
    args = parser.parse_args()
    try:
        job = resolve_job(args.job)
        if args.command == "collect":
            if not required(job) and args.output is None:
                raise ValueError("legacy collection requires explicit --output; do not migrate an existing job silently")
            output = args.output or job / "raw/semantic-queries.json"
            if output.exists():
                raise ValueError("query registry is immutable; choose a new output path")
            data = collect(job, end=date.fromisoformat(args.end_date) if args.end_date else None)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            print(json.dumps({"queries": len(data["queries"]), "start": data["startDate"], "end": data["endDate"], "output": str(output)}))
        elif args.command == "analyze":
            dataset_path = args.queries or job / "raw/semantic-queries.json"
            data = registry(dataset_path)
            if data["source_url"] != json.loads((job / "refresh.json").read_text())["source_url"]:
                raise ValueError("query registry belongs to another URL")
            baseline = job / "baseline/article.md"
            article = baseline if args.stage == "before" else job / "edited.md"
            language_match = re.search(r'^language:\s*[\"\x27]?(en|ru)\b', (job / "job.yaml").read_text(), re.I | re.M)
            if not language_match:
                raise ValueError("job language must be EN or RU")
            baseline_meta_path, brief_path = job / 'baseline/cms-record.json', job / 'brief.md'
            baseline_meta = json.loads(baseline_meta_path.read_text()) if baseline_meta_path.exists() else {}
            if args.stage == 'after' and brief_path.exists():
                if __package__:
                    from scripts.package_article import extract_metadata
                else:
                    from package_article import extract_metadata
                final_meta = extract_metadata(brief_path.read_text())
            else:
                final_meta = baseline_meta
            report = analyze(data, baseline.read_text(), article.read_text(), language_match[1].lower(),
                             before_metadata=baseline_meta, after_metadata=final_meta)
            report.update(source_url=data["source_url"], window={k: data[k] for k in ("startDate", "endDate")},
                          limitations=[LIMITATION, json.loads(morphology.CONFIG.read_text())["limitation"]],
                          hashes={"queries": sha(dataset_path.read_bytes()), "baseline": sha(baseline.read_bytes()), "article": sha(article.read_bytes())})
            plan = job / "semantics_plan.json"
            if plan.exists():
                report["hashes"]["plan"] = sha(plan.read_bytes())
            metadata_inputs = [("baseline_metadata", baseline_meta_path)]
            if args.stage == 'after':
                metadata_inputs.append(("brief", brief_path))
            for key, path in metadata_inputs:
                if path.exists():
                    report['hashes'][key] = sha(path.read_bytes())
            output = args.output_dir or job / f"metrics/semantics-{args.stage}"
            if not required(job) and args.output_dir is None:
                raise ValueError("legacy audit requires --output-dir; existing job artifacts stay unchanged")
            save_report(output, report)
            print(json.dumps(report["summary"], ensure_ascii=False))
        else:
            errors = gate_errors(job, args.stage)
            if errors:
                raise ValueError("\n- ".join(errors))
            print("PASS" if required(job) else "legacy contract: not required")
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
