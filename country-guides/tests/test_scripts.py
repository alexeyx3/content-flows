import copy
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import calc  # noqa: E402
import check_facts  # noqa: E402
import check_guide  # noqa: E402
import lint_article  # noqa: E402
import prepare_pages  # noqa: E402


def fact(fid, **kw):
    base = {"id": fid, "topic": "t", "pages": ["country"], "claim": f"claim {fid}",
            "source": {"publisher": "BMAS", "title": "x", "url": f"https://example.gov/{fid}", "tier": "official"},
            "accessed": "2026-10-07", "quote": "q"}
    base.update(kw)
    return base


FACTS = {
    "country": "Germany", "slug": "germany", "iso": "DE", "currency": "EUR", "currency_symbol": "€",
    "header": {
        "minimumWage": {"value": "€13.90 / hour", "facts": ["F-001"]},
        "averageSalary": {"value": "€4,323 / month", "facts": ["F-001"]},
        "incomeTax": {"value": "14–45%", "facts": ["F-001"]},
        "paidLeave": {"value": "20 days", "facts": ["F-001"]},
        "publicHolidays": {"value": "9–13", "facts": ["F-001"]},
        "probation": {"value": "up to 6 months", "facts": ["F-001"]},
        "noticePeriod": {"value": "4 weeks – 7 months", "facts": ["F-001"]},
        "employerContributions": {"value": 19.6, "facts": ["F-002"]},
    },
    "facts": [fact("F-001"), fact("F-002")],
    "contributions": [
        {"name": "Pension", "employer_pct": 9.3, "cap_monthly": 8450, "facts": ["F-002"]},
        {"name": "Health", "employer_pct": 10.3, "facts": ["F-002"]},
        {"name": "Accident", "employer_pct": 1.2, "in_header": False, "facts": ["F-002"]},
    ],
    "cost_scenarios": [{"label": "High", "gross_monthly": 10000, "facts": ["F-001"]}],
}


def test_valid_pack_passes():
    assert check_facts.validate(FACTS) == []


def fixed_levy_pack():
    data = copy.deepcopy(FACTS)
    data["header"]["employerContributions"] = {
        "value": None, "model": "fixed", "display": "Fixed statutory levies", "facts": ["F-002"]}
    data["contributions"] = []
    data["cost_scenarios"] = []
    return data


def test_fixed_levy_review_never_displays_zero_percentage():
    from common import header_display
    data = fixed_levy_pack()
    assert check_facts.validate(data) == []
    assert header_display(data["header"]["employerContributions"]) == "Fixed statutory levies"
    text = COUNTRY_PAGE.replace("19.6%", "Fixed statutory levies")
    assert check_guide.check_page(text, "country", JOB, data)[0] == []
    errors, _ = check_guide.check_page(COUNTRY_PAGE, "country", JOB, data)
    assert any("Fixed statutory levies" in error for error in errors)
    data["header"]["employerContributions"]["value"] = 0
    assert any("placeholder" in e for e in check_facts.validate(data))


def test_fixed_levy_export_stops_before_remote_checks(monkeypatch):
    import strapi_guides
    monkeypatch.setattr(sys, "argv", ["strapi_guides.py", "--job", "/tmp/fixed-guide", "--write"])
    monkeypatch.setattr(strapi_guides, "load_job", lambda _: {})
    monkeypatch.setattr(strapi_guides, "read_json", lambda _: fixed_levy_pack())
    def forbidden_remote(*args, **kwargs):
        pytest.fail("fixed-levy export must stop before remote checks")
    monkeypatch.setattr(strapi_guides, "export_errors", forbidden_remote)
    monkeypatch.setattr(strapi_guides, "api", forbidden_remote)
    with pytest.raises(SystemExit, match="CMS/frontend display support"):
        strapi_guides.main()


def test_fixed_levy_requires_evidence_and_cannot_hide_percentages():
    data = fixed_levy_pack()
    data["header"]["employerContributions"]["facts"] = []
    data["contributions"] = copy.deepcopy(FACTS["contributions"])
    errors = check_facts.validate(data)
    assert any("no supporting facts" in e for e in errors)
    assert any("hide" in e for e in errors)


