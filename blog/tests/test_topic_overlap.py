import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from scripts import topic_overlap


def test_published_catalog_reads_every_small_page(monkeypatch):
    pages = []

    def api(path):
        query = parse_qs(urlsplit(path).query)
        page = int(query['pagination[page]'][0])
        pages.append(page)
        assert query['pagination[pageSize]'] == ['40']
        return {'data': [{'id': page, 'slug': f'article-{page}', 'publishedAt': '2026-11-22',
                          'content': '<h2>Policy</h2>'}], 'meta': {'pagination': {'pageCount': 2}}}

    monkeypatch.setitem(sys.modules, 'strapi_publish', SimpleNamespace(api=api))
    results = topic_overlap.published_articles()
    assert pages == [1, 2]
    assert [(row['slug'], row['headings']) for row in results] == [('article-1', ['Policy']), ('article-2', ['Policy'])]


def sample_rows():
    return [
        {"key": "old", "kind": "published", "url": "https://example.com/blog/best-contractor-management-software/",
         "title": "Best Contractor Management Software", "slug": "best-contractor-management-software",
         "summary": "Compare contractor management tools for businesses", "headings": ["Fabrikam", "Tyrell"]},
        {"key": "peo", "kind": "published", "url": "https://example.com/blog/best-peos-for-small-businesses/",
         "title": "Best PEOs for Small Businesses", "slug": "best-peos-for-small-businesses",
         "summary": "PEO selection for small US companies", "headings": ["Vandelay", "Cyberdyne"]},
        {"key": "remote", "kind": "published", "url": "https://example.com/blog/remote-onboarding/",
         "title": "Remote onboarding guide", "slug": "remote-onboarding",
         "summary": "Onboarding workflow", "headings": []},
    ]


def test_counted_listicle_retrieves_existing_core_query(monkeypatch):
    monkeypatch.setattr(topic_overlap, "embeddings", lambda texts: [[1.0, 0.0]] * len(texts))
    hits, status = topic_overlap.find_candidates("10 Best Contractor Management Software", "", sample_rows())
    assert hits[0]["key"] == "old"
    assert hits[0]["exact_phrase"] is True
    assert status.startswith("ready")


def test_semantic_scores_can_retrieve_low_lexical_match(monkeypatch):
    rows = sample_rows()
    monkeypatch.setattr(topic_overlap, "embeddings", lambda texts: [
        [1, 0], [0.1, 0.9], [0.9, 0.1], [0, 1]
    ])
    hits, status = topic_overlap.find_candidates("Startup co-employment provider", "", rows)
    assert next(hit for hit in hits if hit["key"] == "peo")["embedding"] > 0.9
    assert status.startswith("ready")


def test_decision_requires_matching_query_and_reason(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(topic_overlap, "REPORTS", tmp_path)
    path = topic_overlap.report_path("b-123", "resolved")
    path.write_text(json.dumps({"cluster_id": "b-123", "stage": "resolved",
                                "topic": "Best PEO for Startups", "keyword": "best peo for startups",
                                "catalog_fingerprint": "abc", "candidates": []}), encoding="utf-8")
    assert topic_overlap.decision_errors("b-123", "resolved", "Best PEO for Startups", "best peo for startups")
    topic_overlap.decide("b-123", "A small-business PEO list already exists, but this article would focus on venture-backed founders.", "resolved")
    assert topic_overlap.decision_errors("b-123", "resolved", "Best PEO for Startups", "best peo for startups") == []
    assert topic_overlap.decision_errors("b-123", "resolved", "Best PEO for Startups", "peo for small business")


def test_embedding_cache_avoids_reembedding_catalog(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(topic_overlap, "EMBEDDING_CACHE", tmp_path / "vectors.json")
    calls = []

    def fake_vectors(texts):
        calls.append(texts)
        return [[float(i), 1.0] for i in range(len(texts))]

    monkeypatch.setattr(topic_overlap, "compute_local_vectors", fake_vectors)
    first = topic_overlap.embeddings(["first", "second"])
    assert topic_overlap.embeddings(["first", "second"]) == first
    assert len(calls) == 1
