"""Observable v2 contracts: real images, exact quotes, current QA and export refusal."""
import argparse
from email import policy
from email.parser import BytesParser
import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import article_materials as m
import gdoc_review as review
import md_to_gdoc as docs
import md_to_strapi_html as html
import package_article as pack
import render_visuals as renderer
import check_visual_layout as visual_layout
import strapi_publish as publish
import upload_visuals as uploader
import workflow_gate


def test_cms_image_html_survives_sanitizer_with_apostrophe_in_alt():
    body = '<figure class="image"><img src="https://example.com/a.png" alt="A country&#x27;s duties" title="Chart" /></figure>\n'
    normalized = m.cms_image_html(body)
    checked = subprocess.run(
        ["node", str(ROOT / "tools" / "sanitize" / "check.js")],
        input=normalized, text=True, capture_output=True, check=True,
    )
    assert checked.stdout == normalized
    assert 'title=' not in normalized


@pytest.mark.parametrize('field', ['title', 'alt', 'caption'])
def test_media_string_capacity_is_checked_before_upload(job, field):
    data = m.read_json(job / 'visuals.json')
    data['visuals'][0][field] = 'a' * 255
    m.write_json(job / 'visuals.json', data)
    assert not any('255 characters' in e for e in m.validate_inputs(job))
    data['visuals'][0][field] = 'a' * 256
    m.write_json(job / 'visuals.json', data)
    assert any(field + ' exceeds 255 characters' in e for e in m.validate_inputs(job))


def test_duplicate_visual_source_label_gate_preserves_prior_jobs(job):
    data = m.read_json(job / 'visuals.json')
    data['visuals'][0]['caption'] = 'Compare the two periods. Sources: Original report.'
    m.write_json(job / 'visuals.json', data)
    assert m.validate_inputs(job) == []
    with (job / 'job.yaml').open('a') as output:
        output.write('visual_caption_sources_version: 1\n')
    assert any('from caption to sources' in e for e in m.validate_inputs(job))


def test_upload_multipart_keeps_metadata_as_form_field(tmp_path, monkeypatch):
    path = tmp_path / "diagram.png"
    path.write_bytes(b"png-transport-fixture")
    info = {"name": "Diagram", "alternativeText": "Alt", "caption": "Caption"}

    def receive(req, timeout):
        message = BytesParser(policy=policy.default).parsebytes(
            ('Content-Type: ' + req.get_header('Content-type') + '\r\n\r\n').encode()
            + req.data)
        parts = {part.get_param('name', header='content-disposition'): part
                 for part in message.iter_parts()}
        assert parts['fileInfo'].get_content_type() == 'text/plain'
        assert parts['fileInfo'].get_filename() is None
        assert json.loads(parts['fileInfo'].get_payload(decode=True)) == info
        assert parts['files'].get_content_type() == 'image/png'
        assert parts['files'].get_filename() == 'diagram.png'
        assert parts['files'].get_payload(decode=True) == path.read_bytes()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'[{"id": 7, "url": "https://example.com/a.png"}]'
        return response

    monkeypatch.setattr(uploader, 'token', lambda: 'test-token')
    monkeypatch.setattr(uploader.urllib.request, 'urlopen', receive)
    assert uploader.upload_file(path, info, 'diagram.png')['id'] == 7


def test_new_visual_qa_stage_blocks_upload_until_current_full_and_mobile_review(job):
    with (job / "job.yaml").open("a") as output:
        output.write("visual_qa_version: 1\n")
    renderer.render(job)
    with pytest.raises(ValueError, match="visual layout check"):
        uploader.upload(job, dry_run=True)
    report = visual_layout.check(job)
    assert report["visuals"][0]["mobile_width"] == 390
    assert report["visuals"][0]["current_render"] == "PASS"
    with pytest.raises(ValueError, match="visual_qa.json"):
        uploader.upload(job, dry_run=True)
    row = report["visuals"][0]
    m.write_json(job / "visual_qa.json", {
        "version": 1, "overall": "PASS",
        "layout_report_sha256": m.digest((job / "out/visual-layout-check.json").read_bytes()),
        "visuals": [{"id": row["id"], "verdict": "PASS", "viewed_full": True,
                     "viewed_mobile": True, "asset_sha256": row["asset_sha256"],
                     "mobile_sha256": row["mobile_sha256"],
                     "notes": "Labels, chart marks and logo remain readable at full and 390 px widths."}],
    })
    assert m.visual_qa_errors(job) == []
    uploader.upload(job, dry_run=True)
    (job / row["mobile_path"]).write_bytes(b"changed")
    assert any("mobile preview" in error for error in m.visual_qa_errors(job))
    with pytest.raises(ValueError, match="mobile preview"):
        uploader.upload(job, dry_run=True)


def test_writer_requires_early_render_but_visual_qa_can_run_in_parallel(job):
    with (job / "job.yaml").open("a") as output:
        output.write("visual_qa_version: 1\n")
    assert any("visual layout check" in error for error in m.writer_ready_errors(job))
    renderer.render(job)
    visual_layout.check(job)
    # The writer can start before an independent verdict exists; upload cannot.
    assert not (job / "visual_qa.json").exists()
    assert m.writer_ready_errors(job) == []
    with pytest.raises(ValueError, match="visual_qa.json"):
        uploader.upload(job, dry_run=True)
    data = m.read_json(job / "visuals.json")
    data["visuals"][0]["data"]["period"] = "Changed period"
    m.write_json(job / "visuals.json", data)
    assert m.writer_ready_errors(job)
    with pytest.raises(ValueError, match="is stale after a PNG or task change"):
        uploader.upload(job, dry_run=True)


