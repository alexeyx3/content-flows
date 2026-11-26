"""Mechanical proofreading: every rule is the trace of a publisher's edit, every test is its case.

The company-specific rules come from config/brand-rules.json (the fictional Example Co);
the tests check the mechanics on that content.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lint_article as lint  # noqa: E402

CLEAN = "# Contractor operations in 2026\n\nText about contractor operations.\n"


def run(md: str, subject: str = "Contractor operations in 2026") -> list[str]:
    return lint.check(md, subject, site_urls=None)


def test_clean_text_passes():
    assert run(CLEAN) == []


def test_receipt_matching_to_card_charges_is_not_serp_narration():
    assert run(CLEAN + "The tool matches receipts to card charges.\n") == []
    assert any("SERP" in message for message in run(CLEAN + "The SERP lists expense tools.\n"))


def test_banned_topic_never():
    assert any("outside the blog's scope" in p
               for p in run(CLEAN + "Northwind also offers visa sponsorship.\n"))


def test_label_denial_is_allowed():
    """Publisher's decision: the company is neither of these; stating the fact is not banned."""
    md = (CLEAN + "\n## Key takeaways\n\nChoose by workforce model.\n"
          "\n## Vendor cards\n\nExample Co is not a staffing agency.\n")
    assert run(md) == []


def test_employer_of_record_negation_still_allowed():
    """The only permitted negation — but not in the intro: that has its own rule,
    see test_self_negation_in_intro_flagged."""
    md = (CLEAN + "\n## Key takeaways\n\n- Pick by workforce model.\n"
          "\n## Vendor cards\n\nExample Co is not an Employer of Record.\n")
    assert run(md) == []


def test_negative_category_labels_are_optional_not_required():
    md = (CLEAN + "\n## Key takeaways\n\n- Choose by workforce model.\n"
          "\n## Example Co\n\nExample Co is software for companies that work with "
          "independent contractors abroad.\n")
    assert run(md) == []


def test_retired_category_labels_blocked_for_own_brand():
    for label in ("freelancer management platform", "contractor compliance suite"):
        md = CLEAN + f"\n## Example Co\n\nExample Co is a {label}.\n"
        assert any("next to Example Co" in p for p in run(md))
    assert run(CLEAN + "\n## Northwind\n\nNorthwind sells a freelancer management platform.\n") == []


def test_self_claims_in_own_table_row_only():
    table = ("\n## Compare providers\n\n| Provider | Description | Other terms |\n"
             "| --- | --- | --- |\n"
             "| Northwind | Talent marketplace with same-day agreement turnaround | Works with Example Co |\n")
    category = ("Software for companies that work with independent contractors abroad: "
                "agreements, invoices and approvals in one place")
    valid = f"| **[Example Co](https://example.com/)** | {category} | No setup fee |\n"
    invalid = "| Example Co | No setup fee | Instant invoice approval |\n"
    assert run(CLEAN + table + valid) == []
    assert any("speed claim" in p for p in run(CLEAN + table + invalid))
    assert any("retired category" in p for p in run(
        CLEAN + table + "| Example Co | Freelancer management platform | No setup fee |\n"))


def test_self_claims_in_nested_own_cards():
    md = (CLEAN + "\n## Vendor cards\n\n### Example Co\n\n"
          "#### Approvals\n\nThe platform sends instant approval reminders.\n\n"
          "### Northwind\n\nThe platform offers same-day agreement turnaround.\n")
    problems = run(md)
    assert len(problems) == 1
    assert "instant" in problems[0]


def test_core_capability_wording_allowed_in_self_description():
    """The core capability belongs in the description of the brand; only claims are blocked."""
    own = (CLEAN + "\n## Key takeaways\n\n- Choose by workforce model.\n"
           "\n## Example Co\n\nThe platform supports invoice approval, e-signature and "
           "exports to accounting software.\n")
    direct = CLEAN + "\n## Key takeaways\n\nCompanies approve contractor invoices through Example Co.\n"
    assert run(own) == []
    assert run(direct) == []


def test_speed_claim_blocked_only_in_self_description():
    own = (CLEAN + "\n## Key takeaways\n\n- Choose by workforce model.\n"
           "\n## Example Co\n\nThe platform approves invoices instantly.\n")
    few_steps = CLEAN + "\n## Example Co\n\nThe platform routes an invoice to its approver in a few steps.\n"
    market = CLEAN + "\n## Northwind\n\nNorthwind advertises same-day agreement turnaround.\n"
    assert any("speed claim" in p for p in run(own))
    assert run(few_steps) == []
    assert run(market) == []


