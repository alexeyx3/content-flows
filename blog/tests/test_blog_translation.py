"""Translation branch retains source structure and cannot bypass review/CMS gates."""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import blog_translation as t
import article_materials as materials
import codex_metrics as metrics


def fixture_record():
    return {'data': {'id': 200, 'attributes': {
        'slug': 'example-alternatives', 'locale': 'en', 'title': 'Example 2026',
        'content': '<p>Use 20+ templates from $40.</p><h2>Options</h2><ul><li>A</li><li>B</li></ul>'
                   '<table><tr><th>Name</th><th>Price</th></tr><tr><td>A</td><td>$40</td></tr></table>',
        'publishedAt': '2026-01-01T00:00:00Z', 'updatedAt': '2026-10-20T00:00:00Z',
        'summary': None, 'metaTitle': None, 'metaDescription': None,
        'cover': {'url': 'https://example.com/cover.png', 'name': 'cover.png'},
        'author': {'id': 9}, 'editors': [{'id': 10}], 'tags': [{'id': 2}], 'indexable': True,
    }}}


def put(job, name, value):
    p = job/name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value)


@pytest.fixture
def job(tmp_path):
    job=tmp_path/'translation'
    t.bootstrap(job, 'example-alternatives', 'ru', fixture_record())
    # These retention/seal fixtures model existing pre-style-gate jobs. New
    # bootstrap defaults are exercised separately without altering old fixtures.
    config=job/'job.yaml'
    config.write_text(config.read_text().replace('translation_style_review_version: 1\n',''))
    article='# Пример 2026\n\nЕсть 20+ шаблонов от $40.\n\n## Варианты\n\n- A\n- B\n\n| Имя | Цена |\n| --- | --- |\n| A | $40 |\n'
    put(job,'edited.md',article)
    put(job,'translation.meta.json',{'title':'Пример 2026','slug':'example-alternatives','locale':'ru',
        'summary':'Варианты по опубликованному исходнику.', 'metaTitle':'Пример 2026', 'metaDescription':'Варианты и цены.'})
    put(job,'translation.links.json',{'links':[]})
    put(job,'translation.visuals.json',{'assets':[{'id':'cover','kind':'cover','source_url':'https://example.com/cover.png',
        'text_inventory':'English cover title','status':'reuse_review_only','rationale':'Untranslated cover explicitly disclosed for review.'}]})
    for name in ('translation.issues.md','translation.editor.md','translation.qa.md'):
        put(job,name,'Source claims were not freshly verified; review only.')
    put(job,'translation.glossary.json',{'terms':[]})
    return job


def approve(job):
    put(job,'translation.qa.json',{'fidelity_status':'PASS','review_status':'PASS',
        'publication_status':'NOT_ASSESSED','fresh_fact_verification':False,'findings':[], 'hashes':t.fingerprint(job)})
    assert t.drift(job,fixture_record())['status']=='PASS'
    assert t.package(job)['status']=='PASS'
    assert t.seal(job)['status']=='PASS'


def test_bootstrap_preserves_complete_record_and_refuses_overwrite(job):
    assert t.read_json(job/'source/cms-record.json')==fixture_record()
    assert t.read_json(job/'source/metadata.json')['summary'] is None
    assert t.read_json(job/'translation.json')['metadata_policy']=='derived_from_source'
    with pytest.raises(ValueError, match='overwrite'):
        t.bootstrap(job,'example-alternatives','ru',fixture_record())


def test_bootstrap_rejects_non_en_or_unpublished(tmp_path):
    for key,value in [('locale','ru'),('publishedAt',None),('slug','other')]:
        data=fixture_record();data['data']['attributes'][key]=value
        with pytest.raises(ValueError,match='exact current published EN'):
            t.bootstrap(tmp_path/key,'example-alternatives','ru',data)


def test_content_drift_blocks_even_when_updated_at_unchanged(job):
    data=fixture_record();data['data']['attributes']['content']+='<p>Changed.</p>'
    assert t.drift(job,data)['status']=='BLOCK'
    data=fixture_record();data['data']['attributes']['updatedAt']='2026-10-21T00:00:00Z'
    assert t.drift(job,data)['status']=='PASS'
    data['data']['attributes']['author']={'id':99}
    assert t.drift(job,data)['status']=='BLOCK'


