import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import verify_refresh_review as verifier


def paragraph(start, text, *, yellow=False):
    style = {"backgroundColor": {"color": {"rgbColor": verifier.converter.HIGHLIGHT}}} if yellow else {}
    return {"startIndex": start, "endIndex": start + len(text),
            "textRun": {"content": text, "textStyle": style}}


def document(*paragraphs):
    content = []
    for fragments in paragraphs:
        content.append({"startIndex": fragments[0]["startIndex"],
                        "endIndex": fragments[-1]["endIndex"],
                        "paragraph": {"elements": fragments}})
    return {"namedRanges": {"BLOG_ARTICLE_BODY": {"namedRanges": [
        {"ranges": [{"startIndex": 1, "endIndex": 500}]}]}}, "body": {"content": content}}


def setup_job(tmp_path: Path):
    job = tmp_path / "refresh-job"
    (job / "review").mkdir(parents=True)
    (job / "baseline").mkdir()
    (job / "job.yaml").write_text("temnik_cluster_id: own-0016\n")
    (job / "refresh.json").write_text(json.dumps({"cycle_id": "cycle-01"}))
    (job / "baseline/article.md").write_text("## Pricing\n\nThe plan costs $37.\n")
    (job / "review/02-sent.md").write_text("## Pricing\n\nThe plan costs $44.\n")
    (job / "review/02-doc-url.txt").write_text("https://docs.google.com/document/d/abc/edit\n")
    (job / "review/02-document.json").write_text(json.dumps({"document_id": "abc", "images": []}))
    return job


def test_local_readback_checks_exact_changed_characters_and_writes_only_review(tmp_path):
    job = setup_job(tmp_path)
    doc = document([paragraph(1, "Pricing\n")], [paragraph(10, "The plan costs $"),
                                              paragraph(26, "44", yellow=True),
                                              paragraph(28, ".\n")])
    docs = Mock()
    docs.documents.return_value.get.return_value.execute.return_value = doc
    report = verifier.verify(job, 2, skip_temnik=True, docs=docs)
    assert report["text_roundtrip"] == "PASS"
    assert report["highlight_readback"] == "PASS"
    assert report["highlighted_characters"] == 2
    assert report["native_tables"] == 0
    assert json.loads((job / "review/02-highlight-readback.json").read_text()) == {
        "actual": "44", "expected": "44"}
    assert not (job / "out/delivery-verification.json").exists()


def test_native_literal_clause_labels_are_verified_and_number_loss_is_not_normalized(tmp_path):
    job = setup_job(tmp_path)
    source = "**1. Relationship and services**\n\nRefer to Section 2.\n\n**2. Effective date and term**\n"
    (job / "baseline/article.md").write_text(source)
    (job / "review/02-sent.md").write_text(source)
    doc = document([paragraph(1, "1. Relationship and services\n")],
                   [paragraph(40, "Refer to Section 2.\n")],
                   [paragraph(70, "2. Effective date and term\n")])
    assert all("bullet" not in block["paragraph"] for block in doc["body"]["content"])
    docs = Mock()
    docs.documents.return_value.get.return_value.execute.return_value = doc
    assert verifier.verify(job, 2, skip_temnik=True, docs=docs)["text_roundtrip"] == "PASS"
    doc["body"]["content"][2]["paragraph"]["elements"][0]["textRun"]["content"] = "1. Effective date and term\n"
    with pytest.raises(verifier.VerificationError, match="native Doc text differs"):
        verifier.verify(job, 2, skip_temnik=True, docs=docs)
    assert "+1. Effective date and term" in (job / "review/02-readback.diff").read_text()


def test_inherited_yellow_on_unchanged_text_fails(tmp_path):
    job = setup_job(tmp_path)
    doc = document([paragraph(1, "Pricing\n")], [paragraph(10, "The plan costs $", yellow=True),
                                              paragraph(26, "44", yellow=True),
                                              paragraph(28, ".\n")])
    docs = Mock()
    docs.documents.return_value.get.return_value.execute.return_value = doc
    with pytest.raises(verifier.VerificationError, match="yellow visible characters"):
        verifier.verify(job, 2, skip_temnik=True, docs=docs)
    assert (job / "review/02-delivery-verification.json").exists()


def test_same_yellow_word_at_wrong_position_fails(tmp_path):
    job = setup_job(tmp_path)
    (job / "baseline/article.md").write_text("## Pricing\n\nThe plan costs $37. Another $44.\n")
    (job / "review/02-sent.md").write_text("## Pricing\n\nThe plan costs $44. Another $44.\n")
    doc = document([paragraph(1, "Pricing\n")],
                   [paragraph(10, "The plan costs $44. Another $"),
                    paragraph(39, "44", yellow=True), paragraph(41, ".\n")])
    docs = Mock()
    docs.documents.return_value.get.return_value.execute.return_value = doc
    with pytest.raises(verifier.VerificationError, match="yellow visible characters"):
        verifier.verify(job, 2, skip_temnik=True, docs=docs)
    comparison = json.loads((job / "review/02-highlight-readback.json").read_text())
    assert comparison == {"actual": "44", "expected": "44"}  # position mask catches the error