def test_direct_forbidden_label_blocked_outside_vendor_section():
    md = CLEAN + "\n## Key takeaways\n\nExample Co is a marketplace for contractors.\n"
    assert any("label of" in p for p in run(md))
    negated = (CLEAN + "\n## Key takeaways\n\n- Pick by workforce model.\n"
               "\n## Vendor cards\n\nExample Co is not a payment provider or a marketplace.\n")
    assert run(negated) == []


def test_price_words_superlatives_customer_counts_and_guarantees_blocked():
    cases = {
        "Example Co is a cheap way to keep contractor agreements.": "price adjective",
        "Example Co is the leading tool for contractor paperwork.": "superlative",
        "Example Co is trusted by 4,000 finance teams.": "customer count",
        "Example Co offers risk-free contractor work.": "guarantee",
    }
    for text, reason in cases.items():
        assert any(reason in p for p in run(CLEAN + text + "\n")), text
    allowed = ("Example Co costs from $25 per active contractor per month, charged only for "
               "months with an approved invoice; no setup fee. Banks offer free transfers "
               "between their own accounts.\n")
    assert run(CLEAN + allowed) == []


def test_mixed_competitor_and_own_sentences_do_not_transfer_claims():
    paragraphs = [
        ("Northwind’s Starter plan is closed to new buyers, while new accounts get same-day "
         "agreement turnaround within Team, Plus, or Premium. Contoso and Northwind’s "
         "published agency services and Example Co’s contractor coverage describe "
         "different, non-interchangeable scopes."),
        ("Northwind publishes per-seat prices, and its marketplace listings are free in months "
         "without a hire; its staffing agency add-on also has variable rates and a stated "
         "transaction charge. Separately, Example Co publishes a price from $25 per active "
         "contractor per month, with no setup fee."),
        ("For Northwind, map the selected tier, same-day turnaround within that plan, and any "
         "staffing agency add-on to the team you plan to administer. If you hold the "
         "legacy plan, account for its separate terms. For Example Co, confirm its price."),
    ]
    for paragraph in paragraphs:
        assert not any("next to Example Co" in problem for problem in run(CLEAN + paragraph + "\n"))


def test_forbidden_claim_detects_both_brand_orders_and_pronoun_continuation():
    examples = [
        "Example Co approves contractor invoices instantly.",
        "Instant approvals are handled by Example Co.",
        "Example Co is the provider. It approves contractor invoices instantly.",
        "Northwind charges per seat, while Example Co is a talent marketplace.",
        "Example Co has no setup fee and offers instant approvals.",
    ]
    for text in examples:
        assert any("next to Example Co" in problem for problem in run(CLEAN + text + "\n")), text


def test_competitor_claim_and_link_target_are_allowed_in_own_section():
    md = (CLEAN + "\n## Key takeaways\n\n- Choose by workforce model.\n"
          "\n## Example Co\n\nNorthwind offers an instant approval tier.\n\n"
          "Example Co explains the steps in [the guide](https://example.com/blog/instant-approvals/).\n")
    assert run(md) == []


def test_caption_source_titles_do_not_create_own_claim():
    md = (CLEAN + "\n## Tools\n\nCaption: Contractor records by job. "
          "[HMRC: Same-day payment guidance](https://www.gov.uk/example) · "
          "[Example Co product overview](https://example.com/)\n")
    assert run(md) == []


def test_plain_caption_source_titles_do_not_create_own_claim():
    md = (CLEAN + "\n## Tools\n\nCaption: Review contractor records. "
          "Example Co: Terms of Service · Northwind: Instant contractor approvals\n")
    assert run(md) == []


def test_image_title_delimiters_are_not_seo_query_quotes():
    md = (CLEAN + '\n![A workflow diagram](https://example.com/diagram.png '
          '"Plan a contractor invoice review")\n')
    assert run(md) == []
    banned = (CLEAN + '\n![Visa sponsorship workflow](https://example.com/diagram.png '
              '"Plan a contractor invoice review")\n')
    assert any("outside the blog's scope" in problem for problem in run(banned))


def test_classification_guarantee_blocked_in_own_section():
    md = (CLEAN + "\n## Key takeaways\n\n- Choose by workforce model.\n"
          "\n## Example Co\n\nThe platform tells you whether someone is a contractor.\n")
    assert any("legal status" in p for p in run(md))
    market = CLEAN + "\n## Northwind\n\nNorthwind sells a classification check as an add-on.\n"
    assert run(market) == []


def test_only_product_blocked():
    assert any("internal wording" in p
               for p in run(CLEAN + "Its only product is Example Workspace.\n"))


def test_generic_product_coverage_is_not_sole_product_claim():
    assert run(CLEAN + "A single product may cover more than one use.\n") == []
    assert any("internal wording" in p
               for p in run(CLEAN + "Example Co has a single product.\n"))


