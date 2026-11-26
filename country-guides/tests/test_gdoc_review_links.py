"""Review exports show link labels while preserving the source used for approvals."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/blog/scripts"))
import gdoc_review
import md_to_gdoc
from article_materials import SPANISH_WORKER_SOURCE_TITLE, SPANISH_WORKER_SOURCE_URL


def test_guide_review_links_render_as_real_links_without_changing_source():
    source = "See [contractors](/guides/romania/independent-contractors/) and [costs](#costs)."
    resolved = md_to_gdoc.resolve_review_links(source, "https://example.com/guides/romania/")
    text, spans = md_to_gdoc.inline(resolved)
    assert text == "See contractors and costs."
    assert [s[3] for s in spans] == [
        "https://example.com/guides/romania/independent-contractors/",
        "https://example.com/guides/romania/#costs",
    ]
    assert md_to_gdoc.resolve_review_links(source, None) == source
    assert "(/guides/" in source and "(#costs)" in source


@pytest.mark.parametrize("page,suffix", [
    ("country", ""), ("eor", "employer-of-record/"),
    ("contractors", "independent-contractors/"),
])
def test_public_route_comes_from_job_metadata_not_review_filename(tmp_path, page, suffix):
    (tmp_path / "job.yaml").write_text(f"country_slug: portugal\npage: {page}\n")
    assert gdoc_review.guide_base_url(tmp_path) == f"https://example.com/guides/portugal/{suffix}"


def test_legacy_jobs_and_absolute_links_keep_existing_behaviour(tmp_path):
    assert gdoc_review.guide_base_url(tmp_path) is None
    (tmp_path / "job.yaml").write_text("topic: Blog article\nworkflow_version: 2\n")
    assert gdoc_review.guide_base_url(tmp_path) is None
    source = "[source](https://example.com/page#section)"
    assert md_to_gdoc.resolve_review_links(source, "https://example.com/guides/poland/") == source
    with pytest.raises(ValueError):
        md_to_gdoc.resolve_review_links("[section](#section)", "javascript:bad")


@pytest.mark.parametrize("extra_marker", [False, True])
def test_docs_preflight_preserves_verified_spanish_source_but_blocks_real_todo(tmp_path, monkeypatch, extra_marker):
    source = tmp_path / "article.md"
    text = f'# Guide\n\n## Sources\n\n1. SUNAFIL. [{SPANISH_WORKER_SOURCE_TITLE}]({SPANISH_WORKER_SOURCE_URL}). Accessed 16 November 2026.'
    source.write_text(text + (' TODO: complete.' if extra_marker else ''))
    monkeypatch.setattr(sys, 'argv', ['md_to_gdoc.py', str(source), '--title', 'Guide'])

    class AuthReached(Exception):
        pass

    def stop_before_auth(*args, **kwargs):
        raise AuthReached

    monkeypatch.setattr(md_to_gdoc.Credentials, 'from_service_account_file', stop_before_auth)
    if extra_marker:
        with pytest.raises(SystemExit, match='service placeholder'):
            md_to_gdoc.main()
    else:
        with pytest.raises(AuthReached):
            md_to_gdoc.main()
