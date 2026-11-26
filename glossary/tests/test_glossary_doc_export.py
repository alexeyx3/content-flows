import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from glossary_md_to_gdoc import render_inline
from gdoc_review import layout_requests


class GlossaryDocInlineTests(unittest.TestCase):
    def test_root_relative_link_does_not_leak_markdown(self):
        text, spans = render_inline("See [Pay Stub](/glossary/pay-stub/).")
        self.assertEqual(text, "See Pay Stub.")
        self.assertIn((4, 12, "link", "https://example.com/glossary/pay-stub/"), spans)

    def test_code_in_bold_keeps_both_styles_without_backticks(self):
        text, spans = render_inline("**Employer FICA: `$124 + $29 = $153`**")
        self.assertEqual(text, "Employer FICA: $124 + $29 = $153")
        self.assertIn((0, len(text), "bold", None), spans)
        self.assertIn((15, len(text), "code", None), spans)

    def test_bold_link_keeps_destination_and_label_style(self):
        text, spans = render_inline("**[IRS](https://www.irs.gov/)**")
        self.assertEqual(text, "IRS")
        self.assertIn((0, 3, "bold", None), spans)
        self.assertIn((0, 3, "link", "https://www.irs.gov/"), spans)

    def test_code_preserves_literal_asterisks_and_entities(self):
        text, spans = render_inline("Use `a*b & c`.")
        self.assertEqual(text, "Use a*b & c.")
        self.assertEqual(spans, [(4, 11, "code", None)])

    def test_unicode_offsets_remain_python_character_offsets(self):
        text, spans = render_inline("😀 [UK](https://www.gov.uk/)")
        self.assertEqual(text, "😀 UK")
        self.assertIn((2, 4, "link", "https://www.gov.uk/"), spans)

    def test_list_intro_stays_with_first_bullet(self):
        document = {"body": {"content": [
            {"startIndex": 1, "endIndex": 20, "paragraph": {"elements": [
                {"textRun": {"content": "Preserve the facts:\n"}}]}},
            {"startIndex": 20, "endIndex": 25, "paragraph": {"bullet": {}, "elements": [
                {"textRun": {"content": "One\n"}}]}},
        ]}}
        first = layout_requests(document)[0]["updateParagraphStyle"]
        self.assertTrue(first["paragraphStyle"]["keepWithNext"])

    def test_normal_paragraph_not_forced_to_follow_next_page(self):
        document = {"body": {"content": [
            {"startIndex": 1, "endIndex": 7, "paragraph": {"elements": [
                {"textRun": {"content": "Done.\n"}}]}}
        ]}}
        first = layout_requests(document)[0]["updateParagraphStyle"]
        self.assertNotIn("keepWithNext", first["paragraphStyle"])

    def test_table_intro_carries_generated_blank_paragraph(self):
        document = {"body": {"content": [
            {"startIndex": 1, "endIndex": 10, "paragraph": {"elements": [
                {"textRun": {"content": "Outputs:\n"}}]}},
            {"startIndex": 10, "endIndex": 11, "paragraph": {"elements": [
                {"textRun": {"content": "\n"}}]}},
            {"startIndex": 11, "endIndex": 30, "table": {}},
        ]}}
        requests = layout_requests(document)
        self.assertTrue(requests[0]["updateParagraphStyle"]["paragraphStyle"]["keepWithNext"])
        self.assertTrue(requests[1]["updateParagraphStyle"]["paragraphStyle"]["keepWithNext"])

    def test_table_rows_do_not_split_across_pages(self):
        requests = layout_requests({"body": {"content": [
            {"startIndex": 12, "endIndex": 50, "table": {}}
        ]}})
        self.assertEqual(requests[0], {"updateTableRowStyle": {
            "tableStartLocation": {"index": 12},
            "tableRowStyle": {"preventOverflow": True}, "fields": "preventOverflow",
        }})


if __name__ == "__main__":
    unittest.main()