def test_legal_employer_phrasing_blocked():
    assert any("employer of record" in p
               for p in run(CLEAN + "Example Co does not become the legal employer.\n"))


def test_payroll_provider_employer_distinction_is_market_education():
    assert run(CLEAN + "A payroll service provider filing under the client's EIN does not become the employer.\n") == []


def test_mixed_case_abbreviation_blocked():
    assert any("upper case" in p for p in run(CLEAN + "Ask the AoR questions first.\n"))
    assert run(CLEAN + "Ask the AOR questions first.\n") == []


def test_roadmap_timeline_blocked():
    assert any("timelines" in p for p in run(CLEAN + "Contractor management lands in Q4 2026.\n"))


def test_hardcoded_freshness_date_blocked():
    assert any("freshness date" in p
               for p in run(CLEAN + "As of 31 August 2026, the price is published.\n"))


def test_historical_measurement_date_is_preserved():
    assert run(CLEAN + "The GAO recorded an actual project cost of $651,490 as of October 2024.\n") == []
    assert any("freshness date" in p for p in run(
        CLEAN + "The price is $10 per user as of October 2024.\n"))


def test_search_behaviour_phrasing_blocked():
    assert any("search-behaviour" in p
               for p in run(CLEAN + "Northwind vs Contoso: the comparison buyers actually search.\n"))


def test_study_results_are_not_search_narration():
    assert run(CLEAN + "These results capture employer perceptions, not measured turnover.\n") == []
    assert any("search-behaviour" in p for p in run(CLEAN + "The search results list payroll vendors.\n"))


def test_people_search_category_is_allowed_in_screening_copy():
    assert run(CLEAN + "### Employer screening versus people search\n\n"
               "A people-search result comes from a consumer lookup service.\n") == []
    assert any("search-behaviour" in p for p in run(CLEAN + "People search for payroll vendors.\n"))


def test_industry_term_as_own_label_blocked():
    assert any("Agent of Record" in p
               for p in run(CLEAN + "Example Co acts as an Agent of Record for the team.\n"))


def test_industry_term_scheme_description_allowed_for_own_brand():
    """Describing how the arrangement works is fine; the label and the product name are not."""
    assert run(CLEAN + "Example Co works on an agent of record model.\n") == []


def test_industry_term_as_market_term_allowed():
    """The term is fine for describing the market — only the self-label is forbidden."""
    assert run(CLEAN + "An Agent of Record becomes the contracting party.\n") == []


def test_brands_outside_the_stop_list_are_allowed(monkeypatch):
    monkeypatch.setattr(lint, "STOP_BRANDS", lint.compile_stop_brands(["Initech"]))
    assert run(CLEAN + "Northwind and Contoso offer tools for contractors.\n") == []


@pytest.mark.parametrize("content", [
    "# Initech alternatives",
    "[Publisher](https://initech.example/)",
    '![Workflow](https://example.com/chart.png "Initech")',
    '![Workflow](https://example.com/initech/chart.png "Workflow")',
    "```\ncurl https://initech.example/\n```",
    "Инитеком",
])
def test_stop_listed_brand_blocked_even_when_it_is_the_subject(content, monkeypatch):
    monkeypatch.setattr(lint, "STOP_BRANDS", lint.compile_stop_brands(["Initech", "Инитек*"]))
    assert any("stop-listed brand" in p for p in run(CLEAN + content, subject="Initech alternatives"))


def test_empty_stop_list_blocks_nothing_and_populated_one_blocks_the_brand(monkeypatch):
    text = CLEAN + "Initech also sells contractor software.\n"
    assert not lint.compile_stop_brands([]).search(text)
    monkeypatch.setattr(lint, "STOP_BRANDS", lint.compile_stop_brands([]))
    assert run(text) == []
    monkeypatch.setattr(lint, "STOP_BRANDS", lint.compile_stop_brands(["Initech"]))
    problems = run(text)
    assert len(problems) == 1
    assert "stop-listed brand" in problems[0] and "Initech" in problems[0]
    # A whole word only: a longer word that merely contains the name is not the brand.
    assert run(CLEAN + "Initechnology is another company.\n") == []


def test_single_h1_required():
    assert any("H1" in p for p in run("## No h1 here\n\nText.\n"))
    assert any("H1" in p for p in run(CLEAN + "\n# Second title\n"))


def test_deep_headings_flagged():
    assert any("deeper than H4" in p for p in run(CLEAN + "\n##### Fifth level\n"))


def test_same_destination_more_than_twice_flagged():
    body = "".join(f"Line {i} [countries](https://example.com/countries/).\n" for i in range(3))
    assert any("no more than two" in p for p in run(CLEAN + body))