def test_diagram_visual_stage_runs_geometry_and_mobile_check(job):
    with (job / "job.yaml").open("a") as output:
        output.write("visual_qa_version: 1\n")
    manifest = m.read_json(job / "visuals.json")
    visual = manifest["visuals"][0]
    visual["type"] = "process"
    visual["data"] = {
        "nodes": [
            {"id": "first", "label": "First check", "evidence_ids": ["PRICE-01"]},
            {"id": "second", "label": "Second check", "evidence_ids": ["PRICE-02"]},
        ],
        "edges": [{"from": "first", "to": "second", "label": "Then"}],
    }
    m.write_json(job / "visuals.json", manifest)
    renderer.render(job)
    report = visual_layout.check(job)
    assert report["visuals"][0]["automatic_geometry"] == "PASS"
    assert report["visuals"][0]["mobile_width"] == 390
    assert (job / report["visuals"][0]["mobile_path"]).exists()


@pytest.fixture
def job(tmp_path):
    (tmp_path / "out").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "job.yaml").write_text('workflow_version: 2\nlanguage: RU\nauthor: "john.roe"\n')
    (tmp_path / "research.md").write_text("R-01: технический пример с условными данными, не для публикации.")
    (tmp_path / "brief.md").write_text("# Технический пример\n\n- **metaTitle:** Технический пример\n"
        "- **metaDescription:** Техническая проверка полного материала.\n"
        "- **summary:** Условный пример для проверки инструментов.\n"
        "- **slug:** technical-example\n")
    (tmp_path / "evidence.md").write_text(
        "| PRICE-01 | условное значение 1200 | pricing | https://example.com | primary | пример | 2026 | supports |\n"
        "| PRICE-02 | условное значение 2400 | pricing | https://example.com | primary | пример | 2026 | supports |\n")
    m.write_json(tmp_path / "sections.json", {"title": "Технический пример", "sections": [
        {"id": "pricing", "title": "Условное сравнение", "instruction": "Технический пример"}],
        "information_gain": [{"section_id": "pricing", "reader_value": "Показать условное сравнение", "research_ref": "R-01"}]})
    visual = {"id": "annual-cost", "section_id": "pricing", "type": "bar",
              "purpose": "Технический пример сравнения", "title": "Условные годовые расходы",
              "alt": "Сценарий B стоит вдвое дороже сценария A в условном примере",
              "caption": "Технический пример: условные данные, не для публикации.",
              "sources": [{"label": "Условный источник", "url": "https://example.com/source", "public": True}],
              "data": {"unit": "USD / год", "period": "Пример", "geography": "Условный сценарий",
                       "categories": ["Сценарий A", "Сценарий B"],
                       "series": [{"name": "Годовые расходы", "values": [1200, 2400],
                                   "evidence_ids": [["PRICE-01"], ["PRICE-02"]]}]}}
    m.write_json(tmp_path / "visuals.json", {"version": 1, "visuals": [visual]})
    quote = {"id": "test-comment", "section_id": "pricing", "speaker": "john.roe",
             "attribution": "Технический пример, не экспертная цитата для публикации",
             "text": "Сравнивайте расходы при одинаковых исходных условиях.",
             "source_type": "editorial_draft", "source": "", "status": "proposed", "evidence_ids": []}
    m.write_json(tmp_path / "expert_quotes.json", {"version": 1, "quotes": [quote]})
    (tmp_path / 'raw').mkdir()
    m.write_json(tmp_path / 'raw/speaker-profiles.json', {
        'source': 'https://example.com/mock-cms', 'checked_at': '2026-09-26',
        'profiles': [{'id': 5, 'username': 'john.roe', 'name': quote['attribution']}]})
    (tmp_path / "edited.md").write_text("# Технический пример\n\n## Условное сравнение\n\n"
        "Это условные данные для проверки инструмента.\n\n[[VISUAL:annual-cost]]\n\n" + m.quote_markdown(quote) + "\n")
    (tmp_path / "out/meta.md").write_text("title: Технический пример\nslug: technical-example\n")
    return tmp_path


def test_quote_attribution_requires_exact_cms_name(job):
    assert m.validate_inputs(job) == []


def test_primary_data_chart_keeps_its_selected_source_trace(job):
    with (job / "job.yaml").open("a") as output:
        output.write("primary_data_research_version: 1\n")
    m.write_json(job / "research.data.json", {
        "version": 1, "candidates": [{"id": "D-01", "status": "read_original"}],
    })
    sections = m.read_json(job / "sections.json")
    sections["visual_audit"] = {
        "considered_data_ids": ["D-01"], "selected_chart_ids": ["D-01"],
        "decision": "Comparable values help the cost decision.",
    }
    sections["visual_candidates"] = [{
        "section_id": "pricing", "type": "bar", "purpose": "Compare costs",
        "data_ref": "D-01",
    }]
    m.write_json(job / "sections.json", sections)
    errors = m.validate_inputs(job)
    assert any("data_ref" in e for e in errors), errors
    visuals = m.read_json(job / "visuals.json")
    visuals["visuals"][0]["data_ref"] = "D-01"
    m.write_json(job / "visuals.json", visuals)
    assert m.validate_inputs(job) == []
    data = m.read_json(job / 'expert_quotes.json')
    data['quotes'][0]['attribution'] = 'Different public spelling'
    m.write_json(job / 'expert_quotes.json', data)
    assert any('match the Strapi name exactly' in e for e in m.validate_inputs(job))


