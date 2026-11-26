"""Upload a DOCX to the publications Drive folder via the service account.

Targets a Shared Drive (supportsAllDrives=True). Reads config from config/.env
(GOOGLE_SA_KEYFILE, GOOGLE_DRIVE_FOLDER_ID). Prints the file id + webViewLink.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "config" / ".env"
SCOPES = ["https://www.googleapis.com/auth/drive"]
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def load_env(env_path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--name", required=True)
    args = ap.parse_args()

    env = load_env()
    keyfile = ROOT / env["GOOGLE_SA_KEYFILE"]
    folder_id = env["GOOGLE_DRIVE_FOLDER_ID"]

    creds = Credentials.from_service_account_file(str(keyfile), scopes=SCOPES)
    service = build("drive", "v3", credentials=creds)

    metadata = {"name": args.name, "parents": [folder_id]}
    media = MediaFileUpload(args.input, mimetype=DOCX_MIME, resumable=False)
    created = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id, name, webViewLink, parents",
            supportsAllDrives=True,
        )
        .execute()
    )
    print("FILE_ID=" + created["id"])
    print("NAME=" + created["name"])
    print("WEBVIEWLINK=" + created.get("webViewLink", ""))
    print("PARENTS=" + ",".join(created.get("parents", [])))


if __name__ == "__main__":
    main()