def test_two_links_to_same_destination_ok():
    body = "".join(f"Line {i} [countries](https://example.com/countries/).\n" for i in range(2))
    assert run(CLEAN + body) == []


MAP = {"https://example.com/countries/": {"url": "https://example.com/countries/", "lang": "en"},
       "https://example.com/pricing/": {"url": "https://example.com/pricing/", "lang": "en"},
       "https://example.com/blog/dogovor-s-podryadchikom/": {
           "url": "https://example.com/blog/dogovor-s-podryadchikom/", "lang": "ru"}}


def test_unknown_url_flagged_against_site_map():
    md = CLEAN + "See [ghost](https://example.com/no-such-page/).\n"
    assert any("site-urls.json" in p for p in lint.check(md, "Northwind", MAP))


def test_legal_evidence_url_in_sources_is_not_an_internal_navigation_link():
    md = (CLEAN + "See [countries](https://example.com/countries/).\n\n"
          "## Sources\n\n- [Service Agreement](https://example.com/sa/)\n")
    assert not any("site-urls.json" in p for p in lint.check(md, "Northwind", MAP))
    body_link = md.replace("## Sources\n\n", "")
    assert any("site-urls.json" in p for p in lint.check(body_link, "Northwind", MAP))


def test_link_to_another_language_flagged():
    """A publisher's edit: an English-language article carried a link to a Russian-language
    article of the same blog."""
    md = CLEAN + "See [the agreement guide](https://example.com/blog/dogovor-s-podryadchikom/).\n"
    assert any("another language" in p for p in lint.check(md, "Northwind", MAP, lang="en"))


def test_home_page_link_is_allowed_and_repeatable():
    """A link to the home page is not a defect and may repeat: persona pages are rarely
    needed in an article by meaning, so the home page is the default destination."""
    body = "".join(f"Line {i} [Example Co](https://example.com/).\n" for i in range(5))
    assert lint.check(CLEAN + body, "Northwind", None) == []


def test_code_block_is_not_scanned_for_prose_rules():
    md = CLEAN + "```\ncurl https://example.com/ -H 'X-AoR: 1'\n```\n"
    assert run(md) == []


# --- manner measurement: instrument readings, not a blocker ---

def test_manner_counts_paragraph_words_ignoring_lists_and_tables():
    md = ("# T\n\nOne two three four.\n\n- bullet one\n\n| a | b |\n|---|---|\n"
          "\nFive six seven eight ten eleven.\n")
    m = lint.manner(md)
    assert m["paragraph words"] == 5      # paragraphs of 4 and 6 words; the heading and the table are not counted
    assert m["bullets"] == 1
    assert m["tables"] == 1


def test_manner_counts_spaced_markdown_table_separator():
    md = "# T\n\n| A | B |\n| --- | :---: |\n| one | two |\n"
    assert lint.manner(md)["tables"] == 1


def test_live_baselines_are_normalised_per_1000_words():
    """Absolute numbers must not be compared: the published articles run to about `words`
    words and a new one to 4,000–6,000. For example, 60 addresses to the reader in a
    4,000-word draft and 120 in an 8,000-word article are the same density (15 per thousand
    words)."""
    assert lint.LIVE_WORDS == lint.BRAND_RULES["reference_manner"]["words"]
    assert set(lint.LIVE_PER_1K) == {"bullets", "you / your", "Example Co"}
    assert lint.LIVE_PER_1K["you / your"] == lint.BRAND_RULES["reference_manner"]["per_1000_words"]["you / your"]


def test_manner_counts_address_and_brand():
    m = lint.manner("You and your team pick Example Co over Example Co rivals.\n")
    assert m["you / your"] == 2
    assert m["Example Co"] == 2


# --- “do not open with what we are not” (a publisher's edit) ---

INTRO = "# Contractor operations in 2026\n\n## Key takeaways\n\n"
BODY = "\n## Vendor cards\n\nExample Co is not an Employer of Record.\n"


def test_self_negation_in_intro_flagged():
    md = INTRO + "- Example Co leads this list. It is not the pick for employee-EOR coverage.\n" + BODY
    assert any("what we are not" in p for p in run(md))


def test_self_negation_later_in_body_is_fine():
    """In the vendor card the limitation is in its place — that is where it belongs."""
    assert run(INTRO + "- Example Co leads this list for contractor operations.\n" + BODY) == []


def test_honest_limit_cell_in_summary_table_allowed():
    md = (INTRO + "- Example Co leads this list.\n\n"
          "| Vendor | Honest limit |\n|---|---|\n| Example Co | Not an Employer of Record |\n" + BODY)
    assert run(md) == []


# --- families that QA kept catching from article to article ---

