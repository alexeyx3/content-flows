"""Codex agent track wiring and role integrity."""
import re
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "blog-article" / "SKILL.md"
ROLES = ROOT / "agents-src" / "agents"
AGENTS = ROOT / ".codex" / "agents"
ROUTING = ROOT / "config" / "codex-model-routing.json"
PAID = ("generate_brief.py", "generate_draft.py", "edit_draft.py")
AGENT_NAMES = (
    "blog-coordinator", "blog-research-map", "blog-topic-research", "blog-primary-data-research", "blog-study-research", "blog-quote-scout", "blog-visual-planner", "blog-visual-qa", "blog-expert-quotes", "blog-strategy-brief", "blog-evidence", "blog-company-cards",
    "blog-section-writer", "blog-editor", "blog-qa-factcheck",
    "blog-translator", "blog-translation-editor", "blog-translation-qa",
)


def text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_exists_and_names_itself():
    assert re.search(r"^name:\s*blog-article\s*$", text(), re.M)


def test_paid_scripts_are_only_mentioned_in_the_comparison_table():
    assert not any(script in text() for script in PAID)


def test_dispatched_agents_exist():
    for name in AGENT_NAMES:
        assert name in text(), f"the skill does not dispatch {name}"
        path = AGENTS / f"{name}.toml"
        assert path.exists(), f"no Codex agent {name}"
        cfg = tomllib.loads(path.read_text(encoding="utf-8"))
        assert cfg["name"] == name
        assert cfg["description"]
        assert cfg["developer_instructions"]
        assert (ROLES / f"{name}.md").exists(), f"no role spec {name}"


def test_model_routing_is_explicit_isolated_and_medium():
    routing = json.loads(ROUTING.read_text(encoding="utf-8"))
    assert routing["schema_version"] == 1
    assert routing["fork_turns"] == "none"
    assert set(routing["agents"]) == set(AGENT_NAMES)
    expected = {
        "blog-coordinator": "gpt-5.6-luna",
        "blog-topic-research": "gpt-6-sol",
        "blog-research-map": "gpt-6-sol",
        "blog-primary-data-research": "gpt-6-sol",
        "blog-study-research": "gpt-6-sol",
        "blog-quote-scout": "gpt-6-sol",
        "blog-visual-planner": "gpt-6.1-terra",
        "blog-visual-qa": "gpt-6.1-sol",
        "blog-expert-quotes": "gpt-6.1-terra",
        "blog-strategy-brief": "gpt-6-sol",
        "blog-evidence": "gpt-6-sol",
        "blog-company-cards": "gpt-6.1-terra",
        "blog-section-writer": "gpt-6.1-terra",
        "blog-editor": "gpt-6-sol",
        "blog-qa-factcheck": "gpt-6-sol",
        "blog-translator": "gpt-6-luna",
        "blog-translation-editor": "gpt-6-sol",
        "blog-translation-qa": "gpt-6-sol",
    }
    assert {name: row["model"] for name, row in routing["agents"].items()} == expected
    assert {row["reasoning_effort"] for row in routing["agents"].values()} == {"medium"}


def test_thin_coordinator_contract_is_wired():
    role = (ROLES / "blog-coordinator.md").read_text(encoding="utf-8")
    skill = text()
    for required in (
        'fork_turns="none"', "codex-model-routing.json", "article_delta.py",
        "build_orchestrator_review.py", "pipeline_lock.py", "followup_task",
    ):
        assert required in role or required in skill


def test_active_track_uses_root_orchestration_without_nested_coordinator():
    skill = text()
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "orchestrates article jobs directly" in skill
    assert "spawns every specialist directly" in skill
    assert "Do not dispatch it in the active flat track" in skill
    assert "required specialist agents directly as depth-1 children" in agents
    assert "Do not insert an intermediate `blog-coordinator`" in agents


def test_section_writer_carries_the_binding_rules():
    """The section writer is the only new agent; rules that the publisher has already
    struck out must be in it, not only in knowledge."""
    t = (ROLES / "blog-section-writer.md").read_text(encoding="utf-8")
    for rule in ("Negative labels are not", "Agent of Record",
                 "Paragraphs follow meaning", "own_product_rank", "format is never",
                 "EOR, AOR",
                 "no length target", "Quotation typography"):
        assert rule in t, f"blog-section-writer lacks the rule: {rule}"