def test_official_document_codes_are_not_workflow_ids_only_in_exact_original_sources(monkeypatch):
    monkeypatch.setattr(check_guide, "ID_LIKE_CODE_HOSTS", ("opinions.gov.example",))
    original = ("## Sources\n1. Office of the Attorney General. "
                "[Opinion OAG-C-150-2022 (contribution ruling)]"
                "(https://www.opinions.gov.example/docs/opinion.html). Accessed 28 October 2026.\n")
    assert list(check_guide.internal_id_matches(original)) == []
    assert [m[0] for m in check_guide.internal_id_matches("Internal C-150 and F-001.\n" + original)] == ["C-150", "F-001"]
    assert [m[0] for m in check_guide.internal_id_matches(original.replace("opinions.gov.example/", "opinions.gov.example.test/"))] == ["C-150"]
    monkeypatch.setattr(check_guide, "ID_LIKE_CODE_HOSTS", ())
    assert [m[0] for m in check_guide.internal_id_matches(original)] == ["C-150"]
    monkeypatch.setattr(check_guide, "ID_LIKE_CODE_HOSTS", ("opinions.gov.example",))
    assert [m[0] for m in check_guide.internal_id_matches(original.replace("OAG-C-150-2022", "F-150"))] == ["F-150"]
    assert list(check_guide.internal_id_matches("[Official](https://law.example/C-150)")) == []


def test_header_rate_must_match_contributions():
    bad = copy.deepcopy(FACTS)
    bad["header"]["employerContributions"]["value"] = 21.0
    assert any("employerContributions" in e for e in check_facts.validate(bad))


def test_header_commentary_and_unknown_fact_rejected():
    bad = copy.deepcopy(FACTS)
    bad["header"]["paidLeave"] = {"value": "20 days, grows with tenure", "facts": ["F-999"]}
    errors = check_facts.validate(bad)
    assert any("commentary" in e for e in errors) and any("F-999" in e for e in errors)


def test_fact_without_https_or_quote_rejected():
    bad = copy.deepcopy(FACTS)
    bad["facts"][0]["source"]["url"] = "http://x"
    bad["facts"][0]["quote"] = ""
    errors = check_facts.validate(bad)
    assert any("https" in e for e in errors) and any("quote" in e for e in errors)


def test_merge_conflict_detected():
    with pytest.raises(ValueError):
        check_facts.merge([{"currency": "EUR", "facts": []}, {"currency": "USD", "facts": []}])
    merged = check_facts.merge([{"header": {"a": 1}, "facts": [1]}, {"header": {"b": 2}, "facts": [2]}])
    assert merged["header"] == {"a": 1, "b": 2} and merged["facts"] == [1, 2]


def test_calc_applies_caps_and_includes_all_contributions():
    rows = calc.build(FACTS)["rows"]
    r = rows[0]
    # pension capped at 8450: 785.85; health 1030; accident 120
    assert r["employer_contributions"] == 1935.85
    assert r["effective_rate_pct"] == 19.36
    assert r["total_monthly_cost"] == 11935.85
    assert r["id"] == "C-001" and "Caps applied: Pension" in r["methodology"]


def test_opt_in_three_decimal_budget_preserves_millime_salary_and_components():
    data = copy.deepcopy(FACTS)
    data.update(currency="TND", currency_symbol="TND")
    data["cost_scenarios"] = [{"label": "Statutory floor", "gross_monthly": 554.736,
                               "facts": ["F-001"]}]
    data["contributions"] = [
        {"name": "CNSS", "employer_pct": 17.07, "facts": ["F-002"]},
        {"name": "Housing", "employer_pct": 1, "facts": ["F-002"]},
        {"name": "Training", "employer_pct": 2, "facts": ["F-002"]}]
    row = calc.build(data, {"calculation_decimals": 3})["rows"][0]
    assert row["gross_monthly"] == 554.736
    assert [part["amount"] for part in row["parts"]] == [94.693, 5.547, 11.095]
    assert row["employer_contributions"] == 111.335
    assert row["total_monthly_cost"] == 666.071
    assert row["total_annual_cost"] == 7992.852
    assert "TND 554.736" in row["claim"] and "TND 666.071" in row["claim"]
    assert "not a statutory remittance rounding rule" in row["methodology"]


def test_three_decimal_spec_item_value_matches_claim_without_cent_truncation():
    spec = {"calculation_decimals": 3,
            "vars": {"floor": {"value": 554.736, "facts": ["F-001"]}},
            "items": [{"expr": "floor * 2", "claim": "Budget {value:.3f}",
                       "methodology": "Two stated periods"}]}
    row = calc.build(FACTS, spec)["rows"][-1]
    assert row["value"] == 1109.472
    assert row["claim"] == "Budget 1109.472"


