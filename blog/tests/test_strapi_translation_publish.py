"""Publication is an existing-ID two-field change after exact review and cover checks."""
import base64
import copy
import struct
import zlib
import sys
import urllib.parse
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import blog_translation as t
import strapi_translation_draft as d
import strapi_translation_publish as p
from test_strapi_translation_draft import ready_job,put,source

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6SMAAAAASUVORK5CYII=')


def mobile_png(width=390,height=260):
    def chunk(kind,data):
        return struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',width,height,8,2,0,0,0))
            +chunk(b'IDAT',zlib.compress((b'\x00'+b'\xff'*(width*3))*height))+chunk(b'IEND',b''))


@pytest.fixture
def publication_job(ready_job):
    job=ready_job;binding=d.review_binding(job,2)
    put(job,d.DIRECTORY+'/record.json',{'id':1001,'source_id':200,'locale':'ru',
        'slug':'example-alternatives','readback_status':'PASS','binding':binding})
    put(job,'publication/request.json',{'version':1,'action':'publish_linked_ru','by':'Publisher',
        'reference':'publish-approval','target_id':1001,'locale':'ru','slug':'example-alternatives'})
    put(job,'publication/readiness.json',{'version':1,'status':'PASS','source_policy_status':'PASS',
        'unresolved_source_policy':[],'fresh_fact_verification':False,
        **{k:binding[k] for k in ('article_sha256','metadata_sha256','qa_receipt_sha256')}})
    (job/'publication/cover.png').write_bytes(PNG)
    mobile=mobile_png();(job/'publication/cover-mobile.png').write_bytes(mobile)
    put(job,'publication/cover-plan.json',{'version':1,'target_id':1001,'locale':'ru',
        'slug':'example-alternatives','title':'Пример 2026','png_path':'publication/cover.png',
        'png_sha256':t.digest(PNG),'mobile_path':'publication/cover-mobile.png','mobile_sha256':t.digest(mobile)})
    put(job,'publication/cover-visual-qa.json',{'version':1,'status':'PASS','png_sha256':t.digest(PNG),
        'mobile_sha256':t.digest(mobile),'viewed_full':True,'viewed_mobile':True,'title_exact':True,'findings':[]})
    put(job,'publication/cover.json',{'version':1,'status':'PASS','target_id':1001,'locale':'ru',
        'slug':'example-alternatives','png_path':'publication/cover.png','png_sha256':t.digest(PNG),
        'media_id':8,'media_url':'https://media.example/cover.png','visual_qa_status':'PASS',
        'visual_qa_receipt_path':'publication/cover-visual-qa.json',
        'visual_qa_receipt_sha256':t.digest((job/'publication/cover-visual-qa.json').read_bytes())})
    return job


class FakeApi:
    def __init__(self,job):
        self.source=source();meta=t.read_json(job/'translation.meta.json')
        self.target={**meta,'id':1001,'content':(job/'out/article.html').read_text(),
            'publishedAt':None,'indexable':False,'cover':{'id':8,'url':'https://media.example/cover.png'},
            'author':{'id':5},'editors':[{'id':4}],'tags':[{'id':2}],
            'createdAt':'2026-10-30T00:00:00Z','updatedAt':'2026-11-05T00:00:00Z'}
        self.linked=True;self.calls=[];self.timeout_before=False;self.timeout_after=False
        self.corrupt=False;self.mutate_en=False;self.public_list=True;self.alternate=True
    @property
    def writes(self):return [c for c in self.calls if c[1]!='GET']
    def __call__(self,path,method='GET',body=None):
        self.calls.append((path,method,copy.deepcopy(body)))
        parsed=urllib.parse.urlparse(path);q=urllib.parse.parse_qs(parsed.query)
        if method!='GET':
            assert method=='PUT' and path=='/articles/1001'
            assert set(body)=={'data'} and set(body['data'])=={'publishedAt','indexable'}
            assert body['data']['publishedAt'] and body['data']['indexable'] is True
            if self.timeout_before:raise TimeoutError('secret=must_not_leak')
            self.target.update(copy.deepcopy(body['data']));self.target['updatedAt']='2026-11-05T10:00:00Z'
            if self.corrupt:self.target['content']='<p>Unexpected body change</p>'
            if self.mutate_en:self.source['title']='Changed EN'
            if self.timeout_after:
                self.timeout_after=False;raise TimeoutError('secret=must_not_leak')
            return {'data':copy.deepcopy(self.target)}
        if parsed.path=='/articles/200':return {'data':copy.deepcopy(self.source)}
        if parsed.path=='/articles/1001':return {'data':copy.deepcopy(self.target)}
        if parsed.path.endswith('/findBySlug'):return {'data':copy.deepcopy(self.target)}
        if parsed.path.endswith('/alternates'):
            rows=[{'locale':'en','slug':self.source['slug']}]
            if self.target['publishedAt'] and self.alternate:rows.append({'locale':'ru','slug':self.target['slug']})
            return {'data':rows}
        if parsed.path=='/articles':
            if q.get('locale')==['ru']:
                return {'data':[copy.deepcopy(self.target)] if self.target['publishedAt'] and self.public_list else []}
            target=q.get('filters[localizations][id][$eq]')
            include=target is None or (self.linked and target==['1001'])
            return {'data':[copy.deepcopy(self.source)] if include else []}
        raise AssertionError((path,method))


