from pathlib import Path

from scripts.validate_research_discovery import validate


PACKET = """# Discovery

## Decision map

Which document changes the reader's decision? Check the controlling definition.

## Search log

| channel | query | outcome | note |
|---|---|---|---|
| primary | official control definition | found | R-01 applies to the named rule. |
| scholarly | control rights investor reporting | none | No transferable study found. |
| social | site:linkedin.com/posts/ affiliate agreements | found | Two posts raise a signing question; no claim copied. |

## Insight cards

R-01: the official rule changes which relationship to test.

## External quote candidates

None: indexed posts were discovery leads only.
"""


def test_new_job_needs_a_traced_discovery_packet(tmp_path: Path) -> None:
    job = tmp_path / "job"
    job.mkdir()
    (job / "job.yaml").write_text("workflow_version: 2\nresearch_discovery_version: 1\n")
    assert any("research.discovery.md" in item for item in validate(job))
    (job / "research.discovery.md").write_text(PACKET)
    assert validate(job) == []


def test_missing_lane_and_unexplained_search_fail(tmp_path: Path) -> None:
    job = tmp_path / "job"
    job.mkdir()
    (job / "job.yaml").write_text("workflow_version: 2\nresearch_discovery_version: 1\n")
    (job / "research.discovery.md").write_text(
        PACKET.replace("| scholarly | control rights investor reporting | none | No transferable study found. |\n", "")
        .replace("| social | site:linkedin.com/posts/ affiliate agreements | found | Two posts raise a signing question; no claim copied. |",
                 "| social | site:linkedin.com/posts/ affiliate agreements | found | |")
    )
    problems = validate(job)
    assert any("scholarly" in item for item in problems)
    assert any("social needs a result" in item for item in problems)


def test_existing_jobs_do_not_require_new_packet(tmp_path: Path) -> None:
    job = tmp_path / "job"
    job.mkdir()
    (job / "job.yaml").write_text("workflow_version: 2\n")
    assert validate(job) == []