@pytest.mark.parametrize("value", [True, None, -1, 7, 2.5, "3"])
def test_invalid_calculation_precision_is_rejected(value):
    with pytest.raises(ValueError, match="calculation_decimals"):
        calc.build(FACTS, {"calculation_decimals": value})


def test_calc_rounds_down_each_legal_contribution_after_cap():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"] = [{"label": "Average", "gross_monthly": 1707, "facts": ["F-001"]}]
    data["contributions"] = [
        {"name": "Sickness", "employer_pct": 1.4, "rounding": "down", "facts": ["F-002"]},
        {"name": "Pension", "employer_pct": 14, "rounding": "down", "facts": ["F-002"]},
        {"name": "Capped", "employer_pct": 4.75, "cap_monthly": 1000.01,
         "rounding": "down", "facts": ["F-002"]},
    ]
    r = calc.build(data)["rows"][0]
    assert [p["amount"] for p in r["parts"]] == [23.89, 238.98, 47.50]
    assert r["employer_contributions"] == 310.37
    assert r["total_monthly_cost"] == 2017.37
    assert "Each contribution rounded down to cents" in r["methodology"]


def test_invalid_contribution_rounding_is_rejected():
    bad = copy.deepcopy(FACTS)
    bad["contributions"][0]["rounding"] = "ceil"
    assert any("rounding" in e for e in check_facts.validate(bad))
    with pytest.raises(ValueError, match="Unknown contribution rounding"):
        calc.build(bad)


def test_calc_rounds_fractional_contribution_up_to_whole_currency_units():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"] = [
        {"label": "Fractional contribution", "gross_monthly": 16710, "facts": ["F-001"]},
        {"label": "Whole contribution", "gross_monthly": 13760, "facts": ["F-001"]},
    ]
    data["contributions"] = [
        {"name": "Pension", "employer_pct": 5, "rounding": "whole_up", "facts": ["F-002"]},
    ]
    fractional, whole = calc.build(data)["rows"]
    assert fractional["employer_contributions"] == 836
    assert fractional["total_monthly_cost"] == 17546
    assert "rounded up to the next whole currency unit" in fractional["methodology"]
    assert whole["employer_contributions"] == 688


def test_cost_deducts_lower_threshold_and_caps_earnings_before_deduction():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"] = [{"label": "Monthly example", "gross_monthly": 3000, "facts": ["F-001"]}]
    data["contributions"] = [
        {"name": "NI", "employer_pct": 15, "floor_monthly": 417, "facts": ["F-002"]},
        {"name": "Pension", "employer_pct": 3, "floor_monthly": 520,
         "cap_monthly": 2000, "facts": ["F-002"]}]
    row = calc.build(data)["rows"][0]
    assert [part["amount"] for part in row["parts"]] == [387.45, 44.40]
    assert row["employer_contributions"] == 431.85
    assert row["total_monthly_cost"] == 3431.85
    assert row["parts"][0]["capped"] is False
    assert row["parts"][1]["capped"] is True


def test_salary_below_contribution_floor_does_not_create_a_credit():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"] = [{"label": "Below threshold", "gross_monthly": 100, "facts": ["F-001"]}]
    data["contributions"] = [{"name": "NI", "employer_pct": 15,
                              "floor_monthly": 417, "facts": ["F-002"]}]
    assert calc.build(data)["rows"][0]["employer_contributions"] == 0


def test_invalid_earnings_band_is_rejected():
    data = copy.deepcopy(FACTS)
    data["contributions"][0].update(floor_monthly=9000, cap_monthly=8450)
    assert any("floor_monthly" in issue for issue in check_facts.validate(data))
    with pytest.raises(ValueError, match="earnings band"):
        calc.build(data)


def test_statutory_assessment_band_can_exceed_salary_without_changing_wage_based_levy():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"] = [{"label": "Band example", "gross_monthly": 406000,
        "contribution_bases": {"Pension": 410000, "Health": 410000},
        "facts": ["F-001", "F-002"], "note": "Specified statutory assessment band."}]
    data["contributions"] = [
        {"name": "Pension", "employer_pct": 9.15, "facts": ["F-002"]},
        {"name": "Health", "employer_pct": 4.925, "facts": ["F-002"]},
        {"name": "Accident", "employer_pct": 0.3, "facts": ["F-002"]}]
    row = calc.build(data)["rows"][0]
    assert [part["amount"] for part in row["parts"]] == [37515, 20192.50, 1218]
    assert row["employer_contributions"] == 58925.50
    assert "assessment base" in row["methodology"]
    assert "Specified statutory assessment band" in row["methodology"]


