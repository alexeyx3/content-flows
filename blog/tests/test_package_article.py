"""Local article packaging does not depend on an LLM or external services."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def make_job(tmp_path: Path, brief: str, article: str, article_type: str = "guide") -> Path:
    job = tmp_path / "job"
    job.mkdir()
    (job / "brief.md").write_text(brief, encoding="utf-8")
    (job / "edited.md").write_text(article, encoding="utf-8")
    (job / "job.yaml").write_text(f"article_type: {article_type}\n", encoding="utf-8")
    (job / "evidence.md").write_text(
        "# Evidence\n\n| ID | Claim | Source |\n|---|---|---|\n"
        "| SRC-01 | A supported claim | https://example.com/source |\n",
        encoding="utf-8",
    )
    return job


def run_package(job: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "package_article.py"),
         "--job", str(job)],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_builds_complete_package_from_final_metadata_block(tmp_path):
    job = make_job(
        tmp_path,
        (
            "| metaTitle | Old draft title |\n| slug | old-draft |\n\n"
            "- **metaTitle:** `A Useful Comparison for Global Teams` (36 chars)\n"
            "- **metaDescription:** A concise description for the finished article. (47 chars)\n"
            "- **summary:** A summary that may continue\n"
            "  on the next line without being lost. (68 chars)\n"
            "- **slug:** `useful-comparison`\n"
        ),
        "# A Useful Comparison\n\n## Key Takeaways\n\nThe article body.\n",
    )
    result = run_package(job)
    assert result.returncode == 0, result.stderr + result.stdout
    out = job / "out"
    assert {p.name for p in out.iterdir()} == {
        "meta.md", "article.md", "article.html", "internal_package.md"
    }
    meta = (out / "meta.md").read_text(encoding="utf-8")
    assert "title: A Useful Comparison" in meta
    assert "slug: useful-comparison" in meta
    assert "continue on the next line" in meta
    assert "<h1>" not in (out / "article.html").read_text(encoding="utf-8")


def test_rejects_multiple_h1s(tmp_path):
    job = make_job(
        tmp_path,
        (
            "- **metaTitle:** Good title\n"
            "- **metaDescription:** Good description\n"
            "- **summary:** Good summary\n"
            "- **slug:** good-slug\n"
        ),
        "# First\n\n# Second\n",
    )
    result = run_package(job)
    assert result.returncode != 0
    assert "exactly one H1" in result.stderr


def test_rejects_suffix_after_alternatives_in_slug(tmp_path):
    job = make_job(
        tmp_path,
        (
            "- **metaTitle:** Umbrella Alternatives\n"
            "- **metaDescription:** A useful description.\n"
            "- **summary:** A useful summary.\n"
            "- **slug:** umbrella-alternatives-contractor-operations\n"
        ),
        "# Umbrella Alternatives for Contractor Operations\n\nArticle body.\n",
        article_type="listicle",
    )
    result = run_package(job)
    assert result.returncode != 0
    assert "nothing after alternatives" in result.stderr


def test_guide_title_ending_rules_and_alternatives_keeps_descriptive_slug(tmp_path):
    job = make_job(
        tmp_path,
        (
            "- **metaTitle:** Non-Compete Agreements for Contractors\n"
            "- **metaDescription:** A useful description.\n"
            "- **summary:** A useful summary.\n"
            "- **slug:** non-compete-agreements-for-independent-contractors\n"
        ),
        "# Non-Compete Agreements for Contractors: Rules and Alternatives\n\nArticle body.\n",
    )
    result = run_package(job)
    assert result.returncode == 0, result.stderr + result.stdout
    assert "slug: non-compete-agreements-for-independent-contractors" in (
        job / "out/meta.md").read_text(encoding="utf-8")