def authorize(job):
    return p.authorize(job,2,1001,'Publisher','publish-approval',t.digest((job/'edited.md').read_bytes()))


def test_no_publication_without_current_explicit_auth_and_dry_run_never_writes(publication_job):
    job=publication_job;api=FakeApi(job)
    with pytest.raises(FileNotFoundError):p.publish(job,apply=True,api_fn=api)
    assert not api.calls
    authorize(job)
    result=p.publish(job,api_fn=api)
    assert result['mode']=='dry_run' and result['target_id']==1001 and result['action']=='publish'
    assert not api.writes and api.target['publishedAt'] is None


def test_only_existing_ru_publication_fields_change_and_backups_precede_write(publication_job):
    job=publication_job;authorize(job);api=FakeApi(job);before=copy.deepcopy(api.source)
    def guarded(path,method='GET',body=None):
        if method=='PUT':
            state=t.read_json(job/p.DIRECTORY/p.STATE)
            assert state['status']=='publish_pending' and state['target_id']==1001
            assert list((job/p.DIRECTORY/'backups').glob('*.json'))
            assert list((job/p.DIRECTORY/'attempts').glob('*.json'))
        return api(path,method,body)
    result=p.publish(job,apply=True,api_fn=guarded)
    assert result['readback_status']=='PASS' and result['publishedAt'] and len(api.writes)==1
    assert api.source==before
    tracking=t.read_json(job/'publication/record.json')
    assert tracking['cover']=={'id':8,'url':'https://media.example/cover.png'}
    assert tracking['published'] is True and tracking['source_id']==200 and tracking['locale']=='ru'
    assert t.read_json(job/d.DIRECTORY/'record.json')['readback_status']=='PASS'


@pytest.mark.parametrize('file,key,value',[
    ('publication/readiness.json','status','BLOCK'),
    ('publication/readiness.json','source_policy_status','BLOCK'),
    ('publication/readiness.json','unresolved_source_policy',['P-01']),
    ('publication/readiness.json','article_sha256','stale'),
    ('publication/readiness.json','metadata_sha256','stale'),
    ('publication/readiness.json','qa_receipt_sha256','stale'),
    ('publication/cover.json','target_id',200),('publication/cover.json','locale','en'),
    ('publication/cover.json','media_id',None),('publication/cover.json','visual_qa_status','BLOCK'),
    ('publication/cover.json','png_path','../outside.png'),
    ('publication/request.json','reference','not the current instruction'),
])
def test_unready_or_stale_material_cannot_authorize(publication_job,file,key,value):
    data=t.read_json(publication_job/file);data[key]=value;put(publication_job,file,data)
    with pytest.raises((p.PublicationError,OSError)):authorize(publication_job)


def test_changed_png_or_visual_receipt_invalidates_existing_auth(publication_job):
    job=publication_job;authorize(job);api=FakeApi(job)
    (job/'publication/cover.png').write_bytes(PNG+b'changed')
    with pytest.raises(p.PublicationError,match='PNG'):p.publish(job,apply=True,api_fn=api)
    assert not api.calls
    (job/'publication/cover.png').write_bytes(PNG)
    put(job,'publication/cover-visual-qa.json',{'status':'BLOCK','png_sha256':t.digest(PNG)})
    with pytest.raises(p.PublicationError,match='visual QA'):p.publish(job,apply=True,api_fn=api)


@pytest.mark.parametrize('field,value',[
    ('id',200),('locale','en'),('slug','other'),('title','Changed title'),
    ('content','<p>Unapproved body</p>'),('author',{'id':77}),
    ('author',{'id':'5'}),('editors',[{'id':True}]),('tags',[{'id':'2'}]),
    ('editors',[{'id':77}]),('tags',[{'id':77}]),('cover',None),
    ('cover',{'id':9,'url':'https://media.example/cover.png'}),
    ('cover',{'id':8,'url':'https://media.example/other.png'}),
])
def test_wrong_locale_content_attribution_or_cover_never_publishes(publication_job,field,value):
    job=publication_job;authorize(job);api=FakeApi(job);api.target[field]=value
    with pytest.raises(p.PublicationError):p.publish(job,apply=True,api_fn=api)
    assert not api.writes