def test_unknown_contribution_assessment_base_is_rejected():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"][0]["contribution_bases"] = {"Nonexistent tax": 1000}
    assert any("assessment base" in issue for issue in check_facts.validate(data))


def test_conditional_sector_contribution_is_not_charged_to_ineligible_scenario():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"][0]["include_contributions"] = ["Health", "Accident"]
    row = calc.build(data)["rows"][0]
    assert row["employer_contributions"] == 1150
    assert {part["name"] for part in row["parts"]} == {"Health", "Accident"}
    assert "Scenario exclusions: Pension" in row["methodology"]


def test_unknown_scenario_contribution_is_rejected():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"][0]["include_contributions"] = ["Nonexistent scheme"]
    assert any("include_contributions" in issue for issue in check_facts.validate(data))
    with pytest.raises(ValueError, match="include_contributions"):
        calc.build(data)


def test_annual_budget_includes_holiday_allowance_and_uses_explicit_annual_cap():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"] = [{"label": "Salary plus annual allowance", "gross_monthly": 3000,
                              "holiday_allowance_pct": 8, "facts": ["F-001", "F-002"]}]
    data["contributions"] = [{"name": "Insurance", "employer_pct": 10,
        "cap_monthly": 4000, "cap_annual": 37000, "facts": ["F-002"]}]
    row = calc.build(data)["rows"][0]
    assert row["total_monthly_cost"] == 3300
    assert row["annual_holiday_allowance"] == 2880
    assert row["annual_gross_pay"] == 38880
    assert row["annual_employer_contributions"] == 3700
    assert row["total_annual_cost"] == 42580


def test_monthly_only_scenario_excludes_unsourced_annual_totals():
    data = copy.deepcopy(FACTS)
    monthly = calc.build(data, {"monthly_only": True})["rows"][0]
    ordinary = calc.build(data)["rows"][0]
    assert monthly["total_monthly_cost"] == ordinary["total_monthly_cost"]
    assert "total_annual_cost" not in monthly and "annual" not in monthly["claim"]


def test_annual_holiday_budget_rejects_inferred_annual_cap():
    data = copy.deepcopy(FACTS)
    data["cost_scenarios"][0]["holiday_allowance_pct"] = 8
    assert any("cap_annual" in issue for issue in check_facts.validate(data))
    with pytest.raises(ValueError, match="cap_annual"):
        calc.build(data)


JOB = {"country": "Germany", "slug": "germany"}

COUNTRY_PAGE = """# Hiring in Germany

You can hire in three ways.

## Three ways to hire in Germany
| Route | Legal employer | What you pay on top of salary | How you end it |
|---|---|---|---|
| Own entity | You | 19.6% contributions | 4 weeks – 7 months |

## The labour market
Salary €4,323 / month.

## Registering as an employer, step by step
Steps.

## Hiring and onboarding
Text.

## Minimum wage
€13.90 / hour, see [BMAS](https://example.gov/F-001).

## Taxes and contributions
14–45% income tax.

![chart](https://s3.example.com/x.png "t")

## Working time and overtime
Text.

## Leave, sick pay and parental leave
20 days, 9–13 holidays.

## Termination: notice and payments
Probation up to 6 months.

## Recent changes
- 2026.

## What a mistake costs and who pays
Text.

## Questions people actually ask
### Q?
A.

## Sources
1. BMAS. [Mindestlohn](https://example.gov/F-001). Accessed 1 October 2026.
"""


def test_country_page_passes():
    errors, warns = check_guide.check_page(COUNTRY_PAGE, "country", JOB, FACTS)
    assert errors == []


