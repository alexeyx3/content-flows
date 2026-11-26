import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import blog_openrouter as blog
import openrouter_blog_experiment as api
from check_research_links import evidence_reference_errors, evidence_table_errors


@pytest.fixture
def batch(tmp_path, monkeypatch):
    routes = blog.read_json(blog.ROOT / 'config/blog-openrouter.json')
    monkeypatch.setattr(blog, 'ROOT', tmp_path)
    monkeypatch.setattr(api, 'ROOT', tmp_path)
    monkeypatch.setattr(blog, 'writer_ready_errors', lambda job: [])
    for name in blog.POLICIES:
        blog.write_text(tmp_path / 'knowledge' / name, 'Current publication policy\n')
    job = tmp_path / 'jobs' / 'test-article'
    blog.write_text(job / 'job.yaml', 'production_text_backend: openrouter_hybrid\ntemnik_cluster_id: b-1001\n')
    blog.write_text(job / 'brief.md', '# Best Title\n\n| H1 | Best Title |\n\n- **metaTitle:** Best Title\n'
                    '- **metaDescription:** Description\n- **summary:** Summary\n- **slug:** best-title\n')
    outline = {'title': 'Best Title', 'sections': [
        {'id': 'intro', 'title': 'Takeaways', 'subheadings': [{'level': 3, 'title': 'Details'}]},
        {'id': 'sources', 'title': 'Sources'},
    ]}
    blog.write_json(job / 'sections.json', outline)
    blog.write_text(job / 'serp.hybrid_outline.md', 'Approved SERP outline\n')
    blog.write_text(job / 'evidence.md', '| claim_id | source_url | article_link |\n'
                    '| --- | --- | --- |\n| E-01 | https://example.org/source | required |\n')
    blog.write_json(job / 'visuals.json', {'visuals': []})
    blog.write_json(job / 'expert_quotes.json', {'quotes': []})
    folder = tmp_path / 'docs/workflow-v2/batches/sample'
    run = tmp_path / 'runs/sample'
    items = [{'cluster_id': 'b-1001', 'job': 'jobs/test-article', 'heading': outline['title'],
              'sections': outline['sections'], 'article_type': 'guide',
              'sha256': {name: api.sha((job / name).read_bytes()) for name in blog.BRIEF_FILES}}]
    proposal = folder / 'publisher-proposal.json'
    blog.write_json(proposal, items)
    blog.write_json(folder / 'brief-approval.json', {
        'status': 'approved', 'publisher': 'the publisher', 'api_budget_usd': 4,
        'publisher_proposal_sha256': api.sha(proposal.read_bytes()), 'items': items,
    })
    return folder, run, job, routes


def mock_generation(experiment, parts):
    variant, = experiment.variants
    calls = []
    for stage, body in zip(experiment.stages(variant), parts, strict=True):
        def transport(request, key, timeout):
            calls.append(request['messages'])
            return 200, {'id': 'test-generation', 'model': variant['model'], 'provider': variant['provider_name'],
                         'usage': {'cost': 0.01}, 'choices': [
                             {'finish_reason': 'stop', 'message': {'content': body}},
                         ]}
        result = experiment.run_stage(variant, stage, 'fixture-key', transport=transport)
        assert result['status'] == 'success', result
    return calls


