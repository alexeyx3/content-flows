import datetime as dt
import json
import re
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from scripts import refresh_semantics as sem
from scripts import collect_refresh_baseline as legacy
from scripts import codex_metrics


def fake_annotator(texts, language):
    lookup = {'invoices': 'invoice', 'contractors': 'contractor', 'employees': 'employee',
              'счета': 'счёт', 'счёт': 'счёт', 'подрядчиков': 'подрядчик', 'подрядчика': 'подрядчик'}
    result = []
    for text in texts:
        tokens, segment, previous = [], 0, 0
        for match in re.finditer(r'[^\W_]+', text):
            if re.search(r'[.!?,;:\n]', text[previous:match.start()]):
                segment += 1
            value = match[0]
            tokens.append({'text': value, 'lemma': lookup.get(value, value), 'start': match.start(),
                           'end': match.end(), 'segment': segment, 'stop': value in {'the', 'to', 'not'}})
            previous = match.end()
        result.append(tokens)
    config=json.loads(sem.morphology.CONFIG.read_text())
    return result, {'sources_sha256': sem.morphology.source_hash(), 'language': language,
                    'spacy':config['spacy_version'],'model':config['models'][language], 'model_version':config['model_version']}


def dataset(*queries):
    return {'version': 1, 'source': 'google_search_console', 'dataState': 'final',
            'source_url': 'https://example.com/blog/example/', 'startDate': '2026-09-19', 'endDate': '2026-10-16',
            'queries': [{'id': sem.query_id(q), 'query': q, 'impressions': 10} for q in queries]}


def audit(before, after, *queries):
    return sem.analyze(dataset(*queries), before, after, 'en', annotator=fake_annotator)


def query_row(report, index=0):
    return [r for r in report['rows'] if r['type'] == 'query'][index]


def test_case_whitespace_literal_and_inflection_are_distinct():
    r = audit('## Costs\n\nContractor\u00a0invoices.', '## Costs\n\nContractor invoice.', 'contractor invoices')
    row = query_row(r)
    assert row['before']['exact'] == row['before']['morph'] == 1
    assert row['after']['exact'] == 0 and row['after']['morph'] == 1
    assert row['after']['morph_locations'][0]['section'] == 'Costs'


@pytest.mark.parametrize('text', ['invoices to contractors', 'contractor annual invoices', 'contractor. Invoices', 'contractor, invoices'])
def test_no_reordering_gaps_or_sentence_bridges(text):
    row = query_row(audit('', text, 'contractor invoices'))
    assert row['after']['exact'] == row['after']['morph'] == 0


def test_word_boundaries_prevent_employee_substring_match():
    row = query_row(audit('', 'employees', 'employee'))
    assert row['after']['exact'] == 0 and row['after']['morph'] == 1


def test_no_cross_table_cells_or_blocks_and_url_sources_code_excluded():
    text = '''## Options
| contractor | invoices |
|---|---|
| one | two |
contractor
invoices
[Read here](https://example.com/contractor-invoices)
![contractor invoices](https://example.com/a.png)
```
contractor invoices
```
## Sources
[contractor invoices](https://example.com/source)
'''
    row = query_row(audit('', text, 'contractor invoices'))
    assert row['after']['exact'] == row['after']['morph'] == 0


def test_bigrams_are_adjacent_and_do_not_drop_stopwords_or_negation():
    r = audit('', 'contractor invoices', 'invoices to contractors', 'not employee')
    terms = {row['text'] for row in r['rows'] if row['type'] != 'query'}
    assert 'invoice to' in terms and 'to contractor' in terms and 'not employee' in terms
    assert 'invoice contractor' not in terms


def test_russian_declensions_have_lemma_matches_only():
    r = sem.analyze(dataset('счета подрядчиков'), '', 'Счёт подрядчика', 'ru', annotator=fake_annotator)
    row = query_row(r)
    assert row['after']['exact'] == 0 and row['after']['morph'] == 1


def test_metadata_is_separate_and_does_not_satisfy_body_target():
    r = sem.analyze(dataset('contractor invoices'), '', '## Costs\n\nOther text', 'en',
                    annotator=fake_annotator, after_metadata={'metaTitle':'Contractor invoices'})
    row=query_row(r)
    assert row['after']['exact']==row['after']['morph']==0
    assert row['metadata_after']['exact']==row['metadata_after']['morph']==1
    p=plan_for(r,action='expand');p['targets']=[{'id':row['id'],'match':'morph','min_count':1,'section':'Costs'}]
    assert sem.plan_errors(r,p,final=True)


def test_term_variants_retain_query_provenance_without_double_counting():
    r = audit('', 'contractor invoice', 'contractor invoice', 'contractor invoices')
    term = next(row for row in r['rows'] if row['type'] == 'bigram' and row['text'] == 'contractor invoice')
    assert len(term['query_ids']) == 2 and len(term['variants']) == 2
    assert term['after']['exact'] == term['after']['morph'] == 1


