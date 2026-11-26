"""Compact figure citations retain exact originals after Sources are renumbered."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor/blog/scripts"))
sys.path.insert(0, str(ROOT / "scripts"))
import article_materials
import order_sources
import package_article


def test_citations_resolve_original_urls_and_follow_renumbering():
    text = "## Sources\n1. A. [Act](https://official.example/act).\n2. B. [Rate](https://official.example/rate).\n"
    sources = [{"url": "https://official.example/rate"}, {"url": "https://official.example/act"}]
    assert package_article.guide_source_numbers(text, sources) == [1, 2]
    assert package_article.guide_source_numbers(text, sources[:1]) == [2]
    swapped = text.replace("1. A.", "2. A.").replace("2. B.", "1. B.")
    assert package_article.guide_source_numbers(swapped, sources[:1]) == [1]
    with pytest.raises(ValueError, match="missing"):
        package_article.guide_source_numbers(text, [{"url": "https://official.example/missing"}])


def test_compact_sources_change_presentation_only_and_legacy_keeps_links():
    visual = {"id": "cost", "title": "Cost", "alt": "Salary and contributions", "caption": "Assumptions.",
              "sources": [{"label": "Official rates", "url": "https://official.example/rate"}],
              "asset": {"url": "https://media.example/cost.png"}}
    before = article_materials.spec_digest(visual)
    assert "[Official rates](https://official.example/rate)" in article_materials.visual_markdown(visual)
    visual["asset"]["source_numbers"] = [3, 7]
    compact = article_materials.visual_markdown(visual)
    assert "Caption: Assumptions. Sources: [3, 7](#sources)." in compact
    assert before == article_materials.spec_digest(visual)
    visual["inserted_markdown"] = compact
    text = compact + "\n\n## Sources\n1. Authority. [Rate](https://official.example/rate).\n"
    assert order_sources.marker_positions(text, {"visuals": [visual]}) == {"https://official.example/rate": 0}
    text = compact + "\n\nSee [Registry](https://official.example/register).\n\n## Sources\n" + (
        "1. Authority. [Registry](https://official.example/register).\n"
        "2. Authority. [Rate](https://official.example/rate).\n")
    assert "[Rate]" in order_sources.ordered(text, {"visuals": [visual]})[0]


def test_visible_table_abbreviations_and_statutory_short_names_control_order():
    items = [
        "1. Kestrel Hungary. [Salary Guide](https://kestrel.example/guide).",
        "2. Hungarian Central Statistical Office (KSH). [Earnings](https://stats.example/earnings).",
        "3. NJT. [Government Decree 324/2018](https://law.example/old).",
        "4. NJT. [Government Decree 426/2025 on the minimum wage](https://law.example/current).",
        "5. NJT. [Act CXXII of 2019 on Social Insurance](https://law.example/social).",
    ]
    text = "| Mean | 100 | KSH |\n| Role | 200 | Kestrel Hungary |\n| Floor | 300 | Decree 426/2025 |\n| Earlier | 50 | Decree 324/2018 |\n| Rate | 10% | Social Insurance Act |\n\n## Sources\n" + "\n".join(items)
    ordered = order_sources.ordered(text)
    assert [order_sources.LINK.search(x)[1] for x in ordered] == [
        "https://stats.example/earnings", "https://kestrel.example/guide", "https://law.example/current",
        "https://law.example/old", "https://law.example/social"]
    duplicate = "6. Ministry. [Social Insurance Act](https://ministry.example/social)."
    assert not order_sources.cell_matches("Social Insurance Act", items[4], items + [duplicate])
    assert not order_sources.cell_matches("Insurance", items[4], items)


def test_combined_source_labels_keep_ambiguous_publishers_and_decree_numbers():
    items = [
        "1. Legislature. [VAT Act](https://law.example/vat).",
        "2. Government. [Decree 243/2025 on minimum wage](https://law.example/wage).",
        "3. National Social Security Institute (NSSI). [Bases](https://nssi.example/base).",
        "4. National Social Security Institute (NSSI). [Code](https://nssi.example/code).",
    ]
    body = "| Floor | 620 | NSSI / Decree 243 |\n| VAT | 10 | VAT Act |\n"
    text = body + "\n## Sources\n" + "\n".join(items)
    assert order_sources.ordered(text) == [items[1], items[0], items[2], items[3]]
    assert not order_sources.cell_matches("NSSI", items[2], items)
    assert "Decree 243/2025" in order_sources.table_names("| Floor | 620 | Decree 243/2025 |\n")


def test_publisher_prefixed_descriptions_require_title_words_and_unique_original():
    items = [
        "1. National Social Security Institute (NSSI). [Temporary-incapacity guidance — eligibility](https://nssi.example/sick).",
        "2. National Social Security Institute (NSSI). [Contribution guidance](https://nssi.example/rate).",
        "3. Council of Ministers / Agency for Social Assistance. [Decree 243 of 2025](https://law.example/wage).",
        "4. European Commission / EURES. [Living and working conditions — taxation](https://eures.example/tax).",
    ]
    assert order_sources.cell_matches("NSSI temporary-incapacity guidance", items[0], items)
    assert order_sources.cell_matches("Council of Ministers — Decree 243", items[2], items)
    assert order_sources.cell_matches("EURES — taxation", items[3], items)
    assert not order_sources.cell_matches("NSSI guidance", items[0], items)
    assert not order_sources.cell_matches("NSSI invented tax rule", items[0], items)


def test_exact_document_title_disambiguates_policy_year_from_publication_year():
    items = [
        "1. Council of Ministers. [Minimum-wage decree for 2025](https://law.example/wage-2025).",
        "2. Council of Ministers. [Decree 243 of 2025: minimum wage for 2026](https://law.example/wage-2026).",
    ]
    assert order_sources.cell_matches("Minimum-wage decree for 2025", items[0], items)
    assert not order_sources.cell_matches("Council of Ministers — 2025 wage decree", items[0], items)
    duplicate = "3. Ministry. [Minimum-wage decree for 2025](https://ministry.example/wage)."
    assert not order_sources.cell_matches("Minimum-wage decree for 2025", items[0], items + [duplicate])


def test_first_party_relative_links_count_as_the_exact_original():
    items = [
        "1. Authority. [Act](https://law.example/act).",
        "2. Example Co. [Employer of record](https://example.com/glossary/employer-of-record/).",
        "3. Other. [Glossary](https://other.example/glossary/employer-of-record/).",
    ]
    body = "[Definition](/glossary/employer-of-record/) then [Act](https://law.example/act)."
    assert order_sources.ordered(body + "\n## Sources\n" + "\n".join(items)) == [items[1], items[0], items[2]]
    different = "[Other route](/glossary/employer-of-record/extra/) then [Act](https://law.example/act)."
    assert order_sources.ordered(different + "\n## Sources\n" + "\n".join(items)) == items


def test_explicit_alias_outranks_words_introduced_by_another_alias():
    items = [
        "1. Tax authority (NAV). [Basic sole-trader flat-rate rules (NAV flat-rate guide)](https://nav.example/flat).",
        "2. Tax authority (NAV). [Sole traders’ contributions (NAV sole-trader guide)](https://nav.example/sole).",
    ]
    assert order_sources._match("NAV sole-trader guide", items[0])
    assert not order_sources.cell_matches("NAV sole-trader guide", items[0], items)
    assert order_sources.cell_matches("NAV sole-trader guide", items[1], items)
    duplicate = "3. Ministry. [Tax rules (NAV sole-trader guide)](https://ministry.example/sole)."
    assert not order_sources.cell_matches("NAV sole-trader guide", items[1], items + [duplicate])


def test_parenthetical_table_citations_count_without_guessing_ambiguous_labels():
    items = [
        "1. Ministry. [Agency register (Register)](https://ministry.example/register).",
        "2. Legislature. [Agency supply law (Agency law)](https://law.example/agency).",
        "3. Ministry. [Contribution rates](https://ministry.example/rates).",
    ]
    body = "| Route | The agency employs the worker. (Agency law; Register) |\n"
    assert order_sources.ordered(body + "\n## Sources\n" + "\n".join(items)) == [items[1], items[0], items[2]]
    ambiguous = "| Route | A Ministry arrangement (Ministry) |\n"
    assert order_sources.ordered(ambiguous + "\n## Sources\n" + "\n".join(items)) == items
