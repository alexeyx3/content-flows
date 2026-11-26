import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import indexnow_glossary as indexnow


class IndexNowGlossaryTests(unittest.TestCase):
    def test_sitemap_excludes_section_index_and_deduplicates_articles(self):
        xml = b'''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/glossary/</loc></url>
          <url><loc>https://example.com/glossary/overtime/</loc></url>
          <url><loc>https://example.com/glossary/overtime/</loc></url>
        </urlset>'''
        session = Mock()
        session.get.return_value.content = xml
        self.assertEqual(indexnow.published_urls_from_sitemap(session),
                         ["https://example.com/glossary/overtime/"])

    def test_rejects_foreign_or_noncanonical_urls(self):
        for url in ("https://other.example/glossary/overtime/",
                    "https://example.com/glossary/", "https://example.com/glossary/overtime/?draft=1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                indexnow.glossary_url(url)

    def test_submit_accepts_202_and_sends_exact_urls(self):
        session = Mock()
        session.post.return_value.status_code = 202
        session.post.return_value.text = ""
        url = "https://example.com/glossary/overtime/"
        with patch.object(indexnow, "verified_key", return_value=("sitekey123", "https://example.com/sitekey123.txt")):
            receipt = indexnow.submit([url], session)
        self.assertTrue(receipt["accepted"])
        self.assertEqual(receipt["urls"], [url])
        self.assertEqual(session.post.call_args.kwargs["json"]["urlList"], [url])


if __name__ == "__main__":
    unittest.main()
