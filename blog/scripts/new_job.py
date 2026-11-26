"""Scaffold a job folder with a job.yaml template."""
from __future__ import annotations
import sys, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = """workflow_version: 2
answer_contract_version: 1 # new-topic jobs only: question -> scoped evidence -> checked answer
production_text_backend: openrouter_hybrid
semantic_refresh_version: 1 # activates only when article_refresh_version: 1; script coverage before/after editing
duplicate_preflight_version: 1 # require owned-content overlap review before starting
research_v3_version: 1 # shared decision map, parallel document/study/external-voice research before brief
research_discovery_version: 1 # GIST and qualitative primary-source discovery packet
primary_data_research_version: 1 # original-document and numeric-data search before brief
visual_qa_version: 1 # rendered diagrams must pass geometry and independent mobile review before media upload
source_policy_version: 1 # one clickable URL per source, in final Sources list
visual_caption_sources_version: 1 # store formal visual source labels in sources
research_coverage_version: 1 # search log must cover each reader decision in the same research stage
geographic_audit_version: 1 # brief and QA must check scope against country-specific evidence
topic: "{topic}"
temnik_cluster_id: "" # required for blog jobs: ID from the approved temnik row
language: EN
mode: owned
article_type: comparison
own_product_rank: first   # first | top-3 | neutral
own_product_placement: pending # ranking/listicle only: ranked | separate | omit; publisher approval required
author: ""              # required: john.roe | jane.doe
author_angle: ""       # optional: your thesis / desired conclusion for this article
key_points: []         # optional: points you want included
my_experience: ""      # optional: real, generic experience framing to weave in (no fabricated checkable facts)
geo: [US, GB, DE, AU]  # every EN topic: four English-language SERPs
semantics_file: semantics.csv
author_persona: null
include_competitors: []
exclude_competitors: []
must_cite: []
approved_claims: []
"""


CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slug(text: str) -> str:
    text = "".join(CYR.get(ch, ch) for ch in text.lower())
    s = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return s[:60] or "article"


if __name__ == "__main__":
    topic = sys.argv[1]
    date = sys.argv[2]  # pass date explicitly (e.g. 2026-06-28)
    label = sys.argv[3] if len(sys.argv) > 3 else ""  # persona/platform — for parallel same-topic runs
    base = f"{date}-{slug(topic)}" + (f"-{slug(label)}" if label else "")
    job = ROOT / "jobs" / base
    n = 2
    while True:  # collision-proof: never claim a folder another session already created
        try:
            (job / "raw").mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            job = ROOT / "jobs" / f"{base}-{n}"
            n += 1
    (job / "sections").mkdir(exist_ok=True)
    (job / "out").mkdir(exist_ok=True)
    (job / "assets").mkdir(exist_ok=True)
    (job / "progress.md").write_text(
        f"# {topic}\n\n## Request and decisions\n\n## Current stage\n\nJob v2 created.\n\n"
        "## Done and verified\n\n## Open questions\n\n## Proofreading and approvals\n\n## Strapi\n", encoding="utf-8")
    (job / "job.yaml").write_text(TEMPLATE.format(topic=topic), encoding="utf-8")
    print(job)
