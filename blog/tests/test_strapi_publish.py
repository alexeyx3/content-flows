"""Draft upload: validation of fields, the slug, and that the body survives the sanitizer."""
import sys
import json
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import strapi_publish as sp  # noqa: E402

GOOD = {
    "title": "Как устроены документы по подрядчикам",
    "slug": "contractor-documentation-basics",
    "metaTitle": "Документы по подрядчикам: что нужно собрать",
    "metaDescription": "Короткое описание страницы для поисковой выдачи." * 2,
    "summary": "Краткое содержание статьи для карточки в листинге." * 3,
}


def test_valid_meta_passes():
    assert sp.validate_meta(GOOD) == []


def test_checked_draft_publishes_once_and_blocks_title_drift(tmp_path, monkeypatch):
    job = tmp_path / 'job'
    job.mkdir()
    (job / 'job.yaml').write_text('workflow_version: 2\narticle_type: guide\n')
    (job / 'out').mkdir()
    html = '<p>Approved body.</p>'
    (job / 'out/article.html').write_text(html)
    receipt = job / 'cover.json'
    receipt.write_text(json.dumps({'status': 'complete', 'target_id': 17, 'locale': 'en',
                                  'media_id': 80, 'title': GOOD['title'], 'slug': GOOD['slug']}))
    monkeypatch.setattr(sys, 'argv', ['strapi', '--job', str(job), '--update', '17', '--publish',
                                     '--cover-receipt', str(receipt)])
    monkeypatch.setattr(sp, 'export_errors', lambda *args: [])
    monkeypatch.setattr(sp, 'read_meta', lambda *args: GOOD)
    monkeypatch.setattr(sp, 'read_author', lambda *args: 'writer')
    monkeypatch.setattr(sp, 'resolve_author_id', lambda *args: 2)
    monkeypatch.setattr(sp, 'html_survives_sanitizer', lambda *args: True)
    article = {**GOOD, 'content': html, 'cover': {'id': 80}, 'locale': 'en', 'publishedAt': None}
    writes = []

    def api(path, method='GET', body=None):
        if method == 'PUT':
            assert path == '/articles/17'
            writes.append(body['data'])
            article.update(body['data'])
        return {'data': {'id': 17, 'attributes': article}}

    monkeypatch.setattr(sp, 'api', api)
    sp.main()
    sp.main()
    assert len(writes) == 1 and writes[0]['publishedAt']
    assert json.loads((job / 'out/strapi_record.json').read_text())['published'] is True
    article['metaTitle'] = 'Different title in CMS'
    with pytest.raises(SystemExit, match='readback differs.*metaTitle'):
        sp.main()
    assert len(writes) == 1


@pytest.mark.parametrize('method', ['GET', 'PUT'])
def test_api_retries_interrupted_reads_only(monkeypatch, method):
    attempts = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            if len(attempts) == 1:
                raise ConnectionResetError('response stream interrupted')
            return b'{"data": {"id": 1}}'

    def open_response(req, timeout):
        attempts.append(req.get_method())
        return Response()

    monkeypatch.setattr(sp, 'token', lambda: 'test-token')
    monkeypatch.setattr(sp.urllib.request, 'urlopen', open_response)
    if method == 'GET':
        assert sp.api('/articles/1', method) == {'data': {'id': 1}}
        assert attempts == ['GET', 'GET']
    else:
        with pytest.raises(ConnectionResetError):
            sp.api('/articles/1', method)
        assert attempts == ['PUT']


def test_meta_title_over_70_rejected():
    bad = dict(GOOD, metaTitle="я" * 71)
    assert any("metaTitle" in e for e in sp.validate_meta(bad))


def test_meta_description_over_200_rejected():
    bad = dict(GOOD, metaDescription="я" * 201)
    assert any("metaDescription" in e for e in sp.validate_meta(bad))


def test_summary_over_400_rejected():
    bad = dict(GOOD, summary="я" * 401)
    assert any("summary" in e for e in sp.validate_meta(bad))


def test_non_latin_slug_rejected():
    bad = dict(GOOD, slug="документы-подрядчиков")
    assert any("slug" in e for e in sp.validate_meta(bad))


def test_uppercase_slug_rejected():
    bad = dict(GOOD, slug="Contractor-Documentation")
    assert any("slug" in e for e in sp.validate_meta(bad))


def test_missing_title_rejected():
    bad = dict(GOOD)
    bad.pop("title")
    assert any("title" in e for e in sp.validate_meta(bad))


