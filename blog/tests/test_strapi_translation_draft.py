"""A reviewed translation can create one linked RU draft, never a publication."""
import copy
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import strapi_translation_draft as d
import blog_translation as t


def put(job,name,value):
    p=job/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False) if isinstance(value,dict) else value)


def source():
    return {'id':200,'locale':'en','slug':'example-alternatives','title':'Example 2026',
        'content':'<p>20+ templates from $40.</p>','publishedAt':'2026-01-15T10:00:00.000Z',
        'createdAt':'2026-01-14T10:00:00Z','updatedAt':'2026-01-20T10:00:00.000Z',
        'summary':None,'metaTitle':None,'metaDescription':None,'indexable':True,
        'cover':None,'author':{'id':5,'name':'Author'},'editors':[{'id':4,'name':'Editor'}],
        'tags':[{'id':2,'name':'Topic'}],'viewCount':'10'}


class FakeApi:
    def __init__(self):
        self.source=source();self.target=None;self.linked=set();self.calls=[]
        self.timeout_after_create=False;self.timeout_before_create=False
        self.corrupt_html=False;self.change_source=False
    @property
    def writes(self):return [c for c in self.calls if c[1]!='GET']
    def __call__(self,path,method='GET',body=None):
        self.calls.append((path,method,copy.deepcopy(body)))
        parsed=urllib.parse.urlparse(path);q=urllib.parse.parse_qs(parsed.query)
        if method in {'POST','PUT'}:
            payload=body if method=='POST' else body['data']
            assert payload['publishedAt'] is None
            assert path!='/articles/200' and not path.startswith('/users') and not path.startswith('/tags')
            if self.timeout_before_create:raise TimeoutError('secret=not_for_receipts')
            if method=='POST':assert path=='/articles/200/localizations' and 'data' not in body
            else:assert path=='/articles/1001'
            self.target={**copy.deepcopy(payload),'id':1001,'content':payload['contentHtml'],
                'author':{'id':payload['author']} if payload['author'] else None,
                'editors':[{'id':x} for x in payload['editors']],
                'tags':[{'id':x} for x in payload['tags']]}
            del self.target['contentHtml'];self.linked.add(1001)
            if self.corrupt_html:self.target['content']='<p>Lost content.</p>'
            if self.change_source:self.source['title']='Unexpected original edit'
            if self.timeout_after_create:self.timeout_after_create=False;raise TimeoutError('outcome unknown')
            return {'id':1001,'locale':'ru'}
        if parsed.path=='/articles/200':return {'data':copy.deepcopy(self.source)}
        if parsed.path=='/articles/1001' and self.target:return {'data':copy.deepcopy(self.target)}
        if parsed.path.endswith('/findBySlug'):
            if self.target:return {'data':copy.deepcopy(self.target)}
            raise urllib.error.HTTPError(path,404,'Not found',{},None)
        if parsed.path.endswith('/alternates'):
            rows=[{'locale':'en','slug':self.source['slug']}]
            if self.target and self.target.get('publishedAt'):rows.append({'locale':'ru','slug':self.source['slug']})
            return {'data':rows}
        if parsed.path=='/articles':
            if q.get('locale')==['ru']:
                rows=[copy.deepcopy(self.target)] if self.target and self.target.get('publishedAt') else []
            else:
                include=True
                if 'filters[localizations][id][$eq]' in q:
                    include=int(q['filters[localizations][id][$eq]'][0]) in self.linked
                if 'filters[localizations][locale][$eq]' in q:
                    include=bool(self.linked)
                rows=[copy.deepcopy(self.source)] if include else []
                if 'fields[0]' in q:rows=[{'id':r['id'],'slug':r['slug']} for r in rows]
            return {'data':rows,'meta':{'pagination':{'total':len(rows)}}}
        raise AssertionError((path,method))


