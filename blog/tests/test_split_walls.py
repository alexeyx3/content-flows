"""Mechanical splitting of walls of text: no word is changed, only paragraph boundaries."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import split_walls as sw  # noqa: E402
import lint_article as lint  # noqa: E402

LONG = ("Finance wants one counterparty and one closing packet per person. "
        "The bench is contractors, and the shortlist drifts toward employment tooling. "
        "Documents live in three systems, and month-end takes a manual chase. "
        "Rights to the work are assumed rather than assigned in writing.")


def test_wall_is_split_and_no_word_is_lost():
    out, changed = sw.process(LONG + "\n")
    assert changed == 1
    assert out.split() == LONG.split()          # same words, only line breaks changed
    assert lint.walls(out) == []


def test_short_paragraph_untouched():
    text = "Two short sentences. Nothing to split here.\n"
    out, changed = sw.process(text)
    assert changed == 0 and out == text


def test_tables_lists_and_headings_are_never_split():
    long_bullet = "- " + " ".join(["word"] * 60)
    long_row = "| " + " | ".join(["cell text here"] * 12) + " |"
    long_head = "## " + " ".join(["word"] * 60)
    text = "\n".join([long_bullet, long_row, long_head]) + "\n"
    out, changed = sw.process(text)
    assert changed == 0 and out == text


def test_bold_lead_in_paragraph_is_split():
    """A paragraph with a bold opening is a paragraph: the counter once had a bug on exactly those."""
    text = "**Best for.** " + LONG + "\n"
    out, changed = sw.process(text)
    assert changed == 1 and lint.walls(out) == []


def test_paragraph_without_sentence_breaks_stays_whole():
    """Never break in the middle of a sentence: better to leave it long and hand it to a person."""
    text = " ".join(["word"] * 60) + "\n"
    out, changed = sw.process(text)
    assert changed == 0 and out == text