def test_quote_cms_name_snapshot_missing_or_wrong_id_blocks(job):
    path = job / 'raw/speaker-profiles.json'
    data = m.read_json(path)
    data['profiles'][0]['id'] = 12345
    m.write_json(path, data)
    assert any('Strapi profile' in e for e in m.validate_inputs(job))
    path.unlink()
    assert any('Strapi names snapshot' in e for e in m.validate_inputs(job))


def test_external_quote_requires_original_and_links_attribution(job):
    quotes = m.read_json(job / 'expert_quotes.json')
    external = {
        'id': 'outside-comment', 'section_id': 'pricing',
        'speaker_kind': 'external', 'speaker': 'jane-doe',
        'attribution': 'Jane Doe, research director',
        'text': 'A short verified statement about the decision.',
        'source_type': 'verbatim', 'source': 'https://example.org/original',
        'published_at': '2026-06-02', 'source_location': 'opening quotation',
        'status': 'proposed', 'evidence_ids': [],
    }
    quotes['quotes'].append(external)
    m.write_json(job / 'expert_quotes.json', quotes)
    assert m.validate_inputs(job) == []
    assert m.quote_markdown(external).endswith(
        '> — [Jane Doe, research director](https://example.org/original)')
    external['source'] = 'https://example.org/search-snippet'
    external['source_location'] = ''
    m.write_json(job / 'expert_quotes.json', quotes)
    assert any('location of the quote' in error for error in m.validate_inputs(job))
    external['source_location'] = 'opening quotation'
    external['source_type'] = 'editorial_draft'
    m.write_json(job / 'expert_quotes.json', quotes)
    assert any('verbatim' in error for error in m.validate_inputs(job))


def test_proposed_external_quote_can_enter_review_but_not_strapi(job):
    external = {
        'id': 'outside-comment', 'section_id': 'pricing',
        'speaker_kind': 'external', 'speaker': 'jane-doe',
        'attribution': 'Jane Doe, research director',
        'text': 'A short verified statement about the decision.',
        'source_type': 'verbatim', 'source': 'https://example.org/original',
        'published_at': '2026-06-02', 'source_location': 'opening quotation',
        'status': 'proposed', 'evidence_ids': [],
    }
    quotes = m.read_json(job / 'expert_quotes.json')
    quotes['quotes'].append(external)
    m.write_json(job / 'expert_quotes.json', quotes)
    with (job / 'edited.md').open('a') as output:
        output.write('\n' + m.quote_markdown(external) + '\n')
    complete(job)
    assert m.export_errors(job, 'review', remote=False) == []
    assert any('outside-comment: quote not approved' in error
               for error in m.export_errors(job, 'strapi', remote=False))


def materialize(job, media_id=999):
    renderer.render(job)
    data = m.read_json(job / "visuals.json")
    a = data["visuals"][0]["asset"]
    uploaded = job / "assets/annual-cost.strapi.png"
    uploaded.write_bytes((job / a["path"]).read_bytes())
    a.update({"media_id": media_id, "url": "https://example.com/chart.png",
              "remote_path": str(uploaded.relative_to(job)), "remote_sha256": m.digest(uploaded.read_bytes())})
    m.write_json(job / "visuals.json", data)
    pack.package(job, bind_visuals=True)


def complete(job):
    materialize(job)
    (job / "qa_report.md").write_text("# QA технического примера\n- Gate 1 Publication-ready: PASS\noverall: PASS\n")
    m.write_json(job / "qa_receipt.json", {"hashes": m.qa_fingerprint(job)})


def test_first_qa_ready_without_final_audit_cannot_accept_or_export(job, monkeypatch, capsys):
    with (job / "job.yaml").open("a") as output:
        output.write("batch_delivery_contract_version: 1\n")
    sections = m.read_json(job / "sections.json")
    sections["delivery_checks"] = [{
        "id": "DLV-01", "section_id": "pricing", "kind": "wording", "evidence_required": False,
        "requirement": "Identify the comparison as a conditional technical example.",
        "basis": {"brief_heading": "Технический пример",
                  "brief_excerpt": "Условный пример для проверки инструментов."},
    }]
    m.write_json(job / "sections.json", sections)
    materialize(job, media_id="drive:review-image")
    assert m.validate_inputs(job) == []
    assert m.article_errors(job, "qa", remote=False) == []
    absent = [job / name for name in ("qa_report.md", "qa_delivery.json", "qa_receipt.json")]
    assert all(not path.exists() for path in absent)
    before = {path: path.read_bytes() for path in job.rglob("*") if path.is_file()}
    monkeypatch.setattr(sys, "argv", ["workflow_gate.py", "check", "--job", str(job),
                                     "--target", "qa", "--offline"])
    capsys.readouterr()
    workflow_gate.main()
    assert capsys.readouterr().out.strip() == "READY: qa (offline)"
    assert {path: path.read_bytes() for path in job.rglob("*") if path.is_file()} == before
    assert not m.qa_is_pass(job)
    monkeypatch.setattr(sys, "argv", ["workflow_gate.py", "seal-qa", "--job", str(job)])
    with pytest.raises(SystemExit, match="delivery QA"):
        workflow_gate.main()
    for target in ("review", "strapi"):
        assert any("delivery QA" in error for error in m.export_errors(job, target, remote=False))
    assert all(not path.exists() for path in absent)

    # Readiness still rejects a stale package/materialization; it is not a bypass.
    edited = job / "edited.md"
    edited.write_text(edited.read_text() + "\n[[VISUAL:unbound-image]]\n")
    monkeypatch.setattr(sys, "argv", ["workflow_gate.py", "check", "--job", str(job),
                                     "--target", "qa", "--offline"])
    with pytest.raises(SystemExit, match="placeholder"):
        workflow_gate.main()
    assert all(not path.exists() for path in absent)