@pytest.mark.parametrize("page,titles", [
    ("eor", ["What an employer of record does in Panama", "Is an EOR arrangement legal in Panama?",
             "What authorisation should the provider show?", "Who signs, directs and remains responsible?",
             "From offer to first payroll: steps and known timing", "What an EOR hire costs in Panama",
             "Where the EOR model runs out", "When you can hire without an EOR",
             "Entity, EOR, PEO or contractor: which route fits?",
             "Questions to put to a Panama EOR provider", "Questions people actually ask"]),
    ("eor", ["How an employer of record works in Finland", "How Finnish law treats the EOR arrangement",
             "What to verify about the provider's Finnish status", "Who signs, directs and pays",
             "Hiring through a Finnish EOR, step by step", "What an EOR employee costs",
             "Where the model stops solving the problem", "When a foreign company can hire directly instead",
             "Alternatives, and when each fits", "How to choose a provider for Finland",
             "Questions people actually ask"]),
    ("eor", ["What an employer of record means in Israel", "Is the arrangement lawful?",
             "Check the licence", "Who signs the contracts?", "From review to the first Rwanda payroll",
             "What an EOR quote needs to itemize", "Where the EOR model stops solving the problem",
             "When an EOR is unnecessary in Jordan", "Compare the ways to engage a Rwanda worker",
             "Questions to put to an EOR provider", "Questions people actually ask"]),
    ("eor", ["How an employer of record works in Testland", "Testland intermediary rules determine the EOR arrangement",
             "Check the Testland employer behind the provider", "Who signs the employment and service agreements",
             "The start date depends on registrations and worker eligibility", "Separate the provider charge from employment costs",
             "Where the EOR arrangement leaves exposure with the client", "When your own registered employer makes an EOR unnecessary",
             "Compare direct employment, EOR and independent services", "Questions a Testland EOR should answer before you sign",
             "Questions people actually ask"]),
    ("eor", ["How an employer of record works in Testland", "Testland’s temporary-agency rules depend on the arrangement",
             "Check the employing agency’s notification and register entry", "Who signs the employment and assignment documents",
             "Hiring through a local employer, step by step", "What a Testland EOR arrangement costs, line by line",
             "Assignment limits, tax exposure and rights need separate checks", "When you may not need an EOR in Testland",
             "Choose the hiring route around control and duration", "Questions to put to a Testland EOR provider",
             "Questions people actually ask"]),
    ("contractors", ["Where the line runs between services and employment", "Where the 2026 freelancer route changes the tax answer",
                     "Registering as an independent entrepreneur or ordinary sole trader", "The service contract must match the work and its end",
                     "Documents depend on the provider’s form and the type of receipt", "How fees reach the contractor’s Testland account",
                     "Payment terms and late payment under Testland law", "What breaks between onboarding and the final service record",
                     "What a mistake costs and who pays", "Choose the service model, or move the role into employment",
                     "One contractor versus ten: repeat the checks and aggregate the right costs", "Who works with contractors in Testland",
                     "Questions people actually ask"]),
    ("contractors", ["Where the line runs between a contractor and an employee", "Where contractor status breaks",
                     "How a contractor registers in Panama", "The service contract: scope, rights and exit",
                     "What the contractor must issue before settlement", "How funds reach a Panama contractor",
                     "Set the due date and late-payment remedy in the contract",
                     "What breaks between contract and accepted invoice", "What a mistake costs and who pays",
                     "Choose the operating model, including employment when needed",
                     "One contractor versus ten: which records must scale", "Who works with contractors in Panama",
                     "Questions people actually ask"]),
    ("contractors", ["Where Jordan draws the employee–contractor line", "Where contractor status breaks",
                     "Registration", "The service contract", "Which tax document follows each VAT status?",
                     "How money reaches a contractor", "When a contractor is due payment",
                     "What can fail, and at which step?", "What a mistake costs", "Which engagement model fits the work",
                     "One contractor versus ten", "Who works with contractors", "Questions people actually ask"]),
])
def test_adapted_core_headings_preserve_required_topics_and_order(page, titles):
    def core_errors(headings):
        text = "# " + check_guide.h1("Germany", page) + "\n\n" + "\n\n".join(
            "## " + title + "\nText." for title in headings + ["Sources"])
        errors, _ = check_guide.check_page(text, page, JOB, None)
        return [e for e in errors if "core section" in e]

    assert core_errors(titles) == []
    for i in range(len(titles)):
        assert core_errors(titles[:i] + titles[i + 1:]), titles[i]
    swapped = titles.copy()
    swapped[3], swapped[4] = swapped[4], swapped[3]
    assert core_errors(swapped)


def test_header_value_missing_from_body_blocks():
    text = COUNTRY_PAGE.replace("20 days", "twenty days")
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert any("paidLeave" in e for e in errors)


def test_unheaded_opening_counts_as_body_and_checks_links():
    text = COUNTRY_PAGE.replace("20 days", "twenty days")
    text = text.replace("\n\n##", "\n\n20 days. [law](https://opening.example/law) "
                        "[provider](https://www.northwind.example/x)\n\n##", 1)
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert not any("paidLeave" in e for e in errors)
    assert any("missing from Sources" in e and "opening.example" in e for e in errors)
    assert any("competitor" in e for e in errors)


def test_sources_and_links_enforced():
    text = COUNTRY_PAGE.replace("Text.\n\n## Minimum", "See [Northwind](https://www.northwind.example/x) and "
                                "[law](https://gesetze.de/a).\n\n## Minimum", 1)
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert any("competitor" in e for e in errors)
    assert any("missing from Sources" in e and "gesetze" in e for e in errors)


