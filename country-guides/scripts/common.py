"""Paths and helpers shared by the guide scripts. Shared dependencies are copied into this project."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "vendor" / "blog"
BLOG_SCRIPTS = BLOG / "scripts"
HINTS = ROOT / "hints"          # optional research memory: hints/<slug>.yaml, hints/<slug>--vendors.yaml
COMPANIES = ROOT / "companies"  # optional vendor cards of the project (*.mdx)
PAGES = ("country", "eor", "contractors")
SEGMENT = {"country": "", "eor": "employer-of-record/", "contractors": "independent-contractors/"}
_PEOPLE = json.loads((BLOG / "config" / "blog-authors.json").read_text(encoding="utf-8"))["defaults"]
AUTHOR = _PEOPLE["author"]
EDITOR = _PEOPLE["editor"]

if str(BLOG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BLOG_SCRIPTS))


def job_dir(value: str) -> Path:
    p = Path(value)
    return (p if p.is_absolute() else ROOT / p).resolve()


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a JSON object")
    return data


def header_display(entry: dict) -> str:
    """Reader-facing header value; fixed levies are never rendered as zero percent."""
    if entry.get("model") == "fixed":
        return entry["display"]
    value = entry["value"]
    return f"{value:g}%" if isinstance(value, (int, float)) else str(value)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_job(job: Path) -> dict:
    """Country job settings live in job.json; page folders carry the blog's job.yaml for its scripts."""
    return read_json(job / "job.json")


def queue() -> dict:
    return json.loads((ROOT / "config" / "queue.json").read_text(encoding="utf-8"))


def save_queue(data: dict) -> None:
    (ROOT / "config" / "queue.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                                                encoding="utf-8")


def page_url(slug: str, page: str) -> str:
    return f"https://example.com/guides/{slug}/{SEGMENT[page]}"


def page_dir(job: Path, page: str) -> Path:
    """pages/guide-<slug>[-eor|-contractors]: the blog's Docs script names the Drive folder after it."""
    slug = load_job(job)["slug"]
    return job / "pages" / (f"guide-{slug}" if page == "country" else f"guide-{slug}-{page}")


# Same list as NEEDS_THE in the site frontend's guides module: the site builds the country H1 itself with
# countryInText(); subpage titles are a Strapi field we write, so they must match.
NEEDS_THE = {"AE", "BS", "CD", "CF", "CG", "CK", "DO", "FK", "FO", "GB", "GM", "IM", "KM",
             "KY", "MH", "MP", "MV", "NL", "PH", "SB", "TC", "US", "VG", "VI"}


def country_in_text(name: str, code: str) -> str:
    return f"the {name}" if code.upper() in NEEDS_THE and not name.lower().startswith("the ") else name


def h1(name: str, page: str, code: str = "") -> str:
    n = country_in_text(name, code)
    return {"country": f"Hiring in {n}", "eor": f"Employer of Record in {n}",
            "contractors": f"Hiring contractors in {n}"}[page]