def test_writer_uses_one_session_and_compact_write_first_style():
    writer = (ROLES / "blog-section-writer.md").read_text(encoding="utf-8")
    skill = text()
    style = (ROOT / "knowledge" / "writer-style.md").read_text(encoding="utf-8")
    assert "persistent writer" in writer
    assert "same session" in writer
    assert "knowledge/writer-style.md" in writer
    assert "one persistent `blog-section-writer` thread" in skill
    assert "one complete H2 subtree per turn" in skill
    assert "3–4 sequential batches" not in skill
    assert "English tells to avoid" in style
    assert "Russian tells to avoid" in style


def test_rework_cycle_budget_is_bounded():
    skill = text()
    coordinator = (ROLES / "blog-coordinator.md").read_text(encoding="utf-8")
    assert re.search(r"at\s+most one targeted correction/re-check", skill)
    assert "one targeted correction/re-check" in coordinator
    assert "Stop after three failed" not in skill


def test_assembler_is_wired_into_the_skill():
    assert "assemble_sections.py" in text()


def test_packager_is_wired_into_the_skill():
    assert "package_article.py" in text()
    assert "build_internal_package.py --job" not in text()


def test_completed_article_is_sent_to_google_docs_automatically():
    skill = text()
    coordinator = (ROLES / "blog-coordinator.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    command = "gdoc_review.py push --job <job> --round 1"
    assert command in skill
    assert command in coordinator
    assert "Standing project exception" in agents
    assert "never authorizes Strapi or publication" in coordinator


def test_sync_does_not_write_to_claude_home():
    src = (ROOT / "scripts" / "sync_agents.py").read_text(encoding="utf-8")
    assert 'Path.home() / ".claude"' not in src
    assert "validate_codex_setup.py" in src


def test_role_contracts_match_real_artifacts():
    brief = (ROLES / "blog-strategy-brief.md").read_text(encoding="utf-8")
    for name in ("serp.serp_synthesis.md", "serp.competitor_structures.csv",
                 "serp.serp_features.json"):
        assert name in brief

    editor = (ROLES / "blog-editor.md").read_text(encoding="utf-8")
    assert "exactly one H1" in editor
    assert "name only" in editor


def test_new_job_requires_known_author_choice():
    source = (ROOT / "scripts" / "new_job.py").read_text(encoding="utf-8")
    assert 'author: ""' in source
    assert "john.roe | jane.doe" in source
    assert "geo: [US, GB, DE, AU]" in source


def test_writer_facing_contract_has_no_length_targets():
    strategy = (ROLES / "blog-strategy-brief.md").read_text(encoding="utf-8")
    writer = (ROLES / "blog-section-writer.md").read_text(encoding="utf-8")
    skill = text()
    assert "Never copy a\n  length, word-count range, target, or section budget" in strategy
    assert "Do not estimate, infer, or optimize for a total word count" in writer
    assert "validate_article_brief.py" in skill


def test_full_hybrid_has_no_numeric_section_cap_or_microbrief_requirement():
    strategy = (ROLES / "blog-strategy-brief.md").read_text(encoding="utf-8")
    validator = (ROOT / "scripts" / "validate_article_brief.py").read_text(encoding="utf-8")
    assert "There is no numerical cap" in strategy
    assert "6-11" not in strategy
    assert "6 <= len(sections) <= 11" not in validator
    assert "specific coverage instruction" not in text()


def test_temnik_topic_is_not_a_final_headline_or_list_size():
    skill = text()
    assert re.search(
        r"not\s+a\s+final\s+query,\s+headline,\s+list\s+size,\s+year,\s+or\s+wording\s+constraint",
        skill,
    )
    assert "Never carry a number such as" in skill


def test_all_english_topics_use_four_serp_geos():
    skill = text()
    coordinator = (ROLES / "blog-coordinator.md").read_text(encoding="utf-8")
    for geo in ("--geo us", "--geo gb", "--geo de", "--geo au"):
        assert geo in skill
    for geo in ("--require-geo us", "--require-geo gb", "--require-geo de", "--require-geo au"):
        assert geo in skill
    assert "every English topic" in coordinator


def test_payroll_and_eor_classification_is_retained():
    positioning = (ROOT / "knowledge" / "positioning.md").read_text(encoding="utf-8")
    qa = (ROLES / "blog-qa-factcheck.md").read_text(encoding="utf-8")
    assert "Not a marketplace, not a law firm" in positioning
    assert "never describe it as a payroll provider, EOR" in qa
    assert "Negative labels are optional" in qa
