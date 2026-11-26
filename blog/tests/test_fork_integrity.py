"""The fork must not refer to the track it was split from."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents-src" / "agents"
SKILL = ROOT / "agents-src" / "skills" / "blog-article" / "SKILL.md"
# blog-section-writer was added together with the agent track: it replaces
# scripts/generate_draft.py when the article is written entirely by subagents.
EXPECTED = {
    "blog-topic-research", "blog-primary-data-research", "blog-visual-planner", "blog-visual-qa", "blog-expert-quotes",
    "blog-coordinator", "blog-company-cards", "blog-editor", "blog-evidence",
    "blog-qa-factcheck", "blog-strategy-brief", "blog-section-writer",
    "blog-translator", "blog-translation-editor", "blog-translation-qa",
    "blog-research-map", "blog-study-research", "blog-quote-scout",
}


def test_all_agents_present():
    assert {p.stem for p in AGENTS.glob("blog-*.md")} == EXPECTED


def test_frontmatter_name_matches_filename():
    for p in sorted(AGENTS.glob("blog-*.md")):
        m = re.search(r"^name:\s*(\S+)", p.read_text(encoding="utf-8"), re.M)
        assert m, f"{p.name}: no name field"
        assert m.group(1) == p.stem, f"{p.name}: name={m.group(1)}"


def test_no_grok_left_in_agents_and_skill():
    for p in sorted(AGENTS.glob("blog-*.md")) + [SKILL]:
        text = p.read_text(encoding="utf-8").lower()
        assert "grok" not in text, f"{p.name}: a mention of grok remains"


def test_skill_points_at_this_repo():
    text = SKILL.read_text(encoding="utf-8")
    assert "articles-grok" not in text
    assert text.strip()
    assert re.search(r"^name:\s*blog-article$", text, re.M)


def test_codex_agents_are_repo_local():
    text = (ROOT / "scripts" / "sync_agents.py").read_text(encoding="utf-8")
    assert 'Path.home() / ".claude"' not in text
    assert (ROOT / ".agents" / "skills" / "blog-article" / "SKILL.md").exists()
    assert {p.stem for p in (ROOT / ".codex" / "agents").glob("blog-*.toml")} == EXPECTED
