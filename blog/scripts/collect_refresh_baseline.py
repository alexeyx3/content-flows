"""Read-only search baseline collector for explicitly selected refresh jobs.

Example: python3 scripts/collect_refresh_baseline.py --job jobs/<refresh> \
  --end-date 2026-10-16 --catalog raw/published-catalog.json
The source job, source URL and optional related-query term come from refresh.json.
An existing raw/analytics.json is never replaced.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parents[1]
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
STOPWORDS = {"a", "an", "the", "and", "or", "to", "for", "of", "in", "on", "is", "are",
             "what", "which", "how", "with", "as", "at", "by", "from", "that", "this", "do",
             "does", "can", "i", "my", "it", "its", "be", "best"}
LIMITATIONS = ("GSC query rows are partial: omitted or anonymized queries are unknown, not zero. "
               "Page totals come from a separate no-dimension request and must not be inferred "
               "by summing query rows. Missing daily rows are unreported, not zero.")


class BaselineError(RuntimeError):
    pass


def load_config_keyfile() -> Path:
    env = ROOT / "config" / ".env"
    settings = dict(line.split("=", 1) for line in env.read_text(encoding="utf-8").splitlines()
                    if "=" in line and not line.lstrip().startswith("#")) if env.exists() else {}
    candidate = ROOT / settings.get("GOOGLE_SA_KEYFILE", "config/google-service-account.json")
    if not candidate.is_file():
        raise BaselineError("Google service account file is unavailable")
    return candidate


def google_client():
    creds = Credentials.from_service_account_file(str(load_config_keyfile()), scopes=SCOPES)
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def retry(call, *, sleep=time.sleep):
    for attempt in range(3):
        try:
            return call()
        except HttpError as exc:
            if getattr(exc.resp, "status", None) not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except urllib.error.URLError:
            if attempt == 2:
                raise
        sleep(2 ** attempt)


def query(svc, prop: str, start: dt.date, end: dt.date, dimensions: list[str], filters: list[dict]) -> list[dict]:
    rows, offset = [], 0
    while True:
        body = {"startDate": str(start), "endDate": str(end), "type": "web", "dataState": "final",
                "dimensions": dimensions, "rowLimit": 25000, "startRow": offset,
                "dimensionFilterGroups": [{"filters": filters}]}
        batch = retry(lambda: svc.searchanalytics().query(siteUrl=prop, body=body).execute()).get("rows", [])
        rows.extend(batch)
        if len(batch) < 25000:
            return rows
        offset += 25000


def bing_key() -> tuple[str, str] | None:
    """Use only configured credentials; never print or store the key in outputs."""
    path = ROOT / "config" / "bing-webmaster.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("api_key") and data.get("site_url"):
            return str(data["api_key"]), str(data["site_url"])
        if data.get("api_key_file") and data.get("site_url"):
            source = Path(data["api_key_file"])
            source = source if source.is_absolute() else ROOT / source
            index = data.get("key_index")
            if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                raise BaselineError("Bing key_index must be an explicit nonnegative integer")
            keys = re.findall(r"\b[0-9a-fA-F]{32}\b", source.read_text(encoding="utf-8"))
            if index >= len(keys):
                raise BaselineError("Bing key_index is outside the configured key file")
            return keys[index], str(data["site_url"])
    env = ROOT / "config" / ".env"
    if env.is_file():
        settings = dict(line.split("=", 1) for line in env.read_text(encoding="utf-8").splitlines()
                        if "=" in line and not line.lstrip().startswith("#"))
        if settings.get("BING_WEBMASTER_API_KEY") and settings.get("BING_WEBMASTER_SITE_URL"):
            return settings["BING_WEBMASTER_API_KEY"], settings["BING_WEBMASTER_SITE_URL"]
    return None


def bing_get(method: str, *, key: str, site_url: str, page_url: str):
    # These are the read-only Webmaster methods. Keep credentials out of errors.
    params = {"siteUrl": site_url, "apikey": key,
              "url" if method == "GetUrlInfo" else "page": page_url}
    url = "https://ssl.bing.com/webmaster/api.svc/json/" + method + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response).get("d")


def bing_snapshot(source_url: str, get=bing_get) -> dict:
    credentials = bing_key()
    if not credentials:
        return {"status": "unavailable", "reason": "no Bing Webmaster credentials under config"}
    key, site_url = credentials
    calls = {}
    for method in ("GetUrlInfo", "GetPageQueryStats"):
        try:
            calls[method] = retry(lambda: get(method, key=key, site_url=site_url, page_url=source_url))
        except Exception as exc:
            # Do not stringify HTTP errors: their request URL contains the API key.
            calls[method] = {"status": "error", "error_type": type(exc).__name__}
    return {"status": "ok" if all(not isinstance(v, dict) or v.get("status") != "error"
                                   for v in calls.values()) else "partial",
            "siteUrl": site_url, **calls, "index_verdict": "not_inferred_from_crawl_metadata"}


def job_inputs(value: str) -> tuple[Path, dict]:
    job = Path(value)
    job = (job if job.is_absolute() else ROOT / job).resolve()
    if not job.is_relative_to(ROOT / "jobs"):
        raise BaselineError("refresh job must be under jobs/")
    yaml_path = job / "job.yaml"
    if not yaml_path.is_file() or not re.search(r"^article_refresh_version:\s*1\s*$",
                                                  yaml_path.read_text(encoding="utf-8"), re.M):
        raise BaselineError("--job must be an article_refresh_version: 1 job")
    if re.search(r"^semantic_refresh_version:\s*1\s*(?:#.*)?$", yaml_path.read_text(), re.M):
        raise BaselineError("use refresh_semantics.py collect for the single 90-day semantic window; this collector is legacy monitoring")
    manifest = json.loads((job / "refresh.json").read_text(encoding="utf-8"))
    source_job = (ROOT / manifest["source_job"]).resolve()
    if not source_job.is_relative_to(ROOT / "jobs") or not (source_job / "job.yaml").is_file():
        raise BaselineError("refresh.json source_job is not an existing article job")
    source_url = str(manifest["source_url"])
    if not re.fullmatch(r"https://example\.com/blog/[a-z0-9-]+/", source_url):
        raise BaselineError("refresh.json source_url must be an Example Co blog URL")
    if (job / "raw" / "analytics.json").exists():
        raise BaselineError(f"existing analytics baseline must not be overwritten: {job}")
    return job, manifest


def catalog_rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("pages") or data.get("articles")
    if not isinstance(rows, list) or not rows:
        raise BaselineError("catalog must contain a nonempty published page list")
    return [row for row in rows if isinstance(row, dict) and row.get("url") and row.get("title")]


def owned_candidates(source_url: str, pages: list[dict]) -> list[dict]:
    source = next((row for row in pages if row["url"] == source_url), None)
    phrase = source["title"] if source else source_url.rsplit("/", 2)[-2].replace("-", " ")
    tokens = set(re.findall(r"[a-z0-9]+", phrase.lower())) - STOPWORDS
    scored = []
    for row in pages:
        title = row["title"].lower()
        words = set(re.findall(r"[a-z0-9]+", title)) - STOPWORDS
        overlap = len(tokens & words) / len(tokens) if tokens else 0.0
        similarity = SequenceMatcher(None, phrase.lower(), title).ratio()
        scored.append({"key": row.get("key", row["url"]), "url": row["url"], "title": row["title"],
                       "token_overlap": round(overlap, 3), "phrase_similarity": round(similarity, 3),
                       "embedding": None})
    return sorted(scored, key=lambda x: (-x["token_overlap"], -x["phrase_similarity"], x["url"]))[:30]


def query_terms(rows: list[dict]) -> dict:
    terms: dict[str, dict] = {}
    for row in rows:
        if not row.get("keys"):
            continue
        text = row["keys"][0]
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        selected = [word for word in tokens if word not in STOPWORDS]
        selected += [" ".join(tokens[i:i + 2]) for i in range(len(tokens) - 1)
                     if tokens[i] not in STOPWORDS and tokens[i + 1] not in STOPWORDS]
        for term in set(selected):
            item = terms.setdefault(term, {"term": term, "queries": [], "sum_query_impressions": 0})
            item["queries"].append(text)
            item["sum_query_impressions"] += row.get("impressions", 0)
    return {"method": "Lowercase token and contiguous-bigram discovery; no lemmatization or semantic claim. "
                      "Counts sum returned query rows and are not page totals.",
            "terms": sorted(terms.values(), key=lambda x: (-x["sum_query_impressions"], x["term"]))}


def semantics_csv(rows: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["query", "clicks", "impressions", "ctr", "position"])
    for row in rows:
        writer.writerow([(row.get("keys") or [""])[0]] + [row.get(key, 0) for key in
                        ("clicks", "impressions", "ctr", "position")])
    return output.getvalue()


def limitations_text(recent: dict, previous: dict, published_at: str | None, bing: dict) -> str:
    lines = ["# Baseline data limitations", "", f"- {LIMITATIONS}"]
    if published_at:
        try:
            published = dt.date.fromisoformat(published_at[:10])
            if dt.date.fromisoformat(previous["startDate"]) < published:
                lines.append("- The previous28 window includes dates before publication; do not infer a percentage uplift across unequal exposure windows.")
        except ValueError:
            lines.append("- Source publication date could not be parsed; equal exposure across the 28-day windows is unverified.")
    else:
        lines.append("- Source publication date was not supplied; equal exposure across the 28-day windows is unverified.")
    lines += ["- Bing URL information is crawl metadata, not an explicit current index-membership verdict; empty query rows are not independently verified zero traffic.",
              f"- Bing collection status: {bing['status']}.",
              "- No post-update outcome is implied by this baseline. Publication requires a separate CMS action.", ""]
    return "\n".join(lines)


def collect(job: Path, manifest: dict, end: dt.date, pages: list[dict], *, client_factory=google_client) -> dict[str, str]:
    url = manifest["source_url"]
    prop = manifest.get("gsc_property") or "sc-domain:example.com"
    svc = client_factory()  # one independent client per worker
    page_filter = [{"dimension": "page", "operator": "equals", "expression": url}]
    periods = {}
    for name, days_ago in (("recent28", 0), ("previous28", 28)):
        stop = end - dt.timedelta(days=days_ago)
        start = stop - dt.timedelta(days=27)
        periods[name] = {"startDate": str(start), "endDate": str(stop),
                         "totals": query(svc, prop, start, stop, [], page_filter),
                         "queries": query(svc, prop, start, stop, ["query"], page_filter)}
    start56 = end - dt.timedelta(days=55)
    daily = {"startDate": str(start56), "endDate": str(end),
             "rows": query(svc, prop, start56, end, ["date"], page_filter)}
    last_sunday = end - dt.timedelta(days=(end.weekday() + 1) % 7)
    weekly = []
    for weeks_ago in reversed(range(6)):
        stop = last_sunday - dt.timedelta(days=7 * weeks_ago)
        start = stop - dt.timedelta(days=6)
        weekly.append({"startDate": str(start), "endDate": str(stop), "complete": True,
                       "rows": query(svc, prop, start, stop, ["query"], page_filter)})
    try:
        inspection = retry(lambda: svc.urlInspection().index().inspect(body={
            "inspectionUrl": url, "siteUrl": prop, "languageCode": "en-US"}).execute())
        inspection = inspection.get("inspectionResult", {}).get("indexStatusResult", {})
    except Exception as exc:
        inspection = {"status": "unavailable", "error_type": type(exc).__name__}
    bing = bing_snapshot(url)
    analytics = {"property": prop, "source_url": url, "dataState": "final",
                 "collected_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                 "periods": periods, "daily_page": daily, "weekly_queries": weekly,
                 "google_inspection": inspection, "bing": bing, "limitations": LIMITATIONS}
    related_term = manifest.get("related_query_term") or url.rstrip("/").split("/")[-1].split("-")[0]
    related = {"startDate": str(start56), "endDate": str(end),
               "rows": query(svc, prop, start56, end, ["query", "page"],
                             [{"dimension": "query", "operator": "contains", "expression": related_term}]),
               "coverage": "Partial returned GSC query-page pairs; presence on multiple URLs does not prove cannibalization."}
    source = next((row for row in pages if row["url"] == url), {})
    owned = {"embedding_status": "not_run: lexical-only; no shared embedding cache touched",
             "pages": pages, "nearest_pages": owned_candidates(url, pages)}
    publication = manifest.get("source_published_at") or source.get("published_at") or source.get("publishedAt")
    return {"raw/analytics.json": json.dumps(analytics, ensure_ascii=False, indent=2) + "\n",
            "semantics.csv": semantics_csv(periods["recent28"]["queries"]),
            "raw/query-terms.json": json.dumps(query_terms(periods["recent28"]["queries"]), ensure_ascii=False, indent=2) + "\n",
            "raw/related-query-pages.json": json.dumps(related, ensure_ascii=False, indent=2) + "\n",
            "raw/owned-pages.json": json.dumps(owned, ensure_ascii=False, indent=2) + "\n",
            "raw/data-limitations.md": limitations_text(periods["recent28"], periods["previous28"], publication, bing)}


def save(job: Path, artifacts: dict[str, str]) -> None:
    baseline = job / "raw/analytics.json"
    if baseline.exists():
        raise BaselineError(f"existing analytics baseline must not be overwritten: {job}")
    for name, body in artifacts.items():
        path = job / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise BaselineError(f"existing baseline artifact must not be overwritten: {path}")
    # Analytics is the completion marker. Exclusive creation and rollback keep a
    # failed local write from leaving a baseline that can never be resumed.
    created = []
    try:
        for name in [key for key in artifacts if key != "raw/analytics.json"] + ["raw/analytics.json"]:
            path = job / name
            with path.open("x", encoding="utf-8") as handle:
                created.append(path)
                handle.write(artifacts[name])
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", action="append", required=True, help="repeat for each selected refresh job")
    parser.add_argument("--end-date", required=True, help="last final-data day, YYYY-MM-DD")
    parser.add_argument("--catalog", required=True, type=Path, help="published-catalog.json supplied by parent")
    parser.add_argument("--max-workers", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.max_workers <= 3:
        parser.error("--max-workers must be between 1 and 3")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.end_date):
        parser.error("--end-date must be YYYY-MM-DD")
    try:
        end = dt.date.fromisoformat(args.end_date)
        pages = catalog_rows(args.catalog)
        jobs = [job_inputs(value) for value in args.job]
        if len({job for job, _ in jobs}) != len(jobs):
            raise BaselineError("duplicate --job argument")
        with ThreadPoolExecutor(max_workers=min(args.max_workers, len(jobs))) as pool:
            futures = {pool.submit(collect, job, manifest, end, pages): job for job, manifest in jobs}
            for future in as_completed(futures):
                job = futures[future]
                save(job, future.result())
                print(f"saved read-only search baseline: {job}")
    except (BaselineError, ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