def test_payload_is_a_draft():
    """Never publish under any condition.

    Verified on production: the ABSENCE of publishedAt in the request body does NOT
    create a draft: Strapi sets the date itself, and the record goes into the public API and the
    site map. A draft is obtained only with an explicit publishedAt: null.
    """
    payload = sp.build_payload(GOOD, "<p>текст</p>", author_id=5, editor_id=4)
    assert "publishedAt" in payload["data"], "the field must be present explicitly"
    assert payload["data"]["publishedAt"] is None
    assert payload["data"]["author"] == 5
    assert payload["data"]["editors"] == [4]
    assert payload["data"]["contentHtml"] == "<p>текст</p>"


def test_payload_has_no_tags():
    payload = sp.build_payload(GOOD, "<p>текст</p>", author_id=5, editor_id=4)
    assert "tags" not in payload["data"]


def test_payload_skips_empty_meta_fields():
    thin = {"title": "Заголовок", "slug": "zagolovok"}
    data = sp.build_payload(thin, "<p>т</p>", author_id=5, editor_id=4)["data"]
    assert "metaTitle" not in data and "summary" not in data


def test_html_that_sanitizer_would_change_is_rejected():
    assert sp.html_survives_sanitizer("<p>чисто</p>\n") is True
    assert sp.html_survives_sanitizer("<h1>нельзя</h1>\n") is False


def test_authors_map_has_ids_for_working_authors():
    import json
    m = json.loads((ROOT / "config" / "blog-authors.json").read_text(encoding="utf-8"))
    assert m["jane.doe"], "the editor must have an id: it is set on every article"
    assert m["john.roe"]


def test_slug_free_when_api_says_not_found(monkeypatch):
    """Verified on production: the ordinary /articles?filters[slug] does NOT see drafts:
    the controller forces publicationState=live. Slug occupancy is requested through findBySlug,
    which goes to the database directly."""
    import urllib.error

    def not_found(path, *a, **kw):
        assert path.endswith("/findBySlug"), f"the findBySlug route is required, not {path}"
        raise urllib.error.HTTPError(path, 404, "Not Found", {}, None)

    monkeypatch.setattr(sp, "api", not_found)
    assert sp.slug_is_free("nikem-ne-zanyat") is True


def test_slug_taken_when_draft_exists(monkeypatch):
    monkeypatch.setattr(sp, "api", lambda path, *a, **kw: {"data": {"id": 217, "slug": "x"}})
    assert sp.slug_is_free("x") is False


def test_meta_parsed_from_file(tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "meta.md").write_text(
        "# Мета\n\n- title: Заголовок статьи\n- slug: article-slug\n"
        "- metaTitle: Заголовок для выдачи\n- metaDescription: Описание\n- summary: Саммари\n",
        encoding="utf-8")
    meta = sp.read_meta(tmp_path)
    assert meta["title"] == "Заголовок статьи"
    assert meta["slug"] == "article-slug"
    assert meta["summary"] == "Саммари"