def test_registry_rejects_duplicates_and_wrong_stable_ids(tmp_path):
    data = dataset('contractor invoices');p = tmp_path/'queries.json'
    data['queries'].append(dict(data['queries'][0]));p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='duplicate'):sem.registry(p)
    data['queries'] = [{'id': 'invented', 'query': 'contractor invoices'}];p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='mismatch'):sem.registry(p)


def plan_for(report, *, action='covered'):
    return {'version': 1, 'queries': [{'query_id': row['id'], 'action': action, 'section': 'Costs',
                                     'reason': 'Existing answer covers the intended question.'}
                                    for row in report['rows'] if row['type'] == 'query'],
            'targets': [], 'loss_exceptions': []}


def test_every_query_needs_a_decision_and_expansion_needs_target():
    r = audit('', 'contractor invoice', 'contractor invoices');p = plan_for(r, action='expand')
    assert any('needs an exact/morph target' in x for x in sem.plan_errors(r,p,final=False))
    p['targets'] = [{'id': query_row(r)['id'], 'match': 'morph', 'min_count': 1, 'section': 'Costs'}]
    assert sem.plan_errors(r,p,final=False) == []
    p['queries'] = []
    assert any('missing decisions' in x for x in sem.plan_errors(r,p,final=False))


def test_target_checks_section_and_mode_after_editor():
    r = audit('', '## Costs\n\ncontractor invoice', 'contractor invoices');p = plan_for(r, action='expand')
    t = {'id': query_row(r)['id'], 'match': 'morph', 'min_count': 1, 'section': 'Costs'};p['targets'] = [t]
    assert sem.plan_errors(r,p,final=True) == []
    t['match'] = 'exact'
    assert any('exact 0 < 1' in x for x in sem.plan_errors(r,p,final=True))
    t.update(match='morph',section='Elsewhere')
    assert any('morph 0 < 1' in x for x in sem.plan_errors(r,p,final=True))


def test_lost_query_presence_needs_reason_even_when_lemma_survives():
    r = audit('contractor invoices', 'contractor invoice', 'contractor invoices');p=plan_for(r)
    assert any('lost exact' in x for x in sem.plan_errors(r,p,final=True))
    p['loss_exceptions']=[{'id':query_row(r)['id'],'match':'exact','reason':'Evidence correction requires singular scope.'}]
    assert sem.plan_errors(r,p,final=True)==[]


def semantic_job(tmp_path):
    job=tmp_path/'job';(job/'baseline').mkdir(parents=True);(job/'raw').mkdir()
    (job/'job.yaml').write_text('workflow_version: 2\narticle_refresh_version: 1\nsemantic_refresh_version: 1\nlanguage: EN\n')
    (job/'refresh.json').write_text(json.dumps({'source_url':'https://example.com/blog/example/'}))
    (job/'baseline/article.md').write_text('## Costs\n\ncontractor invoices')
    (job/'edited.md').write_text('## Costs\n\ncontractor invoices')
    q=job/'raw/semantic-queries.json';q.write_text(json.dumps(dataset('contractor invoices')))
    r=audit((job/'baseline/article.md').read_text(),(job/'edited.md').read_text(),'contractor invoices')
    plan=job/'semantics_plan.json';plan.write_text(json.dumps(plan_for(r)))
    r['hashes']={'queries':sem.sha(q.read_bytes()),'baseline':sem.sha((job/'baseline/article.md').read_bytes()),
                 'article':sem.sha((job/'edited.md').read_bytes()),'plan':sem.sha(plan.read_bytes())}
    for phase in ['before','after']:sem.save_report(job/f'metrics/semantics-{phase}',r)
    return job


def test_gate_rejects_stale_article_dataset_plan_and_missing_report(tmp_path):
    job=semantic_job(tmp_path)
    assert sem.gate_errors(job,'writer')==sem.gate_errors(job,'after')==[]
    for name in ['edited.md','raw/semantic-queries.json','semantics_plan.json']:
        p=job/name;old=p.read_bytes();p.write_bytes(old+b' ')
        assert any('stale' in x for x in sem.gate_errors(job,'after'))
        p.write_bytes(old)
    (job/'metrics/semantics-after/coverage.json').unlink()
    assert any('incomplete' in x for x in sem.gate_errors(job,'after'))


def test_old_jobs_keep_existing_contract_and_metrics_plan(tmp_path):
    job=tmp_path;(job/'job.yaml').write_text('workflow_version: 2\narticle_refresh_version: 1\n')
    assert sem.gate_errors(job,'after')==[]
    assert 'semantic-before' not in codex_metrics.planned_stages(job,'full')
    (job/'job.yaml').write_text((job/'job.yaml').read_text()+'semantic_refresh_version: 1\n')
    assert {'semantic-collect','semantic-before','semantic-plan-check','semantic-after'} <= set(codex_metrics.planned_stages(job,'full'))
    assert sem.gate_errors(job,'writer')


