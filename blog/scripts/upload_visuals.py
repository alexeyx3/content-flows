"""Upload rendered PNGs into Strapi; persist media URLs per job, without publishing."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.parse
import urllib.request
import uuid

from article_materials import (ROOT, asset_path, digest, fetch_remote_image, job_path, read_json, spec_digest,
                              validate_inputs, visual_qa_errors, write_json)
from strapi_publish import API, api, token


def upload_file(path, info, filename):
    boundary = "blogvisual" + uuid.uuid4().hex
    # JSON is the value of a normal form field. A part-level JSON content type
    # can make multipart parsers classify fileInfo as an uploaded file.
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="fileInfo"\r\n'
            f'\r\n{json.dumps(info, ensure_ascii=False)}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            'Content-Type: image/png\r\n\r\n').encode("utf-8")
    body += path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(API + "/upload", data=body, method="POST", headers={
        "Authorization": "Bearer " + token(), "Content-Type": "multipart/form-data; boundary=" + boundary})
    with urllib.request.urlopen(req, timeout=90) as response:
        files = json.loads(response.read())
    if not isinstance(files, list) or len(files) != 1 or not files[0].get("id") or not files[0].get("url"):
        raise ValueError("Strapi did not return exactly one uploaded file")
    return files[0]


def original_url(result):
    """The CMS lifecycle points url to lg_webp; S3 also retains hash + ext."""
    delivery = urllib.parse.urljoin(API.removesuffix("/api") + "/", result["url"])
    if urllib.parse.urlsplit(delivery).path.lower().endswith((".png", ".jpg", ".jpeg")):
        return delivery
    if result.get("provider") != "aws-s3" or not re.fullmatch(r"[A-Za-z0-9_-]+", result.get("hash", "")) \
            or result.get("ext", "").lower() not in (".png", ".jpg", ".jpeg"):
        raise ValueError("Strapi did not return a verifiable address of the source PNG/JPEG")
    # Matches the installed AWS provider's getFileKey; verify the actual bytes before use.
    return urllib.parse.urljoin(delivery, result["hash"] + result["ext"])


def capture_uploaded_png(url, path):
    """Save the actual CMS output for QA; the CMS may quantize PNG colors."""
    body = fetch_remote_image(url)
    result = subprocess.run(["node", str(ROOT / "scripts/visual_verify.mjs"), str(path)],
                            input=body, capture_output=True)
    if result.returncode:
        raise ValueError("Strapi changed the PNG dimensions: " + result.stderr.decode("utf-8").strip())
    info = json.loads(result.stdout)
    remote_path = path.with_name(path.stem + ".strapi.png")
    remote_path.write_bytes(body)
    return remote_path, digest(body), info["pixels_identical"]


def upload(job, dry_run=False):
    job = job.resolve()
    errors = validate_inputs(job) + visual_qa_errors(job)
    if errors:
        raise ValueError("\n".join(errors))
    data = read_json(job / "visuals.json")
    # Validate every file before the first external mutation.
    for v in data["visuals"]:
        a = v.get("asset", {})
        if a.get("spec_sha256") != spec_digest(v) or \
                digest(asset_path(job, a["path"]).read_bytes()) != a.get("sha256"):
            raise ValueError(f'{v["id"]}: render the current task first')
    for v in data["visuals"]:
        a = v["asset"]
        if a.get("url") and a.get("media_id") and not str(a["media_id"]).startswith("drive:") \
                and str(a.get("remote_path", "")).endswith(".strapi.png"):
            print(f'{v["id"]}: already uploaded')
            continue
        filename = f'{job.name[:80]}-{v["id"]}-{a["sha256"][:12]}.png'
        # Strapi uses fileInfo.name as a file name and rejects characters such
        # as ':' even though they are valid in an editorial image title.
        media_name = re.sub(r'[\\/:*?"<>|]', " - ", v["title"])
        info = {"name": media_name, "alternativeText": v["alt"], "caption": v["caption"]}
        if dry_run:
            print(f'{v["id"]}: ready to upload, {filename}')
            continue
        result = api(f'/upload/files/{a["media_id"]}') if a.get("media_id") and not str(a["media_id"]).startswith("drive:") else \
            upload_file(asset_path(job, a["path"]), info, filename)
        a["media_id"] = result["id"]
        a["delivery_url"] = urllib.parse.urljoin(API.removesuffix("/api") + "/", result["url"])
        # Persist the ID before checking the CDN so a retry never creates a duplicate.
        write_json(job / "visuals.json", data)
        public_url = original_url(result)
        remote_path, remote_sha, same_pixels = capture_uploaded_png(public_url, asset_path(job, a["path"]))
        if any(result.get(k) != value for k, value in info.items()):
            raise ValueError(f'{v["id"]}: Strapi changed the image metadata')
        a["url"] = public_url
        a["remote_sha256"] = remote_sha
        a["remote_path"] = str(remote_path.relative_to(job))
        a["pixels_identical"] = same_pixels
        write_json(job / "visuals.json", data)
        print(f'{v["id"]}: uploaded, media_id={a["media_id"]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        upload(job_path(args.job), args.dry_run)
    except (ValueError, OSError, KeyError) as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
