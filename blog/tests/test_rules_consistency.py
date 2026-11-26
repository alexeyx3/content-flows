"""The rules must not contradict each other or refer to deleted things."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
K = ROOT / "knowledge"
RULE_FILES = sorted(K.glob("*.md")) + sorted((ROOT / "prompts").glob("*.md"))
AGENT_FILES = sorted((ROOT / "agents-src" / "agents").glob("blog-*.md"))

DELETED_SCRIPTS = [
    "lj_publish", "telegraph_publish", "tumblr_publish", "devto_publish_draft",
    "hashnode_publish", "differ_sync", "md_to_miralinks_html", "validate_miralinks_txt",
    "check_indexation", "collab_sync", "author-personas",
]


def test_blog_owned_card_exists_and_covers_decisions():
    text = (K / "blog-owned.md").read_text(encoding="utf-8")
    assert "site-urls.json" in text


def test_no_unconditional_first_place_rule():
    """The place of Example Co is set by own_product_rank, not by a hard rule in draft-rules."""
    text = (K / "draft-rules.md").read_text(encoding="utf-8")
    assert "own_product_rank" in text
    assert "Example Co is ranked #1" not in text


def test_category_mismatch_exception_is_consistent():
    """Example Co must not be forced into EOR/PEO/payroll lists under a false label."""
    paths = [
        K / "draft-rules.md",
        K / "blog-owned.md",
        ROOT / "agents-src" / "agents" / "blog-strategy-brief.md",
        ROOT / "agents-src" / "agents" / "blog-company-cards.md",
        ROOT / "agents-src" / "agents" / "blog-section-writer.md",
        ROOT / "agents-src" / "agents" / "blog-editor.md",
        ROOT / "agents-src" / "agents" / "blog-qa-factcheck.md",
    ]
    for path in paths:
        assert "category-mismatch exception" in path.read_text(encoding="utf-8").lower(), path


def test_listicle_placement_requires_publisher_decision():
    paths = [
        K / "draft-rules.md",
        K / "blog-owned.md",
        ROOT / "agents-src" / "agents" / "blog-strategy-brief.md",
        ROOT / "agents-src" / "agents" / "blog-company-cards.md",
        ROOT / "agents-src" / "agents" / "blog-section-writer.md",
        ROOT / "agents-src" / "agents" / "blog-qa-factcheck.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "own_product_placement" in text, path
        assert "ranked" in text and "separate" in text and "omit" in text, path


def test_positioning_does_not_claim_background_checks():
    text = (K / "positioning.md").read_text(encoding="utf-8").lower()
    assert "do not claim that example co runs" in text
    assert "background checks and identity verification are not an example co product function" in text
    assert "«vetted contractors» badge" in text


def test_vendor_headings_are_name_only_in_rules():
    """Rule: a card heading is the service name.

    Only knowledge cards and prompts are checked here; the agents are covered by
    a separate test.
    """
    for p in RULE_FILES:
        text = p.read_text(encoding="utf-8")
        assert "scenario-oriented template" not in text, p.name
        assert "reader scenarios, not attribute labels" not in text, p.name


def test_competitor_links_banned_consistently():
    structure = (K / "article-structure-rules.md").read_text(encoding="utf-8").lower()
    assert "no more than 3 outbound links" not in structure
    assert "there are no outbound links to competitors" in structure


def test_no_word_ceiling_for_blog():
    limits = (K / "platform-limits.md").read_text(encoding="utf-8")
    assert "| Example Co blog | none | 5000 |" not in limits
    assert "**no ceiling.**" in limits.lower()


def test_no_references_to_deleted_tooling():
    for p in RULE_FILES:
        text = p.read_text(encoding="utf-8")
        for name in DELETED_SCRIPTS:
            assert name not in text, f"{p.name} refers to a deleted file: {name}"


# --- agents, prompts and the skill under the owned constant ---

QA = ROOT / "agents-src" / "agents" / "blog-qa-factcheck.md"
SKILL = ROOT / "agents-src" / "skills" / "blog-article" / "SKILL.md"
PROMPTS = [ROOT / "prompts" / "brief-rules.md", ROOT / "prompts" / "edit-rules.md"]


def test_qa_has_blog_gates():
    text = QA.read_text(encoding="utf-8")
    assert "site-urls.json" in text, "no gate on internal links"
    assert "h1" in text.lower(), "no gate banning an H1 in the body"
    assert "contentHtml" in text or "sanitize" in text, "no gate for the HTML contract"


def test_no_third_party_branches_left():
    """The blog branch has one track, owned. There must be no forks by mode or personas."""
    for p in AGENT_FILES + [SKILL] + PROMPTS:
        text = p.read_text(encoding="utf-8").lower()
        assert "third-party" not in text, p.name
        assert "persona" not in text, p.name
        assert "author-personas" not in text, p.name


def test_vendor_headings_are_name_only_in_agents():
    for p in AGENT_FILES + [SKILL]:
        text = p.read_text(encoding="utf-8")
        assert "scenario-oriented template" not in text, p.name
        assert "reader scenarios, not attribute labels" not in text, p.name


def test_length_gate_is_advisory():
    text = QA.read_text(encoding="utf-8")
    assert "115%" not in text, "the length gate must become advisory"


def test_humanize_prompt_is_either_wired_or_gone():
    """No dead files in the prompts: either a script loads the file or the file does not exist."""
    prompt = ROOT / "prompts" / "humanize-ru.md"
    if prompt.exists():
        edit = (ROOT / "scripts" / "edit_draft.py").read_text(encoding="utf-8")
        assert "humanize-ru.md" in edit, "the file exists but the edit does not load it"