@pytest.fixture
def ready_job(tmp_path,monkeypatch):
    job=tmp_path/'translation'
    t.bootstrap(job,'example-alternatives','ru',{'data':source()})
    article='# Пример 2026\n\n20+ шаблонов от $40.\n'
    put(job,'edited.md',article);put(job,'out/article.html','<p>20+ шаблонов от $40.</p>')
    put(job,'translation.meta.json',{'locale':'ru','slug':'example-alternatives','title':'Пример 2026',
        'summary':'Описание','metaTitle':'Пример','metaDescription':'Описание'})
    put(job,'translation.qa.json',{'findings':[{'kind':'source_freshness','explanation':'Historical claims not reverified.'}]})
    put(job,'translation.qa_receipt.json',{'status':'PASS','review_only':True})
    put(job,'out/translation-package.json',{'status':'PASS'})
    article_sha=t.digest(article);seal=t.digest((job/'translation.qa_receipt.json').read_bytes())
    put(job,'review/translation-review.json',{'round':2,'article_sha256':article_sha,
        'qa_receipt_sha256':seal,'review_doc_url':'https://docs.google.com/document/d/doc2/edit'})
    put(job,'review/02-document.json',{'document_id':'doc2','article_sha256':article_sha})
    put(job,'review/02-translation-preface.md','Current limitations\n')
    put(job,'review/02-sent.md',article)
    put(job,'review/02-translation-delivery.json',{'status':'PASS','document_id':'doc2','article_sha256':article_sha,
        'preface_sha256':t.digest('Current limitations\n'),'tables':0,'checked_at':'previous'})
    monkeypatch.setattr(t,'export_errors',lambda *a,**kw:[])
    monkeypatch.setattr(t,'review_preface',lambda *a:'Current limitations\n')
    monkeypatch.setattr(t,'verify_review',lambda *a,**kw:{'status':'PASS'})
    return job


def authorize(job):
    return d.authorize(job,2,'Publisher','Current conversation: draft only',t.digest((job/'edited.md').read_bytes()))


def test_no_writes_without_authorization_or_apply(ready_job):
    api=FakeApi()
    with pytest.raises(FileNotFoundError):d.export(ready_job,api_fn=api,apply=True)
    assert not api.calls
    authorize(ready_job)
    result=d.export(ready_job,api_fn=api)
    assert result['mode']=='dry_run' and result['publishedAt'] is None
    assert not api.writes and api.target is None


def test_explicit_authorization_binds_current_article_and_seal(ready_job):
    authorize(ready_job);api=FakeApi()
    put(ready_job,'out/article.html','<p>Changed unapproved HTML.</p>')
    with pytest.raises(d.DraftError,match='stale'):d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes


def test_missing_review_round_or_delivery_blocks_authorization(ready_job):
    with pytest.raises(FileNotFoundError):d.authorize(ready_job,1,'Publisher','Draft only',t.digest((ready_job/'edited.md').read_bytes()))
    put(ready_job,'review/02-translation-delivery.json',{'status':'BLOCK','document_id':'doc2',
        'article_sha256':t.digest((ready_job/'edited.md').read_bytes())})
    with pytest.raises(d.DraftError,match='delivery'):authorize(ready_job)


def test_current_qa_review_and_sanitizer_all_must_pass(ready_job,monkeypatch):
    authorize(ready_job);api=FakeApi()
    monkeypatch.setattr(t,'export_errors',lambda *a,**kw:['style is BLOCK'])
    with pytest.raises(d.DraftError,match='style is BLOCK'):d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes
    monkeypatch.setattr(t,'export_errors',lambda *a,**kw:[])
    monkeypatch.setattr(t,'verify_review',lambda *a,**kw:{'status':'BLOCK'})
    with pytest.raises(d.DraftError,match='native'):d.export(ready_job,api_fn=api,apply=True)
    monkeypatch.setattr(t,'verify_review',lambda *a,**kw:{'status':'PASS'})
    monkeypatch.setattr(d,'html_survives_sanitizer',lambda _:False)
    with pytest.raises(d.DraftError,match='sanitizer'):d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes


def test_create_one_linked_ru_draft_and_idempotent_retry(ready_job):
    authorize(ready_job);api=FakeApi();before=copy.deepcopy(api.source)
    result=d.export(ready_job,api_fn=api,apply=True)
    assert result['id']==1001 and result['publishedAt'] is None and result['readback_status']=='PASS'
    assert api.source==before
    assert len(api.writes)==1 and api.writes[0][1]=='POST'
    payload=api.writes[0][2]
    assert payload['publishedAt'] is None and payload['cover'] is None and payload['indexable'] is False
    assert payload['author']==5 and payload['editors']==[4] and payload['tags']==[2]
    assert (ready_job/d.DIRECTORY/'record.json').exists()
    result=d.export(ready_job,api_fn=api,apply=True)
    assert result['id']==1001 and len(api.writes)==1