@pytest.mark.parametrize("url,accepted", [
    ("https://example.com/guides/germany/employer-of-record/", True),
    ("https://example.com/guides/germany/independent-contractors/", True),
    ("https://example.com/guides/japan/", False),
    ("https://example.gov/unpublished", False),
    ("https://example.com/contractors/", False),
])
def test_draft_review_date_only_for_own_guide_navigation(url, accepted):
    text = COUNTRY_PAGE + f"2. Example Co. [Draft guide]({url}). Draft reviewed 1 October 2026.\n"
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert (not any("Sources entry needs" in e for e in errors)) == accepted


def test_draft_review_future_date_blocks():
    text = COUNTRY_PAGE + ("2. Example Co. [Draft guide](https://example.com/guides/germany/). "
                           "Draft reviewed 1 October 2099.\n")
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert any("date in the future" in e for e in errors)


@pytest.mark.parametrize("target", [
    "/guides/germany/employer-of-record/",
    "/guides/germany/employer-of-record/#contract",
    "https://example.com/guides/germany/employer-of-record/",
])
def test_internal_navigation_requires_absolute_bibliography_entry(target):
    text = COUNTRY_PAGE.replace("Steps.", f"See [EOR]({target}).")
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert any("missing from Sources" in e for e in errors)
    text += ("2. Example Co. [Employer of Record in Germany]"
             "(https://example.com/guides/germany/employer-of-record/). Draft reviewed 1 October 2026.\n")
    assert check_guide.check_page(text, "country", JOB, FACTS)[0] == []


@pytest.mark.parametrize("quote", ["q", r"Project title \| freelance contract"])
def test_evidence_vendor_domains_enforce_plain_text_sources(tmp_path, quote):
    evidence = tmp_path / "evidence.vendors.md"
    evidence.write_text(
        f"| V-001 | claim | ranking | https://www.newvendor.example/guide | vendor | {quote} | 2026-10-09 | supports |\n"
        "| V-002 | claim | ranking | https://example.com/countries/ | vendor | q | 2026-10-09 | supports |\n"
        "| V-003 | claim | ranking | https://law.example/a | official | q | 2026-10-09 | supports |\n")
    domains = check_guide.vendor_domains(evidence)
    assert domains == {"newvendor.example"}
    source = "2. Vendor. Guide (newvendor.example/guide). Accessed 1 October 2026.\n"
    text = COUNTRY_PAGE + source
    assert check_guide.check_page(text, "country", JOB, FACTS, domains)[0] == []
    linked = text.replace("Guide (newvendor.example/guide)", "[Guide](https://newvendor.example/guide)")
    errors, _ = check_guide.check_page(linked, "country", JOB, FACTS, domains)
    assert any("Sources entry links a competitor" in e for e in errors)
    errors, _ = check_guide.check_page(text.replace("Steps.", "[Vendor](https://sub.newvendor.example/x)."),
                                     "country", JOB, FACTS, domains)
    assert any("outbound link to a competitor" in e for e in errors)
    errors, _ = check_guide.check_page(text.replace("newvendor.example/guide", "unrelated.example/a"),
                                     "country", JOB, FACTS, domains)
    assert any("Sources entry needs a link" in e for e in errors)
    assert not check_guide.is_vendor_url("https://law.example/newvendor.example", domains)
    assert not check_guide.is_vendor_url("https://newvendor.example.other.com/", domains)


def test_order_faq_position_and_forbidden_words(monkeypatch):
    # Fictional policy for the test: one banned topic and one stop-listed brand.
    monkeypatch.setattr(check_guide, "FORBIDDEN", [re.compile(r"\bvisa sponsorship\b", re.I)])
    monkeypatch.setattr(check_guide, "STOP_BRANDS", lint_article.compile_stop_brands(["Soylent"]))
    text = COUNTRY_PAGE.replace("## Recent changes\n- 2026.\n\n", "")
    text = text.replace("## Sources", "## Extra\nVisa sponsorship is popular. Soylent offers it.\n\n## Sources")
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert sum("forbidden" in e for e in errors) == 2
    assert any("recent changes" in e for e in errors)
    assert any("FAQ must be" in e for e in errors)
    assert any("forbidden" in e for e in errors)


