"""Google Docs uploader quota handling."""
from unittest.mock import Mock
import json

from googleapiclient.errors import HttpError

from scripts.md_to_gdoc import execute_docs_write
from scripts.md_to_gdoc import append_run
from scripts.md_to_gdoc import parse, word_highlight_plan, inline, utf16_len, append_table, write_blocks
from googleapiclient.discovery_cache import get_static_doc


def quota_error():
    response = Mock(status=429)
    response.get.return_value = None
    return HttpError(response, b'{"error":{"message":"quota"}}')


def test_docs_write_retries_429_and_then_succeeds():
    request = Mock()
    request.execute.side_effect = [quota_error(), {"ok": True}]
    sleeps = []

    result = execute_docs_write(request, sleep=sleeps.append)

    assert result == {"ok": True}
    assert request.execute.call_count == 2
    assert sleeps == [2.0]


def test_docs_write_does_not_retry_non_quota_error():
    response = Mock(status=400)
    error = HttpError(response, b'{"error":{"message":"bad request"}}')
    request = Mock()
    request.execute.side_effect = error

    try:
        execute_docs_write(request, sleep=Mock())
    except HttpError as caught:
        assert caught is error
    else:
        raise AssertionError("non-quota HttpError must be raised")


def test_list_presets_are_valid_google_docs_discovery_values():
    svc = Mock()
    svc.documents.return_value.get.return_value.execute.return_value = {
        'body': {'content': [{'endIndex': 2}]}}
    append_run(svc, 'doc-id', [
        {'text': 'First step', 'style': 'NORMAL_TEXT', 'spans': [], 'changed': False, 'bullet': 'ordered'},
        {'text': 'A note', 'style': 'NORMAL_TEXT', 'spans': [], 'changed': False, 'bullet': 'unordered'}])
    requests = svc.documents.return_value.batchUpdate.call_args.kwargs['body']['requests']
    schema = json.loads(get_static_doc('docs', 'v1'))
    presets = schema['schemas']['CreateParagraphBulletsRequest']['properties']['bulletPreset']['enum']
    bullets = [r['createParagraphBullets']['bulletPreset'] for r in requests if 'createParagraphBullets' in r]
    assert len(bullets) == 2
    assert all(preset in presets for preset in bullets)


def test_31_literal_clause_labels_are_rendered_as_text_not_auto_numbered_lists():
    source = "\n\n".join(
        f"**{number}. Clause {number}**\n\nBody referring to Section {number}."
        for number in range(1, 32)
    ) + "\n\n## Checklist\n\n1. Confirm scope\n2. Sign\n"
    blocks = parse(source)
    assert all(blocks[index][0] == "para" for index in range(0, 62, 2))
    svc = Mock()
    svc.documents.return_value.get.return_value.execute.return_value = {"body": {"content": [{"endIndex": 2}]}}
    write_blocks(svc, "existing-doc", blocks, [False] * len(blocks))
    requests = svc.documents.return_value.batchUpdate.call_args.kwargs["body"]["requests"]
    inserted = requests[0]["insertText"]["text"]
    for number in range(1, 32):
        assert f"{number}. Clause {number}\n" in inserted
    bullets = [r["createParagraphBullets"] for r in requests if "createParagraphBullets" in r]
    assert len(bullets) == 2  # Only the actual checklist, never the clause paragraphs.
    assert all(b["range"]["startIndex"] > inserted.index("31. Clause 31") for b in bullets)


def test_word_mode_highlights_only_changed_price_token():
    old = "## Pricing\n\nThe plan costs $49 per month.\n"
    new = "## Pricing\n\nThe plan costs $59 per month.\n"
    blocks = parse(new)
    plans, removed = word_highlight_plan(blocks, old)
    text = inline(blocks[1][1])[0]
    assert [text[s:e] for s, e in plans[1]["spans"]] == ["59"]
    assert any("49" in row["text"] for row in removed)


def test_changed_table_leaves_unchanged_cell_unhighlighted():
    old = "## Pricing\n\n| Plan | Price | Scope |\n|---|---|---|\n| Basic | $49 | Global |\n"
    new = old.replace("$49", "$59")
    blocks = parse(new)
    plans, _ = word_highlight_plan(blocks, old)
    table = plans[1]["cells"]
    assert table[1][0] == []
    assert table[1][2] == []
    assert [inline(blocks[1][1][1][1])[0][s:e] for s, e in table[1][1]] == ["59"]
    svc = Mock()
    cells = lambda starts: [{'content': [{'startIndex': start}]} for start in starts]
    svc.documents.return_value.get.return_value.execute.side_effect = [
        {'body': {'content': [{'endIndex': 2}]}},
        {'body': {'content': [{'startIndex': 1, 'table': {'tableRows': [
            {'tableCells': cells([5, 15, 25])}, {'tableCells': cells([35, 45, 55])}]}}]}}]
    append_table(svc, 'doc-id', blocks[1][1], False, table)
    calls = svc.documents.return_value.batchUpdate.call_args_list
    styles = [req['updateTextStyle'] for req in calls[1].kwargs['body']['requests']
              if 'updateTextStyle' in req]
    clears = [style for style in styles if style['fields'] == 'backgroundColor' and style['textStyle'] == {}]
    highlighted = [style for style in styles if style['fields'] == 'backgroundColor' and style['textStyle']]
    assert len(clears) == 6  # the unchanged Scope cell is also cleared
    assert len(highlighted) == 1
    assert highlighted[0]['range'] == {'startIndex': 46, 'endIndex': 48}
    assert styles.index(next(style for style in clears if style['range'] == {'startIndex': 55, 'endIndex': 61})) < styles.index(highlighted[0])


