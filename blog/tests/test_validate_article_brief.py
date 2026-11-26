import json
from pathlib import Path

from scripts.validate_article_brief import validate


def make_job(tmp_path: Path, brief: str, instruction: str | None, count: int = 12) -> Path:
    job = tmp_path / "job"
    job.mkdir()
    (job / "brief.md").write_text(brief, encoding="utf-8")
    sections = []
    for index in range(1, count + 1):
        section = {
            "id": f"section-{index}",
            "title": f"Section {index}",
            "subheadings": [{"level": 3, "title": f"Detail {index}"}],
        }
        if instruction is not None:
            section["instruction"] = instruction
        sections.append(section)
    (job / "sections.json").write_text(
        json.dumps({"title": "Article", "sections": sections}), encoding="utf-8"
    )
    return job


def test_writer_contract_accepts_coverage_without_length(tmp_path: Path) -> None:
    job = make_job(
        tmp_path,
        "# Brief\n\n## Outline\n\nExplain the complete decision path.\n",
        "Explain the distinction, give an evidence-backed example, and state the decision implication.",
    )
    assert validate(job) == []


def test_writer_contract_accepts_more_than_eleven_sections_without_microbriefs(tmp_path: Path) -> None:
    job = make_job(
        tmp_path,
        "# Brief\n\n## Complete hybrid outline\n\nKeep every useful intent.\n",
        None,
        count=18,
    )
    assert validate(job) == []


def test_writer_contract_rejects_length_section_and_word_budget(tmp_path: Path) -> None:
    job = make_job(
        tmp_path,
        "# Brief\n\n## 9. Length\n\nTarget 4,000 words.\n",
        "Budget: 500 words. Explain the distinction.",
    )
    problems = validate(job)
    assert any("brief.md" in problem for problem in problems)
    assert sum("exposes a word-count target" in problem for problem in problems) == 12


def test_writer_contract_rejects_final_metadata_template_even_with_earlier_values(tmp_path: Path) -> None:
    job = make_job(
        tmp_path,
        "# Brief\n\n| Slug | working-slug |\n\n## Meta block\n\n"
        "- **metaTitle:** `Publishable title`\n"
        "- **metaDescription:** `{md}`\n"
        "- **summary:** `Publishable summary`\n"
        "- **slug:** `{slug}`\n",
        None,
    )
    problems = validate(job)
    assert any("metaDescription" in problem and "{md}" in problem for problem in problems)
    assert any("slug" in problem and "{slug}" in problem for problem in problems)
