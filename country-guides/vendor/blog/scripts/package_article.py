"""Insert completed visuals mechanically, then package the current edited article."""
from __future__ import annotations

import argparse
import re

from article_materials import (MARKER, asset_path, digest, guide_source_numbers, is_v2, job_path, read_json,
                              spec_digest, validate_inputs, visual_markdown, write_json)
from md_to_strapi_html import convert



def package(job, bind_visuals=False):
    job = job.resolve()
    text = (job / "edited.md").read_text(encoding="utf-8")
    if is_v2(job):
        problems = validate_inputs(job)
        if problems:
            raise ValueError("\n".join(problems))
        manifest = read_json(job / "visuals.json")
        if bind_visuals:
            metadata = (job / "job.yaml").read_text(encoding="utf-8")
            compact_sources = bool(re.search(r"^country_slug:\s*[a-z][a-z-]*\s*$", metadata, re.M)
                                   and re.search(r"^page:\s*(country|eor|contractors)\s*$", metadata, re.M))
            for v in manifest["visuals"]:
                asset = v.get("asset", {})
                if not asset.get("url") or asset.get("spec_sha256") != spec_digest(v) or \
                        digest(asset_path(job, asset["path"]).read_bytes()) != asset.get("sha256"):
                    raise ValueError(f'{v["id"]}: render and upload the current image first')
                marker = f'[[VISUAL:{v["id"]}]]'
                if compact_sources:
                    asset["source_numbers"] = guide_source_numbers(text, v["sources"])
                block = visual_markdown(v)
                previous = v.get("inserted_markdown")
                if text.count(marker) == 1:
                    text = text.replace(marker, block)
                elif previous and text.count(previous) == 1:
                    text = text.replace(previous, block)
                elif text.count(block) != 1:
                    raise ValueError(f'{v["id"]}: no single marker or previous block; restore the insertion point')
                v["inserted_markdown"] = block
            if MARKER.search(text):
                raise ValueError("an unknown or repeated VISUAL marker remains")
            write_json(job / "visuals.json", manifest)
            (job / "edited.md").write_text(text, encoding="utf-8")
    title, html = convert(text)
    out = job / "out"
    out.mkdir(exist_ok=True)
    (out / "article.md").write_text(text, encoding="utf-8")
    (out / "article.html").write_text(html, encoding="utf-8")
    return title


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--job", required=True)
    ap.add_argument("--bind-visuals", action="store_true")
    args = ap.parse_args()
    try:
        title = package(job_path(args.job), args.bind_visuals)
    except (ValueError, OSError, KeyError) as e:
        raise SystemExit(str(e))
    print(f"packaged: H1={title}; article.md + article.html")


if __name__ == "__main__":
    main()
