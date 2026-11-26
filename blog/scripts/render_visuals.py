"""Render all planned code visuals, recording their input and output hashes."""
from __future__ import annotations

import argparse
import json
import re
import subprocess

from article_materials import (ROOT, asset_path, digest, job_path, read_json, spec_digest,
                              validate_inputs, write_json)


def render(job):
    job = job.resolve()
    errors = validate_inputs(job)
    if errors:
        raise ValueError("\n".join(errors))
    manifest = read_json(job / "visuals.json")
    lang = re.search(r"^language:\s*(\S+)", (job / "job.yaml").read_text(encoding="utf-8"), re.M)
    (job / "assets").mkdir(exist_ok=True)
    for visual in manifest["visuals"]:
        path = asset_path(job, f'assets/{visual["id"]}.png')
        spec = dict(visual, language=lang.group(1).lower() if lang else "en")
        result = subprocess.run(["node", str(ROOT / "scripts" / "visual_renderer.mjs"), str(path)],
                                input=json.dumps(spec, ensure_ascii=False), text=True, capture_output=True)
        if result.returncode:
            raise ValueError(f'{visual["id"]}: {result.stderr.strip()}')
        dimensions = json.loads(result.stdout)
        sha = digest(path.read_bytes())
        previous = visual.get("asset", {})
        asset = {"path": str(path.relative_to(job)), "sha256": sha,
                 "spec_sha256": spec_digest(visual), **dimensions}
        if previous.get("sha256") == sha and previous.get("spec_sha256") == asset["spec_sha256"]:
            asset.update({k: previous[k] for k in ("url", "media_id", "delivery_url", "remote_sha256", "remote_path", "pixels_identical") if k in previous})
        visual["asset"] = asset
        write_json(job / "visuals.json", manifest)
        print(f'{visual["id"]}: {dimensions["width"]}×{dimensions["height"]}, {path.stat().st_size // 1024} KB')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    try:
        render(job_path(args.job))
    except (ValueError, OSError, KeyError) as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
