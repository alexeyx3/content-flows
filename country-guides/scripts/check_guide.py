"""Machine checks of a country's three pages (edited.md in each page folder).

BLOCK: wrong/duplicate H1, headings deeper than H4, missing core section or wrong order,
FAQ not right before Sources, Sources missing/not last/malformed, a body URL absent from Sources,
link to a competitor, internal link outside config/site-links.json, banned topic or stop-listed
brand, a forbidden claim next to the brand, the brand misspelt, header figure absent from the
country page body, a run of ≥ --block-at identical words shared with another page (this country,
another job or a vendor card under companies/).
WARN: shorter shared runs (≥ --warn-at words) — for QA to judge.

Company policy (brand, banned topics, claims forbidden next to the brand) is read from
config/brand-rules.json, the brand stop-list from config/stop-brands.json, competitor hosts
from config/vendors.json.

Usage: python3 scripts/check_guide.py --job jobs/<job> [--page eor] [--warn-at 20 --block-at 45]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit

from common import COMPANIES, PAGES, ROOT, h1, header_display, job_dir, load_job, page_dir, page_url, read_json
from text_overlap import grams, load, runs_for, tokenize
from lint_article import BRAND, BRAND_RE, BRAND_RULES, SITE_HOST, STOP_BRANDS, any_of, configured_rules
import order_sources

CORE = {
    "country": [r"ways to hire", r"labou?r market", r"regist", r"onboarding|hiring and", r"minimum wage",
                r"tax", r"working (time|hours)|overtime", r"leave", r"terminat|notice|dismiss",
                r"recent changes|what changed", r"mistake|who pays", r"questions"],
    "eor": [r"what an employer of record (is|does|means)|what is an employer|how an employer of record works", r"legal|law\b|lawful|qualif|recogni|allowed|permitted|intermediary rules|temporary[- ]agency rules|dispatch rules", r"licen[cs]e|permit|regist|authori[sz]ation|accreditation|regulated activit|provider.*status|check .*employer.*provider",
            r"who signs", r"step|onboarding|first .*payroll|first working day|start date .*regist|start[- ]date planning", r"cost|quote|itemi[sz]e", r"runs out|limit|stops solving|leaves exposure|assignment end.*client liability", r"do not need|don't need|not need|without an|unnecessary|hire directly|no useful employer function",
            r"alternative|compare .*with|compare .*ways|which route fits|compare direct employment|compare an? eor.*(?:own employer|independent services)|choose .*hiring route", r"choose|choosing|questions .*provider|questions .*eor|ask .*provider", r"questions"],
    "contractors": [r"line runs|employee or contractor|employee vs|employee.*contractor.*line|gateway.*common law.*contractor status", r"status breaks|threshold|freelancer route.*tax",
                    r"regist", r"contract|services agreement", r"produce|invoice|issue before settlement|(?:billing|tax).*documents?|documents?.*(?:pay|billing|tax|receipt|provider.?s form)", r"money|funds|paid|payment rails|fees? reach|bank processing|international receipt",
            r"payment terms|late[- ]payment|due payment|due date", r"breaks|fail", r"mistake|who pays", r"models?|which fits|each fits|services.*intermediary.*employment",
                    r"one contractor|versus ten", r"who works with", r"questions"],
}
# Topics the guides never cover (config/brand-rules.json, banned_topics). Empty by default.
FORBIDDEN = [pattern for pattern, _ in configured_rules("banned_topics")]
# Claims that are forbidden only next to the brand (config/brand-rules.json, self_forbidden).
# Checked only in a prose sentence that names the brand; a negated sentence is a boundary statement.
OWNPRODUCT_FORBIDDEN = [(re.compile(rule["pattern"], re.I), rule["message"])
                        for rule in BRAND_RULES["self_forbidden"]["rules"]]
NEGATED = re.compile(r"\b(?:not|no|never|without)\b|n['’]t\b", re.I)
BRAND_MISSPELT = any_of(BRAND_RULES["brand_misspellings"]["patterns"])
# Hosts a guide never links to (config/vendors.json); the job's own vendor evidence adds more.
COMPETITORS = tuple(json.loads((ROOT / "config" / "vendors.json").read_text(encoding="utf-8"))["competitor_domains"])
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
LINK = re.compile(r"\]\((https?://[^)\s]+)")
DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", " ": " ", " ": " "})


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(DASHES)).strip().lower()


def sections(text: str) -> list[tuple[str, str]]:
    """(H2 title, body) in order."""
    parts = re.split(r"^##\s+(.+?)\s*$", text, flags=re.M)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def forbidden_matches(text: str):
    """Banned topics and stop-listed brands anywhere on the page, in order of appearance."""
    found = [m for pattern in [*FORBIDDEN, STOP_BRANDS] for m in pattern.finditer(text)]
    return sorted(found, key=lambda m: m.start())


def ownproduct_claims(visible: str):
    """Yield (matched text, reason) for forbidden claims in sentences naming the brand."""
    for line in visible.split("\n"):
        if line.lstrip().startswith("|"):  # table rows are judged by QA: cells may belong to other vendors
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if not BRAND_RE.search(sentence):
                continue
            for pattern, reason in OWNPRODUCT_FORBIDDEN:
                m = pattern.search(sentence)
                if m and not NEGATED.search(sentence[:m.start()]):
                    yield m.group(0), reason


def allowed_internal(slug: str) -> set[str]:
    path = ROOT / "config" / "site-links.json"
    links = set(json.loads(path.read_text(encoding="utf-8"))["urls"]) if path.exists() else set()
    links |= {page_url(slug, p) for p in PAGES} | {f"https://{SITE_HOST}/guides/"}
    return links


# Official hosts whose document codes (letter-NNN-YYYY, e.g. "C-150-2022") look like workflow IDs.
# Add a host here when a country's primary source titles carry such codes. Empty by default.
ID_LIKE_CODE_HOSTS: tuple[str, ...] = ()


def internal_id_matches(text: str):
    """Find workflow IDs, preserving exact official document codes in Sources from ID_LIKE_CODE_HOSTS."""
    # Keep offsets stable while excluding destinations, as the visible-text check does.
    visible = re.sub(r"\]\([^)]*\)", lambda m: "]" + " " * (len(m[0]) - 1), text)
    sources = re.search(r"^##\s+Sources\s*$", text, re.M)
    if sources and ID_LIKE_CODE_HOSTS:
        hosts = "|".join(re.escape(host) for host in ID_LIKE_CODE_HOSTS)
        original = re.compile(
            r"^\d+\.\s+[^\n]*?\[([^\]\n]+)\]"
            r"\(https://(?:www\.)?(?:" + hosts + r")/[^)\s]+\)", re.M)
        for entry in original.finditer(text, sources.end()):
            for code in re.finditer(r"\bC-\d{3}-\d{4}\b", entry[1]):
                start = entry.start(1) + code.start()
                end = entry.start(1) + code.end()
                visible = visible[:start] + " " * (end - start) + visible[end:]
    return re.finditer(r"\b[CFEV]-\d{3}\b|\bR-[CPA]-\d{2}\b", visible)


def vendor_domains(path: Path) -> set[str]:
    """Read vendor hosts from the job's evidence, without treating our own site as a competitor."""
    domains = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            # Quotes can contain a literal pipe escaped for the Markdown table.
            # It belongs to the quote, not to a ninth evidence column.
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            if len(cells) == 8 and re.fullmatch(r"V-\d{3}", cells[0]) and cells[4] == "vendor":
                host = urlsplit(cells[3]).hostname
                if host and host != SITE_HOST and not host.endswith("." + SITE_HOST):
                    domains.add(host.removeprefix("www."))
    return domains


