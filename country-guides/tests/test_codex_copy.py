"""Observable project invariants: local ownership, optional hints and working assets."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import common
import new_guide_job
import strapi_publish
import sync_agents

ROOT = Path(__file__).resolve().parents[1]


def test_shared_imports_and_credentials_resolve_inside_the_copy():
    import article_materials
    import text_overlap
    import gdoc_review
    import openai_guide_experiment
    import openrouter_experiment
    assert common.BLOG.is_relative_to(ROOT)
    assert common.HINTS.is_relative_to(ROOT) and common.COMPANIES.is_relative_to(ROOT)
    for module in (article_materials, text_overlap, strapi_publish, gdoc_review):
        assert Path(module.__file__).resolve().is_relative_to(ROOT)
    assert strapi_publish.TOKEN_FILE.is_relative_to(ROOT)
    assert strapi_publish.SANITIZER.is_relative_to(ROOT)
    assert gdoc_review.KEYFILE.is_relative_to(ROOT)
    for module in (openai_guide_experiment, openrouter_experiment):
        assert module.KEY_SOURCE.is_relative_to(ROOT)


def test_secrets_are_ignored_and_absent_from_the_template():
    ignored = (ROOT / ".gitignore").read_text().split()
    for path in (strapi_publish.TOKEN_FILE, common.BLOG / "config/.env",
                 common.BLOG / "config/google-service-account.json", common.BLOG / "config/openai-api-key"):
        assert str(path.relative_to(ROOT)) in ignored
    assert (common.BLOG / "config/.env.example").is_file()


def new_job_project(tmp_path, monkeypatch):
    local = tmp_path / "project"
    (local / "config").mkdir(parents=True)
    (local / "config/queue.json").write_bytes((ROOT / "config/queue.json").read_bytes())
    monkeypatch.setattr(common, "ROOT", local)
    monkeypatch.setattr(new_guide_job, "ROOT", local)
    monkeypatch.setattr(new_guide_job, "HINTS", local / "hints")
    monkeypatch.setattr(new_guide_job, "check_country", lambda iso, slug: {
        "status": "PASS", "iso": iso, "slug": slug, "mode": "offline fixture"})
    return local


def test_new_job_copies_optional_hints_and_touches_only_its_own_queue(tmp_path, monkeypatch):
    local = new_job_project(tmp_path, monkeypatch)
    (local / "hints").mkdir()
    # Invented test data: a hint is a lead, never a source.
    (local / "hints/germany.yaml").write_text("minimum_wage: test value, reopen at the primary source\n")
    (local / "hints/germany--vendors.yaml").write_text("- vendor: Northwind\n  note: test value\n")
    original = (ROOT / "config/queue.json").read_bytes()
    relative = new_guide_job.create("germany", "2099-01-01")
    job = local / relative
    assert (job / "raw/hint-facts.yaml").read_bytes() == (local / "hints/germany.yaml").read_bytes()
    assert (job / "raw/hint-vendors.yaml").read_bytes() == (local / "hints/germany--vendors.yaml").read_bytes()
    assert len(list((job / "pages").glob("*/job.yaml"))) == 3
    created = json.loads((job / "job.json").read_text())
    assert created["slug"] == "germany" and created["geos"] == ["us", "gb", "au", "de"]
    assert (ROOT / "config/queue.json").read_bytes() == original
    statuses = {c["slug"]: c["status"] for c in json.loads((local / "config/queue.json").read_text())["countries"]}
    assert statuses.pop("germany") == "in_progress" and set(statuses.values()) == {"planned"}


def test_new_job_without_hints_is_created_silently(tmp_path, monkeypatch):
    local = new_job_project(tmp_path, monkeypatch)
    job = local / new_guide_job.create("australia", "2099-01-01")
    assert sorted(p.name for p in (job / "raw").iterdir()) == ["cms-compatibility.json"]
    assert json.loads((job / "job.json").read_text())["geos"] == ["us", "gb", "au"]


def test_sync_stays_local_and_refuses_unrelated_user_skill(tmp_path, monkeypatch):
    import shutil
    local = tmp_path / "project"
    shutil.copytree(ROOT / "agents-src", local / "agents-src")
    (local / "config").mkdir()
    shutil.copy2(ROOT / "config/codex-model-routing.json", local / "config/codex-model-routing.json")
    monkeypatch.setattr(sync_agents, "ROOT", local)
    user_dir = tmp_path / "user-codex"
    monkeypatch.setenv("CODEX_HOME", str(user_dir))
    sync_agents.sync()
    assert (local / ".agents/skills/country-guide/SKILL.md").is_file()
    assert len(list((local / ".codex/agents").glob("*.toml"))) == 10
    assert not user_dir.exists()
    dest = user_dir / "skills/country-guide"
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("unrelated skill")
    import pytest
    with pytest.raises(SystemExit, match="Refusing"):
        sync_agents.sync(install_user_skill=True)
    assert (dest / "SKILL.md").read_text() == "unrelated skill"


def test_sanitizer_keeps_a_guide_table_and_visual():
    html = '<h2>Cost</h2><table><tbody><tr><td>100</td></tr></tbody></table><figure class="image"><img src="https://example.com/a.png" alt="Cost" width="1200" height="700" /><figcaption>Source</figcaption></figure>'
    result = subprocess.run(["node", str(strapi_publish.SANITIZER)], input=html,
                            text=True, capture_output=True, check=True)
    assert result.stdout == html


def test_renderer_and_cms_verifier_use_bundled_brand(tmp_path, monkeypatch):
    monkeypatch.delenv("BLOG_BRAND_DIR", raising=False)
    monkeypatch.delenv("BLOG_LOGO_PATH", raising=False)
    # Invented test data for a synthetic visual.
    visual = {"id": "wage-history", "type": "bar", "language": "en", "title": "Minimum wage by year",
              "alt": "Minimum wage by year", "caption": "Test data.",
              "sources": [{"label": "Test source", "url": "https://stats.example/wages"}],
              "data": {"unit": "EUR", "categories": ["2024", "2025", "2026"],
                       "series": [{"name": "Minimum wage", "values": [100, 110, 120]}]}}
    output = tmp_path / "visual.png"
    result = subprocess.run(["node", str(common.BLOG / "scripts/visual_renderer.mjs"), str(output)],
                            input=json.dumps(visual), text=True, capture_output=True, check=True)
    dimensions = json.loads(result.stdout)
    assert dimensions["width"] == 1200 and dimensions["height"] > 0
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    verified = subprocess.run(["node", str(common.BLOG / "scripts/visual_verify.mjs"), str(output)],
                              input=output.read_bytes(), capture_output=True, check=True)
    assert json.loads(verified.stdout)["pixels_identical"] is True
