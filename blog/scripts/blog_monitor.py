"""Sync evaluated Google index checks and a linked refresh view in the temnik.

Existing article/refresh lifecycle cells are read-only. Mutations require --apply.
Input is a refresh_indexing receipt, optionally with cluster_id on each page.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3

if __package__:
    from scripts import temnik
else:
    import temnik

TAB = "Blog refreshes"
HEADERS = ["Cluster ID", "Article", "URL", "Refresh status", "Google Doc",
           "Updated on site", "Next content check", "Google: indexing",
           "Google: reason", "Google: checked (UTC)", "Next refresh selection",
           "Bing: indexing", "Cycle"]
STATUS = {"indexed": "Indexed", "index_problem": "Not indexed",
          "canonical_mismatch": "Different canonical", "unknown": "Unknown",
          "unavailable": "Check unavailable"}
SELECTION = {"indexed": "Eligible by index", "index_problem": "Skipped: not indexed",
             "canonical_mismatch": "Skipped: different canonical",
             "unknown": "Skipped: status unknown",
             "unavailable": "Skipped: check unavailable"}


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("inspection timestamp needs an explicit timezone")
    return parsed


def find_page(rows: list[dict], page: dict) -> dict:
    matches = [r for r in rows if page["url"] in {
        r.get(temnik.HEADERS["url"], "").strip(),
        r.get(temnik.HEADERS["publication_url"], "").strip()}]
    if page.get("cluster_id"):
        matches = [r for r in matches if r.get(temnik.HEADERS["cluster"]) == page["cluster_id"]]
    if len(matches) != 1:
        raise ValueError(f"expected one temnik row for {page['url']}; found {len(matches)}")
    return matches[0]


def index_values(page: dict) -> dict:
    status = page["status"]
    if status not in STATUS:
        raise ValueError("unknown inspection status")
    instant(page["checked_at"])
    result = page.get("index_status", {})
    # A receipt cannot promote a different canonical, an exclusion or a missing
    # result to a selectable indexed page.
    if status == "indexed" and not (result.get("verdict") == "PASS" and
                                     result.get("googleCanonical") == page["url"]):
        raise ValueError("indexed receipt lacks matching Google PASS/canonical")
    reason = result.get("coverageState") or page.get("error_type") or "No complete API response"
    return dict(zip(temnik.GOOGLE_MONITOR_HEADERS, [STATUS[status], reason, page["checked_at"],
                    result.get("googleCanonical", ""), result.get("lastCrawlTime", ""), SELECTION[status]]))


def linked(tab: str, cluster_id_col: str, header: str, separator: str = ",") -> str:
    title = tab.replace("'", "''")
    name = header.replace('"', '""')
    s = separator
    return (f'=IFERROR(LET(v{s}INDEX(\'{title}\'!A:ZZ{s}MATCH({cluster_id_col}{s}\'{title}\'!A:A{s}0){s}'
            f'MATCH("{name}"{s}\'{title}\'!1:1{s}0)){s}IF(v=""{s}""{s}v)){s}"")')


def dashboard_row(row: dict, page: dict, number: int, tab_title: str, separator: str = ",") -> list:
    def ref(header):
        return linked(tab_title, f"$A{number}", header, separator)
    title = row.get(temnik.HEADERS["h1"]) or row.get(temnik.HEADERS["title"]) or row.get(temnik.HEADERS["topic"])
    return [row[temnik.HEADERS["cluster"]], title, page["url"],
            ref("Refresh: status"), ref("Refresh: Google Doc"),
            ref("Refresh: published"), ref("Refresh: next check"),
            ref(temnik.GOOGLE_MONITOR_HEADERS[0]), ref(temnik.GOOGLE_MONITOR_HEADERS[1]),
            ref(temnik.GOOGLE_MONITOR_HEADERS[2]), ref(temnik.GOOGLE_MONITOR_HEADERS[5]),
            "Not confirmed: crawl metadata does not prove indexing", ref("Refresh: cycle")]


def sync(receipt: dict, *, apply: bool, db_path: Path | None = None) -> dict:
    book, sheet = temnik.connect()
    headers, rows = temnik.table(sheet)
    prepared, seen = [], set()
    for page in receipt["pages"]:
        row = find_page(rows, page)
        cluster = row[temnik.HEADERS["cluster"]]
        if cluster in seen:
            raise ValueError("duplicate evaluated cluster in receipt")
        seen.add(cluster)
        values = index_values(page)
        prior = row.get(temnik.GOOGLE_MONITOR_HEADERS[2])
        if prior and instant(prior) > instant(page["checked_at"]):
            raise ValueError("refusing an older inspection over a newer temnik check")
        prepared.append((row, page, values))
    try:
        view = book.worksheet(TAB)
        existing = view.get_all_values()
        if not existing or existing[0] != HEADERS:
            raise ValueError("monitor tab headers differ from the managed schema")
    except temnik.gspread.WorksheetNotFound:
        view, existing = None, [HEADERS]
    known = {}
    for number, cells in enumerate(existing[1:], start=2):
        if cells and cells[0]:
            if cells[0] in known:
                raise ValueError("duplicate cluster in monitoring tab")
            known[cells[0]] = number
    result = {"status": "planned", "evaluated_rows": len(prepared), "tab": TAB,
              "sheet_url": book.url, "decisions": [{"url": p["url"], "selection": v[temnik.GOOGLE_MONITOR_HEADERS[5]]}
                                                      for _, p, v in prepared]}
    if not apply:
        return result
    locale = book.fetch_sheet_metadata(params={"fields":"properties(locale)"})["properties"]["locale"]
    # This integration targets the configured Russian temnik; reject unsupported
    # locales rather than publish formulas with guessed separators.
    if locale not in {"ru_RU", "en_US", "en_GB"}:
        raise ValueError(f"unsupported formula locale: {locale}")
    separator = ";" if locale == "ru_RU" else ","
    missing = [name for name in temnik.GOOGLE_MONITOR_HEADERS if name not in headers]
    if missing:
        target = headers + missing
        if sheet.col_count < len(target):
            sheet.resize(cols=len(target))
        sheet.update(range_name=f"A1:{temnik.gspread.utils.rowcol_to_a1(1,len(target))}",
                     values=[target], value_input_option="RAW")
        headers = target
    updates = []
    for row, page, values in prepared:
        for header, value in values.items():
            col = headers.index(header) + 1
            updates.append({"range": temnik.gspread.utils.rowcol_to_a1(int(row["_row"]), col), "values": [[value]]})
    if updates:
        sheet.batch_update(updates, value_input_option="RAW")
    if view is None:
        view = book.add_worksheet(title=TAB, rows=max(100, len(prepared)+1), cols=len(HEADERS))
        view.update(range_name="A1:M1", values=[HEADERS], value_input_option="RAW")
        view.freeze(rows=1, cols=3)
        view.set_basic_filter()
        view.format("A1:M1", {"backgroundColor": {"red":0.12,"green":0.22,"blue":0.32},
                              "textFormat": {"bold":True,"foregroundColor":{"red":1,"green":1,"blue":1}},
                              "wrapStrategy":"WRAP"})
        view.format("A2:M100", {"verticalAlignment":"TOP", "wrapStrategy":"WRAP"})
        widths=[115,320,300,160,230,175,175,150,285,195,260,285,290]
        book.batch_update({"requests":[{"updateDimensionProperties":{"range":{"sheetId":view.id,
            "dimension":"COLUMNS","startIndex":i,"endIndex":i+1},"properties":{"pixelSize":width},
            "fields":"pixelSize"}} for i,width in enumerate(widths)]})
    view_updates=[]
    next_row=max([1,*known.values()])+1
    for row,page,_ in prepared:
        cluster=row[temnik.HEADERS["cluster"]]
        number=known.get(cluster)
        if number is None:
            number=next_row;next_row+=1
        view_updates.append({"range":f"A{number}:M{number}","values":[dashboard_row(row,page,number,sheet.title,separator)]})
    if next_row-1 > view.row_count:
        view.resize(rows=next_row+50)
    if view_updates:
        view.batch_update(view_updates,value_input_option="USER_ENTERED")
    path=db_path or temnik.ROOT/"var/blog-monitor.sqlite3"
    path.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS google_index_checks (
            source_url TEXT NOT NULL, checked_at TEXT NOT NULL, cluster_id TEXT NOT NULL,
            status TEXT NOT NULL, receipt_json TEXT NOT NULL, PRIMARY KEY(source_url,checked_at))""")
        for row,page,_ in prepared:
            packed=json.dumps(page,ensure_ascii=False,sort_keys=True)
            old=db.execute("SELECT receipt_json FROM google_index_checks WHERE source_url=? AND checked_at=?",
                           (page['url'],page['checked_at'])).fetchone()
            if old and old[0]!=packed:
                raise ValueError("historical index receipt identity conflict")
            db.execute("INSERT OR IGNORE INTO google_index_checks VALUES (?,?,?,?,?)",
                       (page['url'],page['checked_at'],row[temnik.HEADERS['cluster']],page['status'],packed))
    result.update(status="synced",view_url=f"{book.url}#gid={view.id}")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(sync(json.loads(args.input.read_text()),apply=args.apply),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