def test_wholly_unchanged_table_clears_inherited_background_in_word_mode():
    article = "## Pricing\n\n| Plan | Price |\n|---|---|\n| Basic | $49 |\n"
    blocks = parse(article)
    plans, _ = word_highlight_plan(blocks, article)
    assert plans[1]['cells'] == []
    svc = Mock()
    cells = lambda starts: [{'content': [{'startIndex': start}]} for start in starts]
    table_doc = {'body': {'content': [{'startIndex': 1, 'table': {'tableRows': [
        {'tableCells': cells([5, 15])}, {'tableCells': cells([25, 35])}]}}]}}
    svc.documents.return_value.get.return_value.execute.side_effect = [
        {'body': {'content': [{'endIndex': 2}]}}, table_doc]
    append_table(svc, 'doc-id', blocks[1][1], False, plans[1]['cells'])
    reqs = svc.documents.return_value.batchUpdate.call_args_list[1].kwargs['body']['requests']
    backgrounds = [req['updateTextStyle'] for req in reqs if 'updateTextStyle' in req
                   and req['updateTextStyle']['fields'] == 'backgroundColor']
    assert len(backgrounds) == 4
    assert all(style['textStyle'] == {} for style in backgrounds)


def test_new_subsection_highlights_all_its_content():
    old = "## Options\n\nExisting introduction.\n"
    new = old + "\n### Newly added\n\nA whole new paragraph.\n"
    blocks = parse(new)
    plans, _ = word_highlight_plan(blocks, old)
    assert [blocks[i][0] for i in (2, 3)] == ["heading", "para"]
    assert plans[2]["spans"] == [(0, len("Newly added"))]
    assert plans[3]["spans"] == [(0, len("A whole new paragraph."))]


def test_repeated_boilerplate_never_aligns_across_sections():
    old = "## First\n\nContact sales for details.\n\n## Second\n\nContact sales for details.\n"
    new = "## First\n\nContact sales for details.\n\n## Second\n\nContact sales for pricing.\n"
    blocks = parse(new)
    plans, _ = word_highlight_plan(blocks, old)
    assert plans[1]["spans"] == []
    assert [blocks[3][1][s:e] for s, e in plans[3]["spans"]] == ["pricing"]


def test_unicode_prefix_uses_utf16_highlight_offsets():
    old = "## Notes\n\n😀 Цена 49 рублей.\n"
    new = "## Notes\n\n😀 Цена 59 рублей.\n"
    blocks = parse(new)
    plans, _ = word_highlight_plan(blocks, old)
    text = inline(blocks[1][1])[0]
    svc = Mock()
    svc.documents.return_value.get.return_value.execute.return_value = {'body': {'content': [{'endIndex': 2}]}}
    append_run(svc, 'doc-id', [{'text': text, 'style': 'NORMAL_TEXT', 'spans': [],
                                'changed': False, 'highlight_spans': plans[1]['spans'], 'bullet': False}])
    requests = svc.documents.return_value.batchUpdate.call_args.kwargs['body']['requests']
    backgrounds = [req['updateTextStyle'] for req in requests
                   if 'updateTextStyle' in req and req['updateTextStyle']['fields'] == 'backgroundColor']
    assert backgrounds[0]['textStyle'] == {}
    highlighted = [style['range'] for style in backgrounds if style['textStyle']]
    start = text.index('59')
    assert highlighted == [{'startIndex': 1 + utf16_len(text[:start]),
                            'endIndex': 1 + utf16_len(text[:start + 2])}]


def test_removed_subsection_is_reported_and_not_inserted():
    old = "## Options\n\n### Retired\n\nOld guidance to remove.\n"
    new = "## Options\n\nCurrent guidance.\n"
    blocks = parse(new)
    plans, removed = word_highlight_plan(blocks, old)
    assert any(row['text'] == 'Old guidance to remove.' for row in removed)
    assert all('Old guidance' not in str(block) for block in blocks)
    assert plans[1]['spans'] == [(0, len('Current guidance.'))]
