"""Brief + sections.json via OpenRouter (replaces the blog-strategy-brief subagent).

The model reads the knowledge base itself with the knowledge_list / knowledge_read tools;
no digest is prepared, and the current knowledge is taken from knowledge/ at run time.

Usage:
  python3 scripts/generate_brief.py --job jobs/<job-dir> [--model brief] [--force]
  python3 scripts/generate_brief.py --job jobs/<job-dir> --sibling-briefs jobs/<other>/brief.md

Input (in the job folder):  job.yaml, serp.serp_synthesis.md, semantics.csv (optional)
Output:                     brief.md, sections.json, brief_meta.json (cost/time/which knowledge was read)

Fallback: if the script fails twice, dispatch the blog-strategy-brief subagent.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import or_client

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
CONFIG = json.loads((ROOT / "config" / "openrouter.json").read_text(encoding="utf-8"))

TOOLS = [
    {"type": "function", "function": {
        "name": "knowledge_list",
        "description": "List knowledge-base files with a one-line summary of each. Call this first.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "knowledge_read",
        "description": "Read one knowledge-base file by its exact filename from knowledge_list.",
        "parameters": {"type": "object", "properties": {"filename": {"type": "string"}},
                       "required": ["filename"]},
    }},
]


def knowledge_summary() -> str:
    lines = []
    for p in sorted(KNOWLEDGE.glob("*.md")):
        if p.name.startswith("_"):
            continue
        first = next((ln.strip("# ").strip() for ln in p.read_text(encoding="utf-8").splitlines()
                      if ln.strip()), "")
        lines.append(f"{p.name} — {first[:110]}")
    return "\n".join(lines)


def tool_handler(name: str, args: dict) -> str:
    if name == "knowledge_list":
        return knowledge_summary()
    if name == "knowledge_read":
        fn = Path(str(args.get("filename", ""))).name
        p = KNOWLEDGE / fn
        if p.suffix != ".md" or not p.exists():
            return f"ERROR: no such knowledge file: {fn}"
        return p.read_text(encoding="utf-8")[:40000]
    return f"ERROR: unknown tool {name}"


def split_output(text: str) -> tuple[str, dict]:
    """Split the response into brief.md and sections.json (the last ```json block)."""
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if not blocks:
        raise ValueError("the response has no ```json block with sections.json")
    sections = json.loads(blocks[-1])
    if "sections" not in sections or not isinstance(sections["sections"], list):
        raise ValueError("sections.json has no sections list")
    n = len(sections["sections"])
    if n < 1:
        raise ValueError("sections.json must contain at least one section")
    for s in sections["sections"]:
        for field in ("id", "title"):
            if not str(s.get(field, "")).strip():
                raise ValueError(f"section without field {field}: {s}")
        if not re.fullmatch(r"[a-z0-9-]+", s["id"]):
            raise ValueError(f"invalid section id: {s['id']}")
        subheadings = s.get("subheadings", [])
        if subheadings is None:
            subheadings = []
        if not isinstance(subheadings, list):
            raise ValueError(f"subheadings must be a list: {s}")
        for subheading in subheadings:
            if not isinstance(subheading, dict):
                raise ValueError(f"a subheading must be an object: {subheading}")
            if subheading.get("level") not in (3, 4):
                raise ValueError(f"subheading level must be 3 or 4: {subheading}")
            if not str(subheading.get("title", "")).strip():
                raise ValueError(f"subheading without title: {subheading}")
    brief = text[:text.rindex("```json")].rstrip()
    # the model sometimes starts with chatter («I have enough to…, writing the brief next»)
    head = re.search(r"^#{1,2} ", brief, re.M)
    if head:
        brief = brief[head.start():]
    return brief, sections


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--model", default="brief", choices=list(CONFIG["models"]))
    ap.add_argument("--sibling-briefs", nargs="*", default=[],
                    help="briefs for the same topic on other platforms; the new brief must differ from them")
    ap.add_argument("--force", action="store_true", help="overwrite the existing brief.md")
    args = ap.parse_args()

    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    brief_path, sections_path = job / "brief.md", job / "sections.json"
    if brief_path.exists() and not args.force:
        print(f"skip: {brief_path} already exists (--force to overwrite)")
        return

    serp = job / "serp.serp_synthesis.md"
    if not serp.exists():
        sys.exit(f"{serp} is missing: run step 1 (SERP scripts) first")
    job_yaml = (job / "job.yaml").read_text(encoding="utf-8")
    semantics = ""
    sem_file = job / "semantics.csv"
    if sem_file.exists():
        semantics = sem_file.read_text(encoding="utf-8")[:8000]

    parts = [
        "# JOB PARAMETERS (job.yaml — binding)\n" + job_yaml,
        "# SERP SYNTHESIS\n" + serp.read_text(encoding="utf-8"),
    ]
    if semantics:
        parts.append("# SEMANTICS (from semantics.csv)\n" + semantics)
    for sb in args.sibling_briefs:
        p = Path(sb) if Path(sb).is_absolute() else ROOT / sb
        if p.exists():
            parts.append("# SIBLING BRIEF (same topic, other platform — your brief MUST differ)\n"
                         + p.read_text(encoding="utf-8")[:12000])
    parts.append("Build the brief and sections.json now. Call the knowledge tools before writing. "
                 "Output the brief in Markdown first, then sections.json in a single ```json fence at the very end.")

    slug = CONFIG["models"][args.model]
    print(f"== brief {job.name} with model {args.model} ({slug})")
    t0 = time.time()
    r = or_client.chat_with_tools(
        slug,
        [{"role": "system", "content": (ROOT / "prompts" / "brief-rules.md").read_text(encoding="utf-8")},
         {"role": "user", "content": "\n\n".join(parts)}],
        TOOLS, tool_handler, temperature=0.4, max_tokens=CONFIG.get("max_tokens_brief", 20000),
    )
    seconds = round(time.time() - t0, 1)
    brief, sections = split_output(r["text"])
    brief_path.write_text(brief + "\n", encoding="utf-8")
    sections_path.write_text(json.dumps(sections, ensure_ascii=False, indent=1), encoding="utf-8")
    read_files = [c["args"].get("filename") for c in r["tool_calls"] if c["name"] == "knowledge_read"]
    (job / "brief_meta.json").write_text(json.dumps({
        "status": "ok", "model": slug, "prompt_tokens": r["prompt_tokens"],
        "completion_tokens": r["completion_tokens"], "cost": round(r["cost"], 6),
        "seconds": seconds, "knowledge_read": read_files, "sections": len(sections["sections"]),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  brief.md + sections.json ({len(sections['sections'])} sections), "
          f"${r['cost']:.4f}, {seconds}s")
    print(f"  knowledge: {read_files}")


if __name__ == "__main__":
    main()
