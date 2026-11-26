"""Grok draft of the article via a section-by-section dialogue over the job folder materials.

Blog track (blog branch): the brief is a script, evidence and cards are blog-* agents,
the draft is written by the model via OpenRouter, editing and QA are agents again.

Usage:
  python3 scripts/generate_draft.py --job jobs/<job-dir> [--model grok|gpt-5.5]

Input (in the job folder):
  brief.md        — the brief (generate_brief.py or blog-strategy-brief)
  sections.json   — section order: {"title": ..., "sections": [{id,title,subheadings?}]}
  evidence.md     — fact pack with sources (blog-evidence)
  company_cards.md — vendor cards (blog-company-cards), optional

Output:
  out/draft.md        — the assembled draft (input for edit_draft.py)
  out/draft_meta.json — tokens/cost/time per section

Voice rules come from knowledge/draft-rules.md (shared by all topics).
Idempotency: if out/draft.md exists the run is skipped (delete it to regenerate).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import or_client

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "openrouter.json").read_text(encoding="utf-8"))


def load_job(job_dir: Path) -> dict:
    pack = {
        "rules": (ROOT / "knowledge" / "draft-rules.md").read_text(encoding="utf-8"),
        "brief": (job_dir / "brief.md").read_text(encoding="utf-8"),
        "evidence": (job_dir / "evidence.md").read_text(encoding="utf-8"),
        "sections": json.loads((job_dir / "sections.json").read_text(encoding="utf-8"))["sections"],
    }
    cards = job_dir / "company_cards.md"
    pack["cards"] = cards.read_text(encoding="utf-8") if cards.exists() else ""
    pack["site_urls"] = site_urls_block()
    pack["track_rules"] = track_rules_block()
    return pack


def track_rules_block() -> str:
    """Blog track rules (knowledge/blog-owned.md).

    This card used to reach only the brief, which reads knowledge/ with its own
    tools. The draft and the edit did not see it, and rules that did not make it into the text of
    the brief did not exist for them: that is how a wrong spelling of a term spread through
    a draft after the rule had been written down.
    """
    path = ROOT / "knowledge" / "blog-owned.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def site_urls_block() -> str:
    """Map of the site's live pages for internal linking.

    Without it the rule "links only from config/site-urls.json" cannot be followed: the model
    sees the prohibition but not the addresses, and either places no links at all or invents
    nonexistent ones. Built by fetch_site_urls.py before the run.
    """
    path = ROOT / "config" / "site-urls.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))
    # The language is printed next to the address: without it the rule "only pages in the article's language"
    # cannot be followed, because in the blog Russian articles live on the same path as English ones.
    return "\n".join(
        f"- {u['url']} — {u['label']}" + (f" [lang: {u['lang']}]" if u.get("lang") else "")
        for u in data["urls"])


def system_prompt(pack: dict) -> str:
    parts = [
        "You are writing one article for publication, section by section. "
        "Follow the WRITING RULES and the BRIEF. Use ONLY facts from the EVIDENCE PACK"
        + (" and COMPANY CARDS" if pack["cards"] else "")
        + " — never invent features, prices or numbers.",
        "# WRITING RULES\n" + pack["rules"],
        "# TRACK RULES (knowledge/blog-owned.md — binding for this blog)\n"
        + pack.get("track_rules", ""),
        "# BRIEF\n" + pack["brief"],
        "# EVIDENCE PACK\n" + pack["evidence"],
    ]
    if pack["cards"]:
        parts.append("# COMPANY CARDS\n" + pack["cards"])
    if pack.get("site_urls"):
        parts.append(
            "# INTERNAL LINKS — the only addresses you may link to on Example Co\n"
            "Link by relevance, not by quota. Never invent an address that is not on this list; "
            "never link out to a competitor.\n"
            "DEFAULT DESTINATION IS THE HOME PAGE (https://example.com/) — the publisher's rule. "
            "Audience pages (for example /founders/ or /finance/) do not belong in "
            "an article just to vary the destination: link one of them only when that page is genuinely "
            "about the subject of that sentence. Repeating the home page is fine; any other single "
            "address at most twice.\n"
            "SAME LANGUAGE ONLY: every row below carries a `lang`. From an English article link only "
            "to `lang: en` pages — an English article linking a Russian blog post is a defect the "
            "publisher has already struck out.\n" + pack["site_urls"])
    return "\n\n".join(parts)


def section_message(section: dict) -> str:
    hierarchy = section.get("subheadings") or []
    hierarchy_note = ""
    if hierarchy:
        rendered = "; ".join(
            f'H{item["level"]} "{item["title"]}"' for item in hierarchy
        )
        hierarchy_note = f" Follow the approved subsection hierarchy: {rendered}."
    return (
        f'Write the next section: "{section["title"]}".{hierarchy_note} '
        "Write it fully, usefully, and naturally. Go deeper than competing pages where the supplied "
        "evidence permits. Add no padding, repetition, or AI clichés, and do not retell earlier "
        "sections. Return only the section text in Markdown, starting with its heading."
    )


def sum_usage(records: list[dict]) -> dict:
    return {
        "prompt_tokens": sum(r["prompt_tokens"] for r in records),
        "completion_tokens": sum(r["completion_tokens"] for r in records),
        "cost": round(sum(r["cost"] for r in records), 6),
        "seconds": round(sum(r["seconds"] for r in records), 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--model", default="grok", choices=list(CONFIG["models"]))
    args = ap.parse_args()
    job_dir = Path(args.job) if Path(args.job).is_absolute() else ROOT / args.job
    out_dir = job_dir / "out"
    out_dir.mkdir(exist_ok=True)
    draft_path = out_dir / "draft.md"
    if draft_path.exists():
        print(f"skip: {draft_path} already exists (delete it to regenerate)")
        return

    pack = load_job(job_dir)
    slug = CONFIG["models"][args.model]
    print(f"== {job_dir.name} x {args.model} ({slug}), sections: {len(pack['sections'])}")
    messages = [{"role": "system", "content": system_prompt(pack)}]
    parts: list[str] = []
    records: list[dict] = []
    for section in pack["sections"]:
        messages.append({"role": "user", "content": section_message(section)})
        t0 = time.time()
        try:
            r = or_client.chat(slug, messages, CONFIG["temperature"], CONFIG["max_tokens_per_section"])
        except or_client.ORError as e:
            (out_dir / "draft_meta.json").write_text(
                json.dumps({"status": "failed", "model": slug, "section": section["id"], "error": str(e),
                            "sections": records, "totals": sum_usage(records)}, indent=1),
                encoding="utf-8",
            )
            print(f"  FAILED on {section['id']}: {e}")
            return
        r["seconds"] = round(time.time() - t0, 1)
        messages.append({"role": "assistant", "content": r["text"]})
        parts.append(r["text"])
        records.append({"id": section["id"], "prompt_tokens": r["prompt_tokens"],
                        "completion_tokens": r["completion_tokens"], "cost": r["cost"],
                        "seconds": r["seconds"], "finish_reason": r["finish_reason"]})
        print(f"  {section['id']}: {r['completion_tokens']} tok out, ${r['cost']:.4f}, {r['seconds']}s")
    (out_dir / "draft_meta.json").write_text(
        json.dumps({"status": "ok", "model": slug, "sections": records, "totals": sum_usage(records)}, indent=1),
        encoding="utf-8",
    )
    draft_path.write_text("\n\n".join(p.strip() for p in parts), encoding="utf-8")
    totals = sum_usage(records)
    print(f"  done: {draft_path} — ${totals['cost']:.4f}, {totals['seconds']}s")


if __name__ == "__main__":
    main()