def approve(job):
    quotes = m.read_json(job / "expert_quotes.json")
    q = quotes["quotes"][0]
    q["status"] = "approved"
    q["approval"] = {"by": "Тест", "at": "2026-09-26", "reference": "тестовый сценарий",
                     "text_sha256": m.digest(q["text"] + "\n" + q["attribution"])}
    m.write_json(job / "expert_quotes.json", quotes)
    m.write_json(job / "review_approval.json", {"by": "Тест", "at": "2026-09-26",
        "reference": "тестовый сценарий", "article_sha256": m.digest((job / "edited.md").read_bytes())})


def test_invalid_metadata_leaves_visuals_unbound(job, monkeypatch):
    brief = job / "brief.md"
    brief.write_text(brief.read_text().replace("technical-example", "{slug}"))
    bind_visuals = Mock()
    monkeypatch.setattr(pack, "bind_article_visuals", bind_visuals)

    with pytest.raises(SystemExit, match="unfilled template"):
        pack.package(job, bind_visuals=True)

    bind_visuals.assert_not_called()
    assert "[[VISUAL:annual-cost]]" in (job / "edited.md").read_text()


def test_render_materialize_and_html_survive(job):
    complete(job)
    article = (job / "edited.md").read_text()
    assert "[[VISUAL:" not in article
    body = (job / "out/article.html").read_text()
    assert '<figcaption>' in body
    assert ' title="Условные годовые расходы"' in html.convert(article)[1]
    assert publish.html_survives_sanitizer(body)
    assert ' title="' not in body
    assert m.export_errors(job, "review", remote=False) == []
    assert (job / "assets/annual-cost.png").read_bytes().startswith(b"\x89PNG")


def test_qa_gate_uses_guide_type_for_rules_and_alternatives_title(job):
    with (job / "job.yaml").open("a", encoding="utf-8") as output:
        output.write("article_type: guide\n")
    edited = job / "edited.md"
    edited.write_text(edited.read_text(encoding="utf-8").replace(
        "# Технический пример", "# Non-Compete Agreements: Rules and Alternatives", 1),
        encoding="utf-8")
    complete(job)
    assert m.article_errors(job, "qa") == []


def test_placeholder_stops_docs_before_any_api(job, monkeypatch):
    create = Mock(side_effect=AssertionError("no API call expected"))
    monkeypatch.setattr(review, "services", create)
    with pytest.raises(SystemExit, match="placeholder"):
        review.cmd_push(argparse.Namespace(job=str(job), round=1, baseline=None))
    create.assert_not_called()


def test_banned_brand_in_metadata_stops_docs_before_any_api(job, monkeypatch):
    complete(job)
    with (job / "out/meta.md").open("a", encoding="utf-8") as output:
        output.write("\nmetaDescription: How to compare Northwind and other tools.\n")
    create = Mock(side_effect=AssertionError("no API call expected"))
    monkeypatch.setattr(publish, "STOP_BRANDS", re.compile(r"\bnorthwind\b", re.I))
    monkeypatch.setattr(review, "services", create)
    with pytest.raises(SystemExit, match="Northwind|northwind"):
        review.cmd_push(argparse.Namespace(job=str(job), round=1, baseline=None))
    create.assert_not_called()


def test_source_title_starting_add_is_not_a_placeholder():
    source = "- [Add or subtract time in Excel — Microsoft Support](https://example.com/guide)"
    assert m.PLACEHOLDERS.search(source) is None
    assert m.PLACEHOLDERS.search("[ADD SOURCE BEFORE PUBLICATION]") is not None
    assert m.PLACEHOLDERS.search("[Add source before publication]") is not None


def test_request_a_quote_in_prose_is_not_a_placeholder():
    assert m.PLACEHOLDERS.search("Request a quote: configuration capability alone is insufficient.") is None
    for marker in ("[[quote:comment-id]]", "Insert QUOTE:comment-id here.", "quote: comment-id"):
        assert m.PLACEHOLDERS.search(marker) is not None


def test_qa_receipt_rejects_later_text_edit(job):
    complete(job)
    (job / "edited.md").write_text((job / "edited.md").read_text() + "\nНовая правка.\n")
    pack.package(job)
    assert any("QA" in e for e in m.export_errors(job, "review", remote=False))


