"""Renumber the Sources list of a page in order of first use in the body.

Visible use is a body link, visual citation or table source label. Vendor names in the ranking
table also attribute their plain-text originals. Uncited supporting originals follow visible
citations in stable order; a publisher mention in narrative alone is not a citation. Run after
edits that move citations. check_guide.py reports a list that is out of order.

Usage: python3 scripts/order_sources.py <page>/edited.md [--check]
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_RULES = json.loads((ROOT / "config" / "brand-rules.json").read_text(encoding="utf-8"))
BRAND, SITE = _RULES["brand"], "https://" + _RULES["site_host"]
# Publisher name of a Sources entry (lower case) -> the vendor's name in the ranking table.
ALIASES = json.loads((ROOT / "config" / "vendors.json").read_text(encoding="utf-8"))["aliases"]
LINK = re.compile(r"\]\((https?://[^)\s]+)\)")
ITEM = re.compile(r"^\d+\.\s+")


def split(text: str) -> tuple[str, list[str], str]:
    m = re.search(r"^##\s+Sources\s*$", text, re.M)
    if not m:
        raise ValueError("no «## Sources» section")
    head, rest = text[:m.end()], text[m.end():]
    nxt = re.search(r"^##\s", rest, re.M)
    block, tail = (rest[:nxt.start()], rest[nxt.start():]) if nxt else (rest, "")
    items = [l for l in block.splitlines() if ITEM.match(l.strip())]
    return head, items, tail


def marker_positions(body: str, visuals: dict | None) -> dict[str, int]:
    """URL -> position of the first [[VISUAL:id]] marker whose visual cites it (before images are bound)."""
    pos: dict[str, int] = {}
    for v in (visuals or {}).get("visuals", []):
        at = body.find(f"[[VISUAL:{v['id']}]]")
        if at < 0 and v.get("inserted_markdown"):
            at = body.find(v["inserted_markdown"])
            if at < 0 and "Caption: " in v["inserted_markdown"]:
                # ordered() omits images before comparing positions. Their
                # captions still cite these originals through compact numbers.
                at = body.find(v["inserted_markdown"].split("Caption: ", 1)[1])
        if at >= 0:
            for s in v.get("sources", []):
                pos[s["url"]] = min(pos.get(s["url"], at), at)
    return pos


def table_names(body: str) -> dict[str, int]:
    """Short source names in table cells («Law on Funded Pensions; Kestrel») -> first position."""
    names: dict[str, int] = {}
    offset = 0
    for line in body.splitlines(keepends=True):
        if line.lstrip().startswith("|"):
            for cell in line.strip().strip("|").split("|"):
                # A spaced slash separates source labels, unlike the slash in
                # a decree number or a URL. Keep ambiguity checks per label.
                segments = re.split(r";|\s+/\s+", cell)
                labelled = re.search(r"\bSources?:\s*(.+)", cell, re.I)
                if labelled:
                    segments.extend(re.split(r";|\s+/\s+", labelled[1]))
                # Route/risk cells can cite originals after the substantive
                # prose: «The agency employs the worker. (Agency law; Register)».
                # Extract those labels too; cell_matches still requires one
                # unambiguous original, rather than guessing from the prose.
                for citation in re.findall(r"\(([^()]*)\)", cell):
                    segments.extend(re.split(r";|\s+/\s+", citation))
                for seg in segments:
                    seg = seg.strip().rstrip(".")
                    # «u.ae (expatriate employment). Dubai fees are…» — the name ends at the first «. »
                    for name in {seg, *(part.strip().rstrip('.') for part in seg.split('. '))}:
                        if name and name not in names:
                            names[name] = offset + line.find(name)  # ties inside a cell: left to right
        offset += len(line)
    return names


@lru_cache(maxsize=4096)
def parts(item: str) -> tuple[str, str, str]:
    """(publisher, title, title parenthetical) of a Sources entry «Publisher. [Title (short)](url)…»."""
    body = ITEM.sub("", item.strip())
    m = re.match(r"(.*?)\.\s+\[(.+?)\]\(", body)
    plain = re.match(r"(.*?)\.\s+(.+)", body)
    publisher, title = ((m.group(1), m.group(2)) if m else
                        (plain.group(1), "") if plain else (body, ""))
    par = re.search(r"\(([^()]+)\)\s*$", title)
    trailing = re.search(r"\bAccessed\s+[^\n]+?\.\s*\(([^()]+)\)\.?\s*$", body)
    alias = par.group(1) if par else trailing.group(1) if trailing else ""
    return publisher.lower(), title.lower(), alias.strip().lower()


def _match(name: str, item: str) -> bool:
    pub, title, par = parts(item)
    n = name.strip().lower()
    if title and n == title:
        return True
    if par and n == par:
        return True
    # Bibliographies commonly spell out a publisher and keep its abbreviation
    # in parentheses, while fact tables use that abbreviation (e.g. KSH).
    if n in {alias.strip() for alias in re.findall(r"\(([^()]+)\)", pub)}:
        return True
    # A descriptive label can combine a publisher/abbreviation with title
    # words, e.g. “NSSI temporary-incapacity guidance” or “EURES — taxation”.
    # Require the remaining words in the actual title; cell_matches still
    # rejects a description that could identify more than one original.
    publisher_names = {pub, pub.split(" (")[0]}
    publisher_names.update(re.findall(r"\(([^()]+)\)", pub))
    publisher_names.update(re.split(r"\s+/\s+", pub))
    title_words = set(re.findall(r"\w+", title))
    for publisher_name in publisher_names:
        if n.startswith(publisher_name + " "):
            suffix = n[len(publisher_name):].strip(" —–-:")
            suffix_words = re.findall(r"\w+", suffix)
            if suffix_words and (len(suffix_words) >= 2 or len(suffix_words[0]) >= 6) \
                    and set(suffix_words).issubset(title_words):
                return True
    # Statutory short names can reorder the title's words: “Social Insurance
    # Act” refers to “Act CXXII ... on Social Insurance”. Require every token,
    # and let cell_matches reject aliases shared by several originals.
    keys = re.findall(r"\w+", n)
    if len(keys) >= 2 and re.search(r"(?:^decree\b|\b(?:act|code)$)", n) \
            and set(keys).issubset(set(re.findall(r"\w+", title))):
        return True
    m = re.match(r"(.+?)\s*\((.+)\)$", n)  # «u.ae (payment of wages)» = publisher (title keyword)
    if m:
        # every keyword of the parenthesis matches a title word up to its ending («expatriate» ~ «expatriates»)
        words = re.findall(r"[\w']+", title)
        keys = re.findall(r"[\w']+", m.group(2))
        return m.group(1) in pub and all(any(w.startswith(k[:max(4, len(k) - 2)]) for w in words) for k in keys)
    plain_pub = pub.split(" (")[0]
    return (n == pub or (len(n) > 3 and n in plain_pub) or
            (len(plain_pub) > 3 and
             re.search(r"(?<!\w)" + re.escape(plain_pub) + r"(?!\w)", n) is not None))


def unique_cell_source(name: str, items: list[str]) -> str | None:
    """Resolve a table-cell short name when it identifies only one entry."""
    n = name.strip().lower()
    exact = [source for source in items if n in parts(source)[1:]]
    if exact:
        # An explicit unique title/alias outranks broad descriptive matching.
        # Added aliases can otherwise introduce generic words into other titles.
        return exact[0] if len(exact) == 1 else None
    candidates = [source for source in items if _match(name, source)]
    return candidates[0] if len(candidates) == 1 else None


def cell_matches(name: str, item: str, items: list[str]) -> bool:
    return unique_cell_source(name, items) == item


def short_name_clashes(items: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    for item in items:
        m = re.search(r"\(([^()]+)\)\]\(", item)
        if m:
            seen[m.group(1).strip()] = seen.get(m.group(1).strip(), 0) + 1
    return [n for n, k in seen.items() if k > 1]


def ordered(text: str, visuals: dict | None = None) -> list[str]:
    head, items, _ = split(text)
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", head)
    markers = marker_positions(body, visuals)
    cells = table_names(body)
    # An explicit textual “Source: <document alias>” is a citation, unlike
    # mentioning a publisher while discussing its advice.
    for match in re.finditer(r'\bSources?:\s*([^\n|]+)', body):
        for name in re.split(r';|\s+/\s+', match[1]):
            name = name.strip().rstrip('.')
            if name:
                at = match.start(1) + match[1].find(name)
                cells[name] = min(cells.get(name, at), at)
    # A unique document alias in parentheses is also an explicit citation.
    # Match aliases exactly, rather than interpreting an ordinary publisher
    # mention or an ambiguous label as a reference to a particular original.
    for match in re.finditer(r'\(([^()\n]+)\)', body):
        name = match[1].strip()
        matches = [item for item in items if parts(item)[2] == name.casefold()]
        if len(matches) == 1:
            cells[name] = min(cells.get(name, match.start(1)), match.start(1))
    cell_positions = {}
    for name, at in cells.items():
        source = unique_cell_source(name, items)
        if source is not None:
            cell_positions[source] = min(cell_positions.get(source, at), at)
    def key(item: str):
        link = LINK.search(item)
        url = link.group(1) if link else ''
        found = [body.find("](" + url + ")"), markers.get(url, -1)] if link else []
        # Vendor facts are visibly attributed by vendor name in the ranking
        # table, while their originals intentionally have no outbound links.
        # Several originals for one vendor share this first-use group.
        pub = parts(item)[0]
        if not link or pub == BRAND.lower():
            raw_pub = re.match(r'(.*?)\.\s+', ITEM.sub('', item.strip()))
            brand = raw_pub[1] if raw_pub else pub
            labels = {brand, ALIASES.get(pub, brand)}
            for name, at in cells.items():
                if name.strip() in labels:
                    found.append(at)
        if url.startswith(SITE + "/"):
            # Our root-relative route is the same first-party original listed
            # with its full URL in Sources. Match the whole destination only.
            found.append(body.find("](" + url[len(SITE): ] + ")"))
        # A short source name in a table cell is a use too: «| Hartak, incapacity |» refers to
        # the entry whose title ends «(Hartak, incapacity)».
        if link:
            found.append(cell_positions.get(item, -1))
        hits = [x for x in found if x >= 0]
        if not hits and link:
            # A bare source URL must end here: a homepage is not cited merely
            # because a longer glossary/product URL starts with it.
            bare = re.search(re.escape(url) + r'(?=$|[\s<>"\]\)])', body)
            hits = [bare.start()] if bare else []
        return (0, min(hits) if hits else 10**9)
    return sorted(items, key=key)  # stable within first-use groups and uncited originals


def renumber(text: str, visuals: dict | None = None) -> str:
    head, items, tail = split(text)
    new = [f"{i}. {ITEM.sub('', it.strip())}" for i, it in enumerate(ordered(text, visuals), 1)]
    return head.rstrip() + "\n\n" + "\n".join(new) + "\n" + (("\n" + tail) if tail else "")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    path = Path(args.file)
    text = path.read_text(encoding="utf-8")
    vpath = path.parent / "visuals.json"
    visuals = json.loads(vpath.read_text(encoding="utf-8")) if vpath.exists() else None
    _, items, _ = split(text)
    clashes = short_name_clashes(items)
    if clashes:
        sys.exit(f"two Sources entries share a short name: {clashes} — give each its own")
    if args.check:
        same = [ITEM.sub("", i.strip()) for i in items] == [ITEM.sub("", i.strip()) for i in ordered(text, visuals)]
        sys.exit(0 if same else "Sources are not in order of first use")
    path.write_text(renumber(text, visuals), encoding="utf-8")
    print(f"{len(items)} sources renumbered in order of first use")


if __name__ == "__main__":
    main()
