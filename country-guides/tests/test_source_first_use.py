"""First use includes attributed prose and compound table citations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import order_sources as sources


def ordered_urls(body, entries):
    text = '# Guide\n\n' + body + '\n\n## Sources\n\n' + '\n'.join(entries)
    return [sources.LINK.search(item)[1] for item in sources.ordered(text)]


def entry(n, publisher, title, slug, trailing=''):
    return f'{n}. {publisher}. [{title}](https://example.gov/{slug}). Accessed 15 November 2026.{trailing}'


def test_narrative_publisher_mentions_are_not_visible_citations():
    entries = [entry(1, 'Ministry of Justice', 'Calculator', 'calculator'),
               entry(2, 'Lane Neave', 'Gateway', 'gateway'),
               entry(3, 'ANZ Bank New Zealand', 'Transfers', 'transfers')]
    body = 'Law firm Lane Neave explains the exception. ANZ’s guidance covers charges.\n\n[Calculator](https://example.gov/calculator).'
    assert ordered_urls(body, entries) == ['https://example.gov/calculator', 'https://example.gov/gateway', 'https://example.gov/transfers']


def test_ambiguous_publisher_cannot_choose_an_original():
    entries = [entry(1, 'Ministry of Justice', 'Calculator', 'calculator'),
               entry(2, 'Lane Neave', 'Gateway', 'gateway'),
               entry(3, 'Lane Neave', 'Other guidance', 'other')]
    body = 'Lane Neave explains the exception. [Calculator](https://example.gov/calculator).'
    assert ordered_urls(body, entries)[0] == 'https://example.gov/calculator'


def test_compound_sources_cell_retains_left_to_right_order_and_trailing_alias():
    entries = [entry(1, 'Business.govt.nz', 'Payment terms (Business payment terms)', 'terms'),
               entry(2, 'Companies Office', 'Company setup (Companies setup)', 'company'),
               entry(3, 'Business.govt.nz', 'Sole trader', 'sole', ' (Business sole trader)'),
               entry(4, 'Business.govt.nz', 'Contracts (Business contracts)', 'contracts')]
    body = '| Check | Evidence |\n|---|---|\n| Identity | Confirm identity. Sources: Business sole trader; Companies setup. |\n| Agreement | Sources: Business contracts; Business payment terms. |'
    assert ordered_urls(body, entries) == ['https://example.gov/sole', 'https://example.gov/company', 'https://example.gov/contracts', 'https://example.gov/terms']


def test_terminal_table_alias_is_visible_even_after_the_substantive_sentence():
    entries = [entry(1, 'Larkin Partners', 'Article', 'article'),
               entry(2, 'MOJ', 'Original Act', 'act', ' (Labor Insurance Act)')]
    body = '| Risk | Amount |\n|---|---|\n| Insurance | Four times the premiums plus loss. Labor Insurance Act. |'
    assert ordered_urls(body, entries) == ['https://example.gov/act', 'https://example.gov/article']


def test_plain_vendor_originals_follow_their_visible_ranking_names_not_link_type():
    entries = [entry(1, 'Official', 'Supporting original', 'uncited'),
               '2. Northwind. First page (northwind.example/a). Accessed 15 November 2026.',
               '3. Northwind. Second page (northwind.example/b). Accessed 15 November 2026.',
               '4. Globex Corporation. Guide (globex.example/a). Accessed 15 November 2026.']
    text = '# Guide\n\n| Vendor | Model |\n|---|---|\n| Globex | Platform |\n| Northwind | Platform |\n\n## Sources\n\n' + '\n'.join(entries)
    ordered = sources.ordered(text)
    assert [sources.ITEM.sub('', x).split('. ', 1)[0] for x in ordered] == ['Globex Corporation', 'Northwind', 'Northwind', 'Official']


def test_renamed_vendor_originals_follow_current_or_legacy_vendor_brand():
    # config/vendors.json maps the publisher «Vandelay» to the ranking name «Vandelay Workforce».
    entries = ['1. Tyrell. Agent of Record (tyrell.example/aor/). Accessed 16 November 2026.',
               '2. Vandelay. Country guide (vandelay.example/peru/). Accessed 16 November 2026.',
               '3. Contoso. Country guide (contoso.example/peru/). Accessed 16 November 2026.',
               '4. Vandelay. Contractor terms (vandelay.example/faq/). Accessed 16 November 2026.']
    for brand in ['Vandelay Workforce', 'Vandelay']:
        body = f'| Vendor | Model |\n|---|---|\n| Contoso | Platform |\n| {brand} | Platform |\n| Tyrell | Agent of Record |'
        text = '# Guide\n\n' + body + '\n\n## Sources\n\n' + '\n'.join(entries)
        assert sources.ordered(text) == [entries[2], entries[1], entries[3], entries[0]]


def test_explicit_source_alias_in_prose_precedes_later_ranking():
    entries = ['1. Northwind. Page (northwind.example/a). Accessed 15 November 2026.',
               entry(2, 'Ministry', 'Union guidance (MOL union insurance guidance)', 'union')]
    text = '# Guide\n\nThe category is separate. Source: MOL union insurance guidance.\n\n| Vendor |\n|---|\n| Northwind |\n\n## Sources\n\n' + '\n'.join(entries)
    assert sources.ordered(text)[0] == entries[1]


def test_unique_parenthetical_document_alias_precedes_later_link():
    entries = [entry(1, 'Ministry', 'Law', 'law'),
               entry(2, 'PRONABEC', 'Graduate report', 'graduates', ' (PRONABEC graduate earnings)')]
    body = 'The cohort is bounded (PRONABEC graduate earnings). [Law](https://example.gov/law).'
    assert ordered_urls(body, entries) == ['https://example.gov/graduates', 'https://example.gov/law']


def test_parenthetical_publisher_name_is_not_a_document_alias():
    entries = [entry(1, 'Ministry', 'Law', 'law'),
               entry(2, 'PRONABEC', 'Graduate report', 'graduates', ' (PRONABEC graduate earnings)')]
    body = 'The publisher (PRONABEC) describes the cohort. [Law](https://example.gov/law).'
    assert ordered_urls(body, entries) == ['https://example.gov/law', 'https://example.gov/graduates']


def test_ambiguous_parenthetical_document_alias_does_not_select_an_original():
    entries = [entry(1, 'Ministry', 'Law', 'law'),
               entry(2, 'PRONABEC', 'Graduate report', 'graduates', ' (Graduate earnings)'),
               entry(3, 'PRONABEC', 'Other cohort', 'other', ' (Graduate earnings)')]
    body = 'The cohort is bounded (Graduate earnings). [Law](https://example.gov/law).'
    assert ordered_urls(body, entries) == ['https://example.gov/law', 'https://example.gov/graduates', 'https://example.gov/other']


def test_generic_word_in_a_description_is_not_the_brand_citation():
    # «Umbrella» is both a vendor name and an ordinary word in other vendors' descriptions.
    entries = ['1. Umbrella. Page (umbrella.example/a). Accessed 15 November 2026.',
               '2. Fabrikam. Page (fabrikam.example/a). Accessed 15 November 2026.',
               '3. Initech. Page (initech.example/a). Accessed 15 November 2026.']
    text = '# Guide\n\n| Vendor | Model |\n|---|---|\n| Fabrikam | Umbrella company marketplace |\n| Initech | Taiwan umbrella directory |\n| Umbrella | Marketplace |\n\n## Sources\n\n' + '\n'.join(entries)
    assert [sources.parts(x)[0] for x in sources.ordered(text)] == ['fabrikam', 'initech', 'umbrella']
