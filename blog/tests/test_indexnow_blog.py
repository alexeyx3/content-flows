import json

import pytest

from scripts import indexnow_blog


class Response:
    def __init__(self, url, text, *, status=200, headers=None, history=None):
        self.url = url
        self.text = text
        self.status_code = status
        self.headers = headers or {}
        self.history = history or []

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, timeout, **kwargs):
        assert timeout == 30
        assert kwargs in ({}, {"allow_redirects": False})
        self.calls.append((url, kwargs))
        return self.response


def test_article_url_requires_published_record(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "strapi_record.json").write_text(json.dumps({"slug": "example", "published": False}))
    with pytest.raises(ValueError, match="not published"):
        indexnow_blog.article_url(tmp_path, Session(None))


def test_article_url_requires_public_canonical(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "strapi_record.json").write_text(json.dumps({"slug": "example", "published": True}))
    url = "https://example.com/blog/example/"
    with pytest.raises(ValueError, match="canonical"):
        indexnow_blog.article_url(tmp_path, Session(Response(url, "<html>No canonical</html>")))
    assert indexnow_blog.article_url(
        tmp_path, Session(Response(url, f'<link rel="canonical" href="{url}" />'))
    ) == url


def test_key_must_match_public_file(tmp_path, monkeypatch):
    config = tmp_path / "indexnow.json"
    config.write_text(json.dumps({"keyLocation": "https://example.com/example123.txt"}))
    monkeypatch.setattr(indexnow_blog, "CONFIG", config)
    with pytest.raises(ValueError, match="does not match"):
        indexnow_blog.verified_key(Session(Response("https://example.com/example123.txt", "wrong")))


RU_URL = "https://example.com/ru/blog/example/"


def ru_html(*, canonical=RU_URL, language="ru", extra=""):
    return (f"<html lang='{language}'><head><link href='{canonical}' rel='canonical'>"
            f"<meta name='robots' content='index, follow'>{extra}</head></html>")


@pytest.fixture
def translation_job(tmp_path):
    (tmp_path / "job.yaml").write_text("article_translation_version: 1\nlanguage: ru\n")
    (tmp_path / "translation.json").write_text(json.dumps({"source_id": 416,
        "source_locale": "en", "target_locale": "ru", "slug": "example"}))
    (tmp_path / "publication").mkdir()
    (tmp_path / "publication" / "record.json").write_text(json.dumps({
        "version": 1, "id": 1001, "source_id": 416, "locale": "ru", "slug": "example",
        "published": True, "publishedAt": "2026-11-05T00:00:00Z", "indexable": True,
        "cover": {"id": 10, "url": "/uploads/ru_cover.png"}, "readback_status": "PASS"}))
    return tmp_path


def change_publication(job, field, value):
    path = job / "publication" / "record.json"
    record = json.loads(path.read_text())
    record[field] = value
    path.write_text(json.dumps(record))


def test_translation_uses_verified_ru_route_and_publication_receipt(translation_job):
    # The historical EN exporter record must not override the translation receipt.
    (translation_job / "out").mkdir()
    (translation_job / "out" / "strapi_record.json").write_text(
        json.dumps({"published": True, "slug": "unrelated"}))
    session = Session(Response(RU_URL, ru_html(language="ru-RU")))
    assert indexnow_blog.article_url(translation_job, session) == RU_URL
    assert session.calls == [(RU_URL, {"allow_redirects": False})]


@pytest.mark.parametrize("field,value,reason", [
    ("published", False, "not published"), ("publishedAt", None, "not published"),
    ("indexable", False, "not published"), ("readback_status", "BLOCK", "not published"),
    ("locale", "en", "locale mismatch"), ("source_id", 417, "identity mismatch"),
    ("source_id", True, "identity mismatch"), ("id", 416, "identity mismatch"),
    ("id", True, "identity mismatch"), ("id", None, "identity mismatch"),
    ("slug", "other", "slug"), ("slug", "../example", "slug"),
    ("cover", None, "cover"), ("cover", {"id": True, "url": "/cover.png"}, "cover"),
    ("cover", {"id": 10, "url": ""}, "cover"),
    ("public_url", "https://example.com/blog/example/", "public URL mismatch"),
])
def test_translation_requires_actual_published_ru_identity_and_cover(translation_job,field,value,reason):
    change_publication(translation_job, field, value)
    session = Session(None)
    with pytest.raises(ValueError, match=reason):
        indexnow_blog.article_url(translation_job, session)
    assert session.calls == []


def test_translation_draft_or_en_record_cannot_stand_in_for_publication(translation_job):
    (translation_job / "publication" / "record.json").unlink()
    (translation_job / "out").mkdir()
    (translation_job / "out" / "strapi_record.json").write_text(
        json.dumps({"published": True, "slug": "example"}))
    with pytest.raises(FileNotFoundError):
        indexnow_blog.article_url(translation_job, Session(None))


@pytest.mark.parametrize("field,value", [("target_locale", "en"), ("source_locale", "ru"),
                                         ("source_id", 417), ("slug", "other")])
def test_translation_manifest_and_publication_must_agree(translation_job,field,value):
    path = translation_job / "translation.json"
    manifest = json.loads(path.read_text()); manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        indexnow_blog.article_url(translation_job, Session(None))


@pytest.mark.parametrize("status", [301,302,404,503])
def test_translation_requires_http_200_without_redirect(translation_job,status):
    with pytest.raises(ValueError, match="redirects or is unavailable"):
        indexnow_blog.article_url(translation_job, Session(Response(RU_URL, ru_html(), status=status)))


@pytest.mark.parametrize("response", [
    Response("https://example.com/blog/example/", ru_html()),
    Response(RU_URL, ru_html(), history=[object()]),
])
def test_translation_redirect_chain_cannot_hide_behind_a_canonical(translation_job,response):
    with pytest.raises(ValueError, match="redirects"):
        indexnow_blog.article_url(translation_job, Session(response))


@pytest.mark.parametrize("markup", [
    ru_html(canonical="https://example.com/blog/example/"),
    "<html lang='ru'><head></head></html>",
    ru_html(extra=f'<link rel="canonical" href="{RU_URL}">'),
])
def test_translation_requires_one_exact_ru_canonical(translation_job,markup):
    with pytest.raises(ValueError, match="canonical"):
        indexnow_blog.article_url(translation_job, Session(Response(RU_URL, markup)))


@pytest.mark.parametrize("language", ["en", ""])
def test_translation_page_language_must_be_russian(translation_job,language):
    with pytest.raises(ValueError, match="language is not Russian"):
        indexnow_blog.article_url(translation_job, Session(Response(RU_URL, ru_html(language=language))))


@pytest.mark.parametrize("markup,headers", [
    (ru_html(extra='<meta content="noindex, follow" name="robots">'), {}),
    (ru_html(extra='<meta name="Googlebot" content="NOINDEX">'), {}),
    (ru_html(), {"X-Robots-Tag": "noindex, follow"}),
    (ru_html(), {"x-robots-tag": "bingbot: none"}),
])
def test_translation_noindex_is_never_submitted(translation_job,markup,headers):
    with pytest.raises(ValueError, match="noindex"):
        indexnow_blog.article_url(translation_job, Session(Response(RU_URL, markup, headers=headers)))
