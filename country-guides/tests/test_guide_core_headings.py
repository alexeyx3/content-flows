"""Country-specific reader headings must retain the ordered core-topic checks."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_guide
from common import h1


CASES = [
    ("Peru", "peru", "PE", "eor", [
        "What an employer of record does in Peru",
        "Which Peruvian legal model supports the arrangement?",
        "Check the employing entity and the applicable registration",
        "Who signs what and who directs the worker",
        "From provider checks to the first working day",
        "What an EOR quote must include, line by line",
        "Where the model runs out: duration, tax presence and rights",
        "When you can hire without an EOR",
        "Compare an EOR, your own employer operation and independent services",
        "Questions to settle before choosing a Peru provider",
        "Questions people actually ask",
    ]),
    ("New Zealand", "new-zealand", "NZ", "contractors", [
        "The gateway test and common law decide contractor status",
        "Tax thresholds do not decide employment status",
        "Check the contractor’s identity, business form and tax registrations",
        "The services agreement must match how the work is done",
        "Invoice evidence depends on the supply value and buyer",
        "Bank processing and international receipt follow different clocks",
        "Agree due dates and separate late charges from court interest",
        "What breaks between scoping the work and closing the record",
        "What a mistake costs depends on the duty and liable party",
        "Direct services, an intermediary and employment solve different needs",
        "One contractor versus ten changes the records and management burden",
        "Who works with contractors in New Zealand",
        "Questions people actually ask",
    ]),
    ("New Zealand", "new-zealand", "NZ", "eor", [
        "What an employer of record does in New Zealand",
        "The legal position of the employer of record",
        "Check the legal employer and the applicable accreditation",
        "Who signs and who directs the work",
        "Onboarding before the first payroll",
        "Read the quote line by line",
        "Where the model leaves exposure",
        "When you do not need an EOR",
        "Compare direct employment and independent services",
        "Choosing a provider",
        "Questions people actually ask",
    ]),
    ("Taiwan", "taiwan", "TW", "eor", [
        "What an employer of record does in Taiwan",
        "Taiwan dispatch rules govern the actual working arrangement",
        "Check the employing entity and its regulated activities",
        "Who signs, directs the work and holds the records",
        "Start-date planning begins before a client interview",
        "Read the Taiwan EOR quote line by line",
        "Assignment end, dismissal and client liability are separate questions",
        "When a Taiwan EOR adds no useful employer function",
        "Compare direct employment, administration and independent services",
        "Ask the provider for documents that resolve Taiwan-specific risks",
        "Questions people actually ask",
    ]),
]


def core_errors(country, slug, iso, page, titles):
    job = {"country": country, "slug": slug, "iso": iso}
    text = f"# {h1(country, page, iso)}\n\nOpening.\n\n"
    text += "\n\n".join(f"## {title}\n\nExplanation." for title in titles)
    text += "\n\n## Sources\n\n1. Example. Reference. Accessed 15 November 2026.\n"
    errors, _ = check_guide.check_page(text, page, job, None)
    return [e for e in errors if e.startswith("core section")]


@pytest.mark.parametrize("country,slug,iso,page,titles", CASES)
def test_country_specific_core_headings_accepted(country, slug, iso, page, titles):
    assert not core_errors(country, slug, iso, page, titles)


@pytest.mark.parametrize("country,slug,iso,page,titles", CASES)
def test_missing_or_reordered_core_topics_still_block(country, slug, iso, page, titles):
    index = 0 if page == "contractors" else 2
    assert core_errors(country, slug, iso, page, titles[:index] + titles[index + 1:])
    swapped = list(titles)
    swapped[index], swapped[index + 1] = swapped[index + 1], swapped[index]
    assert core_errors(country, slug, iso, page, swapped)


@pytest.mark.parametrize("index", [4, 8])
def test_peru_onboarding_and_alternatives_still_required(index):
    country, slug, iso, page, titles = CASES[0]
    assert core_errors(country, slug, iso, page, titles[:index] + titles[index + 1:])