def test_live_profile_metadata_drift_retains_actual_hash_and_existing_seals(job,monkeypatch):
    approve(job)
    protected={name:(job/name).read_bytes() for name in (*t.INPUTS,'translation.qa.json',
        'translation.qa_receipt.json','out/translation-package.json')}
    old=t.read_json(job/'source/cms-record.json')
    current=copy.deepcopy(old)
    r=current['data']['attributes']
    r['author'].update(jobTitle='New role',shortBio='Updated profile',translations=[{'locale':'ru'}])
    r['editors'][0].update(fullBio='New editor biography',linkedin='profile')
    monkeypatch.setattr(t,'fetch',lambda slug:current)
    assert t.export_errors(job,'review',remote=True)==[]
    receipt=t.read_json(job/'out/translation-source-drift.json')
    assert receipt['current_source_sha256']==t.source_hash(current)
    assert receipt['current_source_sha256']!=receipt['source_sha256']
    assert t.drift_receipt_valid(job,receipt)
    assert t.package(job)['status']=='PASS'
    assert all((job/name).read_bytes()==value for name,value in protected.items())


@pytest.mark.parametrize('field,value',[
    ('id',999),('locale','ru'),('content','<p>Changed.</p>'),('contentHtml','<p>New HTML.</p>'),
    ('title','Changed title'),('slug','changed'),('summary','Changed summary'),
    ('metaTitle','Changed SEO'),('metaDescription','Changed description'),
    ('publishedAt',None),('cover',{'id':99}),('tags',[{'id':99}]),('indexable',False),
    ('author',{'id':99}),('editors',[{'id':99}]),
])
def test_live_equivalence_does_not_relax_article_or_attribution_fields(job,field,value):
    current=fixture_record();current['data']['attributes'][field]=value
    assert not t.source_matches_snapshot(job,current)
    assert t.drift(job,current)['status']=='BLOCK'


@pytest.mark.parametrize('field,value',[
    ('author',{}),('author',{'id':None}),('author',{'id':'9'}),('author',{'id':True}),
    ('author',{'attributes':{'id':9}}),('editors',{}),('editors',[{}]),
    ('editors',[{'id':0}]),('editors',[{'id':10},{'id':10}]),
])
def test_malformed_profile_relations_cannot_establish_equivalence(job,field,value):
    current=fixture_record();current['data']['attributes'][field]=value
    assert not t.source_matches_snapshot(job,current)
    assert t.drift(job,current)['status']=='BLOCK'


def test_missing_profile_relation_and_reordered_editors_are_not_equivalent(job):
    current=fixture_record();del current['data']['attributes']['author']
    assert not t.source_matches_snapshot(job,current)
    before=fixture_record();before['data']['attributes']['editors']=[{'id':10},{'id':11}]
    after=copy.deepcopy(before);after['data']['attributes']['editors'].reverse()
    assert t.source_projection(before)!=t.source_projection(after)


@pytest.mark.parametrize('tamper',['raw_hash','live_record','snapshot_hash','projection_hash','boolean'])
def test_package_rejects_fabricated_or_stale_profile_equivalence_proof(job,tamper):
    approve(job)
    current=fixture_record();current['data']['attributes']['author']['jobTitle']='New role'
    assert t.drift(job,current)['status']=='PASS'
    receipt=t.read_json(job/'out/translation-source-drift.json')
    if tamper=='raw_hash':receipt['current_source_sha256']='fake'
    if tamper=='live_record':receipt['source_comparison']['current_source_record']['data']['attributes']['summary']='Changed'
    if tamper=='snapshot_hash':receipt['source_comparison']['snapshot_projection_sha256']='fake'
    if tamper=='projection_hash':receipt['source_comparison']['current_projection_sha256']='fake'
    if tamper=='boolean':receipt['source_comparison']=True
    put(job,'out/translation-source-drift.json',receipt)
    assert not t.drift_receipt_valid(job,receipt)
    assert t.package(job)['status']=='BLOCK'