def test_refresh_qa_seal_binds_plan_evidence_and_source_snapshot(job):
    with (job / "job.yaml").open("a") as output:
        output.write("article_refresh_version: 1\n")
    (job / "baseline").mkdir()
    (job / "refresh_plan.json").write_text('{"decision":"focused update"}')
    (job / "refresh_evidence.md").write_text("Verified refresh evidence.\n")
    (job / "baseline/article.md").write_text("Original published article.\n")
    complete(job)
    assert m.export_errors(job, "review", remote=False) == []
    sealed = m.read_json(job / "qa_receipt.json")["hashes"]
    assert all(name in sealed for name in
               ("refresh_plan.json", "refresh_evidence.md", "baseline/article.md"))
    for name in ("refresh_plan.json", "baseline/article.md"):
        path = job / name
        original = path.read_text()
        path.write_text(original + "\nChanged after QA.\n")
        assert any("QA" in e for e in m.export_errors(job, "review", remote=False))
        path.write_text(original)
    assert m.export_errors(job, "review", remote=False) == []
    (job / "refresh_evidence.md").unlink()
    with pytest.raises(ValueError, match="refresh_evidence.md"):
        m.qa_fingerprint(job)
    assert any("qa_receipt" in e for e in m.export_errors(job, "review", remote=False))


def test_changed_visual_data_requires_new_render(job):
    complete(job)
    data = m.read_json(job / "visuals.json")
    data["visuals"][0]["data"]["series"][0]["values"][0] = 1500
    m.write_json(job / "visuals.json", data)
    assert any("after rendering" in e for e in m.article_errors(job, "qa"))


def test_quote_can_go_to_review_but_not_strapi_until_approved(job):
    complete(job)
    assert m.export_errors(job, "review", remote=False) == []
    assert any("not approved" in e for e in m.export_errors(job, "strapi", remote=False))
    approve(job)
    assert m.export_errors(job, "strapi", remote=False) == []
    q = m.read_json(job / "expert_quotes.json")
    q["quotes"][0]["text"] += " Новый текст."
    m.write_json(job / "expert_quotes.json", q)
    assert any("not approved" in e for e in m.validate_inputs(job))


def test_missing_fact_or_unsupported_illustration_is_rejected(job):
    data = m.read_json(job / "visuals.json")
    data["visuals"][0]["data"]["series"][0]["evidence_ids"][0] = ["MISSING-01"]
    m.write_json(job / "visuals.json", data)
    assert any("unknown evidence_ids" in e for e in m.validate_inputs(job))
    data["visuals"][0]["type"] = "illustration"
    m.write_json(job / "visuals.json", data)
    assert any("discussed separately" in e for e in m.validate_inputs(job))


def test_upload_persists_media_metadata_and_is_idempotent(job, monkeypatch):
    renderer.render(job)
    send = Mock(side_effect=lambda path, info, filename: {"id": 123, "url": "/uploads/test.png", **info})
    monkeypatch.setattr(uploader, "upload_file", send)
    monkeypatch.setattr(uploader, "capture_uploaded_png", Mock(return_value=(job / "assets/annual-cost.strapi.png", "test-remote-hash", True)))
    uploader.upload(job)
    uploader.upload(job)
    assert send.call_count == 1
    info = send.call_args.args[1]
    assert info["alternativeText"] and info["caption"] and info["name"]
    assert m.read_json(job / "visuals.json")["visuals"][0]["asset"]["url"].startswith("https://")


def test_docs_parser_and_diff_preserve_images_quotes_and_captions(job):
    complete(job)
    article = (job / "edited.md").read_text()
    blocks = docs.parse(article)
    assert [b[0] for b in blocks].count("image") == 1
    assert any(b[0] == "caption" for b in blocks)
    assert any(b[0] == "quote" for b in blocks)
    assert not any(b[0] == "para" and b[1].startswith("![") for b in blocks)
    assert not any(docs.mark_changed(blocks, article))


def test_docs_inserts_native_image_and_requires_object_id():
    svc = Mock()
    svc.documents().get().execute.return_value = {"body": {"content": [{"endIndex": 2}]}}
    svc.documents().batchUpdate().execute.return_value = {"replies": [{}, {"insertInlineImage": {"objectId": "image1"}}]}
    block = ("image", "Описание", "https://example.com/image.png", "Название")
    receipt = docs.append_image(svc, "doc1", block)
    assert receipt["object_id"] == "image1"
    req = svc.documents().batchUpdate.call_args.kwargs["body"]["requests"]
    assert req[1]["insertInlineImage"]["uri"] == block[2]
    svc.documents().batchUpdate().execute.return_value = {"replies": [{}, {}]}
    with pytest.raises(RuntimeError, match="did not confirm"):
        docs.append_image(svc, "doc1", block)


