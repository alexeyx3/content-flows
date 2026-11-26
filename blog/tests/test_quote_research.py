import json
from pathlib import Path

from scripts.validate_quote_research import validate


def packet() -> dict:
    return {
        "version": 1,
        "search_log": [
            {"channel": "x", "decision_refs": ["Q-01"], "query": "site:x.com practitioner decision",
             "outcome": "none", "note": "No directly readable original."},
            {"channel": "linkedin", "decision_refs": ["Q-01"],
             "query": "site:linkedin.com/posts practitioner decision", "outcome": "blocked",
             "note": "Indexed lead only.", "access_problem": "Full original unavailable."},
            {"channel": "web_search", "decision_refs": ["Q-01", "Q-02"],
             "query": "practitioner interview decision", "outcome": "found",
             "note": "Signed interview located."},
            {"channel": "original_source", "source_kind": "interview",
             "decision_refs": ["Q-01"], "query": "original interview full text",
             "outcome": "found", "note": "Full Q&A read."},
        ],
        "coverage_note": "Q-01 benefits from practitioner perspective; Q-02 is a factual rule.",
        "candidates": [{
            "id": "XQ-01", "status": "verified_original", "decision_refs": ["Q-01"],
            "source_kind": "interview", "source_url": "https://example.org/interview",
            "source_title": "Interview", "source_access": "full_original",
            "source_location": "Answer 3", "publication_date": "2026-01-15",
            "author_name": "Jane Smith", "author_role": "Practitioner",
            "quote": "A short decision insight.", "context": "Response about onboarding.",
            "decision_value": "Explains when the default process fails.",
            "source_scope": "Practitioner view, not a population estimate.",
        }],
        "no_verified_quote_reason": "",
    }


def make_job(tmp_path: Path, data: dict | None = None, enabled: bool = True) -> Path:
    job = tmp_path / "job"
    job.mkdir(exist_ok=True)
    (job / "job.yaml").write_text("research_v3_version: 1\n" if enabled else "workflow_version: 2\n")
    (job / "research_map.json").write_text(json.dumps({
        "version": 1,
        "decisions": [
            {"id": "Q-01", "question": "Why?", "reader_action": "Choose", "population": "Buyers", "outcome": "Fit"},
            {"id": "Q-02", "question": "When?", "reader_action": "Check", "population": "Buyers", "outcome": "Timing"},
        ],
    }))
    if data is not None:
        (job / "research.quotes.json").write_text(json.dumps(data))
    return job


def test_new_job_requires_packet_and_accepts_verified_original(tmp_path: Path) -> None:
    job = make_job(tmp_path)
    assert any("research.quotes.json is required" in item for item in validate(job))
    (job / "research.quotes.json").write_text(json.dumps(packet()))
    assert validate(job) == []


def test_no_quote_is_allowed_with_real_search_and_reason(tmp_path: Path) -> None:
    data = packet()
    data["candidates"] = []
    data["no_verified_quote_reason"] = "Original interviews found no distinct insight; social originals inaccessible."
    assert validate(make_job(tmp_path, data)) == []


def test_metadata_or_snippet_cannot_become_a_quote(tmp_path: Path) -> None:
    data = packet()
    data["candidates"][0]["source_access"] = "search_snippet"
    data["candidates"][0]["source_url"] = "https://www.google.com/search?q=onboarding"
    errors = validate(make_job(tmp_path, data))
    assert any("full_original" in error for error in errors)
    assert any("search result" in error for error in errors)


def test_unverified_lead_cannot_contain_quote(tmp_path: Path) -> None:
    data = packet()
    data["candidates"][0]["status"] = "lead"
    data["candidates"][0]["reason"] = "Full source unavailable."
    data["no_verified_quote_reason"] = "Only an inaccessible social lead was found."
    assert any("cannot carry exact quote" in error for error in validate(make_job(tmp_path, data)))
    data["candidates"][0].pop("quote")
    assert validate(make_job(tmp_path, data)) == []


def test_search_channels_and_decision_ids_are_checked(tmp_path: Path) -> None:
    data = packet()
    data["search_log"] = [row for row in data["search_log"] if row["channel"] != "x"]
    data["candidates"][0]["decision_refs"] = ["Q-99"]
    errors = validate(make_job(tmp_path, data))
    assert any("needs a x search" in error for error in errors)
    assert any("must name research_map.json Q-IDs" in error for error in errors)


def test_verified_quote_needs_date_context_and_word_limit(tmp_path: Path) -> None:
    data = packet()
    data["candidates"][0]["publication_date"] = "2026-02-30"
    data["candidates"][0]["context"] = ""
    data["candidates"][0]["quote"] = " ".join(["word"] * 26)
    errors = validate(make_job(tmp_path, data))
    assert any("publication_date" in error for error in errors)
    assert any("needs context" in error for error in errors)
    assert any("exceeds 25 words" in error for error in errors)


def test_social_quote_requires_direct_original_post_url(tmp_path: Path) -> None:
    data = packet()
    data["candidates"][0]["source_kind"] = "x_post"
    assert any("direct post URL" in error for error in validate(make_job(tmp_path, data)))
    data["candidates"][0]["source_url"] = "https://x.com/practitioner/status/123456"
    assert validate(make_job(tmp_path, data)) == []


def test_old_job_has_no_new_gate(tmp_path: Path) -> None:
    job = make_job(tmp_path, enabled=False)
    (job / "research.quotes.json").unlink(missing_ok=True)
    assert validate(job) == []