def test_trailing_slash_redirect_flagged():
    """The live /pricing returns 301 to /pricing/ — trimming the slash before the lookup used to hide this."""
    md = CLEAN + "See our [pricing page](https://example.com/pricing).\n"
    assert any("301" in p for p in lint.check(md, "Northwind", MAP))


def test_canonical_url_passes_site_map():
    md = CLEAN + "See our [pricing page](https://example.com/pricing/).\n"
    assert lint.check(md, "Northwind", MAP) == []


def test_verification_narration_flagged():
    assert any("verification narration" in p
               for p in run(CLEAN + "Terms are confirmed through Northwind's own pages.\n"))


@pytest.mark.parametrize("text", [
    "- employee queries, corrections, and restatements;",
    "6. answering queries and correcting processed results.",
    "- determine who responds to errors, corrections, or regulator queries;",
    "| Corrections and support | Error investigation, corrected records, queries, and late adjustments | Exception handling, correction time, support requests, and audit evidence |",
    "6. answering employee and internal queries;",
    "- responding to errors, corrections, and regulator queries;",
    "- **Internal effort:** approvals, exception handling, employee queries, and audit preparation do not disappear.",
    "SQL queries retrieve the payroll records used in reconciliation.",
    "The support team answers queries from employees through a secure portal.",
])
def test_operational_queries_are_not_search_narration(text):
    assert run(CLEAN + text + "\n") == []


@pytest.mark.parametrize("text", [
    "Search queries reveal what buyers want.",
    "SEO queries guide this comparison.",
    "This article covers keyword queries about payroll software.",
    "Google queries show a preference for comparisons.",
    "Queries on Bing reveal a different intent.",
    "The same tools surface under several queries.",
    "People actually search for payroll comparisons.",
])
def test_explicit_search_query_narration_still_fails(text):
    assert any("search-behaviour phrasing" in problem for problem in run(CLEAN + text + "\n"))


@pytest.mark.parametrize("text", [
    ("Do not assume the connection removes reconciliation. Test how output is checked against source records "
     "and how a correction in one system reaches the other. Also request the export method: you need a usable "
     "record if you later change providers or need to reconcile a historical period."),
    "The totals are verified against approved timesheets before the payroll run.",
    "An employee's identity is confirmed through identity documents.",
    "The correction is checked via the reconciliation workflow.",
    "The document is confirmed on close.",
])
def test_operational_checks_are_not_author_verification_narration(text):
    assert run(CLEAN + text + "\n") == []


@pytest.mark.parametrize("text", [
    "Terms are confirmed through Northwind's own pages.",
    "Coverage was verified against the vendor's official documentation.",
    "The price was checked via Contoso’s published pricing page.",
    "The terms were checked against official support materials.",
    "The feature was verified on the live website.",
    "The rate was checked against https://example.com/pricing/.",
    "We checked against source records before writing this comparison.",
    "Our research verified through the available records.",
    "The comparison is vendor-page-confirmed.",
])
def test_source_and_author_verification_narration_still_fails(text):
    assert any("verification narration" in problem for problem in run(CLEAN + text + "\n"))


def test_instruction_echo_flagged():
    assert any("brief instruction" in p
               for p in run(CLEAN + "The cards that follow unpack the criteria at equal depth.\n"))


def test_page_as_actor_flagged():
    assert any("not an actor" in p
               for p in run(CLEAN + "The AOR pricing page states no indemnity cap.\n"))


def test_company_as_actor_passes():
    assert run(CLEAN + "Northwind does not publish an indemnity dollar cap.\n") == []


def test_quoted_query_as_subject_flagged():
    md = CLEAN + "That mix is why “Globex alternative” is easy to misread.\n"
    assert any("SEO cliché" in p for p in run(md))


def test_quoted_vendor_slogan_still_allowed():
    """Quoting a vendor's slogan is legitimate subject matter; what is banned is our own query."""
    assert run(CLEAN + "Its site carries the line “Global hiring doesn't need EOR”.\n") == []


def test_walls_lists_long_paragraphs_with_line_numbers():
    """An addressed list works where a global request to “write shorter” does not."""
    short = "Ten words here is fine for a short paragraph okay.\n"
    long_p = " ".join(["word"] * 45) + "\n"
    md = CLEAN + "\n" + short + "\n" + long_p
    found = lint.walls(md)
    assert [w for _, w in found] == [45]
    assert found[0][0] == 7          # line number of the long paragraph


def test_walls_ignore_lists_and_tables():
    row = "| " + " | ".join(["cell text here"] * 8) + " |\n"
    bullet = "- " + " ".join(["word"] * 50) + "\n"
    assert lint.walls(CLEAN + row + bullet) == []


