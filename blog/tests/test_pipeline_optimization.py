import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DELTA = load_script("article_delta.py")
LOCK = load_script("pipeline_lock.py")


def test_article_delta_reports_only_changed_section(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    edited = job / "edited.md"
    edited.write_text(
        "# Title\n\n## First\n\nKeep this.\n\n## Second\n\nOld sentence.\n",
        encoding="utf-8",
    )
    snapshot = DELTA.snapshot(job, 1)
    assert snapshot.exists()
    edited.write_text(
        "# Title\n\n## First\n\nKeep this.\n\n## Second\n\nNew sentence.\n",
        encoding="utf-8",
    )

    report, sections, structural = DELTA.build_report(job, 1)

    assert sections == ["Second"]
    assert structural is False
    text = report.read_text(encoding="utf-8")
    assert "- Second" in text
    assert "-Old sentence." in text
    assert "+New sentence." in text


def test_article_delta_flags_heading_changes(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "edited.md").write_text("# Title\n\n## Before\n\nText.\n", encoding="utf-8")
    DELTA.snapshot(job, 1)
    (job / "edited.md").write_text("# Title\n\n## After\n\nText.\n", encoding="utf-8")

    _report, sections, structural = DELTA.build_report(job, 1)

    assert structural is True
    assert "After" in sections


def test_editor_delta_reports_section_reduction_and_heading_removal(tmp_path):
    job = tmp_path / "job"
    (job / "out").mkdir(parents=True)
    (job / "out" / "draft.md").write_text(
        "# Title\n\n## First\n\nKeep this useful explanation with several words.\n\n"
        "## Second\n\nRepeated material that the editor removes.\n",
        encoding="utf-8",
    )
    (job / "edited.md").write_text(
        "# Title\n\n## First\n\nKeep this useful explanation.\n",
        encoding="utf-8",
    )

    report = DELTA.editor_report(job)
    text = report.read_text(encoding="utf-8")

    assert "Deterministic coverage signal only" in text
    assert "| First |" in text
    assert "| Second |" in text
    assert "Removed H2: Second" in text
    assert "Word reduction is not an acceptance gate" in text


def test_shared_lock_is_atomic_and_owner_checked(tmp_path):
    path = LOCK.acquire(tmp_path, "companies", "job-a")
    assert path.exists()
    try:
        LOCK.acquire(tmp_path, "companies", "job-b")
    except RuntimeError as exc:
        assert "job-a" in str(exc)
    else:
        raise AssertionError("second owner acquired an existing lock")
    try:
        LOCK.release(tmp_path, "companies", "job-b")
    except RuntimeError as exc:
        assert "job-a" in str(exc)
    else:
        raise AssertionError("wrong owner released the lock")
    LOCK.release(tmp_path, "companies", "job-a")
    assert not path.exists()


def test_compact_orchestrator_review_contains_expected_sections(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "edited.md").write_text(
        "# Example title\n\n## Key takeaways\n\nExample Co keeps contractor records.\n\n"
        "Read [pricing](https://example.com/pricing/).\n\n"
        "Example Co is not a payment provider.\n\n"
        "Example Co is not an employer of record.\n\n"
        "Example Co acts as an Agent of Record.\n\n"
        "Northwind is not a marketplace and offers visa sponsorship.\n",
        encoding="utf-8",
    )
    (job / "brief.md").write_text(
        "## Meta block\n\n"
        "- **metaTitle:** `Example title`\n"
        "- **metaDescription:** `Example description.`\n"
        "- **summary:** `Example summary.`\n"
        "- **slug:** `example-title`\n",
        encoding="utf-8",
    )
    (job / "qa_report.md").write_text(
        "# QA report — Example\n- Gate 1 Publication-ready: PASS — ok\n"
        "## needs_manual_confirmation\n- none\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_orchestrator_review.py"),
         "--job", str(job)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    target = Path(result.stdout.strip())
    packet = target.read_text(encoding="utf-8")
    assert "## Metadata" in packet
    assert "## Example Co excerpts" in packet
    assert "## Risk-language hits" in packet
    # Company policy is read from config/brand-rules.json: a denied label, the industry
    # term as the brand's label and a banned topic are listed; the permitted negation and
    # a competitor's denial are not.
    assert "- Example Co label denial, line 9: Example Co is not a payment provider." in packet
    assert "- Example Co industry-term label, line 13: Example Co acts as an Agent of Record." in packet
    assert "- banned topic, line 15: Northwind is not a marketplace" in packet
    assert packet.count("label denial") == 1
    assert "- internal: [pricing](https://example.com/pricing/)" in packet
    assert "## Links" in packet
    assert "Gate 1 Publication-ready: PASS" in packet
