"""Technical leakage is blocked without treating normal Russian as AI evidence."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import translation_text_artifacts as artifacts


@pytest.mark.parametrize('text', [
    'Текст oai_citation:0‡.',
    'Текст :contentReference[oaicite:0]{index=0}.',
    'Текст 【1†source】.',
    'Текст 【12†L1-L4】.',
    'Текст [cite: 12].',
    'Текст [span_2].',
    '[Файл](sandbox:/mnt/data/report.pdf)',
    'Текст </think> дальше.',
    'Текст &lt;/think&gt; дальше.',
])
def test_actual_tool_markup_is_found(text):
    assert artifacts.findings(text)


def test_line_numbers_and_source_conflict_are_diagnostics_only():
    final = {'edited.md': '# Заголовок\n\nТекст [cite: 12].'}
    source = {'edited.md': '# Title\n\nText [cite: 12].'}
    before = dict(final)
    errors = artifacts.errors(final, source)
    assert len(errors) == 1
    assert 'edited.md at line 3' in errors[0]
    assert 'source-policy review required' in errors[0]
    assert final == before


def test_normal_language_urls_and_unicode_joiners_are_not_style_findings():
    text = ('Подрядчик может получить около 50 документов. Обычно это помогает. '
            'Ссылка https://example.com/?utm_source=chatgpt.com. '
            'Цитата [источник](https://example.com). '
            'Песочница sandbox:/mnt/database, локальный путь /mnt/data/report.pdf. '
            'Семья 👩\u200d👩\u200d👧\u200d👦; فارسی می\u200cروم. '
            'Обычные слова citation, sandbox, contentReference, span и think.')
    assert artifacts.findings(text) == []


def test_source_markers_alone_do_not_block_clean_final_text():
    assert artifacts.errors({'edited.md': 'Готовый текст.'},
                            {'edited.md': 'Source oai_citation:0.'}) == []
