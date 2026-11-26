"""Assembling a draft from the section files of the agent track."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import assemble_sections as asm  # noqa: E402


def make_job(tmp_path, ids, files):
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections.json").write_text(
        json.dumps({"sections": [{"id": i, "title": i, "instruction": "x"} for i in ids]}),
        encoding="utf-8")
    (tmp_path / "brief.md").write_text("# Globex Alternatives in 2026\n\ntext\n", encoding="utf-8")
    for name, text in files.items():
        (tmp_path / "sections" / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_order_comes_from_sections_json_not_filenames(tmp_path):
    """section_10 must not land between section_1 and section_2."""
    ids = [f"s{i}" for i in range(1, 11)]
    files = {f"section_{i}.md": f"## Section {i}\n\ntext {i}" for i in range(1, 11)}
    job = make_job(tmp_path, ids, files)
    body, missing = asm.collect(job)
    assert missing == []
    assert body.index("text 2") < body.index("text 10")


def test_files_can_be_named_by_section_id(tmp_path):
    job = make_job(tmp_path, ["key-takeaways", "faq"],
                   {"section_key-takeaways.md": "## KT\n\na", "faq.md": "## FAQ\n\nb"})
    body, missing = asm.collect(job)
    assert missing == [] and body.index("## KT") < body.index("## FAQ")


def test_files_can_use_zero_padded_section_numbers(tmp_path):
    job = make_job(tmp_path, ["one", "two"],
                   {"section_01.md": "## One\n\na", "section_02.md": "## Two\n\nb"})
    body, missing = asm.collect(job)
    assert missing == []
    assert body.index("## One") < body.index("## Two")


def test_missing_section_is_reported_not_silently_skipped(tmp_path):
    job = make_job(tmp_path, ["one", "two"], {"section_1.md": "## One\n\na"})
    _, missing = asm.collect(job)
    assert missing == ["2. two"]


def test_title_comes_from_sections_json(tmp_path):
    """The first "# " in the brief does not work: agent briefs hold "Strategy brief — X" there,
    and drafts once went to editing with that title."""
    job = make_job(tmp_path, ["one"], {"section_1.md": "## One\n\na"})
    (job / "sections.json").write_text(json.dumps(
        {"title": "Hooli Alternatives in 2026: Two Categories",
         "sections": [{"id": "one", "title": "One", "instruction": "x"}]}), encoding="utf-8")
    (job / "brief.md").write_text("# Strategy brief — Hooli alternatives in 2026\n", encoding="utf-8")
    assert asm.article_title(job) == "Hooli Alternatives in 2026: Two Categories"


def test_title_falls_back_to_brief_skipping_the_brief_heading(tmp_path):
    job = make_job(tmp_path, ["one"], {"section_1.md": "## One\n\na"})
    (job / "sections.json").write_text(json.dumps(
        [{"id": "one", "title": "One", "instruction": "x"}]), encoding="utf-8")
    (job / "brief.md").write_text(
        "# Strategy brief — Initech alternatives\n\n# Initech Alternatives in 2026\n", encoding="utf-8")
    assert asm.article_title(job) == "Initech Alternatives in 2026"