def test_author_accepts_quoted_and_unquoted_yaml_scalars(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    path = job / "job.yaml"
    path.write_text('author: "john.roe"  # required\n', encoding="utf-8")
    assert sp.read_author(job) == "john.roe"
    path.write_text("author: jane.doe\n", encoding="utf-8")
    assert sp.read_author(job) == "jane.doe"


# --- publication from the pipeline: allowed, only with an explicit flag ---

def test_default_payload_is_a_draft():
    """Without the flag the field stays an explicit null: otherwise Strapi sets the date itself."""
    payload = sp.build_payload({"title": "T", "slug": "t"}, "<p>x</p>", 5, 4)
    assert payload["data"]["publishedAt"] is None


def test_publish_flag_sets_iso_timestamp():
    payload = sp.build_payload({"title": "T", "slug": "t"}, "<p>x</p>", 5, 4, publish=True)
    stamp = payload["data"]["publishedAt"]
    assert stamp and stamp.endswith("Z") and "T" in stamp
    assert stamp[:4].isdigit()


def test_year_in_slug_rejected():
    """Articles once went out with a slug like "...-alternatives-2026": an address with a year
    has to be rewritten every January."""
    errors = sp.validate_meta({"title": "T", "slug": "oscorp-alternatives-2026"})
    assert any("year" in e for e in errors)


def test_year_free_slug_passes():
    assert sp.validate_meta({"title": "T", "slug": "oscorp-alternatives"}) == []


def test_digits_that_are_not_a_year_still_pass():
    assert sp.validate_meta({"title": "T", "slug": "top-10-contractor-platforms"}) == []


def test_competitor_alternatives_slug_has_no_suffix():
    errors = sp.validate_meta({
        "title": "Umbrella Alternatives for Contractor Operations",
        "slug": "umbrella-alternatives-contractor-operations",
    }, article_type="listicle")
    assert any("nothing after alternatives" in error for error in errors)


def test_competitor_alternatives_slug_passes():
    assert sp.validate_meta({
        "title": "Umbrella Alternatives for Contractor Operations",
        "slug": "umbrella-alternatives",
    }, article_type="listicle") == []


def test_guide_title_ending_rules_and_alternatives_allows_descriptive_slug():
    assert sp.validate_meta({
        "title": "Non-Compete Agreements for Contractors: Rules and Alternatives",
        "slug": "non-compete-agreements-for-independent-contractors",
    }, article_type="guide") == []


def test_non_alternatives_article_may_have_descriptive_slug():
    assert sp.validate_meta({
        "title": "Contractor Operations for Global Teams",
        "slug": "contractor-operations-global-teams",
    }) == []


def refresh_fixture(tmp_path, monkeypatch, *, mutate=False, conflict=False):
    (tmp_path / "baseline").mkdir()
    (tmp_path / "out").mkdir()
    (tmp_path / "edited.md").write_text("Approved text")
    old = {"id": 100, "slug": "contoso-alternatives", "title": "Original",
           "content": "<p>Old</p>", "publishedAt": "2026-01-15T10:00:00.000Z",
           "updatedAt": "2026-01-20T10:00:00.000Z", "cover": {"id": 10},
           "indexable": True, "author": {"id": 5}, "tags": []}
    (tmp_path / "baseline/cms-record.json").write_text(json.dumps(old))
    state = dict(old, content="<p>Concurrent edit</p>" if conflict else old["content"])
    writes = []
    def api(path, method="GET", body=None):
        assert path in ("/articles/100", "/articles/contoso-alternatives/findBySlug")
        if method == "PUT":
            writes.append(body["data"].copy())
            for key, value in body["data"].items():
                state["content" if key == "contentHtml" else key] = value
            if mutate and len(writes) == 1:
                state["content"] = "<p>Unexpected CMS transform</p>"
            state["updatedAt"] = "2026-10-19T08:00:00.000Z"
        return {"data": dict(state)}
    monkeypatch.setattr(sp, "api", api)
    return state, writes


def test_refresh_preserves_live_state_and_original_date(tmp_path, monkeypatch):
    state, writes = refresh_fixture(tmp_path, monkeypatch)
    sp.refresh_existing(tmp_path, {"title": "New", "slug": state["slug"]}, "<p>New</p>", 100, True, False)
    assert len(writes) == 1
    assert writes[0]["publishedAt"] == "2026-01-15T10:00:00.000Z"
    assert not {"slug", "cover", "author", "tags", "indexable"} & writes[0].keys()
    assert state["content"] == "<p>New</p>" and state["indexable"] is True
    assert json.loads((tmp_path / "out/strapi_record.json").read_text())["published"] is True


def test_refresh_dry_run_and_wrong_identity_never_write(tmp_path, monkeypatch):
    state, writes = refresh_fixture(tmp_path, monkeypatch)
    meta = {"title": "New", "slug": state["slug"]}
    sp.refresh_existing(tmp_path, meta, "<p>New</p>", 100, True, True)
    for record_id, publish in [(None, True), (100, False), (101, True)]:
        with pytest.raises(SystemExit):
            sp.refresh_existing(tmp_path, meta, "<p>New</p>", record_id, publish, False)
    assert writes == []


def test_refresh_refuses_concurrent_live_edit(tmp_path, monkeypatch):
    state, writes = refresh_fixture(tmp_path, monkeypatch, conflict=True)
    with pytest.raises(SystemExit, match="changed since"):
        sp.refresh_existing(tmp_path, {"title": "New", "slug": state["slug"]}, "<p>New</p>", 100, True, False)
    assert writes == []


def test_refresh_readback_mismatch_restores_previous_body(tmp_path, monkeypatch):
    state, writes = refresh_fixture(tmp_path, monkeypatch, mutate=True)
    with pytest.raises(SystemExit, match="readback mismatch"):
        sp.refresh_existing(tmp_path, {"title": "New", "slug": state["slug"]}, "<p>New</p>", 100, True, False)
    assert len(writes) == 2 and all(row["publishedAt"] for row in writes)
    assert state["content"] == "<p>Old</p>"
