"""The internal package is built from the run artefacts, not written by hand."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_internal_package as bip  # noqa: E402

EVIDENCE = """# Evidence

| ID | Claim | Section | Source | Tier |
|---|---|---|---|---|
| FD-01 | Example Co charges from $25 per active contractor per month | pricing | https://example.com/pricing/ | vendor |
| DL-03 | Fabrikam publishes a COR tier | cards | https://www.fabrikam.example/pricing/ | vendor docs |
| DEV-03A | Suffixed evidence ID | cards | https://example.com/ | vendor docs |
| METHOD-01 | Longer evidence prefix | method | https://www.irs.gov/ | primary |
| vendor-northwind | Descriptive vendor evidence ID | cards | https://www.northwind.example/ | vendor docs |
| us-i9-timing | Descriptive legal evidence ID | compliance | https://www.uscis.gov/ | primary |
| A01 | Short numbered evidence ID | payroll | https://www.nacha.org/ | primary |
| A05b | Suffixed short evidence ID | payroll | https://www.frbservices.org/ | primary |
| C01 | Another short numbered evidence ID | status | https://www.gov.uk/ | primary |
| bad | not a row of the source table | x | y | z |

## needs_manual_confirmation
- Hooli list price: the page returns 403.
"""


def test_source_rows_take_only_evidence_ids():
    rows = bip.source_rows(EVIDENCE)
    assert [r[0] for r in rows] == [
        "FD-01",
        "DL-03",
        "DEV-03A",
        "METHOD-01",
        "vendor-northwind",
        "us-i9-timing",
        "A01",
        "A05b",
        "C01",
    ]


def test_source_rows_carry_url():
    rows = dict((r[0], r[2]) for r in bip.source_rows(EVIDENCE))
    assert rows["FD-01"] == "https://example.com/pricing/"


def test_needs_manual_confirmation_section_extracted():
    block = bip.section(EVIDENCE, "needs_manual_confirmation")
    assert "403" in block


def test_missing_section_is_empty_not_error():
    assert bip.section(EVIDENCE, "no such section") == ""


def test_current_manual_confirmation_heading_is_extracted():
    evidence = """# Evidence

## Needs manual confirmation / use restrictions
- Confirm the target-country entity.

## Source ledger and failures
- Source list.
"""
    block = bip.section(evidence, r"Needs manual confirmation\s*/\s*use restrictions")
    assert "target-country entity" in block
    assert "Source list" not in block
