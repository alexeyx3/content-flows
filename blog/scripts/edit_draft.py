"""Edit the draft via OpenRouter (replaces the blog-editor subagent).

Usage:
  python3 scripts/edit_draft.py --job jobs/<job-dir>                 # regular pass
  python3 scripts/edit_draft.py --job jobs/<job-dir> --qa-report qa_report.md --force
                                                                     # fixes from the QA notes

Input:  out/draft.md, brief.md, evidence.md (+ company_cards.md), knowledge/draft-rules.md,
        prompts/edit-rules.md; in fix mode also qa_report.md.
Output: edited.md, editor_issues.md, edit_meta.json.

In --qa-report mode the WHOLE text is edited with the attached notes (an API edit costs
~$0.1, so the agent's section-by-section patch mode is not needed here). Fallback after two failures:
the blog-editor subagent.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import or_client
from generate_draft import site_urls_block, track_rules_block  # shared inputs of the draft and the edit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "openrouter.json").read_text(encoding="utf-8"))
ISSUES_MARKER = "## EDITOR ISSUES"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--model", default="editor", choices=list(CONFIG["models"]))
    ap.add_argument("--qa-report", help="file with QA notes (relative to the job folder)")
    ap.add_argument("--force", action="store_true", help="overwrite the existing edited.md")
    args = ap.parse_args()

    job = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    edited_path = job / "edited.md"
    if edited_path.exists() and not args.force:
        print(f"skip: {edited_path} already exists (--force to overwrite)")
        return
    draft = job / "out" / "draft.md"
    if not draft.exists():
        raise SystemExit(f"{draft} is missing: run step 3 (generate_draft.py) first")

    system_parts = [
        (ROOT / "prompts" / "edit-rules.md").read_text(encoding="utf-8"),
        "# INTERNAL LINKS — the only addresses that may appear as links to Example Co\n"
        "Replace any link to the home page with the section that actually answers the sentence, "
        "or unlink the brand name. Never invent an address absent from this list.\n"
        + site_urls_block(),
        "# TRACK RULES (knowledge/blog-owned.md — binding for this blog)\n"
        + track_rules_block(),
        "# HOUSE RULES (knowledge/draft-rules.md — enforce these)\n"
        + (ROOT / "knowledge" / "draft-rules.md").read_text(encoding="utf-8"),
        "# BRIEF (the draft was written to this; take the H1 from here if the draft lacks one)\n"
        + (job / "brief.md").read_text(encoding="utf-8"),
        "# EVIDENCE PACK (the only allowed facts — never add or drop a fact)\n"
        + (job / "evidence.md").read_text(encoding="utf-8"),
    ]
    cards = job / "company_cards.md"
    if cards.exists():
        system_parts.append("# COMPANY CARDS\n" + cards.read_text(encoding="utf-8"))

    text_to_edit = draft.read_text(encoding="utf-8")
    user_parts = []
    if args.qa_report:
        qa = job / args.qa_report
        if not qa.exists():
            raise SystemExit(f"{qa} is missing")
        if edited_path.exists():
            text_to_edit = edited_path.read_text(encoding="utf-8")
        user_parts.append(
            "REWORK PASS. The QA report below lists what must be fixed. Fix exactly those issues; "
            "leave everything else as it is. Do not add facts to satisfy a gate — if a gate cannot be "
            "closed without a fact that is absent from the evidence pack, rewrite around it and say so "
            f"in the {ISSUES_MARKER} block.\n\n# QA REPORT\n" + qa.read_text(encoding="utf-8"))
    user_parts.append(
        f"After the article, append a final block titled `{ISSUES_MARKER}` listing anything you could not "
        "fix without new facts, plus judgement calls you made (one bullet each). The article itself must "
        "end before that block.")
    user_parts.append("TEXT TO EDIT:\n\n" + text_to_edit)

    slug = CONFIG["models"][args.model]
    print(f"== edit {job.name} with model {args.model} ({slug})"
          + (f", fixes from {args.qa_report}" if args.qa_report else ""))
    t0 = time.time()
    r = or_client.chat(slug, [{"role": "system", "content": "\n\n".join(system_parts)},
                              {"role": "user", "content": "\n\n".join(user_parts)}],
                       temperature=0.3, max_tokens=CONFIG.get("max_tokens_edit", 28000),
                       reasoning=CONFIG.get("reasoning_edit"))
    seconds = round(time.time() - t0, 1)
    text = r["text"]
    if ISSUES_MARKER in text:
        article, issues = text.split(ISSUES_MARKER, 1)
    else:
        article, issues = text, " (the model returned no notes block)\n"
    edited_path.write_text(article.rstrip() + "\n", encoding="utf-8")
    (job / "editor_issues.md").write_text(ISSUES_MARKER + issues.rstrip() + "\n", encoding="utf-8")
    (job / "edit_meta.json").write_text(json.dumps({
        "status": "ok", "model": slug, "mode": "rework" if args.qa_report else "full",
        "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"],
        "cost": round(r["cost"], 6), "seconds": seconds, "finish_reason": r["finish_reason"],
        "words": len(article.split()),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    if r["finish_reason"] == "length":
        print("  WARNING: finish_reason=length: the text may have been truncated, check the end of edited.md")
    print(f"  edited.md ({len(article.split())} words) + editor_issues.md, ${r['cost']:.4f}, {seconds}s")


if __name__ == "__main__":
    main()