def test_brand_spelling():
    errors, _ = check_guide.check_page(COUNTRY_PAGE.replace("Text.", "ExampleCo helps.", 1), "country", JOB, FACTS)
    assert any("brand must be written «Example Co»" in e for e in errors)
    assert not any("brand must" in e for e in check_guide.check_page(
        COUNTRY_PAGE.replace("Text.", "Example Co helps.", 1), "country", JOB, FACTS)[0])


def test_first_party_source_title_keeps_brand_rule():
    original = "2. Example Co. [Northwind vs Contoso vs Example Co: Employer of Record, HR Suite or Contractor Paperwork](https://example.com/blog/northwind-vs-contoso-vs-exampleco/). Accessed 1 October 2026.\n"
    text = COUNTRY_PAGE + original
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert not any("brand must" in e for e in errors)
    for invalid in [text.replace("Text.", "ExampleCo helps.", 1),
                    text.replace("Northwind vs Contoso vs Example Co:", "Northwind vs Contoso vs ExampleCo:"),
                    text.replace("Northwind vs Contoso vs Example Co:", "Another Example.com title:")]:
        errors, _ = check_guide.check_page(invalid, "country", JOB, FACTS)
        assert any("brand must" in e for e in errors)


def test_overlap_blocks_long_shared_run(tmp_path):
    shared = " ".join(f"word{i}" for i in range(60))
    a = tmp_path / "a" / "edited.md"
    b = tmp_path / "b" / "edited.md"
    for p, extra in ((a, "alpha"), (b, "beta")):
        p.parent.mkdir()
        p.write_text(f"# T\n\n{extra} intro\n\n{shared}\n\n## Sources\n{shared}\n", encoding="utf-8")
    errors, warns = check_guide.overlaps([a, b], warn_at=20, block_at=45)
    assert len(errors) == 1 and "61 words" in errors[0]  # "intro" is shared too; Sources excluded


def test_overlap_reads_sources_in_memory_without_writing_beside_articles(tmp_path, monkeypatch):
    page = tmp_path / "edited.md"
    page.write_text("# T\n[Worker’s pay](https://example.gov/rule) — gross–net\n## Sources\nSecret appendix\n")
    before = page.read_bytes()

    def forbid_write(*args, **kwargs):
        raise AssertionError("Overlap checks must not write into article folders")

    monkeypatch.setattr(Path, "write_text", forbid_write)
    assert check_guide.body_words(page) == ["t", "worker's", "pay", "gross", "net"]
    assert check_guide.overlaps([page, page], 20, 45) == ([], [])
    assert page.read_bytes() == before
    assert list(tmp_path.iterdir()) == [page]


def test_visual_bibliography_is_not_copied_prose_but_caption_claims_are(tmp_path):
    shared = " ".join(f"claim{i}" for i in range(60))
    citations = (f"[{shared}](https://official.example/act) · "
                 "[Insurance authority](https://official.example/rates)")
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    a.write_text(f"# Alpha\n\nCaption: Salary assumptions. {citations}\n")
    b.write_text(f"# Beta\n\nCaption: Agency quote conditions. {citations}\n")
    assert check_guide.overlaps([a, b], 20, 45) == ([], [])
    for page in (a, b):
        page.write_text(f"# Title\n\nCaption: {shared}. {citations}\n")
    assert check_guide.overlaps([a, b], 20, 45)[0]
    a.write_text(f"# Title\n\nSee [{shared}](https://official.example/act).\n")
    assert "claim0" in check_guide.body_words(a)


def test_prepare_rows_escape_pipes():
    facts = copy.deepcopy(FACTS)
    facts["facts"][0]["claim"] = "a | b"
    rows = prepare_pages.fact_rows(facts, calc.build(FACTS))
    assert rows[0].count("|") == 9 and "a / b" in rows[0]
    assert any(r.startswith("| C-001 |") for r in rows)
    assert prepare_pages.evidence_rows("| E-001 | x |\n| F-001 | y |\n| V-002 | z |") == ["| E-001 | x |", "| V-002 | z |"]


def test_summary_provenance_cannot_become_publication_support():
    data = copy.deepcopy(FACTS)
    data["facts"] = [fact("F-001", quote="A page summary [summary]"),
                     fact("F-002", quote="Actual corroborating passage"),
                     fact("F-003", quote="Old summary [summary]",
                          status="superseded", superseded_by="F-002")]
    rows = prepare_pages.fact_rows(data, {"rows": []})
    assert rows[0].endswith("| partial |")
    assert rows[1].endswith("| supports |")
    assert rows[2].endswith("| no |")
    assert "SUPERSEDED by F-002" in rows[2]


