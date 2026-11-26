"""Production integration contracts, with fully fake API transport and credentials."""
import copy
import json
from pathlib import Path
import re
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import guide_api as guide
from test_scripts import FACTS

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / 'project'; root.mkdir()
    monkeypatch.setattr(guide, 'ROOT', root)
    monkeypatch.setattr(guide.api, 'ROOT', root)
    (root / 'config').mkdir()
    shutil.copy2(PROJECT / 'config/guide-execution.json', root / 'config/guide-execution.json')
    for name, relative in guide.POLICIES.items():
        p = root / relative; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{}' if name.endswith('.json') else 'Complete policy ' + name)
    job = root / 'jobs/2099-01-01-testland'; job.mkdir(parents=True)
    (job / 'job.json').write_text(json.dumps({'slug': 'testland'}))
    facts = copy.deepcopy(FACTS)
    facts['facts'][0]['claim'] = 'Employment fact sentinel'
    contractor = copy.deepcopy(facts['facts'][0]); contractor.update(id='F-500', claim='Contractor fact sentinel', pages=['contractors'])
    facts['facts'].append(contractor)
    (job / 'facts.json').write_text(json.dumps(facts))
    for n, text in [('derived.json', '{"rows":[]}'), ('evidence.md', 'All employment E-001 and contractors E-900'), ('evidence.vendors.md', 'All vendor V-001 rows')]: (job / n).write_text(text)
    (job / 'research').mkdir()
    for name in ['changes', 'practitioners', 'angle']: (job / 'research' / (name + '.md')).write_text('Full research ' + name)
    for page in guide.PAGES:
        p = guide.page_dir(job, page); p.mkdir(parents=True)
        c = {'title': 'Hiring in Testland', 'sections': [{'id': 'answer', 'title': '', 'instruction': 'Direct answer'}, {'id': 'law', 'title': 'Law', 'instruction': 'All conditions'}, {'id': 'sources', 'title': 'Sources', 'instruction': 'All originals'}]}
        for n, text in [('sections.json', json.dumps(c)), ('brief.md', 'Complete contract'), ('evidence.md', 'ALL F/C/E/V rows, never filter'), ('research.md', 'All research'), ('visuals.json', '{"version":2,"visuals":[]}'), ('company_cards.md', 'Approved full cards')]: (p / n).write_text(text)
    calls = []
    monkeypatch.setattr(guide.api, 'countries_key', lambda *_: 'offline-test')
    def post(request, *_):
        calls.append(request)
        dynamic = request['input'][-1]['content'][0]['text']
        if 'ASSIGNED SECTION:\n' in dynamic:
            assigned = json.JSONDecoder().raw_decode(dynamic.split('ASSIGNED SECTION:\n', 1)[1])[0]['contract']
            sid = assigned['id']; title = assigned['title']
            body = ('## ' + title + '\n\n') if title else ''
            body += ('1. Official. [Original](https://example.gov/original). Accessed 12 November 2026.\n' if sid == 'sources' else 'Draft wording with all conditions.\n')
            if sid == 'law' and '[[VISUAL:figure]]' in assigned['instruction']: body += '\n[[VISUAL:figure]]\n'
            output = {'section_md': body, 'state_delta': [{'key': sid + '/facts/note', 'category': 'facts-used', 'text': 'Full note for ' + sid}]}
        else:
            match = re.search(r'INPUT FILE: ([^\n]+/article.md)\n', dynamic)
            before = (root / match.group(1)).read_text()
            if 'patches (array' in dynamic and 'bounded repair mode' in dynamic:
                old = before.split('\n## Law', 1)[0]
                output = {'patches': [{'old': old, 'new': old.replace('Natural wording', 'Repaired wording', 1)}], 'repair_report': 'Q001 resolved'}
            elif 'SEPARATE whole-page humanization' in dynamic:
                output = {'article_md': before.replace('Edited wording', 'Natural wording'), 'humanization_report': 'Whole page reviewed; concrete wording corrected; all headings, conditions, quotes and sources preserved. AI score not detector.'}
            else: output = {'article_md': before.replace('Draft wording', 'Edited wording'), 'editor_report': 'Full page reviewed; depth preserved'}
        return 200, {'id': 'resp_fake', 'model': request['model'], 'reasoning': {'effort': 'medium'}, 'status': 'completed',
                     'usage': {'input_tokens': 1000, 'input_tokens_details': {'cached_tokens': 500, 'cache_write_tokens': 0, 'cache_write_tokens_details': {'ttl_30m_tokens': 0, 'ttl_12h_tokens': 0}}, 'output_tokens': 100, 'output_tokens_details': {'reasoning_tokens': 10}},
                     'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(output)}]}]}
    monkeypatch.setattr(guide.api, 'post_json', post)
    return job, calls, post


def frozen_legacy_job(job, revision='v1'):
    profile = guide.load_profile()
    profile['default_backend'] = 'openai_api'
    for name in ('writer', 'editor', 'humanizer'):
        profile[name]['backend'] = 'openai_api'
    path = guide.ROOT / 'runs/guide-api' / job.name / revision / 'profile.json'
    guide.write(path, guide.stable(profile), immutable=True)
    return guide.GuideAPI(job, revision)


@pytest.fixture
def setup(project):
    job, calls, post = project
    return frozen_legacy_job(job), calls, post


def execute(run, stage, pages=('country',), round=1, findings=None):
    e = run.prepare(stage, list(pages), round, findings)
    return run.execute(e, stage, list(pages), round)

def test_verified_upstream_rejection_releases_reserve_without_faking_usage(project):
    job, _, _ = project
    run = guide.GuideAPI(job)
    e = run.prepare('writer', ['country'])
    v = e.variants[0]
    stage = e.stages(v)[0]
    error = {'error': {'code': 429, 'message': 'temporarily rate-limited upstream',
                       'metadata': {'provider_name': 'OpenAI'}}}
    result = e.run_stage(v, stage, 'offline-test', transport=lambda *_: (429, error))
    assert result['status'] == 'failed'
    receipt = e.attempts()[0].with_name('receipt.json')
    original = receipt.read_bytes()
    assert e.usage_summary()['unknown_charge_attempts'] == 1
    audit = guide.stable({'schema_version': 1, 'source': 'https://openrouter.ai/api/v1/key',
                          'current_usage_usd': '10.12', 'baseline_usage_usd': '10',
                          'reported_usage_usd': '0.12', 'rejected_receipts': [guide.digest(original)]})
    guide.write(e.run_dir / 'reconciliations' / (guide.digest(audit.encode()) + '.json'), audit)
    usage = e.usage_summary()
    assert usage['unknown_charge_attempts'] == 0
    assert usage['reconciled_upstream_rejections'] == 1
    assert usage['retained_cost_bound_usd'] == 0
    assert usage['provider_reported_cost_usd'] is None
    receipt.with_name('response.json').write_text('{}')
    assert e.usage_summary()['unknown_charge_attempts'] == 1
    assert receipt.read_bytes() == original

def test_compact_resume_keeps_saved_request_and_all_original_inputs(project):
    job, _, fake_post = project
    facts = guide.read(job / 'facts.json')
    page = guide.page_dir(job, 'country')
    rows = guide.fact_rows(facts, guide.read(job / 'derived.json'))
    (page / 'evidence.md').write_text(
        f"# Evidence — {facts['country']} (country)\n\n" + guide.EVIDENCE_HEADER + '\n'.join(rows) + '\n')
    research = sorted((job / 'research').glob('*.md'))
    (page / 'research.md').write_text('\n\n'.join(f'<!-- {p.name} -->\n{p.read_text()}' for p in research))
    e = guide.GuideAPI(job).prepare('writer', ['country'])
    variant = e.variants[0]
    opening, next_stage, _ = e.stages(variant)
    original = e.build_request(variant, opening)

    def respond(request, *_):
        status, response = fake_post(request, '', 1)
        response['usage']['cost'] = 0.1
        response['openrouter_metadata'] = {
            'requested': request['model'], 'attempt': 1, 'is_byok': False,
            'endpoints': {'available': [{'provider': 'OpenAI',
                                        'model': 'openai/gpt-6.1-terra-20261026', 'selected': True}]},
        }
        return status, response

    assert e.run_stage(variant, opening, 'offline', transport=respond)['status'] == 'success'
    resumed = guide.GuideAPI(job, compact_packet=True).prepare('writer', ['country'])
    assert resumed.build_request(variant, opening) == original
    full = e.build_request(variant, next_stage)
    compact = resumed.build_request(variant, next_stage)
    shared = compact['input'][1]['content'][0]
    assert 'Contractor fact sentinel' in shared['text'] and 'E-900' in shared['text']
    assert 'Full research practitioners' in shared['text'] and shared['prompt_cache_breakpoint'] == {'mode': 'explicit'}
    assert compact['input'][-1] == full['input'][-1]
    assert len(guide.api.encoded(compact)) < len(guide.api.encoded(full))


def test_frozen_legacy_flow_keeps_exact_routes_and_native_qa(setup):
    run, calls, _ = setup
    execute(run, 'writer')
    execute(run, 'writer', ('eor', 'contractors'))
    execute(run, 'editor', guide.PAGES)
    execute(run, 'humanizer', guide.PAGES)
    assert len(calls) == 15
    assert [r['model'] for r in calls[:9]] == ['gpt-6.1-terra'] * 9
    assert [r['model'] for r in calls[9:]] == ['gpt-6.2-sol'] * 6
    for r in calls:
        assert r['reasoning'] == {'effort': 'medium'}
        assert r['prompt_cache_options'] == {'mode': 'explicit', 'ttl': '30m'}
        payload = json.dumps(r)
        assert 'Employment fact sentinel' in payload and 'Contractor fact sentinel' in payload
        assert 'E-900' in payload and 'V-001' in payload
    for page in guide.PAGES:
        p = guide.page_dir(run.job, page)
        assert 'Natural wording' in (p / 'edited.md').read_text()
        assert guide.digest((p / 'edited.md').read_bytes()) in (p / 'humanization_report.md').read_text()
        assert not (p / 'qa_receipt.json').exists() and not (p / 'review_approval.json').exists()
    assert run.profile['final_qa']['backend'] == 'codex'
    assert run.profile['final_qa']['model'] == 'gpt-6.2-sol'


def test_dry_run_no_credentials_post_or_job_changes(setup, monkeypatch, capsys):
    run, calls, _ = setup
    before = {str(p): p.read_bytes() for p in run.job.rglob('*') if p.is_file()}
    monkeypatch.setattr(guide.api, 'countries_key', lambda *_: pytest.fail('No credential read in dry run'))
    assert guide.main(['--job', str(run.job), '--stage', 'writer', '--page', 'country']) == 0
    assert json.loads(capsys.readouterr().out)['paid_requests_sent'] == 0
    assert before == {str(p): p.read_bytes() for p in run.job.rglob('*') if p.is_file()}
    assert not calls


@pytest.mark.parametrize('fault', [None, 'wrong_provider', 'missing_cost'])
def test_openrouter_uses_pinned_provider_and_exact_reported_cost(project, monkeypatch, fault):
    job, calls, post = project
    run = guide.GuideAPI(job)
    monkeypatch.setattr(guide.api.router, 'countries_key', lambda *_: 'offline-router-test')

    def openrouter(request, key, timeout, *, endpoint, extra_headers):
        assert key == 'offline-router-test' and endpoint == guide.api.OPENROUTER_RESPONSES
        assert extra_headers == {'X-OpenRouter-Metadata': 'enabled'}
        assert request['model'] == 'openai/gpt-6.1-terra'
        assert request['provider']['only'] == ['openai']
        assert request['provider']['allow_fallbacks'] is False
        assert request['prompt_cache_options'] == {'mode': 'explicit', 'ttl': '30m'}
        _, response = post(request, key, timeout)
        response['openrouter_metadata'] = {
            'requested': request['model'], 'attempt': 1, 'is_byok': False,
            'endpoints': {'available': [{'provider': 'Azure' if fault == 'wrong_provider' else 'OpenAI',
                                        'model': 'openai/gpt-6.1-terra-20261026', 'selected': True}]},
        }
        if fault != 'missing_cost':
            response['usage']['cost'] = 0.123
        return 200, response

    monkeypatch.setattr(guide.api.router, 'post_json', openrouter)
    if fault:
        with pytest.raises(guide.api.ExperimentError, match='stopped'):
            execute(run, 'writer')
        assert not run.public('country', 'out/draft.md').exists() and len(calls) == 1
        if fault == 'missing_cost':
            ledger = guide.read(run.run / 'usage.writer-by-page.json')
            assert ledger['pages']['country']['unknown_charges'] == 1
            assert ledger['total_cost_usd'] is None
    else:
        stats = execute(run, 'writer')['usage']
        assert stats['provider_reported_cost_usd'] == pytest.approx(0.369)
        assert stats['token_charge_estimate_usd'] is None and stats['unknown_charge_attempts'] == 0
        ledger = guide.read(run.run / 'usage.writer-by-page.json')
        assert ledger['pages']['country']['known_cost_usd'] == ledger['total_cost_usd'] == '0.369'
        experiment = run.prepare('writer', ['country'])
        request = calls[0]
        request_bytes = len(guide.api.encoded(request['input']))
        expected_bound = ((request_bytes + 4096) * 2 * 1.25 + request['max_output_tokens'] * 5 * 1.5) / 1_000_000
        assert experiment.cost_bound(request) == pytest.approx(expected_bound)
        execute(run, 'writer')
        assert len(calls) == 3
        execute(run, 'writer', ('eor', 'contractors'))
        ledger = guide.read(run.run / 'usage.writer-by-page.json')
        assert ledger['total_cost_usd'] == '1.107'
        assert {page: row['known_cost_usd'] for page, row in ledger['pages'].items()} == {
            page: '0.369' for page in guide.PAGES
        }


def test_new_guides_route_editing_style_and_qa_to_codex(project):
    job, calls, _ = project
    run = guide.GuideAPI(job)
    assert run.backend == 'openrouter'
    assert run.profile['editor']['backend'] == run.profile['humanizer']['backend'] == 'codex'
    assert run.profile['final_qa']['independent'] is True
    for stage in ('editor', 'humanizer', 'repair'):
        with pytest.raises(guide.api.ExperimentError, match='runs in Codex with guide-editor'):
            run.prepare(stage, ['country'])
    with pytest.raises(guide.api.ExperimentError, match='assigned guide route'):
        guide.GuideAPI(job, backend='openai_api')
    assert not calls and not run.run.exists()


def test_new_revision_budget_can_account_for_earlier_spend(setup):
    run, _, _ = setup
    with pytest.raises(guide.api.ExperimentError):
        guide.GuideAPI(run.job, 'bigger', max_cost_usd=16)
    revised = guide.GuideAPI(run.job, 'remaining', max_cost_usd=7)
    assert revised.profile['max_cost_usd'] == 7 and revised.profile['max_call_cost_usd'] == 7


def test_explicit_call_cap_handles_large_reserve_without_raising_total(setup, monkeypatch, capsys):
    run, calls, _ = setup
    monkeypatch.setattr(guide.api.Experiment, 'cost_bound', lambda *_: 9.0)
    monkeypatch.setattr(guide.api, 'countries_key', lambda *_: pytest.fail('Dry run must not read credentials'))
    assert guide.main(['--job', str(run.job), '--stage', 'writer', '--page', 'country']) == 2
    assert 'per-call cap' in json.loads(capsys.readouterr().out)['error']
    args = ['--job', str(run.job), '--revision', 'large-packet', '--max-call-cost-usd', '10',
            '--stage', 'writer', '--page', 'country']
    assert guide.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['max_call_cost_usd'] == 10 and result['max_cost_usd'] == 15
    assert result['paid_requests_sent'] == 0 and not calls
    profile = guide.read(run.run.parent / 'large-packet/profile.json')
    assert profile['max_call_cost_usd'] == 10 and profile['max_cost_usd'] == 15
    # Resuming uses the saved cap even when the new invocation omits the flag.
    assert guide.main(args) == 0
    capsys.readouterr()
    assert guide.main([x for x in args if x not in ['--max-call-cost-usd', '10']]) == 0
    assert json.loads(capsys.readouterr().out)['max_call_cost_usd'] == 10
    assert not calls


@pytest.mark.parametrize('cap', [0, -1, 15.01, float('inf'), float('nan'), True])
def test_call_cap_override_cannot_escape_total_budget(setup, cap):
    run, calls, _ = setup
    with pytest.raises(guide.api.ExperimentError, match='execution limit'):
        guide.GuideAPI(run.job, 'invalid-cap', max_call_cost_usd=cap)
    assert not calls


def test_call_cap_is_immutable_and_resume_does_not_repeat_transport(setup, monkeypatch):
    run, calls, _ = setup
    enlarged = guide.GuideAPI(run.job, max_call_cost_usd=8)
    execute(enlarged, 'writer')
    count = len(calls)
    monkeypatch.setattr(guide.api, 'countries_key', lambda *_: pytest.fail('Completed resume needs no key'))
    execute(guide.GuideAPI(run.job), 'writer')
    assert len(calls) == count
    with pytest.raises(guide.api.ExperimentError, match='Frozen artifact changed'):
        guide.GuideAPI(run.job, max_call_cost_usd=11).prepare('writer', ['country'])
    assert len(calls) == count
    assert all(r['model'] == 'gpt-6.1-terra' and r['reasoning'] == {'effort': 'medium'} for r in calls)


def test_resume_does_not_pay_or_read_key_and_does_not_undo_humanization(setup, monkeypatch):
    run, calls, _ = setup
    execute(run, 'writer'); execute(run, 'editor'); execute(run, 'humanizer')
    text = run.public('country', 'edited.md').read_bytes(); count = len(calls)
    monkeypatch.setattr(guide.api, 'countries_key', lambda *_: pytest.fail('Completed resume needs no key'))
    execute(run, 'writer'); execute(run, 'editor'); execute(run, 'humanizer')
    assert len(calls) == count and run.public('country', 'edited.md').read_bytes() == text


def test_subpages_wait_for_country_reference_and_use_fixed_snapshot(setup):
    run, _, _ = setup
    with pytest.raises(guide.api.ExperimentError, match='Missing'): run.prepare('writer', ['eor'])
    execute(run, 'writer')
    e = run.prepare('writer', ['eor']); request = e.build_request(e.variants[0], e.stages(e.variants[0])[0])
    run.public('country', 'out/draft.md').write_text('Changed later country text')
    e2 = run.prepare('writer', ['eor'])
    assert request == e2.build_request(e2.variants[0], e2.stages(e2.variants[0])[0])


def test_editor_humanizer_share_complete_prefix_and_prior_state_is_full(setup):
    run, calls, _ = setup
    execute(run, 'writer')
    last = calls[2]['input'][-1]['content'][0]['text']
    assert 'Full note for answer' in last and 'Full note for law' in last
    assert 'PRIOR SECTION: section-01' in last and 'PRIOR SECTION: section-02' in last
    assert 'MERGED WRITER STATE' in last
    execute(run, 'editor'); execute(run, 'humanizer')
    assert calls[-1]['input'][:-1] == calls[-2]['input'][:-1]


def test_changed_facts_stop_before_transport(setup):
    run, calls, _ = setup
    execute(run, 'writer'); count = len(calls)
    d = guide.read(run.job / 'facts.json'); d['facts'][0]['claim'] = 'Changed'; (run.job / 'facts.json').write_text(json.dumps(d))
    with pytest.raises(guide.api.ExperimentError, match='packet changed'): run.prepare('editor', ['country'])
    assert len(calls) == count


@pytest.mark.parametrize('mutation', ['source', 'quote'])
def test_humanizer_cannot_change_sources_or_verbatim_quotes(setup, monkeypatch, mutation):
    run, _, post = setup
    execute(run, 'writer'); execute(run, 'editor')
    p = run.public('country', 'edited.md')
    if mutation == 'quote': p.write_text(p.read_text().replace('## Law', '> Verbatim quote.\n\n## Law'))
    before = p.read_bytes()
    def bad(request, *args):
        status, reply = post(request, *args); d = json.loads(reply['output'][0]['content'][0]['text'])
        d['article_md'] = d['article_md'].replace('example.gov/original', 'example.gov/changed') if mutation == 'source' else d['article_md'].replace('Verbatim quote.', 'Changed quote.')
        reply['output'][0]['content'][0]['text'] = json.dumps(d); return status, reply
    monkeypatch.setattr(guide.api, 'post_json', bad)
    with pytest.raises(guide.api.ExperimentError, match='quote changed|protected bibliography'): execute(run, 'humanizer')
    assert p.read_bytes() == before and not run.public('country', 'humanization_report.md').exists()


@pytest.mark.parametrize('old,new', [
    ('25,250', '24,000'), ('183 days', 'days'), ('5% interest', '5% interest and 40 days'),
])
def test_humanizer_numeric_regression_never_reaches_public_article(setup, monkeypatch, old, new):
    run, _, post = setup
    execute(run, 'writer'); execute(run, 'editor')
    p = run.public('country', 'edited.md')
    p.write_text(p.read_text().replace('## Law', f'{old}.\n\n## Law'))
    before = p.read_bytes()
    def bad(request, *args):
        status, reply = post(request, *args)
        d = json.loads(reply['output'][0]['content'][0]['text'])
        d['article_md'] = d['article_md'].replace(old, new)
        reply['output'][0]['content'][0]['text'] = json.dumps(d)
        return status, reply
    monkeypatch.setattr(guide.api, 'post_json', bad)
    with pytest.raises(guide.api.ExperimentError, match='protected numeric literals'):
        execute(run, 'humanizer')
    assert p.read_bytes() == before
    assert not run.public('country', 'humanization_report.md').exists()
    assert list(run.execution.glob('variants/humanizer*/attempts/*/receipt.json'))


def test_numeric_guard_allows_reordering_and_ignores_destination_digits(monkeypatch):
    monkeypatch.setattr(guide, 'BRAND', 'Example4 Co')  # a brand with a digit of its own
    before = 'Example4 Co: 5% and 183 days. [25,250](https://example.gov/2026).'
    after = 'For 183 days, 5% applies. [25,250](https://example.gov/2027).'
    assert guide.numeric_literals(before) == guide.numeric_literals(after)
    assert guide.numeric_literals('5% and 5%') != guide.numeric_literals('5%')


def test_humanizer_can_repeat_existing_threshold_for_two_qualified_branches(setup, monkeypatch):
    run, _, post = setup
    execute(run, 'writer'); execute(run, 'editor')
    old = 'At least NZ$60,000 in the previous 12 months or expected next 12 months.'
    new = 'At least NZ$60,000 in the previous 12 months or expected NZ$60,000 in the next 12 months.'
    p = run.public('country', 'edited.md')
    p.write_text(p.read_text().replace('## Law', old + '\n\n## Law'))
    def qualified(request, *args):
        status, reply = post(request, *args)
        d = json.loads(reply['output'][0]['content'][0]['text'])
        d['article_md'] = d['article_md'].replace(old, new)
        reply['output'][0]['content'][0]['text'] = json.dumps(d)
        return status, reply
    monkeypatch.setattr(guide.api, 'post_json', qualified)
    execute(run, 'humanizer')
    assert new in p.read_text()
    assert guide.digest(p.read_bytes()) in run.public('country', 'humanization_report.md').read_text()


def test_partial_public_write_resumes_without_paid_replay(setup, monkeypatch):
    run, calls, _ = setup
    original = guide.write; tripped = []
    def crash(path, text, **kw):
        if path == run.public('country', 'sections/section_2.md') and not tripped:
            tripped.append(True); raise OSError('simulated disk interruption')
        return original(path, text, **kw)
    monkeypatch.setattr(guide, 'write', crash)
    with pytest.raises(OSError, match='interruption'): execute(run, 'writer')
    assert len(calls) == 3 and run.public('country', 'sections/section_1.md').exists()
    execute(run, 'writer')
    assert len(calls) == 3 and run.public('country', 'out/draft.md').exists()


def test_manual_edit_during_post_is_never_overwritten(setup, monkeypatch):
    run, _, post = setup
    p = run.public('country', 'out/draft.md')
    def edit(request, *args):
        p.parent.mkdir(exist_ok=True); p.write_text('Manual text during POST')
        return post(request, *args)
    monkeypatch.setattr(guide.api, 'post_json', edit)
    with pytest.raises(guide.api.ExperimentError, match='Concurrent public edit'): execute(run, 'writer')
    assert p.read_text() == 'Manual text during POST'


def test_unknown_transport_never_replays_or_writes_job(setup, monkeypatch):
    run, calls, _ = setup
    def uncertain(*_): calls.append('uncertain'); raise TimeoutError('unknown POST status')
    monkeypatch.setattr(guide.api, 'post_json', uncertain)
    with pytest.raises(guide.api.ExperimentError): execute(run, 'writer')
    with pytest.raises(guide.api.ExperimentError, match='Unreconciled'): execute(run, 'writer')
    assert calls == ['uncertain'] and not run.public('country', 'out/draft.md').exists()


def test_repair_and_affected_humanization_keep_separate_receipts(setup):
    run, _, _ = setup
    execute(run, 'writer'); execute(run, 'editor'); execute(run, 'humanizer')
    finding = run.public('country', 'qa_report.md'); finding.write_text('Q001 replace natural phrasing; overall: BLOCK')
    execute(run, 'repair', round=2, findings=finding)
    assert 'Repaired wording' in run.public('country', 'edited.md').read_text()
    assert not run.public('country', 'humanization_report.md').exists()
    execute(run, 'humanizer', round=2)
    assert guide.digest(run.public('country', 'edited.md').read_bytes()) in run.public('country', 'humanization_report.md').read_text()
    assert len(list((run.run / 'applications').glob('*.json'))) == 10  # five intents + receipts


def test_materialization_metadata_changes_do_not_invalidate_full_cache(setup):
    run, calls, _ = setup
    p = run.public('country', 'sections.json'); d = guide.read(p); d['sections'][1]['instruction'] += ' [[VISUAL:figure]]'; p.write_text(json.dumps(d))
    vp = run.public('country', 'visuals.json'); vp.write_text(json.dumps({'visuals': [{'id': 'figure', 'title': 'Data', 'sources': [], 'data': {}}]}))
    execute(run, 'writer'); execute(run, 'editor')
    edited = run.public('country', 'edited.md'); block = '![Data](https://cdn.example/figure.png)\n\n*Data caption.*'
    edited.write_text(edited.read_text().replace('[[VISUAL:figure]]', block))
    v = guide.read(vp); v['visuals'][0].update(asset={'url': 'https://cdn.example/figure.png'}, inserted_markdown=block); vp.write_text(json.dumps(v))
    execute(run, 'humanizer')
    assert block in edited.read_text()
    assert calls[-1]['input'][:-1] == calls[-2]['input'][:-1]


def test_no_initial_overwrite_or_silent_model_fallback(setup):
    run, calls, _ = setup
    run.public('country', 'edited.md').write_text('Reviewed original')
    execute(run, 'writer')
    count = len(calls)
    with pytest.raises(guide.api.ExperimentError, match='Existing edited'): execute(run, 'editor')
    assert len(calls) == count and run.public('country', 'edited.md').read_text() == 'Reviewed original'
    p = guide.ROOT / 'config/guide-execution.json'; d = guide.read(p); d['writer']['model'] = 'gpt-6.1-sol'; p.write_text(json.dumps(d))
    with pytest.raises(guide.api.ExperimentError, match='route mismatch'): guide.GuideAPI(run.job, 'new')


def test_repair_archives_true_prior_receipts_and_preserves_delivery_ids(setup):
    run, calls, _ = setup
    execute(run, 'writer'); execute(run, 'editor'); execute(run, 'humanizer')
    preserved = {'qa_receipt.json': '{"old_qa":"real-test-record"}', 'review_approval.json': '{"by":"test-user","reference":"https://example.test/review"}'}
    for n, data in preserved.items(): run.public('country', n).write_text(data)
    delivered = run.job / 'out/strapi_record.json'; delivered.parent.mkdir(exist_ok=True); delivered.write_text('{"country_id":42}')
    finding = run.public('country', 'qa_report.md'); finding.write_text('Q001 replace natural wording; overall: BLOCK')
    execute(run, 'repair', round=2, findings=finding)
    for n, data in preserved.items():
        assert not run.public('country', n).exists()
        assert (run.run / 'invalidated/repair-country-r02' / n).read_text() == data
    assert delivered.read_text() == '{"country_id":42}'
    # Same repair resumes from its frozen findings even though active QA was invalidated.
    execute(run, 'repair', round=2, findings=finding)
    execute(run, 'humanizer', round=2)
    assert not run.public('country', 'review_approval.json').exists()
    count = len(calls); final = run.public('country', 'edited.md').read_bytes()
    execute(run, 'humanizer')  # old initial stage cannot undo the newer completed application
    assert len(calls) == count and run.public('country', 'edited.md').read_bytes() == final


def test_reviewed_page_cannot_be_silently_rehumanized(setup):
    run, calls, _ = setup
    execute(run, 'writer'); execute(run, 'editor')
    run.public('country', 'qa_receipt.json').write_text('{}')
    count = len(calls)
    with pytest.raises(guide.api.ExperimentError, match='Reviewed page'): execute(run, 'humanizer')
    assert len(calls) == count


def test_actual_provider_mismatch_blocks_public_outputs(setup, monkeypatch):
    run, calls, post = setup
    execute(run, 'writer')
    def wrong(request, *args):
        status, response = post(request, *args); response['model'] = 'gpt-6.1-sol'; return status, response
    monkeypatch.setattr(guide.api, 'post_json', wrong)
    with pytest.raises(guide.api.ExperimentError, match='stopped'): execute(run, 'editor')
    assert len(calls) == 4 and not run.public('country', 'edited.md').exists()


def test_job_input_symlink_cannot_smuggle_another_directory(setup):
    run, calls, _ = setup
    target = guide.ROOT / 'config/private.json'; target.write_text('{"sensitive":"not for models"}')
    source = run.job / 'evidence.md'; source.unlink(); source.symlink_to(target)
    with pytest.raises(guide.api.ExperimentError, match='escapes its job'): run.prepare('writer', ['country'])
    assert not calls


def test_configuration_cannot_move_final_qa_into_api(setup):
    _, calls, _ = setup
    p = guide.ROOT / 'config/guide-execution.json'; d = guide.read(p); d['final_qa']['backend'] = 'openai_api'; p.write_text(json.dumps(d))
    with pytest.raises(guide.api.ExperimentError, match='independent-QA'): guide.load_profile()
    assert not calls
