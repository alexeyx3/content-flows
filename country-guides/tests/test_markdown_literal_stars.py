"""Literal stars in source publishers must survive both delivery formats."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/blog/scripts"))
import gdoc_review
import md_to_gdoc
import md_to_strapi_html
import strapi_publish


def test_source_publisher_star_does_not_cross_link_boundaries():
    source = r"O\*NET OnLine. [Local wages (O*NET — metro)](https://example.com/wages)."
    rendered = md_to_strapi_html.inline(source)
    assert rendered == 'O*NET OnLine. <a href="https://example.com/wages">Local wages (O*NET — metro)</a>.'
    sanitized = subprocess.run(["node", str(strapi_publish.SANITIZER)], input=rendered,
                               text=True, capture_output=True, check=True).stdout
    assert sanitized == rendered


def test_escaped_stars_preserve_real_emphasis_and_private_characters():
    assert md_to_strapi_html.inline(r"\*literal\* and *emphasis* and **bold**") == (
        "*literal* and <em>emphasis</em> and <strong>bold</strong>")
    assert md_to_strapi_html.inline("\ue000 " + r"\*") == "\ue000 *"


def test_review_text_and_link_offsets_preserve_literal_stars():
    source = r"O\*NET: [wages](https://example.com/wages)"
    text, spans = md_to_gdoc.inline(source)
    assert text == "O*NET: wages"
    assert spans == [(7, 12, "link", "https://example.com/wages")]
    assert md_to_gdoc.norm(source) == md_to_gdoc.norm("O*NET: wages")
    assert not gdoc_review.build_diff("4. " + source, "4. O*NET: wages")
