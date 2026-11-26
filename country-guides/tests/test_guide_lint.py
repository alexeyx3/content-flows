"""Country ranking exceptions must not weaken other publication checks."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor/blog/scripts"))
import pytest

import lint_article


TEXT = """# Hiring contractors in Portugal

Globex appears outside the ranking.

## Who works with contractors in Portugal

| Provider | Scope |
|---|---|
| Globex | Contractor services |

### Globex

Globex describes contractor services.

## Frequently asked questions

Globex appears after the ranking.

## Sources

1. Globex. Contractor guide (globex.example/guide). Accessed 12 October 2026.
"""
SUBJECT_ONLY = "is named only on a page about this brand"
STOP_LISTED = "a stop-listed brand"


@pytest.fixture
def subject_only(monkeypatch):
    # Fictional policy: these vendors are named only on a page about them.
    monkeypatch.setattr(lint_article, "SUBJECT_ONLY_BRANDS", ("Globex", "Umbrella Group"))


def brand_errors(text, guide=False):
    return [e for e in lint_article.check(text, "", None, guide_contractors=guide)
            if SUBJECT_ONLY in e]


def test_empty_brand_lists_block_nothing():
    assert lint_article.SUBJECT_ONLY_BRANDS == ()
    assert lint_article.STOP_BRANDS is lint_article.NEVER
    errors = lint_article.check(TEXT, "", None)
    assert not any(SUBJECT_ONLY in e or STOP_LISTED in e for e in errors)


def test_country_context_only_allows_ranked_card_and_its_sources(subject_only):
    assert len(brand_errors(TEXT)) == 6
    errors = brand_errors(TEXT, guide=True)
    assert len(errors) == 2
    assert "line 3:" in errors[0]
    assert "line 17:" in errors[1]


def test_exception_requires_a_named_card_and_is_brand_specific(subject_only):
    assert len(brand_errors(TEXT.replace("### Globex", "### Unrelated"), guide=True)) == 5
    errors = brand_errors(TEXT.replace("Globex describes", "Umbrella Group and Globex describe"), guide=True)
    assert any("Umbrella Group" in e for e in errors)


def test_other_prohibitions_still_apply_inside_guide_ranking(subject_only, monkeypatch):
    errors = lint_article.check(TEXT.replace("contractor services.", "AoR services."),
                                "", None, guide_contractors=True)
    assert any("abbreviations" in e for e in errors)
    # A configured topic ban (fictional here) applies inside the ranking too.
    monkeypatch.setattr(lint_article, "RULES", [
        (re.compile(r"\bvisa sponsorship\b", re.I), "visa sponsorship is outside the site's scope"),
        *lint_article.RULES])
    errors = lint_article.check(TEXT.replace("contractor services.", "visa sponsorship services."),
                                "", None, guide_contractors=True)
    assert any("outside the site's scope" in e for e in errors)


def test_stop_list_overrides_ranking_and_subject_exceptions(subject_only, monkeypatch):
    monkeypatch.setattr(lint_article, "STOP_BRANDS", lint_article.compile_stop_brands(["Globex", "Глобекс*"]))
    for guide in (False, True):
        errors = lint_article.check(TEXT, "Globex", None, guide_contractors=guide)
        assert sum(STOP_LISTED in e for e in errors) == 7
    for brand in ["Глобекса", "Globex"]:
        assert any(STOP_LISTED in e for e in lint_article.check(
            "# Guide\n\n" + brand, brand, None, guide_page=True))
    for brand in ["Northwind", "Contoso", "Fabrikam", "Initech", "Hooli", "Umbrella Group",
                  "Soylent", "Vandelay", "Cyberdyne", "Globexia"]:
        assert not any(STOP_LISTED in e for e in lint_article.check(
            "# Guide\n\n" + brand, "", None, guide_page=True))


def test_guide_eor_distinction_does_not_allow_other_self_negations():
    text = "# Guide\n\nExample Co is not an Employer of Record."
    assert any("what we are not" in e for e in lint_article.check(text, "", None))
    assert not any("what we are not" in e for e in lint_article.check(text, "", None, guide_page=True))
    for extra in ["Example Co is not a marketplace.", "It is not a law firm."]:
        assert any("what we are not" in e for e in lint_article.check(text + " " + extra, "", None, guide_page=True))


def test_draft_link_inventory_is_exact_and_does_not_mutate_live_inventory():
    live = {"https://example.com/": {"lang": "en"}}
    urls = lint_article.guide_site_urls(live, "finland", ["https://example.com/countries/"])
    assert live == {"https://example.com/": {"lang": "en"}}
    assert urls["https://example.com/guides/finland/"]["draft"] is True
    for path in ["finland/", "finland/employer-of-record/", "finland/independent-contractors/"]:
        assert not any("address is not in" in e for e in lint_article.check(
            "# Guide\n\n[Guide](https://example.com/guides/" + path + ")", "", urls, guide_page=True))
    assert any("address is not in" in e for e in lint_article.check(
        "# Guide\n\n[Other](https://example.com/guides/denmark/)", "", urls, guide_page=True))


def test_guide_wage_observation_quarter_is_not_a_product_roadmap():
    text = "# Hiring\n\n![Q2 2026 gross wages](https://media.example.com/chart.png)\n\nCaption: NSI preliminary Q2 2026 salary means.\n"
    legacy = lint_article.check(text, "", None)
    assert sum("product timelines" in e for e in legacy) == 2
    assert not any("product timelines" in e for e in lint_article.check(text, "", None, guide_page=True))
    stats = ("# Hiring\n\nMalta had an estimated 339,935 people in employment in Q2 2026.\n"
             "| All employees | €2,282 / month | NSO Labour Force Survey Q2 2026 |\n"
             "1. National Statistics Office Malta. [Labour Force Survey: Q2/2026 "
             "(NSO Labour Force Survey Q2 2026)](https://nso.gov.mt/labour-force-survey-q2-2026/).\n")
    assert not any("product timelines" in e for e in lint_article.check(stats, "", None, guide_page=True))
    for promise in ["Example Co salary feature launches in Q2 2027.",
                    "The product's salary module is planned for Q2 2027."]:
        assert any("product timelines" in e for e in lint_article.check("# Hiring\n\n" + promise, "", None, guide_page=True))
    assert any("abbreviations" in e for e in lint_article.check(text + "AoR\n", "", None, guide_page=True))


def test_guide_image_title_is_not_quoted_seo_prose():
    title = '"Contractor or employee: factors to review"'
    image = '# Guide\n\n![Classification](https://example.com/chart.png ' + title + ')'
    seo = lambda text: [e for e in lint_article.check(text, "", None, guide_page=True)
                        if "search query" in e]
    assert not seo(image)
    assert seo('# Guide\n\nCompare ' + title + ' before hiring.')
    assert any("abbreviations" in e for e in lint_article.check(
        image.replace('Classification', 'AoR'), "", None, guide_page=True))


def test_configured_brand_wording_rules_apply_to_guide_pages():
    rules = lint_article.BRAND_RULES
    check = lambda line: lint_article.check("# Guide\n\n" + line, "", None, guide_page=True)
    label = rules["industry_term_not_a_label"]["message"]
    assert any(label in e for e in check("Example Co is an Agent of Record for contractors."))
    assert not any(label in e for e in check("Example Co explains how an agent of record arrangement works."))
    assert not any(label in e for e in check("| Northwind (Agent of Record) | One agreement with Example Co |"))
    withdrawn = rules["negation_paraphrases"]["message"]
    assert any(withdrawn in e for e in check("Example Co does not become the employer."))
    assert not any(withdrawn in e for e in check("Example Co is not an employer of record."))
