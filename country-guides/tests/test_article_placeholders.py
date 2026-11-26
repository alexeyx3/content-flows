"""Export gates distinguish production markers from ordinary reference prose."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/blog/scripts"))
from article_materials import (PLACEHOLDERS, SPANISH_WORKER_SOURCE_TITLE,
                               SPANISH_WORKER_SOURCE_URL, placeholder_matches)


@pytest.mark.parametrize("text", [
    "Ask for an itemised EOR quote: salary, holiday allowance and contributions.",
    "The visual: salary plus contributions, is described in the caption.",
])
def test_ordinary_quote_and_visual_prose_is_exportable(text):
    assert PLACEHOLDERS.search(text) is None


@pytest.mark.parametrize("text", ["QUOTE: practitioner-1", "VISUAL: cost", "[[quote:lawyer]]"])
def test_unmaterialized_markers_still_block(text):
    assert PLACEHOLDERS.search(text)


def test_verified_spanish_source_todo_is_not_a_draft_marker():
    text = f'## Sources\n\n1. SUNAFIL. [{SPANISH_WORKER_SOURCE_TITLE}]({SPANISH_WORKER_SOURCE_URL}). Accessed 16 November 2026.'
    assert not list(placeholder_matches(text))


def test_spanish_source_exception_does_not_hide_adjacent_placeholders():
    text = f'## Sources\n\n1. SUNAFIL. [{SPANISH_WORKER_SOURCE_TITLE}]({SPANISH_WORKER_SOURCE_URL}). TODO: verify date.\n2. todo'
    assert [m.group() for m in placeholder_matches(text)] == ['TODO', 'todo']


def test_spanish_source_exception_requires_sources_and_exact_identity():
    link = f'[{SPANISH_WORKER_SOURCE_TITLE}]({SPANISH_WORKER_SOURCE_URL})'
    assert list(placeholder_matches(link))
    assert list(placeholder_matches('## Sources\n\n' + link.replace('www.gob.pe', 'example.com')))