def test_profile_metadata_drift_allows_draft_without_changing_legacy_binding(ready_job):
    authorize(ready_job);api=FakeApi()
    before_source=(ready_job/'source/cms-record.json').read_bytes()
    before_binding=copy.deepcopy(d.validate_authorization(ready_job)['binding'])
    api.source['author'].update(jobTitle='New role',shortBio='New biography',translations=[{'locale':'ru'}])
    api.source['editors'][0].update(fullBio='Updated editor biography')
    current=copy.deepcopy(api.source)
    result=d.export(ready_job,api_fn=api,apply=True)
    assert result['readback_status']=='PASS' and len(api.writes)==1
    assert api.source==current
    assert (ready_job/'source/cms-record.json').read_bytes()==before_source
    assert d.validate_authorization(ready_job)['binding']==before_binding
    assert api.writes[0][2]['author']==5 and api.writes[0][2]['editors']==[4]


@pytest.mark.parametrize('field,value',[
    ('author',{'id':77}),('editors',[{'id':77}]),('author',{}),('editors',[{}]),
    ('summary','Changed summary'),('cover',{'id':7}),('tags',[{'id':7}]),
])
def test_equivalence_preflight_still_blocks_source_identity_and_content_drift(ready_job,field,value):
    authorize(ready_job);api=FakeApi();api.source[field]=value
    with pytest.raises(d.DraftError,match='immutable snapshot'):
        d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes


def test_profile_metadata_change_during_write_still_fails_strict_en_readback(ready_job):
    authorize(ready_job)
    class ConcurrentProfileApi(FakeApi):
        def __call__(self,path,method='GET',body=None):
            result=super().__call__(path,method,body)
            if method=='POST':self.source['author']['jobTitle']='Concurrent profile change'
            return result
    api=ConcurrentProfileApi()
    with pytest.raises(d.DraftError,match='EN editorial record'):
        d.export(ready_job,api_fn=api,apply=True)
    assert len(api.writes)==1
    assert t.read_json(ready_job/d.DIRECTORY/d.STATE)['status']=='created_unverified'


def existing_target(api,*,linked=True,published=False):
    payload=d.build_payload({'slug':'example-alternatives','title':'Old Russian','summary':'Old','metaTitle':'Old','metaDescription':'Old'},'<p>Old.</p>',api.source)
    api('/articles/200/localizations','POST',payload);api.calls=[]
    if not linked:api.linked=set()
    if published:api.target['publishedAt']='2026-10-23T10:00:00Z'


def test_existing_linked_draft_updates_only_target_with_explicit_null(ready_job):
    authorize(ready_job);api=FakeApi();existing_target(api)
    before=copy.deepcopy(api.source)
    result=d.export(ready_job,api_fn=api,apply=True)
    assert result['id']==1001 and api.source==before
    assert len(api.writes)==1 and api.writes[0][1]=='PUT'
    assert api.writes[0][2]['data']['publishedAt'] is None


@pytest.mark.parametrize('published,linked',[(True,True),(False,False),(True,False)])
def test_published_or_unrelated_same_slug_ru_is_never_overwritten(ready_job,published,linked):
    authorize(ready_job);api=FakeApi();existing_target(api,linked=linked,published=published)
    before=copy.deepcopy(api.target)
    with pytest.raises(d.DraftError,match='published|unrelated'):d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes and api.target==before


def test_group_with_ru_elsewhere_but_missing_expected_slug_blocks(ready_job):
    authorize(ready_job);api=FakeApi();api.linked.add(1002)
    with pytest.raises(d.DraftError,match='another slug'):d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes


def test_ambiguous_committed_create_is_reconciled_without_duplicate_post(ready_job):
    authorize(ready_job);api=FakeApi();api.timeout_after_create=True
    with pytest.raises(d.DraftError,match='ambiguous'):d.export(ready_job,api_fn=api,apply=True)
    assert len(api.writes)==1 and api.target['id']==1001
    assert t.read_json(ready_job/d.DIRECTORY/d.STATE)['status']=='create_ambiguous'
    result=d.export(ready_job,api_fn=api,apply=True)
    assert result['id']==1001 and len(api.writes)==1