def test_collect_single_page_window_since_publication_without_related_queries(tmp_path,monkeypatch):
    (tmp_path/'baseline').mkdir()
    (tmp_path/'refresh.json').write_text(json.dumps({'source_url':'https://example.com/blog/example/'}))
    (tmp_path/'baseline/cms-record.json').write_text(json.dumps({'publishedAt':'2026-09-19T15:00:00Z'}))
    calls=[]
    def request(svc,prop,start,end,dims,filters):
        calls.append((str(start),str(end),dims,filters));return [{'keys':['contractor invoices'],'impressions':7}]
    monkeypatch.setattr(legacy,'query',request)
    result=sem.collect(tmp_path,end=dt.date(2026,10,16),service=object())
    assert len(calls)==1 and calls[0][:3]==('2026-09-19','2026-10-16',['query'])
    assert calls[0][3]==[{'dimension':'page','operator':'equals','expression':'https://example.com/blog/example/'}]
    assert result['queries'][0]['id']==sem.query_id('contractor invoices')
    assert result['limitations']==sem.LIMITATION
    (tmp_path/'baseline/cms-record.json').write_text(json.dumps({'publishedAt':'2025-01-01T15:00:00Z'}))
    result=sem.collect(tmp_path,end=dt.date(2026,10,16),service=object())
    assert result['startDate']=='2026-07-19'  # inclusive 90 days


def test_collect_latest_final_day_is_property_level_not_page_zero_signal(tmp_path,monkeypatch):
    (tmp_path/'baseline').mkdir();(tmp_path/'refresh.json').write_text(json.dumps({'source_url':'https://example.com/blog/example/'}))
    (tmp_path/'baseline/cms-record.json').write_text(json.dumps({'publishedAt':'2026-09-19T15:00:00Z'}))
    calls=[]
    def request(svc,prop,start,end,dims,filters):
        calls.append((dims,filters));return [{'keys':['2026-10-16']}] if dims==['date'] else []
    monkeypatch.setattr(legacy,'query',request)
    result=sem.collect(tmp_path,service=object())
    assert calls[0]==(['date'],[]) and result['endDate']=='2026-10-16' and result['queries']==[]


def test_no_query_data_is_not_invented_coverage():
    r=audit('Text','Improved text')
    assert r['summary']['queries']==0 and r['rows']==[]
    assert sem.plan_errors(r,plan_for(r),final=True)==[]


def test_new_job_defaults_enable_semantics_only_for_refresh(tmp_path):
    from scripts.new_job import TEMPLATE
    (tmp_path/'job.yaml').write_text(TEMPLATE.format(topic='Example'))
    assert 'semantic_refresh_version: 1' in (tmp_path/'job.yaml').read_text()
    assert not sem.required(tmp_path)
    with (tmp_path/'job.yaml').open('a') as f:f.write('article_refresh_version: 1\n')
    assert sem.required(tmp_path)


def test_gate_rejects_wrong_language_or_engine(tmp_path):
    job=semantic_job(tmp_path);p=job/'metrics/semantics-after/coverage.json';original=p.read_text();report=json.loads(original)
    report['language']='ru';p.write_text(json.dumps(report))
    assert any('language' in x for x in sem.gate_errors(job,'after'))
    report=json.loads(original);report['engine']['spacy']='fake';p.write_text(json.dumps(report))
    assert any('unpinned' in x for x in sem.gate_errors(job,'after'))


def test_strategy_may_create_brief_after_baseline_audit_without_staling_writer_gate(tmp_path):
    job=semantic_job(tmp_path)
    (job/'brief.md').write_text('Strategy created this after the before report.')
    assert sem.gate_errors(job,'writer')==[]
    assert any('stale' in x for x in sem.gate_errors(job,'after'))


def test_article_and_writer_gates_call_semantic_checks(tmp_path):
    import article_materials as materials
    job=semantic_job(tmp_path);(job/'metrics/semantics-before/coverage.json').unlink()
    assert any('semantic' in x for x in materials.writer_ready_errors(job))
    assert any('semantic' in x for x in materials.article_errors(job,'qa',remote=False))


def test_qa_receipt_binds_semantic_plan_and_both_reports(tmp_path):
    import article_materials as materials
    job=semantic_job(tmp_path)
    for name in materials.QA_FILES:
        p=job/name
        if not p.exists() and name!='raw/speaker-profiles.json':
            p.parent.mkdir(exist_ok=True,parents=True);p.write_text('{"quotes":[]}' if name=='expert_quotes.json' else 'fixture')
    for name in ['refresh_plan.json','refresh_evidence.md']:(job/name).write_text('fixture')
    hashes=materials.qa_fingerprint(job)
    for name in ['raw/semantic-queries.json','semantics_plan.json','metrics/semantics-before/coverage.json','metrics/semantics-after/coverage.json']:
        assert hashes[name]==sem.sha((job/name).read_bytes())
