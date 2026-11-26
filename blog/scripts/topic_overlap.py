"""Read-only owned-content search and a recorded editorial topic decision.

Usage:
  python3 scripts/topic_overlap.py check --cluster-id b-0123 --topic "Contractor agreement software" --keyword "contractor agreement software"
  python3 scripts/topic_overlap.py decide --cluster-id b-0123 --reason "The existing page answers ...; this one ..."

The report is a retrieval aid, not an automatic duplicate verdict. ``decide``
records a distinct-intent decision only; duplicate rows use ``temnik.py skip``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "topic-overlap"
TOKEN = re.compile(r"[\w]+", re.UNICODE)
STOPWORDS = {"a", "an", "and", "best", "for", "in", "of", "the", "to", "top"}
H2 = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")
EMBEDDING_MODEL = "apple-natural-language-sentence-en"
EMBEDDING_CACHE = ROOT / "var" / "topic-overlap-embeddings.json"
EMBEDDING_SOURCE = ROOT / "scripts" / "topic_overlap_embedding.swift"
EMBEDDING_BINARY = ROOT / "var" / "topic-overlap-embedding"


def normalize(value: str) -> str:
    return " ".join(TOKEN.findall(value.casefold()))


def report_path(cluster_id: str, stage: str = "seed") -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", cluster_id):
        raise ValueError("invalid cluster ID")
    if stage not in {"seed", "resolved"}:
        raise ValueError("stage must be seed or resolved")
    return REPORTS / f"{cluster_id}.{stage}.json"


def published_articles() -> list[dict]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import strapi_publish

    rows: list[dict] = []
    page = 1
    while True:
        query = urlencode({"pagination[page]": page, "pagination[pageSize]": 40})
        response = strapi_publish.api(f"/articles?{query}")
        for item in response.get("data", []):
            if not item.get("publishedAt") or not item.get("slug"):
                continue
            headings = [unescape(TAG.sub("", h)).strip() for h in H2.findall(item.get("content") or "")]
            rows.append({
                "key": f"strapi:{item['id']}", "kind": "published",
                "url": f"https://example.com/blog/{item['slug']}/",
                "title": item.get("title") or "", "slug": item["slug"],
                "summary": item.get("summary") or item.get("metaDescription") or "",
                "headings": headings[:25],
            })
        pagination = response.get("meta", {}).get("pagination", {})
        if not pagination or page >= pagination.get("pageCount", 1):
            break
        page += 1
    if not rows:
        raise RuntimeError("Strapi returned no published blog articles; preflight cannot pass")
    return rows


def local_jobs(published_slugs: set[str], exclude: Path | None = None,
               cluster_id: str = "") -> list[dict]:
    rows = []
    for yaml_path in sorted((ROOT / "jobs").glob("*/job.yaml")):
        job = yaml_path.parent
        if exclude and job.resolve() == exclude.resolve():
            continue
        raw = yaml_path.read_text(encoding="utf-8")
        if cluster_id and re.search(rf'^temnik_cluster_id:\s*["\']?{re.escape(cluster_id)}["\']?\s*(?:#.*)?$', raw, re.M):
            continue
        topic = re.search(r'^topic:\s*["\']?(.*?)["\']?\s*(?:#.*)?$', raw, re.M)
        if not topic:
            continue
        title = topic.group(1).strip().strip('"\'')
        meta = job / "out" / "meta.md"
        slug = ""
        if meta.exists():
            m = re.search(r"^-?\s*slug:\s*(.+)$", meta.read_text(encoding="utf-8"), re.M)
            slug = m.group(1).strip().strip('"\'') if m else ""
        if slug and slug in published_slugs:
            continue
        brief = job / "brief.md"
        summary = ""
        headings = []
        if brief.exists():
            content = brief.read_text(encoding="utf-8")
            m = re.search(r"\|\s*Primary query\s*\|\s*(.*?)\s*\|", content, re.I)
            summary = m.group(1).strip() if m else ""
            headings = re.findall(r"^#{2,3}\s+(.+)$", content, re.M)[:25]
        rows.append({"key": f"job:{job.name}", "kind": "job", "url": str(job.relative_to(ROOT)),
                     "title": title, "slug": slug, "summary": summary, "headings": headings})
    return rows


def catalog(exclude: Path | None = None, cluster_id: str = "") -> list[dict]:
    live = published_articles()
    return live + local_jobs({row["slug"] for row in live}, exclude, cluster_id)


def fingerprint(rows: list[dict]) -> str:
    payload = [(r["key"], r["title"], r["slug"]) for r in rows]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def lexical_scores(query: str, rows: list[dict]) -> dict[str, float]:
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE VIRTUAL TABLE pages USING fts5(title, slug, summary, headings, tokenize='porter unicode61')")
        for i, row in enumerate(rows):
            db.execute("INSERT INTO pages(rowid,title,slug,summary,headings) VALUES (?,?,?,?,?)",
                       (i + 1, row["title"], row["slug"].replace("-", " "),
                        row["summary"], " ".join(row["headings"])))
        words = list(dict.fromkeys(TOKEN.findall(query.casefold())))
        if not words:
            return {}
        match = " OR ".join('"' + word.replace('"', '""') + '"' for word in words)
        hits = db.execute("SELECT rowid,bm25(pages,8,5,2,1) FROM pages WHERE pages MATCH ? ORDER BY 2 LIMIT 30",
                          (match,)).fetchall()
        return {rows[rowid - 1]["key"]: max(0, -score) for rowid, score in hits}
    finally:
        db.close()


def compute_local_vectors(texts: list[str]) -> list[list[float]]:
    if not EMBEDDING_BINARY.exists() or EMBEDDING_BINARY.stat().st_mtime < EMBEDDING_SOURCE.stat().st_mtime:
        EMBEDDING_BINARY.parent.mkdir(parents=True, exist_ok=True)
        temporary = EMBEDDING_BINARY.with_name(f"{EMBEDDING_BINARY.name}.{os.getpid()}.tmp")
        subprocess.run(["swiftc", str(EMBEDDING_SOURCE), "-o", str(temporary)],
                       capture_output=True, text=True, check=True)
        temporary.replace(EMBEDDING_BINARY)
    result = subprocess.run([str(EMBEDDING_BINARY)], input=json.dumps(texts),
                            capture_output=True, text=True, check=True)
    vectors = json.loads(result.stdout)
    if len(vectors) != len(texts) or any(not isinstance(v, list) or len(v) != 512 for v in vectors):
        raise RuntimeError("local embedding returned incomplete vectors")
    return vectors


def embeddings(texts: list[str]) -> list[list[float]]:
    try:
        cache = json.loads(EMBEDDING_CACHE.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, json.JSONDecodeError):
        cache = {}
    keys = [hashlib.sha256((EMBEDDING_MODEL + "\n" + text).encode()).hexdigest() for text in texts]
    missing = [(key, text) for key, text in zip(keys, texts) if key not in cache]
    for start in range(0, len(missing), 100):
        batch = missing[start:start + 100]
        vectors = compute_local_vectors([text for _key, text in batch])
        for (key, _text), vector in zip(batch, vectors):
            cache[key] = vector
    if missing:
        EMBEDDING_CACHE.parent.mkdir(parents=True, exist_ok=True)
        temporary = EMBEDDING_CACHE.with_name(f"{EMBEDDING_CACHE.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
        temporary.replace(EMBEDDING_CACHE)
    return [cache[key] for key in keys]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return dot / norm if norm else 0.0


def find_candidates(topic: str, keyword: str, rows: list[dict]) -> tuple[list[dict], str]:
    query = " ".join(x for x in (topic, keyword) if x).strip()
    if not query:
        raise ValueError("topic or keyword is required")
    scores = lexical_scores(query, rows)
    semantic: dict[str, float] = {}
    semantic_queries = [topic]
    if keyword.strip() and normalize(keyword) != normalize(topic):
        semantic_queries.append(keyword)
    # Short title vectors keep the article's core intent prominent. Longer cards
    # diluted the PEO/startups signal behind unrelated provider names and H2s.
    cards = [r["title"] for r in rows]
    try:
        vectors = embeddings(semantic_queries + cards)
        query_vectors = vectors[:len(semantic_queries)]
        semantic = {r["key"]: max(cosine(q, vector) for q in query_vectors)
                    for r, vector in zip(rows, vectors[len(semantic_queries):])}
        embedding_status = f"ready: {EMBEDDING_MODEL}"
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        embedding_status = f"unavailable: local embedding failed ({type(exc).__name__})"
    phrases = [re.sub(r"^(?:\d+|(?:19|20)\d\d)\s+", "", normalize(x))
               for x in (topic, keyword) if x.strip()]
    results = []
    for row in rows:
        title = normalize(row["title"])
        slug = normalize(row["slug"].replace("-", " "))
        overlap = max((len((set(phrase.split()) - STOPWORDS) & set(title.split())) /
                       len(set(phrase.split()) - STOPWORDS)
                       for phrase in phrases if set(phrase.split()) - STOPWORDS), default=0)
        fuzzy = max((score for phrase in phrases for score in
                     (SequenceMatcher(None, phrase, title).ratio(),
                      SequenceMatcher(None, phrase, slug).ratio())), default=0)
        exact = any(phrase and (phrase in title or phrase in slug) for phrase in phrases)
        results.append({"key": row["key"], "kind": row["kind"], "url": row["url"],
                        "title": row["title"], "exact_phrase": exact,
                        "lexical": round(scores.get(row["key"], 0), 5),
                        "token_overlap": round(overlap, 3), "phrase_similarity": round(fuzzy, 3),
                        "embedding": round(semantic[row["key"]], 3) if semantic else None})
    results.sort(key=lambda r: (r["exact_phrase"], r["token_overlap"],
                                r["phrase_similarity"], r["embedding"] or 0, r["lexical"]), reverse=True)
    # All exact phrases survive the display limit; both retrieval methods contribute candidates.
    selected = {r["key"] for r in results[:10] if r["exact_phrase"]}
    selected.update(r["key"] for r in sorted(results, key=lambda r: r["lexical"], reverse=True)[:10])
    if semantic:
        selected.update(r["key"] for r in sorted(results, key=lambda r: r["embedding"], reverse=True)[:10])
    selected.update(r["key"] for r in results if r["exact_phrase"])
    return [r for r in results if r["key"] in selected][:max(10, len(selected))], embedding_status


def check(cluster_id: str, topic: str, keyword: str = "", exclude: Path | None = None,
          stage: str = "seed", rows: list[dict] | None = None) -> dict:
    rows = rows if rows is not None else catalog(exclude, cluster_id)
    candidates, embedding_status = find_candidates(topic, keyword, rows)
    report = {"cluster_id": cluster_id, "stage": stage, "topic": topic, "keyword": keyword,
              "checked_at": datetime.now(timezone.utc).isoformat(), "catalog_fingerprint": fingerprint(rows),
              "published_count": sum(r["kind"] == "published" for r in rows),
              "job_count": sum(r["kind"] == "job" for r in rows),
              "embedding_status": embedding_status, "candidates": candidates,
              "decision": None, "reason": ""}
    path = report_path(cluster_id, stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def decide(cluster_id: str, reason: str, stage: str = "seed") -> dict:
    path = report_path(cluster_id, stage)
    report = json.loads(path.read_text(encoding="utf-8"))
    if len(reason.strip()) < 40:
        raise ValueError("record at least 40 characters explaining distinct reader intent versus closest pages")
    report["decision"] = "distinct"
    report["reason"] = reason.strip()
    report["decided_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def resolved_query(brief: str) -> str:
    match = re.search(r"\|\s*Primary query\s*\|\s*(.*?)\s*\|", brief, re.I)
    return match.group(1).strip() if match else ""


def decision_errors(cluster_id: str, stage: str, topic: str, keyword: str) -> list[str]:
    path = report_path(cluster_id, stage)
    if not path.exists():
        return [f"missing overlap report {path}; run topic_overlap.py check --stage {stage}"]
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid overlap report {path}: {exc}"]
    errors = []
    if (report.get("cluster_id") != cluster_id or report.get("stage") != stage
            or report.get("topic") != topic or report.get("keyword") != keyword):
        errors.append("overlap report does not match current topic or primary query")
    if report.get("decision") != "distinct" or len(report.get("reason", "").strip()) < 40:
        errors.append("overlap report lacks a recorded distinct-intent decision")
    if not isinstance(report.get("candidates"), list) or not report.get("catalog_fingerprint"):
        errors.append("overlap report has no catalog or candidate list")
    return errors


def new_close_matches(cluster_id: str, topic: str, keyword: str,
                      exclude: Path | None = None, own_slug: str = "") -> list[dict]:
    """Find strong newly indexed overlaps since the resolved editorial review."""
    report = json.loads(report_path(cluster_id, "resolved").read_text(encoding="utf-8"))
    reviewed = {item["key"] for item in report["candidates"]}
    rows = catalog(exclude, cluster_id)
    current, _status = find_candidates(topic, keyword, rows)
    return [item for item in current if item["key"] not in reviewed
            and (item["exact_phrase"] or item["token_overlap"] >= 0.8)
            and not (own_slug and item["url"].endswith(f"/{own_slug}/"))]


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    c = sub.add_parser("check")
    c.add_argument("--cluster-id", required=True)
    c.add_argument("--topic", required=True)
    c.add_argument("--keyword", default="")
    c.add_argument("--exclude-job", type=Path)
    c.add_argument("--stage", choices=["seed", "resolved"], default="seed")
    d = sub.add_parser("decide")
    d.add_argument("--cluster-id", required=True)
    d.add_argument("--reason", required=True)
    d.add_argument("--stage", choices=["seed", "resolved"], default="seed")
    args = parser.parse_args()
    try:
        if args.action == "check":
            report = check(args.cluster_id, args.topic, args.keyword, args.exclude_job, args.stage)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            report = decide(args.cluster_id, args.reason, args.stage)
            print(f"{report_path(args.cluster_id, args.stage)}: distinct intent recorded")
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