def test_google_docs_roundtrip_image_and_preface_exclusion():
    svc = Mock()
    image = {"object_id": "img1", "alt": "Схема", "url": "https://example.com/a.png", "title": "Решение"}
    svc.documents().get().execute.return_value = {
        "namedRanges": {"BLOG_ARTICLE_BODY": {"namedRanges": [{"ranges": [{"startIndex": 10, "endIndex": 40}]}]}},
        "inlineObjects": {"img1": {"inlineObjectProperties": {"embeddedObject": {"imageProperties": {"sourceUri": image["url"]}}}}},
        "body": {"content": [
            {"paragraph": {"elements": [{"startIndex": 1, "endIndex": 10, "textRun": {"content": "Служебная заметка\n"}}]}},
            {"paragraph": {"elements": [{"startIndex": 10, "endIndex": 25, "textRun": {"content": "Текст статьи\n"}}]}},
            {"paragraph": {"elements": [{"startIndex": 25, "endIndex": 26, "inlineObjectElement": {"inlineObjectId": "img1"}},
                                       {"startIndex": 26, "endIndex": 27, "textRun": {"content": "\n"}}]}}
        ]}}
    current = review.doc_text(svc, "doc", [image])
    sent = 'Текст статьи\n\n![Схема](https://example.com/a.png "Решение")\n'
    assert "Служебная заметка" not in current
    assert review.build_diff(sent, current) == ""
    svc.documents().get().execute.return_value["body"]["content"].pop()
    assert "-IMAGE:" in review.build_diff(sent, review.doc_text(svc, "doc", [image]))


def test_export_refuses_alt_stripped_by_cms_before_publish(job, monkeypatch):
    complete(job)
    approve(job)
    monkeypatch.setattr(publish, "export_errors", lambda *a: [])
    monkeypatch.setattr(publish, "slug_is_free", lambda *a: True)
    calls = []
    body = (job / "out/article.html").read_text()
    def api(path, method="GET", payload=None):
        calls.append((path, method, payload))
        if method == "POST":
            assert payload["data"]["publishedAt"] is None
            return {"data": {"id": 123}}
        if method == "GET":
            return {"data": {"content": publish.cms_image_html(body).replace(' alt="Сценарий B стоит вдвое дороже сценария A в условном примере"', '')}}
        raise AssertionError("публикация не должна произойти")
    monkeypatch.setattr(publish, "api", api)
    monkeypatch.setattr(sys, "argv", ["strapi_publish.py", "--job", str(job), "--publish"])
    with pytest.raises(SystemExit, match="left as a draft"):
        publish.main()
    assert not any(method == "PUT" for _, method, _ in calls)


def test_materialization_is_repeatable_and_preserves_quote(job):
    complete(job)
    before = (job / "edited.md").read_text()
    pack.package(job, bind_visuals=True)
    assert (job / "edited.md").read_text() == before
    assert "Сравнивайте расходы" in before


@pytest.mark.parametrize("kind", ["line", "process", "decision"])
def test_other_supported_visuals_render_without_truncation(job, kind):
    data = m.read_json(job / "visuals.json")
    v = data["visuals"][0]
    v["type"] = kind
    if kind == "line":
        v["data"].update(x_label="Условный объём", x_values=[1, 3])
    else:
        v["data"] = {"nodes": [
            {"id": "start", "label": "Исходные условия", "evidence_ids": ["PRICE-01"]},
            {"id": "next", "label": "Comparable comparison", "evidence_ids": ["PRICE-02"]}],
            "edges": [{"from": "start", "to": "next", "label": "Проверка"}]}
    m.write_json(job / "visuals.json", data)
    renderer.render(job)
    assert (job / "assets/annual-cost.png").stat().st_size > 1000


def test_diagram_dashed_edge_is_rendered_and_invalid_style_is_rejected(job):
    data = m.read_json(job / "visuals.json")
    v = data["visuals"][0]
    v["type"] = "process"
    v["data"] = {"nodes": [
        {"id": "parent", "label": "Parent", "evidence_ids": ["PRICE-01"]},
        {"id": "associate", "label": "Associate", "evidence_ids": ["PRICE-02"]}],
        "edges": [{"from": "parent", "to": "associate", "label": "Influence", "style": "dashed"}]}
    m.write_json(job / "visuals.json", data)
    renderer.render(job)
    assert 'stroke-dasharray="14 10"' in (job / "assets/annual-cost.svg").read_text()
    v["data"]["edges"][0]["style"] = "dotted"
    m.write_json(job / "visuals.json", data)
    assert any("solid or dashed" in e for e in m.validate_inputs(job))


