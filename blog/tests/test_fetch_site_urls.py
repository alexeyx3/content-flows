"""Internal links go only to pages that actually exist."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_site_urls as f  # noqa: E402

SAMPLE = [
    "https://example.com/",
    "https://example.com/product/",
    "https://example.com/de/product/",
    "https://example.com/ru/product/",
    "https://example.com/terms-of-service/",
    "https://example.com/customer-privacy-notice/",
    "https://example.com/blog/fabrikam-alternatives/",
    "https://example.com/industries/agencies/",
]


def test_localized_urls_dropped():
    urls = {r["url"] for r in f.filter_urls(SAMPLE)}
    assert "https://example.com/de/product/" not in urls
    assert "https://example.com/ru/product/" not in urls
    assert "https://example.com/product/" in urls


def test_legal_pages_dropped():
    urls = {r["url"] for r in f.filter_urls(SAMPLE)}
    assert "https://example.com/terms-of-service/" not in urls
    assert "https://example.com/customer-privacy-notice/" not in urls


def test_contracts_dropped():
    """Agreement pages and the legal section are dropped by prefix as well as by substring."""
    contracts = [
        "https://example.com/legal/terms/",
        "https://example.com/legal/privacy/",
        "https://example.com/sla-standard/",
        "https://example.com/partner-terms-and-conditions/",
        "https://example.com/legal/subprocessors-list/",
    ]
    assert f.filter_urls(contracts) == []


def test_lookalike_slugs_survive():
    """The prefix filter must not swallow ordinary pages that start with the same letters."""
    urls = {r["url"] for r in f.filter_urls([
        "https://example.com/slack-integration/",
        "https://example.com/legal-teams/",
        "https://example.com/sla-standard/",
    ])}
    assert "https://example.com/slack-integration/" in urls
    assert "https://example.com/legal-teams/" in urls
    assert "https://example.com/sla-standard/" not in urls


def test_blog_and_sections_kept():
    urls = {r["url"] for r in f.filter_urls(SAMPLE)}
    assert "https://example.com/blog/fabrikam-alternatives/" in urls
    assert "https://example.com/industries/agencies/" in urls


def test_label_derived_from_slug():
    rows = {r["url"]: r for r in f.filter_urls(SAMPLE)}
    assert rows["https://example.com/blog/fabrikam-alternatives/"]["label"] == "fabrikam alternatives"
    assert rows["https://example.com/"]["label"] == "home"


def test_duplicates_collapsed():
    rows = f.filter_urls(["https://example.com/product/", "https://example.com/product/"])
    assert len(rows) == 1


def test_sitemap_locs_parsed():
    xml = ("<urlset><url><loc>https://example.com/a/</loc></url>"
           "<url><loc>https://example.com/b/</loc></url></urlset>")
    assert f.parse_locs(xml) == ["https://example.com/a/", "https://example.com/b/"]


# --- page language: an English article links only to English pages ---

def test_page_lang_from_html_attribute():
    assert f.page_lang('<!doctype html><html lang="en" class="x">') == "en"


def test_cyrillic_title_means_russian_even_when_html_says_en():
    """Some sites set the same lang attribute on every page, whatever the article's language."""
    html = ('<html lang="en"><head><title>Как согласовать счёт подрядчика</title>'
            '</head><body><h1>Согласование счетов</h1></body></html>')
    assert f.page_lang(html) == "ru"


def test_english_title_stays_english():
    html = '<html lang="en"><title>Fabrikam alternatives in 2026</title><h1>Fabrikam alternatives</h1>'
    assert f.page_lang(html) == "en"
    assert f.page_lang("<html lang='ru-RU'>") == "ru"
    assert f.page_lang('<html data-x="1">') == ""


def test_page_lang_is_case_insensitive():
    assert f.page_lang('<HTML LANG="EN">') == "en"


def test_refresh_preserves_url_order_and_failed_language(monkeypatch, tmp_path, capsys):
    output = tmp_path / "site-urls.json"
    sitemap = "https://example.com/blog-sitemap.xml"
    pages = {
        f.INDEX: f"<loc>{sitemap}</loc>",
        sitemap: ("<loc>https://example.com/second/</loc><loc>https://example.com/first/</loc>"),
        "https://example.com/first/": '<html lang="en"><title>Первая статья</title>',
    }

    def fetch(url):
        if url == "https://example.com/second/":
            raise TimeoutError
        return pages[url]

    monkeypatch.setattr(f, "fetch", fetch)
    monkeypatch.setattr(sys, "argv", ["fetch_site_urls.py", "--date", "2026-11-22", "--output", str(output)])
    f.main()

    rows = json.loads(output.read_text())["urls"]
    assert [(row["path"], row["lang"]) for row in rows] == [("/first/", "ru"), ("/second/", "")]
    assert "/second/ (TimeoutError)" in capsys.readouterr().out