def test_empty_first_native_table_cell_roundtrips_with_exact_yellow_mask(tmp_path):
    job = setup_job(tmp_path)
    (job / "baseline/article.md").write_text(
        "| | Fabrikam | Example Co |\n|---|---|---|\n| Price | $37 | Per active contractor |\n")
    (job / "review/02-sent.md").write_text(
        "| | Fabrikam | Example Co |\n|---|---|---|\n| Price | $44 | Per active contractor |\n")

    def cell(*runs):
        return {"content": [{"paragraph": {"elements": list(runs)}}]}

    table = {"startIndex": 1, "endIndex": 100, "table": {"tableRows": [
        {"tableCells": [cell(paragraph(5, "\n")), cell(paragraph(10, "Fabrikam\n")),
                        cell(paragraph(20, "Example Co\n"))]},
        {"tableCells": [cell(paragraph(35, "Price\n")),
                        cell(paragraph(45, "$"), paragraph(46, "44", yellow=True), paragraph(48, "\n")),
                        cell(paragraph(55, "Per active contractor\n"))]}]}}
    doc = {"namedRanges": {"BLOG_ARTICLE_BODY": {"namedRanges": [
        {"ranges": [{"startIndex": 1, "endIndex": 100}]}]}}, "body": {"content": [table]}}
    docs = Mock()
    docs.documents.return_value.get.return_value.execute.return_value = doc
    report = verifier.verify(job, 2, skip_temnik=True, docs=docs)
    assert report["text_roundtrip"] == "PASS"
    assert report["highlight_readback"] == "PASS"
    assert report["native_tables"] == 1
    assert (job / "review/02-readback.diff").read_text() == ""


def test_image_receipt_validates_native_object():
    image = {"object_id": "img1", "url": "https://example.com/chart.png", "alt": "Chart", "title": "Trend"}
    doc = document([{"startIndex": 1, "endIndex": 2,
                     "inlineObjectElement": {"inlineObjectId": "img1"}}, paragraph(2, "\n")])
    doc["inlineObjects"] = {"img1": {"inlineObjectProperties": {"embeddedObject": {
        "imageProperties": {"sourceUri": image["url"]}}}}}
    text, yellow, _, tables, mask = verifier.doc_readback(doc, [image])
    assert text == '![Chart](https://example.com/chart.png "Trend")\n'
    assert yellow == "" and tables == 0 and mask == []
    doc["inlineObjects"]["img1"]["inlineObjectProperties"]["embeddedObject"]["imageProperties"]["sourceUri"] = "https://example.com/other.png"
    with pytest.raises(verifier.VerificationError, match="differs"):
        verifier.doc_readback(doc, [image])


class Sheet:
    def __init__(self, rows):
        self.rows = rows

    def get_all_values(self):
        return self.rows


class Book:
    def __init__(self, rows):
        self.history = Sheet(rows)

    def worksheet(self, title):
        assert title == "Refresh history"
        return self.history


def test_temnik_checks_exact_cycle_history_and_nonblank_legacy_values(tmp_path, monkeypatch):
    job = setup_job(tmp_path)
    legacy = {"Status": "published", "Google Doc": "https://docs.google.com/document/d/original/edit",
              "Publication date": "2026-09-07", "Publication URL": "https://example.com/blog/contoso-alternatives/"}
    (job / "baseline/temnik-row.json").write_text(json.dumps(legacy))
    headers = ["Cluster ID", *legacy, "Refresh: cycle", "Refresh: status", "Refresh: Google Doc"]
    url = "https://docs.google.com/document/d/abc/edit"
    row = ["own-0016", *legacy.values(), "cycle-01", "in review", url]
    history = [["cycle_id", "cluster_id", "status", "review_doc_url"],
               ["cycle-01", "own-0016", "in review", url]]
    book, sheet = Book(history), Sheet([headers, row])
    monkeypatch.setattr(verifier, "temnik_service", lambda: (book, sheet))
    assert verifier.verify_temnik(job, url, "cycle-01", "own-0016") == (2, 1)
    history.append(history[1][:])
    with pytest.raises(verifier.VerificationError, match="exactly one"):
        verifier.verify_temnik(job, url, "cycle-01", "own-0016")
    history.pop()
    row[1] = "in review"
    with pytest.raises(verifier.VerificationError, match="original temnik field changed"):
        verifier.verify_temnik(job, url, "cycle-01", "own-0016")