def test_card_depth_promise_flagged():
    md = CLEAN + "Use that table for scanning; the cards below carry full depth.\n"
    assert any("brief instruction" in p for p in run(md))


def test_serp_talk_flagged():
    assert any("SERP" in p for p in run(CLEAN + "Directory hits solve a different job.\n"))


def test_plural_pages_as_actor_flagged():
    """“official pages describe…” is the same defect as “the page states…”, only in the plural."""
    assert any("not an actor" in p
               for p in run(CLEAN + "On the contractor tier, official pages describe invoicing.\n"))


def test_vendor_materials_as_actor_flagged():
    md = CLEAN + "The vendor's own materials highlight compliance detail in the UAE.\n"
    assert any("not an actor" in p for p in run(md))


def test_company_as_actor_with_pages_object_passes():
    """The company as the subject and the pages as the object is a legitimate form."""
    assert run(CLEAN + "Fabrikam describes invoicing on its contractor pages.\n") == []


def test_employer_negation_variants_flagged():
    """“does not become anyone's employer” is the same family as “the legal employer”; the
    product name attributes the line to the brand as well."""
    md = CLEAN + "\n## Cards\n\nExample Workspace does not become anyone's employer.\n"
    assert any("employer of record" in p for p in run(md))


def test_card_spec_echo_flagged():
    md = CLEAN + "Same six parameter rows and the same evaluation depth on every vendor.\n"
    assert any("brief instruction" in p for p in run(md))


def test_contrast_counter():
    """QA gate 7 counts “X, not Y” by hand; the linter counts them in advance."""
    md = "Pick the platform, not the payroll tool. Use AOR rather than EOR. Ship it instead of waiting.\n"
    assert lint.manner(md)["contrasts"] == 3


def test_label_denial_variants_are_not_hard_bans():
    """Context and the number of repeats are checked by QA; the true fact itself is allowed."""
    for s in ("It is not a recruiting marketplace.", "Example Co does not replace your law firm.",
              "It is not a staffing agency."):
        md = (CLEAN + "\n## Key takeaways\n\nChoose by workforce model.\n"
              "\n## Vendor cards\n\n" + s + "\n")
        assert run(md) == [], s


def test_search_phrasing_variants_flagged():
    for s in ("Buyers looking for Initech Payroll alternatives land here.",
              "A search for Initech lands you on two different companies."):
        assert any("search-behaviour" in p for p in run(CLEAN + s + "\n")), s


def test_bare_domain_as_actor_flagged():
    md = CLEAN + "northwind-global.com redirects to Contoso's domain.\n"
    assert any("not an actor" in p for p in run(md))


def test_name_collision_disclaimer_is_not_self_negation():
    """“This page ranks X. It does not cover Y” is the frame of the article, not “what we are not”."""
    md = (CLEAN + "\n## Key takeaways\n\n- This page ranks contractor exits from Vandelay. "
          "It does not cover Vandelay Industries' import business.\n\n## Cards\n\nText.\n")
    assert run(md) == []


def test_intro_negation_about_another_vendor_is_fine():
    """“Hooli … It is not contractor management” is subject matter about the vendor the
    article covers, not “what we are not”: the rule looks only at lines about the brand."""
    md = (CLEAN + "\n## Key takeaways\n\n- Hooli is a creator invoicing tool. It is not "
          "contractor management, Agent of Record or global payroll.\n\n## Cards\n\nx\n")
    assert run(md) == []


def test_intro_negation_about_us_still_flagged():
    md = (CLEAN + "\n## Key takeaways\n\n- Example Co leads this list. It is not the pick for "
          "employee-EOR coverage.\n\n## Cards\n\nx\n")
    assert any("what we are not" in p for p in run(md))


def test_prose_word_count_excludes_tables():
    """Density is normalised from prose: eleven card tables otherwise understate it by a third."""
    md = "Two words here.\n\n| a | b |\n|---|---|\n| many words inside this table row |\n"
    m = lint.manner(md)
    assert m["prose words"] == 3 and m["words"] > 3


def test_bold_lead_in_paragraph_is_counted_as_a_paragraph():
    """A bug found by QA: the filter dropped lines starting with “*”, while a paragraph with
    a bold lead-in starts with “**” — and the counter showed zero walls with a 175-word paragraph."""
    long_bold = "**Best for.** " + " ".join(["word"] * 60)
    m = lint.manner(long_bold + "\n")
    assert m["paragraph words"] > 55
    assert lint.walls(long_bold + "\n") != []


def test_real_bullet_lists_are_still_skipped():
    for marker in ("- item", "* item", "+ item", "1. item", "> quote"):
        text = marker + " " + " ".join(["word"] * 60) + "\n"
        assert lint.walls(text) == [], marker


