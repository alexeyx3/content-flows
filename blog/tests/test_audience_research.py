import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


REDDIT = load_script("collect_reddit_signals.py")
LINKS = load_script("check_research_links.py")


def test_reddit_queries_are_bounded_and_keep_topic():
    queries = REDDIT.build_queries("Fabrikam alternatives")
    assert len(queries) == 2
    assert all("site:reddit.com" in query for query in queries)
    assert all("Fabrikam alternatives" in query for query in queries)


def test_reddit_records_filter_and_deduplicate_threads():
    rows = [
        (
            "q1",
            [
                {
                    "position": "1",
                    "url": "https://www.reddit.com/r/startups/comments/abc123/example/?utm_source=x",
                    "title": "A <b>real</b> question",
                    "snippet": "A practical problem",
                },
                {
                    "position": "2",
                    "url": "https://example.com/not-reddit",
                    "title": "Ignore",
                    "snippet": "Ignore",
                },
            ],
        ),
        (
            "q2",
            [
                {
                    "position": "3",
                    "url": "https://old.reddit.com/r/startups/comments/abc123/example/",
                    "title": "Duplicate",
                    "snippet": "Duplicate",
                }
            ],
        ),
    ]
    records = REDDIT.build_records(rows)
    assert len(records) == 1
    assert records[0]["url"] == "https://www.reddit.com/r/startups/comments/abc123/example/"
    assert records[0]["search_queries"] == ["q1", "q2"]
    assert records[0]["title"] == "A real question"


def test_reddit_packet_states_discovery_boundary():
    packet = REDDIT.render_packet("topic", "US", "2026-09-18", ["q"], [])
    assert "not verified facts" in packet
    assert "independent" in packet
    assert "Do not manufacture audience signals" in packet


def test_required_research_links_are_checked_by_exact_evidence_url():
    evidence = """| claim_id | claim | section | source_url | article_link | decision_use |
|---|---|---|---|---|---|
| R1 | Useful finding | Choice | https://study.example/report | required | changes choice |
| V1 | Vendor feature | Card | https://vendor.example/ | forbidden | background |
"""
    article = "Use the [study](https://study.example/report) before deciding."
    missing, links = LINKS.check(evidence, article)
    assert missing == []
    assert links == ["https://study.example/report"]


def test_wrong_research_url_does_not_pass():
    evidence = """| claim_id | claim | section | source_url | article_link | decision_use |
|---|---|---|---|---|---|
| R1 | Useful finding | Choice | https://study.example/right | required | changes choice |
"""
    missing, _ = LINKS.check(evidence, "See [research](https://study.example/wrong).")
    assert [row["claim_id"] for row in missing] == ["R1"]


def test_new_source_policy_requires_one_link_in_final_sources(tmp_path):
    (tmp_path / "job.yaml").write_text("source_policy_version: 1\n")
    evidence = """| claim_id | source_url | article_link |
|---|---|---|
| R1 | https://study.example/report | required |
"""
    article = "# Title\n\nAccording to Study, this matters.\n\n## Sources\n\n- [Study report](https://study.example/report)\n"
    assert LINKS.source_policy_errors(tmp_path, evidence, article) == []
    duplicate = article.replace("According to Study", "See [Study](https://study.example/report). According to Study")
    assert any("outside Sources" in error for error in LINKS.source_policy_errors(tmp_path, evidence, duplicate))
    missing = article.replace("## Sources", "## References")
    assert any("missing" in error for error in LINKS.source_policy_errors(tmp_path, evidence, missing))