def test_writer_critic_and_targeted_repair_use_one_approved_ledger(batch):
    folder, run, job, routes = batch
    writer = blog.prepare(folder, run, 'writer', 'writing', None, routes)
    assert writer.dry_run()['paid_requests_sent'] == 0
    assert writer.variants[0]['model'].startswith('minimax/')
    blocks = ['## Takeaways\n\n### Details\n\nKeep the whole sentence E-01.\n',
              '## Sources\n\n- [Primary source](https://example.org/source)\n']
    messages = mock_generation(writer, blocks)
    assert any(m['role'] == 'assistant' and m['content'] == blocks[0] for m in messages[1])
    paths = {'b-1001': job}
    assert blog.import_outputs(writer, 'writer', paths, None) == {'imported': ['b-1001'], 'blocked': {}}
    draft = (job / 'out/draft.md').read_text()
    assert draft.startswith('# Best Title\n\n## Takeaways')
    assert 'E-01' in blog.read_json(job / 'raw/openrouter-draft-check.json')['warnings'][0]

    critic = blog.prepare(folder, run, 'critic', 'first-pass', None, routes)
    assert critic.variants[0]['model'].startswith('deepseek/')
    assert critic.stages(critic.variants[0])[0]['max_tokens'] == 16384
    mock_generation(critic, ['{"overall":"BLOCK","findings":[]}'])
    assert not blog.import_outputs(critic, 'critic', paths, None)['blocked']
    assert blog.read_json(job / 'raw/openrouter-critic.json')['overall'] == 'BLOCK'

    blog.write_text(job / 'edited.md', draft)
    blog.write_json(job / 'raw/openrouter-rework-plan.json', {'intro': 'Remove the internal evidence identifier.'})
    repair = blog.prepare(folder, run, 'repair', 'repair-1', ['b-1001'], routes)
    mock_generation(repair, [blocks[0].replace(' E-01', '')])
    assert not blog.import_outputs(repair, 'repair', paths, None)['blocked']
    assert (job / 'edited.md').read_text() == draft.replace(' E-01', '')
    assert blog.cost(run) == {'known_total_usd': '0.04', 'attempts': 4, 'unreconciled': [],
                              'articles': {'b-1001': {'known_usd': '0.04', 'attempts': 4}}}


def test_exact_title_amendment_resumes_an_interrupted_local_write(batch):
    folder, run, job, _ = batch
    body = b'\r\n## Takeaways\r\n\r\nOriginal body, spacing and facts.\r\n'
    (job / 'edited.md').write_bytes(b'# Best Title\r\n' + body)
    receipt = {'status': 'approved', 'publisher': 'the publisher', 'reference': 'publisher-response',
               'original_heading': 'Best Title', 'heading': 'Title', 'metaTitle': 'Title to use in search'}
    proof = blog.amend_title(folder, run, 'b-1001', receipt)
    assert (job / 'edited.md').read_bytes() == b'# Title\r\n' + body
    assert proof['body_sha256'] == api.sha(body)
    backup = run / 'title-amendments/b-1001/sections.json.before'
    (job / 'sections.json').write_bytes(backup.read_bytes())
    assert blog.amend_title(folder, run, 'b-1001', receipt) == proof
    assert blog.read_json(job / 'sections.json')['title'] == 'Title'
    assert blog.extract_metadata((job / 'brief.md').read_text())['metaTitle'] == receipt['metaTitle']


def test_heading_restoration_binds_output_and_preserves_other_bytes():
    raw = '## takeaways\n\nOriginal body.\n\n### Details\n\nUnchanged.  \n'
    unit = {'headings': [{'level': 2, 'title': 'Takeaways'}, {'level': 3, 'title': 'Details'}]}
    entry = {'ordinal': 1, 'raw_sha256': api.sha(raw.encode()),
             'old_heading': '## takeaways', 'new_heading': '## Takeaways'}
    assert blog.restore_headings(raw, unit, [entry]) == raw.replace('takeaways', 'Takeaways')
    with pytest.raises(api.ExperimentError, match='exact raw output'):
        blog.restore_headings(raw + '\n', unit, [entry])


def test_evidence_rows_hidden_by_blank_line_and_public_internal_ids(batch):
    _, _, job, _ = batch
    text = (job / 'evidence.md').read_text()
    text += '\n| E-41 | https://example.org/other | required |\n'
    assert 'E-41' in evidence_table_errors(text)[0]
    assert evidence_table_errors(text.replace('|\n\n| E-41', '|\n| E-41')) == []
    assert evidence_reference_errors(text, 'An E-1 visa and an E-14 contract.') == []
    assert 'E-41' in evidence_reference_errors(text, 'Source (E-41).')[0]