@pytest.mark.parametrize("status,quote,verdict", [
    ("restricted", "Exact original clause", "partial"),
    ("unconfirmed", "Exact original clause", "partial"),
    (None, "A page summary [summary]", "partial"),
    ("superseded", "Exact original clause", "no"),
    (None, "Exact original clause", "supports"),
])
def test_calculation_does_not_promote_restricted_fact_inputs(status, quote, verdict):
    source = fact("F-001", quote=quote)
    if status:
        source["status"] = status
    data = {"facts": [source, fact("F-002")]}
    derived = {"rows": [{"id": "C-001", "claim": "Budget illustration", "source_url": source["source"]["url"],
                         "methodology": "Arithmetic", "facts": ["F-001", "F-002"]}]}
    rows = prepare_pages.fact_rows(data, derived)
    assert rows[0].endswith(f"| {verdict} |")
    assert quote in rows[0]  # Restriction never changes the original quotation.
    assert rows[1].endswith("| supports |")
    assert rows[2].endswith(f"| {verdict} |")
    assert ("RESTRICTED INPUTS" in rows[2]) == (verdict != "supports")


def test_calc_spec_items_and_extra_scenarios():
    spec = {"scenarios": [{"label": "Low", "gross_monthly": 1000, "facts": []}],
            "vars": {"w": {"value": 13.9, "facts": ["F-001"]}, "h": {"value": 173.33, "facts": []}},
            "items": [{"claim": "Pay {cur}{value:,.2f}", "expr": "w * h", "methodology": "w×h"}]}
    rows = calc.build(FACTS, spec)["rows"]
    assert [r["id"] for r in rows] == ["C-001", "C-002", "C-003"]
    assert rows[1]["scenario"] == "Low" and rows[2]["value"] == 2409.29
    assert rows[2]["facts"] == ["F-001"] and rows[2]["claim"] == "Pay €2,409.29"
    assert rows[2]["source_url"] == "https://example.gov/F-001"


def test_relative_internal_links_checked():
    text = COUNTRY_PAGE.replace("Text.", "See [the EOR page](/guides/germany/employer-of-record/) and [x](/blog/not-a-page/).", 1)
    errors, _ = check_guide.check_page(text, "country", JOB, FACTS)
    assert any("/blog/not-a-page/" in e for e in errors)
    assert not any("internal link not in" in e and "employer-of-record/" in e for e in errors)
    assert any("missing from Sources" in e and "employer-of-record/" in e for e in errors)


def test_order_sources_counts_table_short_names():
    import order_sources
    text = """# T

| Fact | Value | u.ae (payment of wages) |

See [law](https://x.gov/law).

## Sources

1. Ministry. [The law](https://x.gov/law). Accessed 1 October 2026.
2. UAE Government portal (u.ae). [Payment of wages](https://u.ae/wages). Accessed 1 October 2026.
"""
    order = [order_sources.ITEM.sub("", i) for i in order_sources.ordered(text)]
    assert order[0].startswith("UAE Government portal")


def test_order_sources_does_not_treat_homepage_as_a_glossary_citation():
    import order_sources
    text = """# T
See [the definition](https://example.com/glossary/eor/).
Then [law](https://x.gov/law).

## Sources
1. Example. [Homepage](https://example.com/). Accessed 1 October 2026.
2. Example. [Definition](https://example.com/glossary/eor/). Accessed 1 October 2026.
3. Ministry. [Law](https://x.gov/law). Accessed 1 October 2026.
"""
    order = [order_sources.ITEM.sub("", i) for i in order_sources.ordered(text)]
    assert "Definition" in order[0]
    assert "Law" in order[1]
    assert "Homepage" in order[2]


def test_order_sources_counts_embedded_unique_publisher_without_guessing():
    import order_sources
    text = """# T
| Senior developer: Kestrel 2026 gross salary mode | 1000 | Excludes benefits |
See [law](https://x.gov/law).

## Sources
1. Ministry. [Law](https://x.gov/law). Accessed 1 October 2026.
2. Kestrel. [Salary guide](https://example.com/salary). Accessed 1 October 2026.
"""
    order = [order_sources.ITEM.sub("", i) for i in order_sources.ordered(text)]
    assert order[0].startswith("Kestrel")
    ambiguous = text + "3. Kestrel. [Another guide](https://example.com/other). Accessed 1 October 2026.\n"
    order = [order_sources.ITEM.sub("", i) for i in order_sources.ordered(ambiguous)]
    assert order[0].startswith("Ministry")
