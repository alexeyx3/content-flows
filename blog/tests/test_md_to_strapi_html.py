"""The converter output must survive the Strapi sanitizer unchanged.

A difference of even one byte means that part of the markup silently disappears on the site.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import md_to_strapi_html as conv  # noqa: E402


def sanitize(html: str) -> str:
    r = subprocess.run(
        ["node", str(ROOT / "tools" / "sanitize" / "check.js")],
        input=html, capture_output=True, text=True, check=True,
    )
    return r.stdout


def survives(md: str) -> str:
    _, html = conv.convert(md)
    after = sanitize(html)
    assert after == html, f"the sanitizer changed the output:\nwas:\n{html}\nbecame:\n{after}"
    return html


def test_h1_goes_to_title_not_body():
    h1, html = conv.convert("# Заголовок статьи\n\nТекст.\n")
    assert h1 == "Заголовок статьи"
    assert "<h1" not in html


def test_headings_h2_h3_h4():
    html = survives("## Второй\n\n### Третий\n\n#### Четвёртый\n")
    assert "<h2>Второй</h2>" in html
    assert "<h3>Третий</h3>" in html
    assert "<h4>Четвёртый</h4>" in html


def test_h5_downgraded_to_h4():
    html = survives("##### Пятый\n")
    assert "<h4>Пятый</h4>" in html


def test_lists_and_blank_lines_between_items():
    html = survives("1. Раз\n\n2. Два\n\n3. Три\n")
    assert html.count("<ol>") == 1
    assert html.count("<li>") == 3


def test_bullet_list():
    html = survives("- Первый\n- Второй\n")
    assert html.count("<ul>") == 1 and html.count("<li>") == 2


def test_link_becomes_anchor():
    html = survives("Смотри [условия](https://example.com/countries/) на сайте.\n")
    assert '<a href="https://example.com/countries/">условия</a>' in html


def test_table_renders():
    md = "| Критерий | Example Co |\n|---|---|\n| Документы | да |\n"
    html = survives(md)
    assert "<table>" in html
    assert "<th>Критерий</th>" in html
    assert "<td>да</td>" in html


def test_ampersand_and_angle_brackets_escaped():
    html = survives("Срок < 30 дней & растёт\n")
    assert "&amp;" in html and "&lt;" in html


def test_bold_italic_code():
    html = survives("**жирный**, *курсив*, `код`\n")
    assert "<strong>жирный</strong>" in html
    assert "<em>курсив</em>" in html
    assert "<code>код</code>" in html


def test_image_wrapped_in_figure():
    html = survives("![Схема согласования счетов](https://cdn.example.com/a.png)\n")
    assert '<figure class="image">' in html
    assert 'alt="Схема согласования счетов"' in html


def test_blockquote_and_hr():
    html = survives("> Цитата\n\n---\n")
    assert "<blockquote>" in html
    assert "<hr />" in html


def test_code_fence():
    html = survives("```\ncurl -s https://example.com\n```\n")
    assert "<pre><code>" in html


def test_paragraph_lines_joined():
    html = survives("Первая строка\nвторая строка абзаца.\n")
    assert html.count("<p>") == 1


def test_headerless_table_has_no_empty_head():
    """A parameter table is written without headers: "| | |". An empty thead would give the site
    an empty strip above every such table; vendor cards have seven of them."""
    md = "| | |\n|---|---|\n| **Category** | Global contractor software |\n| **Best fit** | Contractor-only teams |\n"
    html = survives(md)
    assert "<thead>" not in html
    assert "<th></th>" not in html
    assert html.count("<tr>") == 2
    assert "<td><strong>Category</strong></td>" in html


def test_table_with_headers_keeps_thead():
    md = "| Vendor | Category |\n|---|---|\n| Fabrikam | EOR |\n"
    html = survives(md)
    assert "<thead>" in html and "<th>Vendor</th>" in html


def test_numbered_list_keeps_indented_continuation_in_one_ol():
    """QA found: every item went into its own <ol>, and the numbering on the site restarted."""
    md = "1. First.\n\n   Body one.\n\n2. Second.\n\n   Body two.\n"
    _, html = conv.convert(md)
    assert html.count("<ol>") == 1
    assert html.count("<li>") == 2
    assert "Body one." in html and "Body two." in html


def test_numbered_relationship_map_keeps_nested_bullets_inside_parent_items():
    """A nested vendor map must remain one ordered list, otherwise every vendor is 1."""
    md = (
        "1. **Soylent**\n"
        "   - **Provider role:** employer.\n"
        "   - **Client role:** directs work.\n"
        "2. **Fabrikam**\n"
        "   - **Provider role:** employer or COR.\n"
        "3. **Example Co**\n"
        "   - **Provider role:** contractual counterparty.\n"
    )
    html = survives(md)
    assert html.count("<ol>") == 1
    assert html.count("</ol>") == 1
    assert html.count("<ul>") == 3
    assert "<li><strong>Soylent</strong><ul>" in html
    assert "</ul></li><li><strong>Fabrikam</strong><ul>" in html
    assert "</ul></li><li><strong>Example Co</strong><ul>" in html


def test_paragraph_after_a_list_stays_a_paragraph():
    md = "1. First.\n\n2. Second.\n\nA normal paragraph.\n"
    _, html = conv.convert(md)
    assert html.count("<ol>") == 1
    assert "<p>A normal paragraph.</p>" in html