def test_strict_legacy_drift_receipt_remains_compatible(job):
    approve(job)
    receipt=t.read_json(job/'out/translation-source-drift.json')
    del receipt['source_comparison']
    put(job,'out/translation-source-drift.json',receipt)
    assert t.drift_receipt_valid(job,receipt)
    assert t.package(job)['status']=='PASS'
    receipt['current_source_sha256']='different'
    assert not t.drift_receipt_valid(job,receipt)


def test_snapshot_changes_are_detected(job):
    (job/'source/article.md').write_text('Changed')
    assert 'immutable source changed' in ' '.join(t.source_errors(job))


def test_retention_gate_accepts_complete_translation(job):
    assert t.check(job)['status']=='PASS'


@pytest.mark.parametrize('old,new,expected',[
    ('20+','21+','numeric-token'),
    ('- B\n','','list structure'),
    ('## Варианты','### Варианты','heading hierarchy'),
    ('| A | $40 |','| A | $40 | extra |','table dimensions'),
])
def test_retention_gate_rejects_loss_or_changes(job,old,new,expected):
    p=job/'edited.md';p.write_text(p.read_text().replace(old,new))
    assert expected in ' '.join(t.check(job)['errors'])


def test_missing_image_or_cover_cannot_disappear(job):
    put(job,'translation.visuals.json',{'assets':[]})
    assert 'visual inventory' in ' '.join(t.check(job)['errors'])


def test_missing_or_stale_qa_blocks_export_and_all_cms_exports(job):
    assert t.export_errors(job,'review',remote=False)
    approve(job)
    assert t.export_errors(job,'review',remote=False)==[]
    assert materials.export_errors(job,'review',remote=False)==[]
    assert 'unsupported' in ' '.join(materials.export_errors(job,'strapi',remote=False))
    (job/'edited.md').write_text((job/'edited.md').read_text().replace('Есть','Доступны'))
    assert 'stale' in ' '.join(t.export_errors(job,'review',remote=False))


@pytest.mark.parametrize('artifact',['out/article.html','out/meta.md','translation.qa.md','translation.visuals.json','translation.qa.json'])
def test_seal_detects_every_review_material_change(job,artifact):
    approve(job)
    p=job/artifact
    if p.suffix=='.json':
        value=json.loads(p.read_text());value['changed']=True;put(job,artifact,value)
    else:p.write_text(p.read_text()+'\nChanged')
    assert t.export_errors(job,'review',remote=False)


def test_review_export_rechecks_live_source(job,monkeypatch):
    approve(job)
    data=fixture_record();data['data']['attributes']['summary']='new claim'
    monkeypatch.setattr(t,'fetch',lambda slug:data)
    assert 'live source' in ' '.join(t.export_errors(job,'review',remote=True))
    def unavailable(slug):raise RuntimeError('secret=must_not_leak')
    monkeypatch.setattr(t,'fetch',unavailable)
    errors=t.export_errors(job,'review',remote=True)
    assert errors and 'must_not_leak' not in str(errors)


def test_qa_cannot_claim_freshness_or_publication_approval(job):
    approve(job)
    qa=t.read_json(job/'translation.qa.json');qa['publication_status']='PASS';put(job,'translation.qa.json',qa)
    assert 'must not claim' in ' '.join(t.qa_errors(job))


def test_metrics_plan_translation_is_complete_without_new_topic_stages(job):
    stages=metrics.planned_stages(job,'full')
    assert stages==['translation-source','translator','translation-editor','translation-check','translation-qa',
                    'translation-source-drift','translation-package','translation-seal','gdoc-review-push']
    assert not set(stages)&{'evidence','serp','writer','strategy-brief'}


def test_review_preface_discloses_fidelity_scope_and_assets(job):
    approve(job)
    preface=t.review_preface(job)
    assert 'свежая фактическая проверка' in preface
    assert 'reuse_review_only' in preface
    assert 'derived_from_source' in preface
    assert t.read_json(job/'translation.json')['source_sha256'] in preface