def test_unlinked_or_changed_en_source_never_publishes(publication_job):
    job=publication_job;authorize(job)
    for which in ('link','content'):
        api=FakeApi(job)
        if which=='link':api.linked=False
        else:api.source['content']='<p>Changed EN</p>'
        with pytest.raises(p.PublicationError):p.publish(job,apply=True,api_fn=api)
        assert not api.writes


def test_fresh_concurrency_change_stops_before_put(publication_job,monkeypatch):
    job=publication_job;authorize(job);api=FakeApi(job)
    original=p.validate_authorization;counter=0
    def race(job):
        nonlocal counter
        counter+=1;result=original(job)
        if counter==2:api.target['title']='Concurrent edit'
        return result
    monkeypatch.setattr(p,'validate_authorization',race)
    with pytest.raises(p.PublicationError,match='changed after preflight'):
        p.publish(job,apply=True,api_fn=api)
    assert not api.writes


def test_ambiguous_committed_put_reconciles_without_second_write_or_new_date(publication_job):
    job=publication_job;authorize(job);api=FakeApi(job);api.timeout_after=True
    with pytest.raises(p.PublicationError,match='ambiguous'):p.publish(job,apply=True,api_fn=api)
    date=api.target['publishedAt'];assert len(api.writes)==1
    result=p.publish(job,apply=True,api_fn=api)
    assert result['publishedAt']==date and len(api.writes)==1
    assert 'secret=' not in str(t.read_json(job/p.DIRECTORY/p.STATE))


def test_unconfirmed_ambiguous_put_is_never_blindly_repeated(publication_job):
    job=publication_job;authorize(job);api=FakeApi(job);api.timeout_before=True
    with pytest.raises(p.PublicationError,match='ambiguous'):p.publish(job,apply=True,api_fn=api)
    with pytest.raises(p.PublicationError,match='never blindly repeat'):
        p.publish(job,apply=True,api_fn=api)
    assert len(api.writes)==1


@pytest.mark.parametrize('which',['body','en','published_list','alternates'])
def test_postwrite_corruption_or_publication_leaks_are_detected(publication_job,which):
    job=publication_job;authorize(job);api=FakeApi(job)
    if which=='body':api.corrupt=True
    if which=='en':api.mutate_en=True
    if which=='published_list':api.public_list=False
    if which=='alternates':api.alternate=False
    with pytest.raises(p.PublicationError):p.publish(job,apply=True,api_fn=api)
    assert len(api.writes)==1 and t.read_json(job/p.DIRECTORY/p.STATE)['status']=='published_unverified'


def test_existing_matching_publication_is_verified_without_republishing(publication_job):
    job=publication_job;authorize(job);api=FakeApi(job)
    api.target.update(publishedAt='2026-11-05T05:00:00.000Z',indexable=True)
    result=p.publish(job,apply=True,api_fn=api)
    assert result['action']=='already_published' and result['publishedAt']=='2026-11-05T05:00:00.000Z'
    assert not api.writes


@pytest.mark.parametrize('key,value',[('viewed_full',False),('viewed_mobile',False),
    ('title_exact',False),('viewed_full','true'),('version',True),('mobile_sha256','stale')])
def test_visual_qa_requires_actual_full_and_mobile_inspection(publication_job,key,value):
    job=publication_job;data=t.read_json(job/'publication/cover-visual-qa.json');data[key]=value
    put(job,'publication/cover-visual-qa.json',data)
    cover=t.read_json(job/'publication/cover.json')
    cover['visual_qa_receipt_sha256']=t.digest((job/'publication/cover-visual-qa.json').read_bytes())
    put(job,'publication/cover.json',cover)
    with pytest.raises(p.PublicationError,match='full/mobile'):authorize(job)


