"""Host checked article PNGs in the article's Google Drive review folder.

This route is for review Docs only. It does not create Strapi media or authorize
publication. Each file is publicly readable because Google Docs fetches inline
images by URL; the article itself remains in the private review folder.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from googleapiclient.http import MediaFileUpload

from article_materials import (ROOT, asset_path, digest, fetch_remote_image, job_path,
                               read_json, spec_digest, validate_inputs, visual_qa_errors,
                               write_json)
from gdoc_review import ensure_folder, services


def upload(job: Path, dry_run: bool = False) -> None:
    job = job.resolve()
    errors = validate_inputs(job) + visual_qa_errors(job)
    if errors:
        raise ValueError("\n".join(errors))
    manifest = read_json(job / "visuals.json")
    for visual in manifest["visuals"]:
        asset = visual["asset"]
        local = asset_path(job, asset["path"])
        if asset.get("spec_sha256") != spec_digest(visual) or digest(local.read_bytes()) != asset.get("sha256"):
            raise ValueError(f'{visual["id"]}: rendered PNG or spec is stale')
    if dry_run:
        for visual in manifest["visuals"]:
            print(f'{visual["id"]}: ready for Google Drive review upload')
        return

    drive, _ = services()
    folder = ensure_folder(drive, job.name)
    for visual in manifest["visuals"]:
        asset = visual["asset"]
        local = asset_path(job, asset["path"])
        name = f'review-{visual["id"]}-{asset["sha256"][:12]}.png'
        file_id = asset.get("review_drive_id")
        if not file_id:
            query = f"name = '{name}' and '{folder}' in parents and trashed = false"
            found = drive.files().list(q=query, fields="files(id,name)", corpora="drive",
                                       driveId="0ALRemzb0E-o3Uk9PVA", includeItemsFromAllDrives=True,
                                       supportsAllDrives=True).execute().get("files", [])
            if found:
                file_id = found[0]["id"]
            else:
                file_id = drive.files().create(
                    body={"name": name, "parents": [folder]},
                    media_body=MediaFileUpload(str(local), mimetype="image/png"),
                    supportsAllDrives=True, fields="id").execute()["id"]
            asset["review_drive_id"] = file_id
            write_json(job / "visuals.json", manifest)
        permissions = drive.permissions().list(fileId=file_id, supportsAllDrives=True,
                                                fields="permissions(id,type,role)").execute().get("permissions", [])
        if not any(p.get("type") == "anyone" and p.get("role") == "reader" for p in permissions):
            drive.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"},
                                       supportsAllDrives=True, fields="id").execute()
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        body = fetch_remote_image(url)
        if digest(body) != asset["sha256"]:
            raise ValueError(f'{visual["id"]}: Google Drive bytes differ from the checked PNG')
        check = subprocess.run(["node", str(ROOT / "scripts/visual_verify.mjs"), str(local)],
                               input=body, capture_output=True)
        if check.returncode:
            raise ValueError(f'{visual["id"]}: Google Drive PNG dimensions differ')
        remote = local.with_name(local.stem + ".drive.png")
        remote.write_bytes(body)
        asset.update({"url": url, "delivery_url": url, "media_id": f"drive:{file_id}",
                      "remote_path": str(remote.relative_to(job)), "remote_sha256": digest(body),
                      "pixels_identical": True})
        write_json(job / "visuals.json", manifest)
        print(f'{visual["id"]}: Google Drive review image ready')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        upload(job_path(args.job), args.dry_run)
    except (ValueError, OSError, KeyError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