@pytest.mark.parametrize('fragment',[
    '<table><caption>Prices exclude tax</caption><tr><td>A</td></tr></table>',
    '<table><tr><td colspan="2">A</td></tr></table>',
    '<table><tr><td rowspan="2">A</td></tr><tr><td>B</td></tr></table>',
    '<ol start="5"><li>A</li></ol>',
    '<ol reversed><li>A</li></ol>',
    '<ol><li value="8">A</li></ol>',
    '<ul><li>A<ul><li>B</li></ul></li></ul>',
    '<p>X<sup>2</sup></p>',
])
def test_unsupported_semantic_source_shapes_fail_before_snapshot(tmp_path,fragment):
    data=fixture_record();data['data']['attributes']['content']=fragment
    job=tmp_path/'unsupported'
    with pytest.raises(ValueError,match='unsupported|conversion'):
        t.bootstrap(job,'example-alternatives','ru',data)
    assert not job.exists()


def test_caption_loss_is_detected_even_when_table_dimensions_match():
    content='<table><caption>Prices exclude tax</caption><tr><td>A</td></tr></table>'
    md='# Title\n\n'+t.markdown(t.Tree(content).root)
    assert any('text' in e for e in t.conversion_errors(content,md))


def test_missing_source_text_cannot_hide_behind_matching_counts():
    content='<h2>Details</h2><p>Prices exclude tax.</p>'
    assert 'changed text' in ' '.join(t.conversion_errors(content,'# Title\n\n## Details\n'))


def test_numeric_tokens_ignore_alphanumeric_brand_but_retain_coverage_and_prices():
    assert t.number_tokens('Example Co 50+ countries $29 4.2 stars W-2 1099-NEC') == t.Counter({'50+':1,'29':1,'4.2':1,'2':1,'1099':1})
    assert t.number_tokens('Example Co helps 50+ countries') != t.number_tokens('50 countries')


def test_translation_doc_push_avoids_sheet_mutation_and_has_preface(job,monkeypatch):
    from argparse import Namespace
    from types import SimpleNamespace
    import gdoc_review as review
    approve(job)
    monkeypatch.setattr(review,'export_errors',lambda *args:[])
    monkeypatch.setattr(review,'services',lambda:(None,None))
    monkeypatch.setattr(review,'ensure_folder',lambda *args:'folder-id')
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        assert 'md_to_gdoc.py' in command[1]
        assert '--preface' in command
        assert 'RU translation' in command[command.index('--title')+1]
        put(job,'review/01-document.json',{'document_id':'doc-id','images':[]})
        return SimpleNamespace(returncode=0,stdout='URL=https://docs.google.com/document/d/doc-id/edit\n',stderr='')
    monkeypatch.setattr(review.subprocess,'run',run)
    review.cmd_push(Namespace(job=str(job),round=1,baseline=None,highlight_mode='blocks'))
    assert len(calls)==1
    tracking=t.read_json(job/'review/translation-review.json')
    assert tracking['locale']=='ru' and tracking['status']=='in review'
    assert tracking['temnik_sync']=='not_applicable_translation_fields_not_defined'
    assert 'temnik_cluster_id' not in (job/'job.yaml').read_text()
    assert 'свежая фактическая проверка' in (job/'review/01-translation-preface.md').read_text()


def test_body_image_retention_gate_blocks_silent_drop(job,tmp_path):
    data=fixture_record();data['data']['attributes']['content']+='<p><img src="https://example.com/body.png" alt="Chart"></p>'
    image_job=tmp_path/'image-translation'
    t.bootstrap(image_job,'example-alternatives','ru',data)
    for name in t.INPUTS:
        if name.startswith('source/') or name=='translation.json' or not (job/name).exists():continue
        put(image_job,name,(job/name).read_text())
    cover=t.read_json(job/'translation.visuals.json')['assets'][0]
    body={'id':'body-1','kind':'body','source_url':'https://example.com/body.png',
          'text_inventory':'No textual labels','status':'reuse_review_only','rationale':'Source retained for review.'}
    put(image_job,'translation.visuals.json',{'assets':[body,cover]})
    assert 'body images omitted' in ' '.join(t.check(image_job)['errors'])
    p=image_job/'edited.md';p.write_text(p.read_text()+'\n![Диаграмма](https://example.com/body.png)\n')
    assert t.check(image_job)['status']=='PASS'
    body['status']='needs_translation'
    put(image_job,'translation.visuals.json',{'assets':[body,cover]})
    assert 'requires translation' in ' '.join(t.check(image_job)['errors'])


