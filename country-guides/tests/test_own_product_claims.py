"""Claims from config/brand-rules.json are caught only in a prose sentence that names the brand."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_guide
import lint_article


def reasons(text):
    return [reason for _, reason in check_guide.ownproduct_claims(text)]


def test_category_formula_and_both_sides_description_are_allowed():
    text = ("Companies can sign agreements with and approve invoices from independent contractors "
            "in Portugal in Example Co, and contractors based in Portugal can work with clients "
            "abroad. Invoices go through approval and are exported to accounting software.")
    assert reasons(text) == []


def test_forbidden_claims_next_to_the_brand_are_caught():
    cases = {
        "Example Co approves invoices instantly.": "speed",
        "Example Co is a marketplace for contractors.": "label",
        "Example Co is a freelancer management system.": "retired-label",
        "With Example Co the engagement is risk-free.": "guarantee",
        "Example Co is the leading tool for contractor paperwork.": "superlative",
        "Example Co is a cheap way to keep agreements.": "price",
        "Example Co is trusted by 5,000 companies.": "customers",
    }
    by_kind = {rule["kind"]: rule["message"] for rule in check_guide.BRAND_RULES["self_forbidden"]["rules"]}
    assert sorted(by_kind) == sorted(set(cases.values()))
    for text, kind in cases.items():
        assert by_kind[kind] in reasons(text), text


def test_market_sentences_negations_and_table_rows_are_not_flagged():
    assert reasons("Northwind advertises instant onboarding and calls itself a marketplace.") == []
    assert reasons("Example Co is not a marketplace or a law firm.") == []
    assert reasons("| Example Co | Northwind | instant approval |") == []


def test_brand_misspelling_is_checked_in_visible_text_only():
    assert check_guide.BRAND_MISSPELT.search("ExampleCo helps.")
    assert check_guide.BRAND_MISSPELT.search("Sign up at Example.com today.")
    assert not check_guide.BRAND_MISSPELT.search("Example Co helps. Example. Homepage")


def test_empty_stop_list_and_topic_ban_block_nothing(monkeypatch):
    text = "Northwind and Contoso offer visa sponsorship."
    assert list(check_guide.forbidden_matches(text)) == []
    monkeypatch.setattr(check_guide, "STOP_BRANDS", lint_article.compile_stop_brands(["Contoso"]))
    monkeypatch.setattr(check_guide, "FORBIDDEN", [check_guide.re.compile(r"\bvisa sponsorship\b", check_guide.re.I)])
    assert [m.group() for m in check_guide.forbidden_matches(text)] == ["Contoso", "visa sponsorship"]