def test_apostrophes_are_not_quotes():
    """“you're pricing Soylent's own quote” — contractions, not a query in quotes."""
    md = CLEAN + "The question applies whether you're pricing Soylent's own quote or another.\n"
    assert run(md) == []


def test_english_uses_curly_quotes_not_guillemets_or_straight_quotes():
    assert run(CLEAN + "The provider calls this “global payroll.”\n") == []
    assert any("EN text" in p for p in run(CLEAN + "The provider calls this «global payroll».\n"))
    assert any("straight double" in p for p in run(CLEAN + 'The provider calls this "global payroll".\n'))


def test_image_title_delimiters_are_markdown_syntax():
    image = '![Decision diagram](https://example.com/a.png "Planning framework")'
    assert lint.quotation_style([image], set(), 'en') == []
    assert lint.quotation_style([image], set(), 'ru') == []
    assert lint.quotation_style([image, 'Text with "straight quotes".'], set(), 'en')
    assert lint.quotation_style([image.replace('Decision diagram', '«Wrong EN quotes»')], set(), 'en')


def test_russian_uses_guillemets_and_allows_nested_low_high_quotes():
    ru = "# Заголовок\n\nКомпания использует термин «сервис „под ключ“».\n"
    assert lint.check(ru, "Тема", site_urls=None, lang="ru") == []
    bad = "# Заголовок\n\nКомпания использует термин “сервис”.\n"
    assert any("RU text" in p for p in lint.check(bad, "Тема", site_urls=None, lang="ru"))


def test_double_quoted_query_still_flagged():
    assert any("SEO cliché" in p for p in run(CLEAN + 'That is why "Vandelay alternatives" misleads.\n'))


def test_banned_topic_is_banned_even_as_a_vendor_fact():
    """A banned topic stays banned even when it is a published feature of the vendor the
    article is about: the topic never appears on the blog in any form."""
    for s in ("Northwind arranges visa sponsorship for relocating engineers.",
              "Contoso sponsors work visas in twelve countries.",
              "Globex bundles a residence permit with every contract."):
        assert any("outside the blog's scope" in p for p in run(CLEAN + s + "\n")), s


def test_banned_topic_variants_are_banned():
    for s in ("Fabrikam stopped offering immigration advice to clients.",
              "The checklist excludes work permits.", "Immigration lawyers complicate hiring."):
        assert any("outside the blog's scope" in p for p in run(CLEAN + s + "\n")), s


def test_ordinary_text_passes_the_banned_topics():
    assert run(CLEAN + "Contractors in Poland and Chile invoice monthly.\n") == []
    assert run(CLEAN + "The contractor pays the filing fee with a Visa card.\n") == []


def test_key_features_of_one_bullet_is_a_broken_card():
    """A publisher's edit: “a single one in a bulleted list, as if the cards were unfinished”."""
    md = CLEAN + "\n**Key features**\n\n- Stated operations across 40 countries\n"
    assert any("Key features" in p for p in run(md))


def test_key_features_of_two_bullets_passes():
    md = (CLEAN + "\n**Key features**\n\n- Stated operations across 40 countries\n"
          "- Documentation prepared with audit review in mind\n")
    assert run(md) == []


def test_card_separator_line_is_flagged():
    """The blog has no --- lines between cards: cards are separated by an H3 heading."""
    assert any("separator" in p for p in run(CLEAN + "\n---\n\n### Northwind\n"))


def test_industry_term_label_rule_stops_at_a_table_cell_boundary():
    """Neighbouring cells of a comparison table speak about different vendors."""
    row = ("| **Counterparty** | Northwind's entity signs; the top tier makes Northwind the party "
           "(Agent of Record) | One agreement template in Example Co covers every contractor |\n")
    assert run(CLEAN + row) == []


def test_industry_term_label_rule_still_catches_our_own_label():
    assert any("not an Example Co label" in p
               for p in run(CLEAN + "Example Co works as an Agent of Record here.\n"))


def test_industry_term_glossary_link_is_market_term_not_our_label():
    """A glossary link target names the site, not the company's label (it matters when the
    brand is spelled like the domain)."""
    text = ("An [Agent of Record](https://example.com/glossary/agent-of-record/) "
            "label does not settle worker status or the provider’s contractual scope.\n")
    assert not any("not an Example Co label" in p for p in run(CLEAN + text))


def test_industry_term_actual_self_label_is_caught_with_links_in_both_directions():
    glossary = "https://example.com/glossary/agent-of-record/"
    brand_first = f"Example Co acts as an [Agent of Record]({glossary}) here.\n"
    term_first = f"[Agent of Record]({glossary}) is how Example Co describes its service.\n"
    assert any("not an Example Co label" in p for p in run(CLEAN + brand_first))
    assert any("not an Example Co label" in p for p in run(CLEAN + term_first))