def test_internal_link_provenance_rejects_other_language(job,tmp_path):
    data=fixture_record();data['data']['attributes']['content']+='<p><a href="https://example.com/">Website</a></p>'
    link_job=tmp_path/'link-translation'
    t.bootstrap(link_job,'example-alternatives','ru',data)
    for name in t.INPUTS:
        if name.startswith('source/') or name=='translation.json' or not (job/name).exists():continue
        put(link_job,name,(job/name).read_text())
    p=link_job/'edited.md';p.write_text(p.read_text()+'\n[Сайт](https://example.com/)\n')
    put(link_job,'translation.links.json',{'links':[{'source':'https://example.com/','target':'https://example.com/','reason':'retained'}]})
    assert 'verified Russian URL' in ' '.join(t.check(link_job)['errors'])
    p.write_text(p.read_text().replace('[Сайт](https://example.com/)','Сайт'))
    put(link_job,'translation.links.json',{'links':[{'source':'https://example.com/','target':None,'reason':'no_verified_ru_target'}]})
    assert t.check(link_job)['status']=='PASS'
    put(link_job,'translation.links.json',{'links':[]})
    assert 'provenance' in ' '.join(t.check(link_job)['errors'])


def test_derived_metadata_still_obeys_caps(job):
    meta=t.read_json(job/'translation.meta.json');meta['metaTitle']='Я'*71
    put(job,'translation.meta.json',meta)
    assert 'metaTitle: 71' in ' '.join(t.check(job)['errors'])


def native_doc(preface,article):
    import md_to_gdoc as converter
    index=1
    content=[]
    def paragraph(value):
        nonlocal index
        plain=converter.inline(value)[0]+'\n'
        start=index;index+=len(plain)
        return {'startIndex':start,'endIndex':index,'paragraph':{'elements':[
            {'startIndex':start,'endIndex':index,'textRun':{'content':plain}}]}}
    def add(block):
        nonlocal index
        if block[0]=='table':
            begin=index;rows=[]
            for row in block[1]:
                rows.append({'tableCells':[{'content':[paragraph(cell)]} for cell in row]})
            content.append({'startIndex':begin,'endIndex':index,'table':{'tableRows':rows}})
        else:content.append(paragraph(block[2] if block[0]=='heading' else block[1]))
    for block in converter.parse(preface):add(block)
    start=index
    for block in converter.parse(article):add(block)
    return {'documentId':'doc-id','title':'01 — Example — RU translation',
        'body':{'content':content},'namedRanges':{'BLOG_ARTICLE_BODY':{'namedRanges':[
        {'ranges':[{'startIndex':start,'endIndex':index}]}]}}}


def test_native_review_verification_checks_article_tables_and_preface(job):
    approve(job)
    article=(job/'edited.md').read_text();preface=t.review_preface(job)
    put(job,'review/01-document.json',{'document_id':'doc-id','images':[],'article_sha256':t.digest(article)})
    put(job,'review/01-sent.md',article);put(job,'review/01-translation-preface.md',preface)
    put(job,'review/translation-review.json',{'review_doc_url':'https://docs.google.com/document/d/doc-id/edit',
        'round':1,'article_sha256':t.digest(article),'qa_receipt_sha256':t.digest((job/'translation.qa_receipt.json').read_bytes())})
    doc=native_doc(preface,article)
    assert t.verify_review(job,1,doc)['status']=='PASS'
    # An intact article cannot conceal a dropped source/freshness limitation.
    doc=native_doc(preface.replace('свежая фактическая проверка','ПРОПУЩЕНО'),article)
    assert 'preface/limitations' in ' '.join(t.verify_review(job,1,doc)['errors'])
    doc=native_doc(preface,article.replace('$40','$41'))
    assert 'text/table readback' in ' '.join(t.verify_review(job,1,doc)['errors'])



