"""Parsing edits from a Google Doc: comments and a diff against the sent version."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gdoc_review as g  # noqa: E402

COMMENTS = [
    {
        "id": "c1",
        "content": "тут слишком длинно",
        "quotedFileContent": {"value": "Контрактор получает документы"},
        "author": {"displayName": "Aleksei"},
        "resolved": False,
        "replies": [],
    },
    {
        "id": "c2",
        "content": "ок",
        "quotedFileContent": {"value": "FAQ"},
        "author": {"displayName": "Aleksei"},
        "resolved": True,
        "replies": [{"content": "поправил", "author": {"displayName": "bot"}}],
    },
]


def test_unresolved_comments_come_first():
    """Work starts with open comments, so they come first, even if a resolved one came earlier in the
    source list."""
    out = g.format_comments(list(reversed(COMMENTS)))
    assert out.index("[open]") < out.index("[resolved]")


def test_comment_carries_quote_and_author():
    out = g.format_comments(COMMENTS)
    assert "Контрактор получает документы" in out
    assert "Aleksei" in out


def test_resolved_marked():
    out = g.format_comments(COMMENTS)
    assert "resolved" in out


def test_replies_included():
    out = g.format_comments(COMMENTS)
    assert "поправил" in out


def test_no_comments_says_so():
    assert "no comments" in g.format_comments([]).lower()


def test_diff_shows_changed_line():
    sent = "Первый абзац.\nВторой абзац.\n"
    current = "Первый абзац.\nВторой абзац переписан.\n"
    d = g.build_diff(sent, current)
    assert "-Второй абзац." in d
    assert "+Второй абзац переписан." in d
    assert "-Первый абзац." not in d


def test_diff_empty_when_identical():
    assert g.build_diff("Текст.\n", "Текст.\n").strip() == ""


# --- normalization: the doc returns plain text without markdown markup ---

def test_normalize_strips_heading_marks():
    assert g.normalize_for_diff("# Заголовок\n\nТекст.\n") == ["Заголовок", "Текст."]


def test_normalize_strips_list_markers():
    assert g.normalize_for_diff("- Раз\n- Два\n\n1. Три\n") == ["Раз", "Два", "Три"]


def test_literal_numbered_clauses_roundtrip_without_stripping_native_numbers():
    sent = "# Agreement\n\n" + "\n\n".join(
        f"**{number}. Clause {number}**\n\nText referring to Section {number}."
        for number in range(1, 32)
    )
    current = sent.replace("# ", "").replace("**", "")
    assert g.build_diff(sent, current) == ""
    assert g.normalize_for_diff("31. Clause 31", preserve_ordered_numbers=True) == ["31. Clause 31"]


@pytest.mark.parametrize("actual", [
    "Relationship and services",  # Lost label.
    "2. Relationship and services",  # Changed/restarted label.
    "1. Relationship and services\n1. Relationship and services",  # Duplicate clause.
])
def test_missing_changed_or_duplicated_literal_clause_numbers_remain_real_differences(actual):
    delta = g.build_diff("**1. Relationship and services**\n", actual + "\n")
    assert delta
    assert "-1. Relationship and services" in delta or "+1. Relationship and services" in delta
    if actual.startswith("2."):
        assert "+2. Relationship and services" in delta


def test_literal_clauses_and_real_ordered_lists_keep_distinct_comparison_behavior():
    sent = ("**1. Relationship**\n\nBody refers to Section 2.\n\n**2. Term**\n\n"
            "## Checklist\n\n1. Check scope\n2. Sign\n")
    current = "1. Relationship\nBody refers to Section 2.\n2. Term\nChecklist\nCheck scope\nSign\n"
    assert g.build_diff(sent, current) == ""
    assert g.build_diff(sent, current.replace("2. Term", "1. Term"))


def test_source_bullet_keeps_literal_number_in_link_title():
    sent = "## Sources\n\n- [7. I need to discipline or fire an employee](https://www.eeoc.gov/employers)\n"
    current = "Sources\n7. I need to discipline or fire an employee\n"
    assert g.build_diff(sent, current) == ""
    assert g.build_diff(sent, current.replace("7. ", ""))
    assert g.build_diff(sent, current.replace("7. ", "8. "))


def test_normalize_strips_emphasis_and_links():
    md = "Смотри **условия** и [список стран](https://example.com/countries/).\n"
    assert g.normalize_for_diff(md) == ["Смотри условия и список стран."]


def test_normalize_table_rows_match_doc_shape():
    md = "| Критерий | Example Co |\n|---|---|\n| Документы | да |\n"
    assert g.normalize_for_diff(md) == ["Критерий | Example Co", "Документы | да"]


def test_diff_ignores_markdown_only_differences():
    """Markup does not reach the doc, so it must not look like an edit."""
    sent = "# Заголовок\n\n- **Пункт** списка\n"
    current = "Заголовок\nПункт списка\n"
    assert g.build_diff(sent, current).strip() == ""


def test_diff_catches_real_edit_inside_markdown():
    sent = "## Раздел\n\nВторой абзац: этот текст поправят.\n"
    current = "Раздел\nВторой абзац: этот текст уже поправили.\n"
    d = g.build_diff(sent, current)
    assert "-Второй абзац: этот текст поправят." in d
    assert "+Второй абзац: этот текст уже поправили." in d
    # "Раздел" arrives as a context line (with a leading space), but not as an edit
    changed = [ln for ln in d.splitlines()
               if ln[:1] in "+-" and not ln.startswith(("---", "+++"))]
    assert not any("Раздел" in ln for ln in changed)
    assert len(changed) == 2


def test_doc_id_from_url_or_bare_id():
    assert g.doc_id("https://docs.google.com/document/d/ABC123xyz/edit") == "ABC123xyz"
    assert g.doc_id("ABC123xyz") == "ABC123xyz"


def test_headerless_table_row_is_not_a_diff_artifact():
    """A parameter table is written as "| | |". That row carries no text and is absent from
    the document: if it stays in the normalization, the diff shows a false deletion of the "|" row.
    Caught in round 2 of an article: the reviewer saw seven deletions they had not made."""
    md = "| | |\n|---|---|\n| **Category** | Global contractor software |\n"
    assert g.normalize_for_diff(md) == ["Category | Global contractor software"]


def test_diff_clean_when_only_headerless_tables_differ_in_markup():
    sent = "| | |\n|---|---|\n| **Category** | Platform |\n"
    current = "Category | Platform\n"
    assert g.build_diff(sent, current).strip() == ""


def test_native_table_readback_preserves_empty_first_header_cell_and_real_edits():
    from unittest.mock import Mock

    def cell(start, value):
        return {"content": [{"paragraph": {"elements": [{"startIndex": start,
                 "endIndex": start + len(value) + 1, "textRun": {"content": value + "\n"}}]}}]}

    def native_doc(price):
        return {"body": {"content": [{"startIndex": 1, "table": {"tableRows": [
            {"tableCells": [cell(5, ""), cell(10, "Fabrikam"), cell(20, "Example Co")]},
            {"tableCells": [cell(35, "Price"), cell(45, price), cell(55, "Per active contractor")]}]}}]}}

    sent = "| | Fabrikam | Example Co |\n|---|---|---|\n| Price | $37 | Per active contractor |\n"
    docs = Mock()
    docs.documents.return_value.get.return_value.execute.return_value = native_doc("$37")
    readback = g.doc_text(docs, "doc")
    assert readback.startswith("|  | Fabrikam | Example Co |\n")
    assert g.build_diff(sent, readback) == ""
    docs.documents.return_value.get.return_value.execute.return_value = native_doc("$44")
    changed = g.build_diff(sent, g.doc_text(docs, "doc"))
    assert "-Price | $37 | Per active contractor" in changed
    assert "+Price | $44 | Per active contractor" in changed


def test_refresh_review_routes_to_refresh_sync_without_legacy_review_mutation(tmp_path):
    url = "https://docs.google.com/document/d/abc/edit"
    refresh = g.review_sync_command(tmp_path, url, is_refresh=True)
    ordinary = g.review_sync_command(tmp_path, url, is_refresh=False)
    assert refresh[-5:] == ["--job", str(tmp_path), "--status", "in review", "--apply"]
    assert refresh[1].endswith("blog_refresh.py")
    assert ordinary[1].endswith("temnik.py")
    assert "--google-doc" in ordinary
