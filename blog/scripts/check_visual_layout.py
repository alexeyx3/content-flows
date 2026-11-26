"""Prepare deterministic visual QA: current render, geometry, and 390 px previews."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from article_materials import (ROOT, asset_path, digest, job_path, read_json, spec_digest,
                               validate_inputs, visual_render_sources_sha, write_json)


def png_dimensions(body: bytes) -> tuple[int, int]:
    if not body.startswith(b"\x89PNG\r\n\x1a\n") or body[12:16] != b"IHDR":
        raise ValueError("PNG with an IHDR chunk expected")
    return int.from_bytes(body[16:20], "big"), int.from_bytes(body[20:24], "big")


def check(job: Path) -> dict:
    job = job.resolve()
    errors = validate_inputs(job)
    if errors:
        raise ValueError("\n".join(errors))
    manifest = read_json(job / "visuals.json")
    lang_match = re.search(r"^language:\s*(\S+)", (job / "job.yaml").read_text(), re.M)
    language = lang_match.group(1).lower() if lang_match else "en"
    preview_dir = job / "out/visual-qa"
    preview_dir.mkdir(parents=True, exist_ok=True)
    items = []
    with tempfile.TemporaryDirectory(prefix="visual-layout-") as temp:
        for visual in manifest["visuals"]:
            vid, asset = visual["id"], visual.get("asset", {})
            try:
                image_path = asset_path(job, asset["path"])
                body = image_path.read_bytes()
            except (KeyError, OSError, ValueError) as exc:
                raise ValueError(f"{vid}: no rendered PNG ({exc})") from exc
            if digest(body) != asset.get("sha256") or asset.get("spec_sha256") != spec_digest(visual):
                raise ValueError(f"{vid}: PNG or visual spec changed after rendering")
            width, height = png_dimensions(body)
            if (width, height) != (asset.get("width"), asset.get("height")):
                raise ValueError(f"{vid}: PNG size does not match the visual manifest")
            svg = image_path.with_suffix(".svg")
            if not svg.is_file() or "<svg" not in svg.read_text(encoding="utf-8")[:400]:
                raise ValueError(f"{vid}: no SVG for the diagram check")
            replay = Path(temp) / f"{vid}.png"
            spec = dict(visual, language=language)
            result = subprocess.run(
                ["node", str(ROOT / "scripts/visual_renderer.mjs"), str(replay)],
                input=json.dumps(spec, ensure_ascii=False), text=True, capture_output=True,
            )
            if result.returncode:
                raise ValueError(f"{vid}: render/geometry BLOCK: {result.stderr.strip()}")
            if replay.read_bytes() != body:
                raise ValueError(f"{vid}: PNG does not match the current renderer; rerun render_visuals.py")
            if replay.with_suffix(".svg").read_bytes() != svg.read_bytes():
                raise ValueError(f"{vid}: SVG does not match the current renderer; rerun render_visuals.py")
            preview = preview_dir / f"{vid}-390.png"
            result = subprocess.run(
                ["node", str(ROOT / "scripts/visual_mobile_preview.mjs"), str(image_path), str(preview)],
                text=True, capture_output=True,
            )
            if result.returncode:
                raise ValueError(f"{vid}: mobile preview was not created: {result.stderr.strip()}")
            mobile = preview.read_bytes()
            mobile_width, mobile_height = png_dimensions(mobile)
            if mobile_width != 390:
                raise ValueError(f"{vid}: mobile preview must be 390 px")
            items.append({
                "id": vid,
                "type": visual["type"],
                "asset_path": str(image_path.relative_to(job)),
                "asset_sha256": digest(body),
                "spec_sha256": spec_digest(visual),
                "width": width, "height": height,
                "mobile_path": str(preview.relative_to(job)),
                "mobile_sha256": digest(mobile),
                "mobile_width": mobile_width, "mobile_height": mobile_height,
                "automatic_geometry": "PASS" if visual["type"] in {"process", "decision"} else "N/A",
                "current_render": "PASS",
            })
    report = {
        "version": 1,
        "status": "PASS",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "render_sources_sha256": visual_render_sources_sha(),
        "visuals": items,
    }
    write_json(job / "out/visual-layout-check.json", report)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    args = ap.parse_args()
    try:
        report = check(job_path(args.job))
    except (KeyError, OSError, ValueError) as exc:
        raise SystemExit(f"BLOCK: {exc}") from exc
    print(f"PASS: {len(report['visuals'])} visual(s); mobile previews in out/visual-qa/")


if __name__ == "__main__":
    main()