def test_native_review_rejects_old_local_and_native_preface_after_new_qa_seal(job):
    approve(job)
    article=(job/'edited.md').read_text();old_preface=t.review_preface(job)
    old_seal=t.digest((job/'translation.qa_receipt.json').read_bytes())
    put(job,'review/01-document.json',{'document_id':'doc-id','images':[],'article_sha256':t.digest(article)})
    put(job,'review/01-sent.md',article);put(job,'review/01-translation-preface.md',old_preface)
    put(job,'review/translation-review.json',{'review_doc_url':'https://docs.google.com/document/d/doc-id/edit',
        'round':1,'article_sha256':t.digest(article),'qa_receipt_sha256':old_seal})
    old_doc=native_doc(old_preface,article)
    assert t.verify_review(job,1,old_doc)['status']=='PASS'
    qa=t.read_json(job/'translation.qa.json')
    qa['findings']=[{'id':'NEW-POLICY','kind':'source_policy','severity':'warning',
        'explanation':'New issue requiring explicit review.','resolution':'Publisher review required.'}]
    put(job,'translation.qa.json',qa)
    assert t.package(job)['status']=='PASS'
    assert t.seal(job)['status']=='PASS'
    assert (job/'edited.md').read_text()==article
    result=t.verify_review(job,1,old_doc)
    assert result['status']=='BLOCK'
    assert any('preface is stale' in e for e in result['errors'])
    assert any('tracking seal' in e for e in result['errors'])



def enable_style_review(job):
    config=job/'job.yaml'
    config.write_text(config.read_text()+'translation_style_review_version: 1\n')


def test_style_gate_is_explicit_opt_in_and_does_not_migrate_old_seal(job):
    approve(job)
    before={str(p.relative_to(job)):p.read_bytes() for p in job.rglob('*') if p.is_file()}
    assert not t.style_review_required(job)
    assert t.qa_errors(job)==[]
    assert t.export_errors(job,'review',remote=False)==[]
    assert before=={str(p.relative_to(job)):p.read_bytes() for p in job.rglob('*') if p.is_file()}
    enable_style_review(job)
    errors=t.qa_errors(job)
    assert 'natural_ru_status' in ' '.join(errors)
    assert 'style_status' in ' '.join(errors)
    assert t.package(job)['status']=='BLOCK'
    assert t.export_errors(job,'review',remote=False)


@pytest.mark.parametrize('natural,style', [('BLOCK','PASS'),('PASS','BLOCK'),(None,'PASS'),('PASS',None)])
def test_fidelity_pass_does_not_override_failed_or_missing_native_ru_style_qa(job,natural,style):
    approve(job);enable_style_review(job)
    qa=t.read_json(job/'translation.qa.json')
    qa.update(natural_ru_status=natural,style_status=style)
    put(job,'translation.qa.json',qa)
    assert qa['fidelity_status']=='PASS' and qa['review_status']=='PASS'
    assert t.qa_errors(job)
    assert t.package(job)['status']=='BLOCK'


def test_opt_in_requires_actual_style_resolution_and_allows_disclosed_authorized_edits(job):
    approve(job);enable_style_review(job)
    qa=t.read_json(job/'translation.qa.json')
    qa.update(natural_ru_status='PASS',style_status='PASS',findings=[{
        'id':'STYLE-1','kind':'language_style','severity':'warning',
        'explanation':'Recurring unnatural formulation remains.',
        'resolution':'Inherited from the English source.'}])
    put(job,'translation.qa.json',qa)
    assert 'unresolved native-RU/style defect' in ' '.join(t.qa_errors(job))
    qa['findings'][0]['resolution']='fixed'
    qa['findings'].append({'id':'AUTHORIZED-1','kind':'publisher_authorized_edit','severity':'info',
        'explanation':'Comparative wording neutralized at explicit publisher request.',
        'resolution':'Applied within exact comment scope; source retained.'})
    put(job,'translation.qa.json',qa)
    assert t.qa_errors(job)==[]
    assert t.package(job)['status']=='PASS'
    assert t.seal(job)['status']=='PASS'
    assert t.export_errors(job,'review',remote=False)==[]



