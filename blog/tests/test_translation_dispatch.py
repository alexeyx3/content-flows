"""Persistent complete-H2 translation cannot silently truncate or replace drafts."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import translation_dispatch as d
import blog_translation as t
import codex_metrics as metrics


def put(job,name,value):
    p=job/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False) if isinstance(value,dict) else value)


@pytest.fixture
def job(tmp_path):
    job=tmp_path/'translation'
    source={'data':{'id':18,'locale':'en','slug':'example','title':'Example 2026',
        'publishedAt':'2026-01-01T00:00:00Z','content':'<p>Before 7.</p><h2>First</h2><p>Intro.</p>'
        '<h3>Child</h3><p>Keep 15+.</p><h4>Detail</h4><ul><li>A</li><li>B</li></ul>'
        '<h2>Second</h2><table><tr><th>Name</th><th>Price</th></tr><tr><td>A</td><td>$29</td></tr></table>',
        'cover':None}}
    t.bootstrap(job,'example','ru',source)
    config=job/'job.yaml';config.write_text(config.read_text()+'translation_units_version: 1\n')
    put(job,'translated.meta.json',{'title':'Пример 2026','slug':'example','locale':'ru',
        'summary':'Описание','metaTitle':'Пример','metaDescription':'Описание'})
    put(job,'translation.links.json',{'links':[]});put(job,'translation.visuals.json',{'assets':[]})
    put(job,'translation.glossary.json',{'terms':[]});put(job,'translation.issues.md','Source issues recorded.')
    d.prepare(job)
    return job


RU={
    'preamble':'# Пример 2026\n\nДо 7.\n',
    'h2-001':'## Первый\n\nВведение.\n\n### Подраздел\n\nСохранить 15+.\n\n#### Подробности\n\n- A\n- B\n',
    'h2-002':'## Второй\n\n| Имя | Цена |\n| --- | --- |\n| A | $29 |\n',
}


def finish(job):
    for uid,text in RU.items():
        put(job,f'translation_units/ru/{uid}.md',text)
        d.complete(job,uid)


def test_plan_keeps_full_h2_descendants_and_all_source_bytes(job):
    plan=d.load_plan(job)
    assert [u['requested_unit'] for u in plan['units']]==['preamble','h2-001','h2-002']
    assert [h['level'] for h in plan['units'][1]['headings']]==[2,3,4]
    for source,unitkey in [('source/article.md','source_md'),('source/article.html','source_html')]:
        assert ''.join((job/u[unitkey]).read_text() for u in plan['units'])==(job/source).read_text()
    before={str(p.relative_to(job)):p.read_bytes() for p in job.rglob('*') if p.is_file()}
    assert d.prepare(job)==plan
    assert before=={str(p.relative_to(job)):p.read_bytes() for p in job.rglob('*') if p.is_file()}


def test_sealed_job_cannot_prepare_or_assemble_or_complete(job):
    put(job,'translation.qa_receipt.json',{'status':'PASS'})
    for call in (lambda:d.prepare(job),lambda:d.assemble(job),lambda:d.complete(job,'preamble')):
        with pytest.raises(ValueError,match='sealed'):call()


@pytest.mark.parametrize('mutation',[
    lambda text:text.replace('### Подраздел\n\nСохранить 15+.\n\n',''),
    lambda text:text.replace('15+','15'),
    lambda text:text.replace('- B\n',''),
    lambda text:text.replace('- A\n- B\n',''),
    lambda text:text.replace('Введение.\n\n',''),
    lambda text:text+'\n[[VISUAL:missing]]\n',
])
def test_partial_or_changed_subtree_never_gets_completion_receipt(job,mutation):
    put(job,'translation_units/ru/h2-001.md',mutation(RU['h2-001']))
    with pytest.raises(ValueError):d.complete(job,'h2-001')
    assert not (job/'translation_units/ru/h2-001.complete.json').exists()


def test_changed_table_shape_is_incomplete(job):
    put(job,'translation_units/ru/h2-002.md',RU['h2-002'].replace('| A | $29 |','| A | $29 | extra |'))
    with pytest.raises(ValueError,match='table_shapes'):d.complete(job,'h2-002')


def test_empty_leaf_is_not_complete_even_if_headings_exist(job):
    put(job,'translation_units/ru/h2-001.md','## Первый\n\n### Подраздел\n\n#### Подробности\n')
    with pytest.raises(ValueError,match='empty|lists|numeric'):d.complete(job,'h2-001')


def test_incomplete_unit_set_cannot_create_translated_article(job):
    put(job,'translation_units/ru/preamble.md',RU['preamble']);d.complete(job,'preamble')
    assert d.assemble(job)['status']=='BLOCK'
    assert not (job/'translated.md').exists()


def test_assembly_has_source_order_one_h1_and_never_overwrites_existing_prose(job):
    finish(job)
    put(job,'translated.md','Existing translator output\n')
    with pytest.raises(ValueError,match='refusing overwrite'):d.assemble(job)
    assert (job/'translated.md').read_text()=='Existing translator output\n'
    (job/'translated.md').unlink()
    assert d.assemble(job)['status']=='PASS'
    assert (job/'translated.md').read_text()=='\n\n'.join(RU[u].strip() for u in RU)+'\n'
    assert d.assembly_errors(job)==[]
    before=(job/'translated.md').read_bytes()
    assert d.assemble(job)['status']=='PASS' and (job/'translated.md').read_bytes()==before


def test_unit_hash_change_invalidates_receipt_and_existing_assembly(job):
    finish(job);d.assemble(job)
    p=job/'translation_units/ru/h2-001.md';p.write_text(p.read_text().replace('Введение','Начало'))
    assert 'stale/incomplete' in ' '.join(d.check_all(job)['errors'])
    assert d.assembly_errors(job)


def test_changed_plan_or_source_slice_is_not_accepted(job):
    p=job/'translation_units/source/h2-001.md';p.write_text(p.read_text()+'Changed')
    with pytest.raises(ValueError,match='source unit changed'):d.load_plan(job)


def test_changed_unit_order_cannot_reorder_source_article(job):
    p=job/d.PLAN;plan=json.loads(p.read_text());plan['units'][1:]=reversed(plan['units'][1:]);put(job,d.PLAN,plan)
    with pytest.raises(ValueError,match='stale/altered'):d.load_plan(job)


def test_mode_is_explicit_and_unflagged_legacy_contract_remains_unmodified(job):
    config=job/'job.yaml';config.write_text(config.read_text().replace('translation_units_version: 1\n',''))
    assert not d.required(job)
    assert d.assembly_errors(job)==[] and d.fingerprint_paths(job)==[]
    with pytest.raises(ValueError,match='opt-in'):d.complete(job,'preamble')


def test_opt_in_adds_assembly_to_metrics_without_restarting_translator(job):
    before={'scope':'full','finished_at':None,'required_stages':['translation-source','translator'],
        'stages':[{'id':'persistent-stage','stage':'translator','status':'running','thread_id':'same-thread'}]}
    put(job,'metrics/manifest.json',before)
    assert 'translation-assemble' in metrics.planned_stages(job,'full')
    d.sync_metrics_plan(job)
    after=json.loads((job/'metrics/manifest.json').read_text())
    assert after['stages']==before['stages']
    assert after['required_stages']==before['required_stages']+['translation-assemble']
    d.sync_metrics_plan(job)
    assert json.loads((job/'metrics/manifest.json').read_text())==after


def test_gate_and_fingerprint_require_current_complete_assembly_only_for_unit_jobs(job):
    finish(job);d.assemble(job)
    put(job,'edited.md',(job/'translated.md').read_text())
    put(job,'translation.meta.json',json.loads((job/'translated.meta.json').read_text()))
    put(job,'translation.editor.md','Editor check recorded.');put(job,'translation.qa.md','Independent QA recorded.')
    assert t.check(job)['status']=='PASS'
    hashes=t.fingerprint(job)
    assert d.PLAN in hashes and d.ASSEMBLY in hashes and 'translation_units/ru/h2-001.md' in hashes
    p=job/'translated.md';p.write_text(p.read_text()+'Unapproved appended prose.\n')
    assert 'assembly is missing/stale' in ' '.join(t.check(job)['errors'])
    config=job/'job.yaml';config.write_text(config.read_text().replace('translation_units_version: 1\n',''))
    assert set(t.fingerprint(job))==set(t.INPUTS)


def test_title_only_preamble_is_valid_when_source_has_no_pre_h2_body(tmp_path):
    source={'data':{'id':18,'locale':'en','slug':'example','title':'Title','publishedAt':'2026-01-01',
        'content':'<h2>One</h2><p>Body.</p>'}}
    job=tmp_path/'title-only';t.bootstrap(job,'example','ru',source)
    config=job/'job.yaml';config.write_text(config.read_text()+'translation_units_version: 1\n')
    d.prepare(job);put(job,'translated.meta.json',{'title':'Заголовок'})
    put(job,'translation_units/ru/preamble.md','# Заголовок\n')
    assert d.complete(job,'preamble')['status']=='complete'
