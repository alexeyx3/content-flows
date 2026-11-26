"""Malformed table input must fail explicitly instead of looping in conversion."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/blog/scripts"))
from md_to_strapi_html import convert


def test_missing_table_separator_fails_with_line():
    with pytest.raises(ValueError, match="line 3: table requires"):
        convert("# Guide\n\n| | | |\n| A | B | C |\n")


def test_headerless_fact_table_keeps_all_cells_and_has_no_thead():
    _, html = convert("# Guide\n\n| | | |\n|---|---|---|\n| Rate | 14.75% | CSS Law 51 |\n")
    assert "<thead>" not in html
    assert "<td>Rate</td><td>14.75%</td><td>CSS Law 51</td>" in html