def is_vendor_url(url: str, domains: set[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def check_page(text: str, page: str, job: dict, facts: dict | None,
               extra_vendor_domains: set[str] | None = None) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    competitors = set(COMPETITORS) | (extra_vendor_domains or set())
    h1s = re.findall(r"^#\s+(.+?)\s*$", text, re.M)
    if h1s != [h1(job["country"], page, job.get("iso", ""))]:
        errors.append(f"H1 must be exactly one line «# {h1(job['country'], page, job.get('iso', ''))}», found {h1s}")
    deep = [m.group(2) for m in HEADING.finditer(text) if len(m.group(1)) > 4]
    if deep:
        errors.append(f"headings deeper than H4: {deep[:3]}")
    secs = sections(text)
    titles = [t for t, _ in secs]
    pos = -1
    for pattern in CORE[page]:
        hit = next((i for i, t in enumerate(titles) if re.search(pattern, t, re.I) and i > pos), None)
        if hit is None:
            errors.append(f"core section missing or out of order: /{pattern}/")
        else:
            pos = hit
    if not titles or titles[-1] != "Sources":
        errors.append("the last H2 must be «Sources»")
    elif len(titles) < 2 or not re.search(r"questions", titles[-2], re.I):
        errors.append("FAQ must be the H2 right before Sources")
    # The answer-first opening is body prose too. Check its figures and links,
    # while keeping the H1 out of the figure-presence check.
    opening = re.split(r"^##\s+", text, maxsplit=1, flags=re.M)[0]
    opening = re.sub(r"^#\s+.*$", "", opening, flags=re.M)
    body = opening + "\n" + "\n".join(b for t, b in secs if t != "Sources")
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)  # images are media, not sources
    src = dict(secs).get("Sources", "")
    items = [l for l in src.splitlines() if re.match(r"^\d+\.\s", l.strip())]
    if not items:
        errors.append("Sources: no numbered entries")
    own_guide_routes = {page_url(job["slug"], p) for p in PAGES}
    for item in items:
        linked = LINK.search(item)
        plain_urls = re.findall(r"(?<![\w.-])(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/[^\s)]*)?", item, re.I)
        vendor_text = not linked and any(is_vendor_url(u if "://" in u else "https://" + u,
                                                       competitors) for u in plain_urls)
        draft_reviewed = ("Draft reviewed" in item and linked is not None
                          and all(url in own_guide_routes for url in LINK.findall(item)))
        if ("Accessed" not in item and not draft_reviewed) or not (linked or vendor_text):
            errors.append(f"Sources entry needs a link (vendor pages: plain text) and «Accessed <date>»: {item[:90]}")
        if any(is_vendor_url(url, competitors) for url in LINK.findall(item)):
            errors.append(f"Sources entry links a competitor — give it as plain text: {item[:90]}")
    for m in re.finditer(r"(?:Accessed|Draft reviewed) (\d{1,2} [A-Z][a-z]+ \d{4})", src):
        try:
            when = datetime.strptime(m.group(1), "%d %B %Y").date()
        except ValueError:
            errors.append(f"Sources: unreadable access date «{m.group(1)}»")
            continue
        if when > date.today():
            errors.append(f"Sources: access date in the future «{m.group(1)}»")
    source_urls = set(LINK.findall(src))
    internal = allowed_internal(job["slug"])
    for url in LINK.findall(body):
        host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
        if host.endswith(SITE_HOST):
            if url.split("#")[0] not in internal:
                errors.append(f"internal link not in site-links.json: {url}")
            if url.split("#")[0] not in source_urls:
                errors.append(f"URL used in the body but missing from Sources: {url}")
        elif is_vendor_url(url, competitors):
            errors.append(f"outbound link to a competitor: {url}")
        elif url not in source_urls:
            errors.append(f"URL used in the body but missing from Sources: {url}")
    for rel in re.findall(r"\]\((/[^)\s]*)\)", body):
        absolute = f"https://{SITE_HOST}" + rel.split("#")[0]
        if absolute not in internal:
            errors.append(f"internal link not in site-links.json: {rel}")
        if absolute not in source_urls:
            errors.append(f"URL used in the body but missing from Sources: {absolute}")
    visible = re.sub(r"\]\([^)]*\)", "]", text)  # link targets are not shown to readers
    for m in internal_id_matches(text):
        errors.append(f"internal evidence ID visible to readers: {m.group(0)}")
    for m in forbidden_matches(text):
        errors.append(f"forbidden word: «{m.group(0)}»")
    for found, reason in ownproduct_claims(visible):
        errors.append(f"next to {BRAND}: {reason} — «{found}»")
    if BRAND_MISSPELT.search(visible):
        errors.append(BRAND_RULES["brand_misspellings"]["message"])
    if page == "country" and facts:
        nbody = norm(body)
        for key, entry in facts["header"].items():
            shown = header_display(entry)
            if norm(shown) not in nbody:
                errors.append(f"header {key} «{shown}» does not appear in the body")
    return errors, warns


def body_words(path: Path) -> list:
    if path.suffix == ".mdx":
        return load(path)
    text = path.read_text(encoding="utf-8")
    text = re.split(r"^##\s+Sources\s*$", text, flags=re.M)[0]
    # Materialized visuals append a bibliography to their caption. Reusing the
    # same official document titles is not copied prose; retain the caption's
    # claims and ordinary body anchors in the overlap comparison.
    citation = r"\[[^\]\n]+\]\(https://[^\s)\n]+\)"
    text = re.sub(r"^(Caption: .*?) " + citation + r"(?: · " + citation + r")*[ \t]*$",
                  r"\1", text, flags=re.M)
    return tokenize(text)


def overlaps(files: list[Path], warn_at: int, block_at: int, n: int = 8) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    docs = {f: body_words(f) for f in files}
    index = {f: grams(w, n) for f, w in docs.items()}
    for a, b in combinations(files, 2):
        shared = set(index[a]) & set(index[b])
        for start, end in runs_for([index[a][g] for g in shared]):
            length = end - start + n
            if length >= warn_at:
                snippet = " ".join(docs[a][start:end + n])
                name = lambda p: p.parent.name if p.suffix == ".md" else f"{p.parent.name}/{p.name}"
                label = f"{name(a)} ↔ {name(b)}: {length} words «{snippet[:160]}…»"
                (errors if length >= block_at else warns).append(label)
    return errors, warns


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--page", choices=PAGES)
    ap.add_argument("--warn-at", type=int, default=20)
    ap.add_argument("--block-at", type=int, default=45)
    args = ap.parse_args()
    job_path = job_dir(args.job)
    job = load_job(job_path)
    facts = read_json(job_path / "facts.json") if (job_path / "facts.json").exists() else None
    vendors = vendor_domains(job_path / "evidence.vendors.md")
    errors, warns = [], []
    mine = []
    for page in ([args.page] if args.page else PAGES):
        edited = page_dir(job_path, page) / "edited.md"
        if not edited.exists():
            errors.append(f"{page}: no edited.md")
            continue
        mine.append(edited)
        vfile = edited.parent / "visuals.json"
        if vfile.exists():
            for v in json.loads(vfile.read_text(encoding="utf-8")).get("visuals", []):
                for k in ("title", "alt", "caption"):
                    if len(v.get(k, "")) > 255:  # Strapi media fields are strings: >255 → HTTP 500
                        errors.append(f"{page}: visual {v['id']} {k} is {len(v[k])} chars, max 255")
        e, w = check_page(edited.read_text(encoding="utf-8"), page, job, facts, vendors)
        vjson = edited.parent / "visuals.json"
        try:
            if order_sources.ordered(edited.read_text(encoding="utf-8"),
                                     json.loads(vjson.read_text(encoding="utf-8")) if vjson.exists() else None) != \
                    order_sources.split(edited.read_text(encoding="utf-8"))[1]:
                e.append("Sources are not in order of first use — run scripts/order_sources.py")
        except ValueError:
            pass
        errors += [f"{page}: {x}" for x in e]
        warns += [f"{page}: {x}" for x in w]
    others = [p for p in (ROOT / "jobs").glob("*/pages/*/edited.md") if job_path not in p.parents]
    # Optional vendor cards of the project are research memory: shared facts are fine, shared
    # prose is not. Nothing is compared when the folder is absent.
    others += sorted(COMPANIES.rglob("*.mdx"))
    all_mine = [p for p in (page_dir(job_path, pg) / "edited.md" for pg in PAGES) if p.exists()]
    pool = sorted(set(mine) | set(all_mine) | set(others))
    if len(pool) > 1:
        e, w = overlaps(pool, args.warn_at, args.block_at)
        mine_names = {p.parent.name for p in mine}
        errors += [x for x in e if any(m in x for m in mine_names)]
        warns += [x for x in w if any(m in x for m in mine_names)]
    for w in warns:
        print("WARN", w)
    if errors:
        sys.exit("BLOCK:\n- " + "\n- ".join(errors))
    print("PASS check_guide")


if __name__ == "__main__":
    main()
