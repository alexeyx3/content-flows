"""Thin wrapper around the publications Google Sheet (service-account auth).

Shared by check_indexation.py and record_publication.py. Reads config from
config/.env (GOOGLE_SA_KEYFILE, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB_GID).
"""
from __future__ import annotations

from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "config" / ".env"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_env(env_path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def connect(env: dict[str, str] | None = None):
    """Return (gspread client, spreadsheet, target worksheet)."""
    env = env or load_env()
    keyfile = ROOT / env["GOOGLE_SA_KEYFILE"]
    creds = Credentials.from_service_account_file(str(keyfile), scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(env["GOOGLE_SHEET_ID"])
    ws = sh.get_worksheet_by_id(int(env["GOOGLE_SHEET_TAB_GID"]))
    return gc, sh, ws


def read_table(ws) -> tuple[list[str], list[dict]]:
    """Read the worksheet as (headers, rows).

    Each row is a dict keyed by header name, plus `_row` = the 1-based sheet
    row number (header is row 1, data starts at row 2).
    """
    values = ws.get_all_values()
    if not values:
        return [], []
    headers = values[0]
    rows: list[dict] = []
    for sheet_row, raw in enumerate(values[1:], start=2):
        row = {headers[c]: (raw[c] if c < len(raw) else "") for c in range(len(headers))}
        row["_row"] = sheet_row
        rows.append(row)
    return headers, rows


def header_index(headers: list[str]) -> dict[str, int]:
    """Map header name -> 0-based column index (first occurrence wins)."""
    index: dict[str, int] = {}
    for i, name in enumerate(headers):
        if name and name not in index:
            index[name] = i
    return index


def apply_updates(ws, updates: list[tuple[int, int, str]], value_input_option: str = "RAW") -> int:
    """Apply cell updates. `updates` = list of (row_number, col_index_0based, value)."""
    if not updates:
        return 0
    data = [
        {"range": gspread.utils.rowcol_to_a1(row, col + 1), "values": [[value]]}
        for row, col, value in updates
    ]
    ws.batch_update(data, value_input_option=value_input_option)
    return len(data)