@pytest.mark.parametrize('which',['bytes','width','plan_title','plan_hash'])
def test_mobile_preview_and_plan_are_part_of_publication_binding(publication_job,which):
    job=publication_job;authorize(job);api=FakeApi(job)
    plan=t.read_json(job/'publication/cover-plan.json')
    if which=='bytes':(job/'publication/cover-mobile.png').write_bytes(mobile_png()+b'changed')
    if which=='width':
        wrong=mobile_png(width=389);(job/'publication/cover-mobile.png').write_bytes(wrong)
        plan['mobile_sha256']=t.digest(wrong)
    if which=='plan_title':plan['title']='Wrong title'
    if which=='plan_hash':plan['png_sha256']='wrong'
    put(job,'publication/cover-plan.json',plan)
    with pytest.raises(p.PublicationError):p.publish(job,apply=True,api_fn=api)
    assert not api.calls


@pytest.mark.parametrize('receipt',['publication/readiness.json','publication/request.json','publication/cover.json'])
def test_boolean_schema_version_cannot_authorize_publication(publication_job,receipt):
    data=t.read_json(publication_job/receipt);data['version']=True;put(publication_job,receipt,data)
    with pytest.raises(p.PublicationError):authorize(publication_job)


class LifecycleApi(FakeApi):
    """Production article lifecycle aliases observed in saved live readbacks."""
    def __init__(self,job):
        super().__init__(job)
        self.target['datePublished']=None
        self.target['dateModified']=self.target['updatedAt']
        self.alias_override={}
    def __call__(self,path,method='GET',body=None):
        result=super().__call__(path,method,body)
        if method=='PUT':
            self.target['datePublished']=self.target['publishedAt']
            self.target['dateModified']=self.target['updatedAt']
            self.target.update(self.alias_override)
            return {'data':copy.deepcopy(self.target)}
        return result


def test_realistic_automatic_date_aliases_are_validated_then_allowed(publication_job):
    job=publication_job;authorize(job);api=LifecycleApi(job)
    result=p.publish(job,apply=True,api_fn=api)
    assert result['readback_status']=='PASS' and len(api.writes)==1
    assert p.same_instant(api.target['datePublished'],result['publishedAt'])
    assert p.same_instant(api.target['dateModified'],api.target['updatedAt'])
    date=api.target['publishedAt']
    again=p.publish(job,apply=True,api_fn=api)
    assert again['publishedAt']==date and len(api.writes)==1


@pytest.mark.parametrize('key,value',[
    ('datePublished','2026-01-01T00:00:00Z'),('datePublished',None),
    ('datePublished','malformed'),('datePublished','2026-11-05'),
    ('dateModified','2026-01-01T00:00:00Z'),('dateModified',None),
    ('dateModified','malformed'),('dateModified','2026-11-05T10:00:00'),
])
def test_wrong_or_malformed_derived_dates_still_block(publication_job,key,value):
    job=publication_job;authorize(job);api=LifecycleApi(job);api.alias_override[key]=value
    with pytest.raises(p.PublicationError,match='lifecycle-derived '+key):
        p.publish(job,apply=True,api_fn=api)
    assert len(api.writes)==1
    assert t.read_json(job/p.DIRECTORY/p.STATE)['status']=='published_unverified'


def test_lifecycle_alias_allowance_does_not_ignore_other_changes(publication_job):
    job=publication_job;authorize(job);api=LifecycleApi(job)
    api.alias_override['summary']='Unapproved summary change'
    with pytest.raises(p.PublicationError,match='metadata differs'):
        p.publish(job,apply=True,api_fn=api)
    assert len(api.writes)==1


@pytest.mark.parametrize('key',['datePublished','dateModified'])
def test_previously_present_alias_cannot_disappear_during_write(publication_job,key):
    job=publication_job;authorize(job);api=LifecycleApi(job)
    def missing_alias(path,method='GET',body=None):
        result=api(path,method,body)
        if method=='PUT':api.target.pop(key)
        return result
    with pytest.raises(p.PublicationError,match='lifecycle-derived '+key):
        p.publish(job,apply=True,api_fn=missing_alias)
    assert len(api.writes)==1


def test_already_published_wrong_alias_is_not_rewritten_to_fix_it(publication_job):
    job=publication_job;authorize(job);api=LifecycleApi(job)
    api.target.update(publishedAt='2026-11-05T05:00:00.000Z',indexable=True,
        datePublished='2026-11-04T05:00:00.000Z')
    with pytest.raises(p.PublicationError,match='lifecycle-derived datePublished'):
        p.publish(job,apply=True,api_fn=api)
    assert not api.writes and api.target['publishedAt']=='2026-11-05T05:00:00.000Z'


def test_timestamp_equivalence_requires_timezone_aware_real_instants():
    assert p.same_instant('2026-01-15T10:00:00.000Z','2026-01-15T10:00:00Z')
    assert not p.same_instant('2026-01-15T10:00:00','2026-01-15T10:00:00')
    assert not p.same_instant('malformed','malformed')