def test_ordered_list_broken_by_a_flush_left_paragraph():
    """Found by QA: the converter closes the list and the numbering on the site starts again."""
    md = CLEAN + "\n1. **First bench.**\n\nA paragraph with no indent.\n\n2. **Second bench.**\n"
    assert any("ordered list" in p for p in run(md))


def test_ordered_list_with_indented_continuation_passes():
    md = CLEAN + "\n1. **First.**\n\n   Indented body.\n\n2. **Second.**\n\n   Indented body.\n"
    assert run(md) == []


def test_six_column_table_reports_exact_header_line_and_width():
    header = "| Vendor | Scope | Coverage | Price | Limit | Evidence |"
    md = CLEAN + "\n" + header + "\n|---|---|---|---|---|---|\n| A | B | C | D | E | F |\n"
    found = [p for p in run(md) if "columns" in p]
    assert found == [f"line 5: table has 6 columns (no more than five); header: {header}"]


@pytest.mark.parametrize("header,separator", [
    ("| A | B | C | D | E |", "|---|---|---|---|---|"),
    ("A | B | C | D | E", "--- | :---: | ---: | :--- | ---"),
    (r"| A\|B | C | D | E | F |", "|---|---|---|---|---|"),
    (r"| A | B | C | D | E\|", "|---|---|---|---|---|"),
    ("| `A|B` | C | D | E | F |", "|---|---|---|---|---|"),
    ("| ``A`|B`` | C | D | E | F |", "|---|---|---|---|---|"),
    ("| A | B | C | D | `E|` |", "|---|---|---|---|---|"),
])
def test_five_actual_columns_allow_escaped_and_inline_code_pipes(header, separator):
    assert run(CLEAN + "\n" + header + "\n" + separator + "\n") == []


@pytest.mark.parametrize("header", [
    r"| A\|B | C | D | E | F | G |",
    "| `A|B` | C | D | E | F | G |",
    "| ``A`|B`` | C | D | E | F | G |",
    r"| A\\|B | C | D | E | F |",
    "| `A | B | C | D | E | F |",  # An unmatched backtick does not hide delimiters.
])
def test_six_real_columns_are_not_hidden_by_literal_pipe_syntax(header):
    md = CLEAN + "\n" + header + "\n|---|---|---|---|---|---|\n"
    assert any("6 columns" in problem for problem in run(md))


@pytest.mark.parametrize("opening,closing", [
    ("```markdown", "```"), ("~~~markdown", "~~~"),
    ("````markdown", "````"), ("~~~", "~~~~"),
])
def test_wide_table_examples_inside_fences_are_not_actual_tables(opening, closing):
    table = "| A | B | C | D | E | F |\n|---|---|---|---|---|---|\n"
    md = CLEAN + "\n" + opening + "\n" + table + closing + "\n\n" + table
    found = [p for p in run(md) if "columns" in p]
    assert len(found) == 1
    assert found[0].startswith("line 10: table has 6 columns")


def test_shorter_or_other_character_fences_do_not_close_a_code_example():
    md = CLEAN + "\n````markdown\n```\n~~~\n| A | B | C | D | E | F |\n|---|---|---|---|---|---|\n````\n"
    assert lint.wide_markdown_tables(md.splitlines()) == []


def test_non_tables_and_indented_code_do_not_trigger_width_gate():
    examples = [
        "| A | B | C | D | E | F |\nOrdinary prose.\n",
        "| A | B | C | D | E | F |\n|---|---|---|---|---|\n",  # Mismatched delimiters.
        "    | A | B | C | D | E | F |\n    |---|---|---|---|---|---|\n",
        "| A | B | C | D | E | F |\n| one | two | three | four | five | six |\n",
    ]
    for example in examples:
        assert lint.wide_markdown_tables(example.splitlines()) == []


def test_blockquote_table_counts_columns_but_quoted_fenced_example_does_not():
    table = "> | A | B | C | D | E | F |\n> |---|---|---|---|---|---|\n"
    assert len(lint.wide_markdown_tables(table.splitlines())) == 1
    assert lint.wide_markdown_tables(("> ~~~\n" + table + "> ~~~\n").splitlines()) == []


def test_every_wide_table_is_reported_including_empty_header_parameters():
    md = ("| A | B | C | D | E | F | G |\n|---|---|---|---|---|---|---|\n\n"
          "| | | | | | |\n|---|---|---|---|---|---|\n")
    found = lint.wide_markdown_tables(md.splitlines())
    assert len(found) == 2
    assert found[0].startswith("line 1: table has 7 columns")
    assert found[1].startswith("line 4: table has 6 columns")
