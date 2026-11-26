"""Isolated blog API pilot: fake HTTP only, never real credentials."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('blog_experiment', Path(__file__).resolve().parents[1] / 'scripts/openrouter_blog_experiment.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    monkeypatch.delenv('OPENROUTER_BLOG_API_KEY', raising=False)
    key = tmp_path / 'config/.env'; key.parent.mkdir()
    key.write_text('geo: sk-or-geo_synthetic\n# Blog\nKEY=sk-or-blog_synthetic\nOTHER=sk-or-other_synthetic\n')
    monkeypatch.setattr(m, 'SHARED_KEY_FILE', key)
    for name, value in [('rules.md','Use supplied facts.'),('packet.md','Verified input.'),('prompt.md','Write requested unit.')]:
        (tmp_path / name).write_text(value)
    data = {'schema_version':1,'experiment_id':'blog-test','revision':'r1','run_dir':'runs/test',
            'system_files':['rules.md'],'input_sha256':{n:m.sha((tmp_path/n).read_bytes()) for n in ['rules.md','packet.md','prompt.md']},
            'max_cost_usd':3,'max_call_cost_usd':0.5,
            'variants':[{'id':'writer','model':'minimax/minimax-m3.1-flash','canonical_slug':'minimax/minimax-m3.1-flash-20261019',
                         'provider':'minimax','provider_name':'Minimax','price_cap':{'prompt':0.15,'completion':0.6},
                         'input_files':['packet.md'],'reasoning':{'effort':'low','exclude':True}}],
            'stages':[{'id':'h2-01','prompt_file':'prompt.md','max_tokens':8192}]}
    path=tmp_path/'manifest.json';path.write_text(json.dumps(data))
    return path,data


def load(tree):
    tree[0].write_text(json.dumps(tree[1]));return m.Experiment(tree[0])


def success(payload,key,timeout):
    assert key == 'sk-or-blog_synthetic'
    return 200,{'id':'gen-synthetic','model':payload['model'],'provider':'Minimax',
                'choices':[{'finish_reason':'stop','message':{'content':'## Complete unit\n\nScoped answer.'}}],
                'usage':{'prompt_tokens':120,'completion_tokens':90,'cost':0.012}}


def test_only_explicit_blog_key_selected(tree,monkeypatch):
    assert m.blog_key()=='sk-or-blog_synthetic'
    m.SHARED_KEY_FILE.write_text('GEO=sk-or-geo_synthetic\nKEY=sk-or-generic_synthetic\n')
    with pytest.raises(m.ExperimentError,match='BLOG-labeled'):m.blog_key()
    monkeypatch.setenv('OPENROUTER_BLOG_API_KEY','sk-or-explicit_synthetic')
    assert m.blog_key()=='sk-or-explicit_synthetic'


def test_ambiguous_blog_credentials_rejected(tree):
    with m.SHARED_KEY_FILE.open('a') as f:f.write('blog backup: sk-or-backup_synthetic\n')
    with pytest.raises(m.ExperimentError,match='exactly one'):m.blog_key()


def test_pinned_route_price_and_reasoning_without_secrets(tree):
    e=load(tree);req=e.build_request(e.variants[0],e.stages(e.variants[0])[0])
    assert req['provider']=={'only':['minimax'],'allow_fallbacks':False,'require_parameters':True,'max_price':{'prompt':0.15,'completion':0.6}}
    assert req['reasoning']=={'effort':'low','exclude':True}
    assert 'sk-or-' not in json.dumps(req)


@pytest.mark.parametrize('model',['openai/gpt-99','google/gemini-99','anthropic/claude-99','minimax/latest'])
def test_other_models_rejected(tree,model):
    tree[1]['variants'][0]['model']=model
    with pytest.raises(m.ExperimentError):load(tree)


def test_frozen_input_change_stops_before_paid_request(tree):
    (m.ROOT/'packet.md').write_text('Changed source')
    with pytest.raises(m.ExperimentError,match='frozen input hash'):load(tree)


def test_credentials_cannot_be_inputs(tree):
    tree[1]['variants'][0]['input_files']=['config/.env']
    with pytest.raises(m.ExperimentError,match='cannot be a model input'):load(tree)


def test_dry_run_needs_no_credentials_or_network(tree,monkeypatch):
    m.SHARED_KEY_FILE.unlink();monkeypatch.setattr(m,'post_json',lambda *a:pytest.fail('Paid call'))
    assert load(tree).dry_run()['paid_requests_sent']==0


def test_receipt_and_resume_do_not_pay_twice(tree):
    e=load(tree);v=e.variants[0];s=e.stages(v)[0]
    assert e.run_stage(v,s,m.blog_key(),transport=success)['status']=='success'
    assert e.run_stage(v,s,m.blog_key(),transport=lambda *a:pytest.fail('Repeated POST'))['status']=='resumed'
    assert e.usage_summary()['cost_usd']==0.012


@pytest.mark.parametrize('field,value',[('model','other/model'),('provider','Other')])
def test_unexpected_route_keeps_charge_and_blocks_output(tree,field,value):
    e=load(tree);v=e.variants[0];s=e.stages(v)[0]
    def wrong(*args):
        code,body=success(*args);body[field]=value;return code,body
    assert e.run_stage(v,s,m.blog_key(),transport=wrong)['status']=='failed'
    assert not e.output_path(v,s).exists()
    assert e.usage_summary()['cost_usd']==0.012


def test_truncation_is_charged_failure_without_automatic_retry(tree):
    e=load(tree);v=e.variants[0];s=e.stages(v)[0]
    def short(*args):
        code,body=success(*args);body['choices'][0]['finish_reason']='length';return code,body
    assert e.run_stage(v,s,m.blog_key(),transport=short)['status']=='failed'
    with pytest.raises(m.ExperimentError,match='failed/uncertain'):
        e.run_stage(v,s,m.blog_key(),transport=success)
    assert e.usage_summary()['cost_usd']==0.012


def test_unknown_charge_blocks_next_call(tree):
    e=load(tree);v=e.variants[0];s=e.stages(v)[0]
    def disconnected(*a):raise TimeoutError('synthetic disconnect')
    assert e.run_stage(v,s,m.blog_key(),transport=disconnected)['status']=='uncertain'
    with pytest.raises(m.ExperimentError,match='unknown cost'):
        e.run_stage(v,s,m.blog_key(),retry_failed=True,transport=success)


def test_budget_never_exceeds_authorization(tree):
    tree[1]['max_cost_usd']=4
    with pytest.raises(m.ExperimentError,match='at most USD 3'):load(tree)
    tree[1]['max_cost_usd']=0.5;e=load(tree);v=e.variants[0];s=e.stages(v)[0]
    e.run_stage(v,s,m.blog_key(),transport=success)
    s2={**s,'id':'different-unit'}
    with pytest.raises(m.ExperimentError,match='reservation limit'):
        e.run_stage(v,s2,m.blog_key(),transport=success)


def authorize_batch(tree):
    """Synthetic local approval, never reads the real approval or credentials."""
    receipt = {'status': 'approved_topics_and_batch_plan', 'date': '2026-01-15',
               'publisher': 'the publisher', 'api_budget_usd': 8,
               'selected_cluster_ids': [f'b-{n:04d}' for n in range(12)]}
    path = m.ROOT / m.BATCH_APPROVAL_FILE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(receipt))
    tree[1].update(run_dir=m.BATCH_RUN_DIR, max_cost_usd=8,
                   batch_authorization={'approval_file': m.BATCH_APPROVAL_FILE,
                                        'approval_sha256': m.sha(path.read_bytes())})
    tree[1]['variants'][0]['cluster_id'] = 'b-0000'
    return path, receipt


def authorize_second_batch(tree):
    approval = 'docs/workflow-v2/batches/example-batch-two/approval.json'
    receipt = {'status': 'approved_topics_and_batch_plan', 'date': '2026-01-22',
               'publisher': 'the publisher', 'api_budget_usd': 4,
               'selected_cluster_ids': [f'b-{n:04d}' for n in range(6)]}
    path = m.ROOT / approval
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(receipt))
    tree[1].update(run_dir='runs/example-batch-two', max_cost_usd=4,
                   batch_authorization={'approval_file': approval,
                                        'approval_sha256': m.sha(path.read_bytes())})
    tree[1]['variants'][0]['cluster_id'] = 'b-0000'
    return path, receipt


def test_second_batch_has_separate_capped_ledger(tree, monkeypatch):
    authorize_second_batch(tree)
    monkeypatch.setattr(m, 'post_json', lambda *args: pytest.fail('Unexpected HTTP'))
    executor = load(tree)
    assert executor.max_cost == 4
    assert executor.run_dir == m.ROOT / 'runs/example-batch-two'
    assert executor.run_dir != m.ROOT / m.BATCH_RUN_DIR


@pytest.mark.parametrize('defect', ['old-ledger', 'nested-ledger', 'oversized',
                                   'unapproved-cid', 'no-authorization'])
def test_new_batch_cannot_reuse_old_ledger_or_expand_authorization(tree, defect):
    authorize_second_batch(tree)
    data = tree[1]
    if defect == 'old-ledger': data['run_dir'] = m.BATCH_RUN_DIR
    elif defect == 'nested-ledger': data['run_dir'] += '/another-ledger'
    elif defect == 'oversized': data['max_cost_usd'] = 4.01
    elif defect == 'unapproved-cid': data['variants'][0]['cluster_id'] = 'b-0006'
    else:
        data['max_cost_usd'] = 3
        data.pop('batch_authorization')
    with pytest.raises(m.ExperimentError): load(tree)


@pytest.mark.parametrize('field,value', [('date', '2026-01-15'), ('api_budget_usd', 8),
    ('selected_cluster_ids', [f'b-{n:04d}' for n in range(12)]),
    ('selected_cluster_ids', ['b-0000'] * 6)])
def test_new_batch_hash_does_not_override_registered_scope(tree, field, value):
    path, receipt = authorize_second_batch(tree)
    receipt[field] = value
    path.write_text(json.dumps(receipt))
    tree[1]['batch_authorization']['approval_sha256'] = m.sha(path.read_bytes())
    with pytest.raises(m.ExperimentError): load(tree)


@pytest.mark.parametrize('defect', ['absent', 'missing-file', 'stale', 'other-receipt',
                                  'other-run', 'nested-run', 'oversized', 'cid-absent', 'cid-other'])
def test_batch_authorization_fails_closed_before_http(tree, monkeypatch, defect):
    path, _ = authorize_batch(tree)
    monkeypatch.setattr(m, 'post_json', lambda *args: pytest.fail('Unauthorized POST'))
    data = tree[1]
    if defect == 'absent': data.pop('batch_authorization')
    elif defect == 'missing-file': path.unlink()
    elif defect == 'stale': path.write_text(path.read_text() + '\n')
    elif defect == 'other-receipt': data['batch_authorization']['approval_file'] = 'other.json'
    elif defect == 'other-run': data['run_dir'] = 'runs/other-batch'
    elif defect == 'nested-run': data['run_dir'] = m.BATCH_RUN_DIR + '/another-ledger'
    elif defect == 'oversized': data['max_cost_usd'] = 8.01
    elif defect == 'cid-absent': data['variants'][0].pop('cluster_id')
    elif defect == 'cid-other': data['variants'][0]['cluster_id'] = 'b-9999'
    with pytest.raises(m.ExperimentError): load(tree)


@pytest.mark.parametrize('field,value', [('status', 'pending'), ('publisher', 'Other'),
    ('date', '2026-01-14'), ('api_budget_usd', 9), ('api_budget_usd', '8'),
    ('selected_cluster_ids', ['b-0000'] * 12), ('selected_cluster_ids', ['b-0000']),
    ('selected_cluster_ids', [f'other-{n}' for n in range(12)])])
def test_hash_alone_cannot_authorize_another_batch_schema(tree, field, value):
    path, receipt = authorize_batch(tree)
    receipt[field] = value
    path.write_text(json.dumps(receipt))
    tree[1]['batch_authorization']['approval_sha256'] = m.sha(path.read_bytes())
    with pytest.raises(m.ExperimentError): load(tree)


def test_batch_receipt_change_after_initialization_blocks_paid_call(tree):
    path, _ = authorize_batch(tree)
    e = load(tree); v = e.variants[0]; s = e.stages(v)[0]
    path.write_text(path.read_text() + '\n')
    with pytest.raises(m.ExperimentError, match='stale batch authorization'):
        e.run_stage(v, s, 'synthetic', transport=lambda *a: pytest.fail('Stale approval POST'))
    assert not e.attempts()


def test_shared_batch_budget_counts_other_variants_and_failed_attempts(tree, monkeypatch):
    authorize_batch(tree)
    e = load(tree)
    # Prior manifests and failed calls are in the same ledger even when their
    # variants are absent from this manifest. A zero-cost rejection costs zero.
    for n, status, cost in [(1, 'success', 4), (2, 'failed', 3.49), (3, 'rejected', 0)]:
        m.write_json(e.run_dir / f'variants/earlier-{n}/attempts/unit-001/receipt.json',
                     {'status': status, 'cost_usd': cost, 'usage': {}})
    monkeypatch.setattr(m, 'post_json', success)
    report = e.execute()
    assert report['results'][0][0]['status'] == 'success'
    assert report['usage']['cost_usd'] == pytest.approx(7.502)
    assert report['usage']['attempts'] == 4
    # An entirely new manifest/revision cannot reset the shared USD 8 ledger.
    tree[1]['experiment_id'] = 'next-manifest'; tree[1]['revision'] = 'r2'
    tree[1]['variants'][0]['id'] = 'new-writer'
    newer = load(tree)
    monkeypatch.setattr(m, 'post_json', lambda *a: pytest.fail('Over-budget POST'))
    assert newer.execute()['results'][0][0]['status'] == 'blocked'
    assert newer.usage_summary()['cost_usd'] == pytest.approx(7.502)


def test_shared_batch_unknown_cost_blocks_http(tree, monkeypatch):
    authorize_batch(tree); e = load(tree)
    m.write_json(e.run_dir / 'variants/older/attempts/unit-001/receipt.json',
                 {'status': 'failed', 'cost_usd': None})
    monkeypatch.setattr(m, 'post_json', lambda *a: pytest.fail('Unknown-charge POST'))
    result = e.execute()['results'][0][0]
    assert result['status'] == 'blocked' and 'unknown cost' in result['error']


def test_shared_batch_process_lock_blocks_another_executor(tree, monkeypatch):
    authorize_batch(tree); e = load(tree); e.run_dir.mkdir(parents=True)
    monkeypatch.setattr(m, 'post_json', lambda *a: pytest.fail('Parallel POST'))
    with (e.run_dir / '.executor.lock').open('a') as handle:
        m.fcntl.flock(handle, m.fcntl.LOCK_EX | m.fcntl.LOCK_NB)
        with pytest.raises(m.ExperimentError, match='Another executor'):
            load(tree).execute()


def test_shared_batch_reservations_cover_parallel_variants(tree, monkeypatch):
    import threading
    authorize_batch(tree)
    tree[1]['max_call_cost_usd'] = 6
    duplicate = json.loads(json.dumps(tree[1]['variants'][0]))
    duplicate.update(id='second-writer', cluster_id='b-0001')
    tree[1]['variants'].append(duplicate)
    e = load(tree); entered = threading.Event(); release = threading.Event(); result = []
    def fake_http(*args):
        entered.set()
        assert release.wait(timeout=5)
        return success(*args)
    first = threading.Thread(target=lambda: result.append(
        e.run_stage(e.variants[0], e.stages(e.variants[0])[0], m.blog_key(), transport=fake_http)))
    first.start()
    try:
        assert entered.wait(timeout=5)
        with pytest.raises(m.ExperimentError, match='reservation limit'):
            e.run_stage(duplicate, e.stages(duplicate)[0], 'synthetic',
                        transport=lambda *a: pytest.fail('Unreserved parallel POST'))
    finally:
        release.set(); first.join(timeout=5)
    assert result[0]['status'] == 'success' and e.reserved == 0


def test_shared_pending_intent_cannot_be_lost_by_a_new_manifest(tree, monkeypatch):
    authorize_batch(tree); e = load(tree)
    m.write_json(e.run_dir / 'variants/older/attempts/unit-001/intent.json', {'fingerprint': 'older'})
    monkeypatch.setattr(m, 'post_json', lambda *a: pytest.fail('Pending-charge POST'))
    with pytest.raises(m.ExperimentError, match='no receipt'): e.execute()


def test_shared_batch_directory_requires_scope_even_at_legacy_cap(tree):
    tree[1]['run_dir'] = m.BATCH_RUN_DIR
    with pytest.raises(m.ExperimentError, match='requires batch_authorization'): load(tree)


def stable_units(tree):
    tree[1]['request_mode'] = 'stable_conversation_v1'
    for n in range(2, 4):
        name = f'prompt-{n}.md'; path = m.ROOT / name
        path.write_text(f'Write unit {n}, retaining all qualifications.')
        tree[1]['input_sha256'][name] = m.sha(path.read_bytes())
        tree[1]['stages'].append({'id': f'h2-0{n}', 'prompt_file': name, 'max_tokens': 8192})
    return load(tree)


def test_conversation_extends_exact_messages_without_extra_http(tree):
    e = stable_units(tree); v = e.variants[0]; requests = []
    def fake_http(payload, key, timeout):
        requests.append(payload)
        code, body = success(payload, key, timeout)
        body['choices'][0]['message']['content'] += f'\n\nFull qualification {len(requests)}.'
        return code, body
    for stage in e.stages(v):
        assert e.run_stage(v, stage, m.blog_key(), transport=fake_http)['status'] == 'success'
    assert len(requests) == 3
    for previous, current in zip(requests, requests[1:]):
        assert current['messages'][:len(previous['messages'])] == previous['messages']
        assert current['messages'][len(previous['messages'])]['role'] == 'assistant'
        assert 'Full qualification' in current['messages'][len(previous['messages'])]['content']
    assert requests[0]['messages'][0]['role'] == 'system'
    assert requests[0]['messages'][1]['content'] == 'INPUT FILE: packet.md\nVerified input.'
    assert requests[0]['messages'][2]['content'] == 'Write requested unit.'
    assert e.run_stage(v, e.stages(v)[-1], m.blog_key(),
                       transport=lambda *a: pytest.fail('Resume POST'))['status'] == 'resumed'


@pytest.mark.parametrize('target', ['output', 'sidecar', 'attempt', 'request', 'missing-sidecar'])
def test_conversation_tamper_blocks_before_next_http(tree, target):
    e = stable_units(tree); v = e.variants[0]; first, second = e.stages(v)[:2]
    e.run_stage(v, first, m.blog_key(), transport=success)
    output = e.output_path(v, first); sidecar = output.with_suffix('.receipt.json')
    attempt = e.attempts()[0]
    if target == 'output': output.write_text('Changed qualifications')
    elif target == 'missing-sidecar': sidecar.unlink()
    else:
        path = {'sidecar': sidecar, 'attempt': attempt, 'request': attempt.parent / 'request.json'}[target]
        data = m.read_json(path); data['tampered'] = True; m.write_json(path, data)
    with pytest.raises(m.ExperimentError, match='prior-stage|Prior-stage'):
        e.run_stage(v, second, m.blog_key(), transport=lambda *a: pytest.fail('Tampered-context POST'))


def test_conversation_rejects_stage_system_changes(tree):
    stable_units(tree)
    tree[1]['stages'][1]['system_files'] = ['packet.md']
    with pytest.raises(m.ExperimentError, match='identical system rules'): load(tree)


def test_conversation_requires_every_earlier_success_even_without_dependencies(tree):
    e = stable_units(tree); v = e.variants[0]
    with pytest.raises(m.ExperimentError, match='prior-stage receipt/output'):
        e.run_stage(v, e.stages(v)[1], 'synthetic', transport=lambda *a: pytest.fail('Missing-context POST'))


def test_legacy_request_and_fingerprint_unchanged(tree):
    e = load(tree); v = e.variants[0]; stage = e.stages(v)[0]
    expected = {'model': 'minimax/minimax-m3.1-flash',
        'provider': {'only': ['minimax'], 'allow_fallbacks': False, 'require_parameters': True,
                     'max_price': {'prompt': 0.15, 'completion': 0.6}},
        'messages': [{'role': 'system', 'content': 'SOURCE FILE: rules.md\nUse supplied facts.'},
                     {'role': 'user', 'content': 'Write requested unit.\n\nINPUT FILE: packet.md\nVerified input.'}],
        'max_tokens': 8192, 'stream': False, 'usage': {'include': True},
        'reasoning': {'effort': 'low', 'exclude': True}}
    assert e.build_request(v, stage) == expected
    assert e.fingerprint(expected) == '286ccbabf8380315ba77f7b8be687a407a7cf2dddca6f474007366e64ec3340d'
    tree[1]['request_mode'] = 'legacy'
    explicit = load(tree)
    assert explicit.build_request(explicit.variants[0], explicit.stages(explicit.variants[0])[0]) == expected


def reconciliation_tree(tree, monkeypatch):
    """A single timeout plus all lifetime known charges and two mature counters."""
    authorize_batch(tree)
    monkeypatch.setattr(m, 'now', lambda: '2026-01-15T17:00:00+00:00')
    e = load(tree); v = e.variants[0]; s = e.stages(v)[0]
    def timeout(*args):
        raise TimeoutError('synthetic uncertain POST')
    e.run_stage(v, s, m.blog_key(), transport=timeout)
    target = e.attempts()[0]
    pilot = m.ROOT / m.RECONCILIATION_LEDGERS[0] / 'variants/earlier/attempts/unit-001'
    m.write_json(pilot / 'intent.json', {'fingerprint': 'old', 'started_at': m.now()})
    m.write_json(pilot / 'request.json', {'synthetic': True})
    m.write_json(pilot / 'receipt.json', {'fingerprint': 'old', 'started_at': m.now(), 'finished_at': m.now(),
                                        'status': 'success', 'cost_usd': .9007449245})
    ledger, _ = m._ledger_files()
    snapshots = []
    for n, time, http_date in [(2, '17:10:00', '17:10:00'), (3, '17:12:00', '17:12:00')]:
        path = m.ROOT / f'snapshots/key-{n}.json'
        m.write_json(path, {'observed_at': f'2026-01-15T{time}+00:00',
            'provider_http_date': f'Thu, 15 Jan 2026 {http_date} GMT',
            'endpoint': 'https://openrouter.ai/api/v1/key',
            'authenticated_key_sha256': m.sha(m.blog_key().encode()), 'ledger_sha256': ledger,
            'data': {'is_management_key': False, 'usage': .900744916}})
        snapshots.append(str(path.relative_to(m.ROOT)))
    monkeypatch.setattr(m, 'now', lambda: '2026-01-15T17:12:30+00:00')
    return e, v, s, target, snapshots


def test_append_only_zero_counter_proof_resolves_cost_not_generation_and_requires_explicit_retry(tree, monkeypatch):
    e, v, s, target, snapshots = reconciliation_tree(tree, monkeypatch)
    original = target.read_bytes()
    proof = m.build_charge_reconciliation(target, snapshots, audited_by='parent-thread', audit_reference='Two authenticated counter observations')
    m.write_json(target.parent / 'cost-reconciliation.json', proof)
    assert m.validate_charge_reconciliation(target, proof) == 0
    summary = e.usage_summary()
    assert summary['cost_usd'] == 0 and summary['unknown_cost_attempts'] == 0
    assert summary['successes'] == 0 and summary['failed'] == 1
    assert not e.output_path(v, s).exists()
    assert target.read_bytes() == original
    with pytest.raises(m.ExperimentError, match='failed/uncertain'):
        e.run_stage(v, s, m.blog_key(), transport=lambda *a: pytest.fail('Implicit retry'))
    assert e.run_stage(v, s, m.blog_key(), retry_failed=True, transport=success)['status'] == 'success'
    assert e.usage_summary()['cost_usd'] == .012
    assert e.usage_summary()['unknown_cost_attempts'] == 0
    assert target.read_bytes() == original and len(e.attempts()) == 2


@pytest.mark.parametrize('defect', ['unknown-extra', 'pending-intent', 'cost-delta', 'different-key', 'different-source',
    'wrong-receipt-hash', 'changed-original-request', 'too-early', 'too-close', 'clock-mismatch', 'stale-snapshots', 'missing-time', 'generation-id'])
def test_zero_counter_reconciliation_blocks_ambiguous_stale_or_inconsistent_proof(tree, monkeypatch, defect):
    e, v, s, target, snapshots = reconciliation_tree(tree, monkeypatch)
    snapshot = m.read_json(m.path_in_repo(snapshots[1]))
    if defect == 'unknown-extra':
        path = m.ROOT / m.RECONCILIATION_LEDGERS[0] / 'variants/other/attempts/unit-001'
        m.write_json(path / 'intent.json', {'fingerprint': 'x', 'started_at': '2026-01-15T17:00:00+00:00'})
        m.write_json(path / 'request.json', {})
        m.write_json(path / 'receipt.json', {'fingerprint': 'x', 'started_at': '2026-01-15T17:00:00+00:00', 'finished_at': '2026-01-15T17:00:00+00:00', 'cost_usd': None})
    elif defect == 'pending-intent':
        m.write_json(m.ROOT / m.RECONCILIATION_LEDGERS[0] / 'variants/other/attempts/unit-001/intent.json', {'started_at': m.now()})
    elif defect == 'cost-delta': snapshot['data']['usage'] += .00000002
    elif defect == 'different-key': snapshot['authenticated_key_sha256'] = 'f' * 64
    elif defect == 'different-source': snapshot['endpoint'] = 'https://other.example/key'
    elif defect == 'wrong-receipt-hash': snapshot['ledger_sha256'][str(target.relative_to(m.ROOT))] = 'f' * 64
    elif defect == 'changed-original-request': (target.parent / 'request.json').write_text('Changed request')
    elif defect == 'too-early':
        first = m.read_json(m.path_in_repo(snapshots[0])); first['observed_at'] = '2026-01-15T17:01:00+00:00'; first['provider_http_date'] = 'Thu, 15 Jan 2026 17:01:00 GMT'
        m.write_json(m.path_in_repo(snapshots[0]), first)
    elif defect == 'too-close': snapshot['observed_at'] = '2026-01-15T17:10:30+00:00'; snapshot['provider_http_date'] = 'Thu, 15 Jan 2026 17:10:30 GMT'
    elif defect == 'clock-mismatch': snapshot['provider_http_date'] = 'Thu, 15 Jan 2026 16:00:00 GMT'
    elif defect == 'stale-snapshots': monkeypatch.setattr(m, 'now', lambda: '2026-01-15T17:30:00+00:00')
    elif defect == 'missing-time': snapshot.pop('provider_http_date')
    elif defect == 'generation-id':
        receipt = m.read_json(target); receipt['generation_id'] = 'known-generation'; m.write_json(target, receipt)
    m.write_json(m.path_in_repo(snapshots[1]), snapshot)
    with pytest.raises((m.ExperimentError, OSError, ValueError, KeyError)):
        proof = m.build_charge_reconciliation(target, snapshots, audited_by='parent', audit_reference='Observed counters')
        if defect == 'changed-original-request':
            # A request changed before the audit cannot be identified solely by
            # receipt inventory; mutate it AFTER sealing to exercise the binding.
            (target.parent / 'request.json').write_text('Changed again after seal')
            m.validate_charge_reconciliation(target, proof)


def test_invalid_sidecar_or_wrong_execution_key_keeps_unknown_cost_block(tree, monkeypatch):
    e, v, s, target, snapshots = reconciliation_tree(tree, monkeypatch)
    proof = m.build_charge_reconciliation(target, snapshots, audited_by='parent', audit_reference='Observed counters')
    sidecar = target.parent / 'cost-reconciliation.json'; m.write_json(sidecar, proof)
    with pytest.raises(m.ExperimentError, match='unknown cost'):
        e.run_stage(v, s, 'sk-or-different_synthetic', retry_failed=True, transport=lambda *a: pytest.fail('Wrong-key retry'))
    e.active_key_sha256 = m.sha(m.blog_key().encode())
    assert e.usage_summary()['unknown_cost_attempts'] == 0
    snapshot_path = m.path_in_repo(snapshots[1]); snapshot_path.write_text(snapshot_path.read_text() + '\n')
    assert e.usage_summary()['unknown_cost_attempts'] == 1
    with pytest.raises(m.ExperimentError, match='unknown cost'):
        e.run_stage(v, s, m.blog_key(), retry_failed=True, transport=lambda *a: pytest.fail('Invalid-proof retry'))


def test_new_paid_intent_between_observations_and_seal_invalidates_proof(tree, monkeypatch):
    e, v, s, target, snapshots = reconciliation_tree(tree, monkeypatch)
    proof = m.build_charge_reconciliation(target, snapshots, audited_by='parent', audit_reference='Observed counters')
    m.write_json(m.ROOT / m.BATCH_RUN_DIR / 'variants/unrecorded/attempts/new-001/intent.json',
                 {'started_at': '2026-01-15T17:11:00+00:00'})
    with pytest.raises(m.ExperimentError, match='before the audit seal'):
        m.validate_charge_reconciliation(target, proof)