def test_new_bootstrap_enables_mandatory_native_ru_and_style_gate(tmp_path):
    new_job=tmp_path/'new-translation'
    t.bootstrap(new_job,'example-alternatives','ru',fixture_record())
    assert 'translation_style_review_version: 1\n' in (new_job/'job.yaml').read_text()
    assert t.style_review_required(new_job)


def test_new_bootstrap_enables_manifest_bound_technical_artifact_gate(job):
    assert t.read_json(job/'translation.json')['text_artifact_check_version'] == 1


@pytest.mark.parametrize('marker', ['oai_citation:0', ':contentReference[oaicite:0]',
                                    '【1†source】', '[cite: 1]', '[span_1]',
                                    'sandbox:/mnt/data/file.pdf', '</think>', '&lt;/think&gt;'])
def test_final_raw_article_artifacts_block_before_conversion_and_packaging(job,marker):
    approve(job)
    article=job/'edited.md'
    article.write_text(article.read_text()+'\n'+marker+'\n')
    # Even a freshly recomputed QA cannot waive an actual technical leak.
    qa=t.read_json(job/'translation.qa.json');qa['hashes']=t.fingerprint(job)
    put(job,'translation.qa.json',qa)
    assert 'technical text artifact in edited.md' in ' '.join(t.check(job)['errors'])
    assert t.package(job)['status']=='BLOCK'
    assert t.seal(job)['status']=='BLOCK'
    assert 'technical text artifact' in ' '.join(t.export_errors(job,'review',remote=False))


@pytest.mark.parametrize('key', ['title','summary','metaTitle','metaDescription'])
def test_visible_metadata_is_checked_for_technical_artifacts(job,key):
    meta=t.read_json(job/'translation.meta.json');meta[key]='Описание </think>'
    put(job,'translation.meta.json',meta)
    assert f'technical text artifact in translation.meta.json.{key}' in ' '.join(t.check(job)['errors'])


def test_alt_text_is_checked_but_editor_and_qa_reports_are_not_public_copy(job):
    for name in ('translation.editor.md','translation.qa.md'):
        put(job,name,'Reviewed marker examples: oai_citation and </think>.')
    assert t.check(job)['status']=='PASS'
    p=job/'edited.md';p.write_text(p.read_text()+'\n![oai_citation](https://example.com/image.png)\n')
    assert 'technical text artifact in edited.md' in ' '.join(t.check(job)['errors'])


def test_removing_bound_gate_flag_invalidates_existing_qa_and_seal(job):
    approve(job)
    manifest=t.read_json(job/'translation.json')
    del manifest['text_artifact_check_version']
    put(job,'translation.json',manifest)
    assert 'stale' in ' '.join(t.qa_errors(job))
    assert t.export_errors(job,'review',remote=False)


def test_legacy_absence_does_not_migrate_or_rewrite_an_old_seal(job):
    manifest=t.read_json(job/'translation.json')
    del manifest['text_artifact_check_version']
    put(job,'translation.json',manifest)
    # Models an older sealed job; all legacy fingerprints remain unchanged.
    approve(job)
    before={str(p.relative_to(job)):p.read_bytes() for p in job.rglob('*') if p.is_file()}
    assert t.export_errors(job,'review',remote=False)==[]
    assert before=={str(p.relative_to(job)):p.read_bytes() for p in job.rglob('*') if p.is_file()}


@pytest.mark.parametrize('version', [None,False,[],{},0,2,True,'1'])
def test_unknown_artifact_gate_version_cannot_silently_disable_new_check(job,version):
    manifest=t.read_json(job/'translation.json');manifest['text_artifact_check_version']=version
    put(job,'translation.json',manifest)
    assert 'unsupported translation text_artifact_check_version' in ' '.join(t.check(job)['errors'])