def test_diagram_cycle_and_unproven_fact_stop_before_render(job):
    data = m.read_json(job / "visuals.json")
    v = data["visuals"][0]
    v["type"] = "decision"
    v["data"] = {"nodes": [
        {"id": "a", "label": "A", "evidence_ids": ["PRICE-01"]},
        {"id": "b", "label": "B", "evidence_ids": ["PRICE-02"]}],
        "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "a"}]}
    m.write_json(job / "visuals.json", data)
    assert any("without cycles" in e for e in m.validate_inputs(job))
    (job / "evidence.md").write_text((job / "evidence.md").read_text().replace("supports", "no"))
    assert any("evidence_ids" in e for e in m.validate_inputs(job))


def test_two_input_process_merges_independent_inputs(job):
    data = m.read_json(job / "visuals.json")
    v = data["visuals"][0]
    v["type"] = "process"
    nodes = [
        {"id": f"n{i}", "label": label, "evidence_ids": ["PRICE-01"]}
        for i, label in enumerate([
            "Review status", "Establish baseline", "Employer ceiling",
            "Worker floor", "Feasible offer range", "Local route", "Record transition",
        ])
    ]
    pairs = [(0, 1), (1, 2), (1, 3), (2, 4), (3, 4), (4, 5), (5, 6)]
    v["data"] = {"layout": "two-input-merge", "nodes": nodes,
                 "edges": [{"from": f"n{a}", "to": f"n{b}"} for a, b in pairs]}
    m.write_json(job / "visuals.json", data)
    assert not any("tree" in e or "two-input-merge" in e for e in m.validate_inputs(job))
    renderer.render(job)
    assert (job / "assets/annual-cost.png").stat().st_size > 1000
    v["data"]["edges"].remove({"from": "n3", "to": "n4"})
    m.write_json(job / "visuals.json", data)
    assert any("two-input-merge" in e for e in m.validate_inputs(job))


def test_competitor_sources_stay_internal(job):
    data = m.read_json(job / "visuals.json")
    v = data["visuals"][0]
    v["sources"][0]["public"] = False
    v["asset"] = {"url": "https://example.com/image.png"}
    block = m.visual_markdown(v)
    assert "https://example.com/source" not in block
    assert "Условный источник" in block


def test_upload_selects_verified_original_when_cms_returns_webp(job, monkeypatch):
    renderer.render(job)
    remote = Mock(return_value=(job / "assets/annual-cost.strapi.png", "remote-verified-hash", True))
    send = Mock(side_effect=lambda path, info, filename: {
        "id": 124, "url": "https://bucket.example.com/lg_webp_hash_abc.webp",
        "provider": "aws-s3", "hash": "hash_abc", "ext": ".png", **info})
    monkeypatch.setattr(uploader, "upload_file", send)
    monkeypatch.setattr(uploader, "capture_uploaded_png", remote)
    uploader.upload(job)
    asset = m.read_json(job / "visuals.json")["visuals"][0]["asset"]
    assert asset["url"] == "https://bucket.example.com/hash_abc.png"
    assert asset["delivery_url"].endswith(".webp")
    remote.assert_called_once_with(asset["url"], job / asset["path"])
    assert asset["remote_sha256"] == "remote-verified-hash"


def test_upload_retry_after_remote_failure_reuses_media(job, monkeypatch):
    renderer.render(job)
    initial = m.read_json(job / "visuals.json")
    initial["visuals"][0]["asset"].update({
        "url": "https://drive.google.com/old-review.png", "media_id": "drive:review",
        "remote_path": "assets/annual-cost.drive.png"})
    m.write_json(job / "visuals.json", initial)
    data = {"id": 125, "url": "/uploads/test.png", "name": "Условные годовые расходы",
            "alternativeText": "Сценарий B стоит вдвое дороже сценария A в условном примере",
            "caption": "Технический пример: условные данные, не для публикации."}
    send = Mock(return_value=data)
    remote = Mock(side_effect=[ValueError("CDN unavailable"), (job / "assets/annual-cost.strapi.png", "remote-verified-hash", True)])
    lookup = Mock(return_value=data)
    monkeypatch.setattr(uploader, "upload_file", send)
    monkeypatch.setattr(uploader, "api", lookup)
    monkeypatch.setattr(uploader, "capture_uploaded_png", remote)
    with pytest.raises(ValueError, match="CDN"):
        uploader.upload(job)
    asset = m.read_json(job / "visuals.json")["visuals"][0]["asset"]
    assert asset["media_id"] == 125 and asset["url"].startswith("https://drive.google.com/")
    uploader.upload(job)
    assert send.call_count == 1
    lookup.assert_called_once_with("/upload/files/125")
    assert m.read_json(job / "visuals.json")["visuals"][0]["asset"]["url"].endswith("/uploads/test.png")


def test_remote_png_recompression_captured_for_qa_with_original_dimensions(job, monkeypatch):
    import subprocess
    renderer.render(job)
    path = job / "assets/annual-cost.png"
    brand = ROOT / "tools/covers"
    code = "const sharp=require('sharp'); sharp(process.argv[1]).png({compressionLevel:0}).toBuffer().then(b=>process.stdout.write(b));"
    optimized = subprocess.run(["node", "-e", code, str(path)], cwd=brand, capture_output=True, check=True).stdout
    assert m.digest(optimized) != m.digest(path.read_bytes())
    monkeypatch.setattr(uploader, "fetch_remote_image", lambda url: optimized)
    delivered, sha, identical = uploader.capture_uploaded_png("https://example.com/chart.png", path)
    assert sha == m.digest(optimized) and identical
    assert delivered.read_bytes() == optimized
    code = "const sharp=require('sharp'); sharp({create:{width:1200,height:720,channels:4,background:'#fff'}}).png().toBuffer().then(b=>process.stdout.write(b));"
    different = subprocess.run(["node", "-e", code], cwd=brand, capture_output=True, check=True).stdout
    monkeypatch.setattr(uploader, "fetch_remote_image", lambda url: different)
    with pytest.raises(ValueError, match="dimensions"):
        uploader.capture_uploaded_png("https://example.com/changed.png", path)


def test_modified_local_delivery_file_blocks_qa(job):
    complete(job)
    data = m.read_json(job / "visuals.json")
    a = data["visuals"][0]["asset"]
    remote = job / "assets/annual-cost.strapi.png"
    remote.write_bytes((job / a["path"]).read_bytes())
    a.update({"remote_path": str(remote.relative_to(job)), "remote_sha256": m.digest(remote.read_bytes())})
    m.write_json(job / "visuals.json", data)
    assert m.article_errors(job, "qa") == []
    remote.write_bytes(b"changed")
    assert any("file for QA" in e for e in m.article_errors(job, "qa"))


def test_strapi_export_works_without_cms_title_support(job, monkeypatch):
    complete(job)
    approve(job)
    monkeypatch.setattr(publish, "export_errors", lambda *a: [])
    monkeypatch.setattr(publish, "slug_is_free", lambda *a: True)
    source = (job / "out/article.html").read_text()
    calls = []
    stored = {}
    def api(path, method="GET", payload=None):
        calls.append((path, method, payload))
        if method == "POST":
            exported = payload["data"]["contentHtml"]
            assert ' title="' not in exported
            assert ' alt="' in exported and '<figcaption>' in exported
            assert payload["data"]["publishedAt"] is None
            stored["content"] = exported
            return {"data": {"id": 123}}
        if method == "GET":
            return {"data": stored}
        return {"data": {"id": 123}}
    monkeypatch.setattr(publish, "api", api)
    monkeypatch.setattr(sys, "argv", ["strapi_publish.py", "--job", str(job), "--publish"])
    publish.main()
    assert any(method == "PUT" for _, method, _ in calls)
    assert (job / "out/article.html").read_text() == source
    assert ' title="' in html.convert((job / 'edited.md').read_text())[1]


def test_codex_evidence_extra_columns_and_varied_ids_are_supported(job):
    (job / "evidence.md").write_text(
        "| claim_id | claim | section | source_url | source_tier | supporting_quote | last_checked | entailment_verdict | article_link | decision_use |\n"
        "| A01 | Claim A | pricing | https://example.com | primary | Quote | 2026 | supports | required | Decide |\n"
        "| vendor-northwind | Claim B | pricing | https://example.com | primary | Quote | 2026 | partial | forbidden | Compare |\n"
        "| PKG-01A | Claim C | pricing | https://example.com | primary | Quote | 2026 | no | forbidden | Discard |\n")
    assert m.evidence_ids(job) == {"A01", "vendor-northwind"}


def test_evidence_ids_preserve_escaped_pipe_quote_columns(job):
    (job / "evidence.md").write_text(
        "| claim_id | claim | section | source_url | source_tier | supporting_quote | last_checked | entailment_verdict | article_link | decision_use |\n"
        "| E-21 | Verified rate | safety | https://example.com | primary | Construction \\| 1034 \\| 9.2 | 2026 | supports | required | Compare |\n"
        "| E-22 | Rejected rate | safety | https://example.com | primary | supports \\| 99 | 2026 | no | forbidden | Reject |\n")
    assert m.evidence_ids(job) == {"E-21"}


def test_nonexistent_research_reference_blocks_writer(job):
    data = m.read_json(job / "sections.json")
    data["information_gain"][0]["research_ref"] = "R-99"
    m.write_json(job / "sections.json", data)
    assert any("research.md" in e for e in m.validate_inputs(job))


def test_external_quote_must_match_verified_scout_excerpt():
    quote = {"source": "https://example.org/interview", "text": "Exact practitioner words."}
    packet = {"candidates": [
        {"status": "verified_original", "source_url": "https://example.org/interview",
         "quote": "Exact practitioner words."},
        {"status": "lead", "source_url": "https://example.org/other",
         "quote": "Unverified words."},
    ]}
    assert m.external_quote_in_scout(quote, packet)
    assert not m.external_quote_in_scout({**quote, "text": "Paraphrased words."}, packet)
    assert not m.external_quote_in_scout(
        {"source": "https://example.org/other", "text": "Unverified words."}, packet)


def test_v2_export_requires_actual_delivered_png_copy(job):
    complete(job)
    data = m.read_json(job / "visuals.json")
    asset = data["visuals"][0]["asset"]
    del asset["remote_path"]
    del asset["remote_sha256"]
    m.write_json(job / "visuals.json", data)
    m.write_json(job / "qa_receipt.json", {"hashes": m.qa_fingerprint(job)})
    assert any("PNG from the CMS" in e for e in m.export_errors(job, "review", remote=False))


def test_unknown_docs_image_identity_is_not_silently_unchanged():
    svc = Mock()
    svc.documents().get().execute.return_value = {
        "body": {"content": [{"paragraph": {"elements": [{"startIndex": 1, "endIndex": 2,
            "inlineObjectElement": {"inlineObjectId": "img1"}}]}}]},
        "inlineObjects": {"img1": {"inlineObjectProperties": {"embeddedObject": {
            "imageProperties": {"contentUri": "https://example.com/replacement.png"}}}}}}
    original = [{"object_id": "img1", "alt": "Original", "url": "https://example.com/original.png", "title": "Original"}]
    current = review.doc_text(svc, "doc", original)
    assert "Changed image" in current
    assert "original.png" not in current


def test_conflicting_overall_qa_verdicts_block_export(job):
    complete(job)
    (job / "qa_report.md").write_text("overall: PASS\noverall: BLOCK\n")
    m.write_json(job / "qa_receipt.json", {"hashes": m.qa_fingerprint(job)})
    assert not m.qa_is_pass(job)
    assert any("QA" in e for e in m.export_errors(job, "review", remote=False))