def test_ambiguous_unseen_create_is_not_posted_again(ready_job):
    authorize(ready_job);api=FakeApi();api.timeout_before_create=True
    with pytest.raises(d.DraftError,match='ambiguous'):d.export(ready_job,api_fn=api,apply=True)
    with pytest.raises(d.DraftError,match='never repeat POST'):d.export(ready_job,api_fn=api,apply=True)
    assert len(api.writes)==1
    state=t.read_json(ready_job/d.DIRECTORY/d.STATE)
    assert 'secret=' not in json.dumps(state)


def test_target_id_persisted_before_failed_html_readback(ready_job):
    authorize(ready_job);api=FakeApi();api.corrupt_html=True
    with pytest.raises(d.DraftError,match='HTML readback'):d.export(ready_job,api_fn=api,apply=True)
    assert t.read_json(ready_job/d.DIRECTORY/d.STATE)['target_id']==1001
    assert len(api.writes)==1


def test_changed_original_and_missing_persisted_link_fail_readback(ready_job):
    authorize(ready_job);api=FakeApi();api.change_source=True
    with pytest.raises(d.DraftError,match='EN editorial'):d.export(ready_job,api_fn=api,apply=True)
    assert len(api.writes)==1 and api.writes[0][0]!='/articles/200'


def test_live_source_drift_blocks_before_write(ready_job):
    authorize(ready_job);api=FakeApi();api.source['content']='<p>Changed.</p>'
    with pytest.raises(d.DraftError,match='live EN source'):d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes


def test_create_permission_error_is_recorded_and_never_blindly_reposted(ready_job):
    authorize(ready_job);api=FakeApi()
    def forbidden(path,method='GET',body=None):
        if method=='POST':
            api.calls.append((path,method,body))
            raise urllib.error.HTTPError(path,403,'Forbidden',{},None)
        return api(path,method,body)
    with pytest.raises(d.DraftError,match='failed or outcome'):d.export(ready_job,api_fn=forbidden,apply=True)
    assert t.read_json(ready_job/d.DIRECTORY/d.STATE)['error_type']=='HTTPError'
    with pytest.raises(d.DraftError,match='never repeat POST'):d.export(ready_job,api_fn=forbidden,apply=True)
    assert len(api.writes)==1


def test_persisted_link_disappearance_and_publication_leaks_are_detected(ready_job):
    authorize(ready_job)
    for leak in ('unlink','published_list','public_alternates','malformed_alternates'):
        case=ready_job/d.DIRECTORY/d.STATE
        case.unlink(missing_ok=True)
        api=FakeApi()
        def broken(path,method='GET',body=None):
            response=api(path,method,body)
            if method=='POST' and leak=='unlink':api.linked=set()
            if method=='GET' and leak=='published_list' and path.startswith('/articles?locale=ru'):
                return {'data':[{'id':1001,'slug':'example-alternatives'}]}
            if method=='GET' and '/alternates?' in path:
                if leak=='public_alternates':return {'data':[{'locale':'en','slug':'example-alternatives'},{'locale':'ru','slug':'example-alternatives'}]}
                if leak=='malformed_alternates':return {}
            return response
        with pytest.raises(d.DraftError,match='membership|published-only|public published|unavailable'):
            d.export(ready_job,api_fn=broken,apply=True)


def test_target_published_between_preflight_and_write_is_not_unpublished(ready_job,monkeypatch):
    authorize(ready_job);api=FakeApi();existing_target(api)
    original_validate=d.validate_authorization
    counter=0
    def validate_then_publish(job):
        nonlocal counter
        counter+=1
        result=original_validate(job)
        if counter==2:api.target['publishedAt']='2026-10-23T12:00:00Z'
        return result
    monkeypatch.setattr(d,'validate_authorization',validate_then_publish)
    with pytest.raises(d.DraftError,match='published after preflight'):d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes and api.target['publishedAt'] is not None



def test_existing_ru_cover_is_not_changed_without_cover_authorization(ready_job):
    authorize(ready_job);api=FakeApi();existing_target(api)
    api.target['cover']={'id':999,'url':'https://example.com/manual-cover.png'}
    with pytest.raises(d.DraftError,match='cover change'):d.export(ready_job,api_fn=api,apply=True)
    assert not api.writes and api.target['cover']['id']==999
