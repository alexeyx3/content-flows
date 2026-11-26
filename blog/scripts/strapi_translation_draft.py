"""Dedicated linked RU draft exporter. Dry-run is the default; never publishes.

`authorize` records a human instruction already received in this conversation.
`export --apply` is the only command that writes to CMS, and sends publishedAt:null.
Normal strapi_publish.py remains blocked for translation jobs.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import urllib.error
import urllib.parse
import uuid

if __package__:
    from . import blog_translation as translation
    from .article_materials import digest, read_json, write_json
    from .strapi_publish import api, html_survives_sanitizer, validate_meta
else:
    import blog_translation as translation
    from article_materials import digest, read_json, write_json
    from strapi_publish import api, html_survives_sanitizer, validate_meta

DIRECTORY='out/strapi-translation-draft'
AUTH='authorization.json'
STATE='state.json'


class DraftError(RuntimeError):
    pass


def check(condition, message):
    if not condition:
        raise DraftError(message)


def folder(job):
    return job/DIRECTORY


def sha_json(value):
    return digest(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')))


def normalized(value):
    return translation.record(value)


def relation_ids(value):
    if isinstance(value,dict) and 'data' in value:value=value['data']
    if value is None:return []
    if not isinstance(value,list):value=[value]
    return [int(normalized(v)['id']) for v in value]


def review_binding(job, round_number):
    """Local identity checks complement the existing fresh native readback gate."""
    check(translation.required(job),'article_translation_version:1 is required')
    manifest=read_json(job/'translation.json')
    check(manifest['source_locale']=='en' and manifest['target_locale']=='ru','only EN→RU draft export is supported')
    tracking=read_json(job/'review/translation-review.json')
    doc=read_json(job/f'review/{round_number:02d}-document.json')
    delivery=read_json(job/f'review/{round_number:02d}-translation-delivery.json')
    article_sha=digest((job/'edited.md').read_bytes())
    seal_sha=digest((job/'translation.qa_receipt.json').read_bytes())
    preface=(job/f'review/{round_number:02d}-translation-preface.md').read_text()
    check(tracking['round']==round_number,'authorization must select the current review round')
    check(tracking['article_sha256']==article_sha and tracking['qa_receipt_sha256']==seal_sha,'review tracking is stale')
    check(doc['article_sha256']==article_sha and delivery['article_sha256']==article_sha,'review article hash differs')
    check(delivery.get('status')=='PASS' and delivery['document_id']==doc['document_id'],'native review delivery is not PASS/current document')
    check(delivery['preface_sha256']==digest(preface) and preface==translation.review_preface(job),'review preface is stale')
    check(digest((job/f'review/{round_number:02d}-sent.md').read_bytes())==article_sha,'sent review text differs')
    check(tracking['review_doc_url'].split('/d/',1)[-1].split('/',1)[0]==doc['document_id'],'review document identities differ')
    return {'source_id':int(manifest['source_id']),'source_sha256':manifest['source_sha256'],
        'locale':'ru','slug':manifest['slug'],'review_round':round_number,'document_id':doc['document_id'],
        'article_sha256':article_sha,'html_sha256':digest((job/'out/article.html').read_bytes()),
        'metadata_sha256':digest((job/'translation.meta.json').read_bytes()),'qa_receipt_sha256':seal_sha,
        'package_receipt_sha256':digest((job/'out/translation-package.json').read_bytes()),
        'preface_sha256':digest(preface),'delivery_signature':sha_json({key:delivery.get(key) for key in
            ('status','document_id','article_sha256','preface_sha256','tables')})}


def authorize(job, round_number, by, reference, article_sha256):
    check(bool(by.strip()) and bool(reference.strip()),'human authorization by/reference is required')
    check(not translation.export_errors(job,'review',remote=False),'translation QA/package/seal is not current')
    binding=review_binding(job,round_number)
    check(binding['article_sha256']==article_sha256,'authorization article hash differs from reviewed article')
    result={'version':1,'action':'linked_ru_draft_only','by':by,'reference':reference,
        'authorized_at':translation.stamp(),'binding':binding,'publishedAt':None,
        'cover_policy':'null; source cover has not passed localized visual review',
        'publication_authorized':False,'cms_media_authorized':False}
    write_json(folder(job)/AUTH,result)
    return result


def validate_authorization(job):
    authorization=read_json(folder(job)/AUTH)
    check(authorization.get('action')=='linked_ru_draft_only' and authorization.get('publication_authorized') is False
          and authorization.get('cms_media_authorized') is False and authorization.get('publishedAt','missing') is None,
          'explicit draft-only authorization required')
    check(bool(authorization.get('by')) and bool(authorization.get('reference')),'authorization needs human provenance')
    binding=review_binding(job,authorization['binding']['review_round'])
    check(authorization['binding']==binding,'draft authorization is stale against reviewed article/QA/package')
    return authorization


@contextmanager
def export_lock(job):
    directory=folder(job);directory.mkdir(parents=True,exist_ok=True)
    with (directory/'.export.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def query(api_fn, params):
    response=api_fn('/articles?'+urllib.parse.urlencode(params))
    rows=response.get('data')
    check(isinstance(rows,list),'article query did not return a collection')
    return [normalized(row) for row in rows],response


def group_predicate(api_fn, source_id, *, target_id=None, locale=None):
    params={'locale':'en','filters[id][$eq]':source_id,'fields[0]':'slug','pagination[pageSize]':100}
    if target_id is not None:params['filters[localizations][id][$eq]']=target_id
    if locale is not None:params['filters[localizations][locale][$eq]']=locale
    rows,response=query(api_fn,params)
    check(len(rows)<=1 and all(row.get('id')==source_id for row in rows),'localization predicate returned unexpected source identity')
    return bool(rows),response


def find_target(api_fn, slug):
    try:return normalized(api_fn('/articles/'+urllib.parse.quote(slug,safe='')+'/findBySlug?locale=ru'))
    except urllib.error.HTTPError as exc:
        if exc.code==404:return None
        raise


def source_record(api_fn,source_id):
    return normalized(api_fn('/articles/'+str(source_id)))


def source_render_record(api_fn,source_id,slug):
    rows,response=query(api_fn,{'locale':'en','filters[id][$eq]':source_id,'filters[slug][$eq]':slug})
    check(len(rows)==1 and rows[0]['id']==source_id,'published EN source query identity differs')
    return rows[0],response


def editorial_record(record):
    # Concurrent public view increments are telemetry, not an editorial mutation.
    return {key:value for key,value in record.items() if key not in {'viewCount','localizations'}}


def build_payload(meta, html, source):
    # Strapi4 i18n treats relation fields as localized (isRelationalAttribute).
    # These IDs belong to the new RU row. No user/tag/profile endpoint is written.
    author=relation_ids(source.get('author'))
    check(len(author)<=1,'unexpected source attribution')
    return {'locale':'ru','slug':meta['slug'],'title':meta['title'],
        'summary':meta.get('summary'),'metaTitle':meta.get('metaTitle'),'metaDescription':meta.get('metaDescription'),
        'contentHtml':html,'publishedAt':None,'cover':None,'indexable':False,
        'author':author[0] if author else None,'editors':relation_ids(source.get('editors')),
        'tags':relation_ids(source.get('tags'))}


def preflight(job, api_fn):
    authorization=validate_authorization(job)
    errors=translation.export_errors(job,'review',remote=True)
    check(not errors,'translation review gate: '+'; '.join(errors))
    native=translation.verify_review(job,authorization['binding']['review_round'])
    check(native.get('status')=='PASS','fresh native review readback is not PASS')
    # Fresh readback may change its timestamp, never the authorized contents.
    check(authorization['binding']==review_binding(job,authorization['binding']['review_round']),
          'native review contents changed since authorization')
    binding=authorization['binding'];source_id=binding['source_id'];slug=binding['slug']
    source=source_record(api_fn,source_id)
    check(source.get('id')==source_id and source.get('locale')=='en' and source.get('slug')==slug
          and bool(source.get('publishedAt')),'exact published EN source required')
    check(translation.source_matches_snapshot(job,source),'live EN source differs from immutable snapshot')
    rendered,render_response=source_render_record(api_fn,source_id,slug)
    exists,positive=group_predicate(api_fn,source_id)
    impossible,negative=group_predicate(api_fn,source_id,target_id=-1)
    check(exists and not impossible,'relational-filter readback controls failed')
    ru_exists,group_ru=group_predicate(api_fn,source_id,locale='ru')
    target=find_target(api_fn,slug)
    if target:
        check(target.get('locale')=='ru' and target.get('slug')==slug,'RU target identity differs')
        check(target.get('publishedAt') is None,'existing RU localization is published; refusing to change it')
        check(target.get('cover') in (None,{'data':None}),'existing RU cover is not null; draft-only approval does not authorize a cover change')
        linked,group_exact=group_predicate(api_fn,source_id,target_id=target['id'])
        check(linked and ru_exists,'same-slug RU belongs to an unrelated localization group')
    else:
        group_exact=None
        check(not ru_exists,'source group already contains RU with another slug; identity cannot be safely resolved')
    meta=read_json(job/'translation.meta.json')
    check(not validate_meta({k:v for k,v in meta.items() if v is not None}),'translated metadata fails schema limits')
    html=(job/'out/article.html').read_text()
    check(html_survives_sanitizer(html),'approved HTML changes under Strapi sanitizer')
    payload=build_payload(meta,html,source)
    result={'version':1,'status':'PASS','checked_at':translation.stamp(),'preflight_id':str(uuid.uuid4()),
        'binding':binding,'authorization_sha256':digest((folder(job)/AUTH).read_bytes()),
        'action':'update' if target else 'create','target_id':target.get('id') if target else None,
        'source_before':source,'source_render_before':rendered,'target_before':target,
        'predicate_receipts':{'positive':positive,'negative':negative,'ru_exists':group_ru,'exact_target':group_exact},
        'payload':payload,'payload_sha256':sha_json(payload)}
    write_json(folder(job)/'preflights'/(result['preflight_id']+'.json'),result)
    return result


def target_errors(target,payload):
    errors=[]
    for key in ('locale','slug','title','summary','metaTitle','metaDescription','publishedAt','indexable'):
        if target.get(key)!=payload.get(key):errors.append('RU readback differs: '+key)
    if target.get('content')!=payload['contentHtml']:errors.append('RU supported HTML readback differs')
    if target.get('cover') not in (None,{'data':None}):errors.append('RU cover must remain null')
    for key in ('author','editors','tags'):
        expected=payload[key] if isinstance(payload[key],list) else ([] if payload[key] is None else [payload[key]])
        if relation_ids(target.get(key))!=expected:errors.append('RU attribution/taxonomy differs: '+key)
    return errors


def verify_readback(job,plan,target_id,api_fn):
    target=source_record(api_fn,target_id)
    errors=target_errors(target,plan['payload'])
    if target.get('id')!=target_id:errors.append('RU ID readback returned another record')
    by_slug=find_target(api_fn,plan['binding']['slug'])
    if not by_slug or by_slug.get('id')!=target_id:errors.append('RU locale+slug does not resolve to target ID')
    linked,link_response=group_predicate(api_fn,plan['binding']['source_id'],target_id=target_id)
    if not linked:errors.append('persisted EN→RU localization membership is absent')
    source_after=source_record(api_fn,plan['binding']['source_id'])
    render_after,render_response=source_render_record(api_fn,plan['binding']['source_id'],plan['binding']['slug'])
    if editorial_record(source_after)!=editorial_record(plan['source_before']):errors.append('EN editorial record/relations changed')
    if editorial_record(render_after)!=editorial_record(plan['source_render_before']):errors.append('EN rendered record/relations changed')
    published,published_response=query(api_fn,{'locale':'ru','filters[slug][$eq]':plan['binding']['slug'],'fields[0]':'slug'})
    if published:errors.append('RU unexpectedly appears in the published-only article list')
    alternates=api_fn('/articles/'+urllib.parse.quote(plan['binding']['slug'],safe='')+'/alternates?locale=en')
    alternate_rows=alternates.get('data')
    if not isinstance(alternate_rows,list) or not all(isinstance(row,dict) for row in alternate_rows):
        errors.append('public alternates readback is unavailable')
    else:
        if not any(row.get('locale')=='en' and row.get('slug')==plan['binding']['slug'] for row in alternate_rows):
            errors.append('public alternates omit the published EN source')
        if any(row.get('locale')=='ru' for row in alternate_rows):
            errors.append('RU unexpectedly appears among public published alternates')
    result={'version':1,'status':'BLOCK' if errors else 'PASS','checked_at':translation.stamp(),
        'target_id':target_id,'binding':plan['binding'],'publishedAt':target.get('publishedAt'),
        'target':target,'source_after':source_after,'source_render_after':render_after,
        'persisted_link_predicate':link_response,'published_ru_query':published_response,
        'public_alternates':alternates,'errors':errors,
        'limitations':{'fresh_fact_verification':False,'publication_readiness':'NOT_ASSESSED',
            'cover':'null; source visual review remains open',
            'qa_findings':read_json(job/'translation.qa.json').get('findings',[])}}
    write_json(folder(job)/'readbacks'/(str(uuid.uuid4())+'.json'),result)
    check(not errors,'; '.join(errors))
    return result


def export(job, *, apply=False, api_fn=None):
    api_fn=api_fn or api
    with export_lock(job):
        plan=preflight(job,api_fn)
        state_path=folder(job)/STATE
        state=read_json(state_path) if state_path.exists() else None
        target=plan['target_before']
        if state:
            check(state.get('source_id')==plan['binding']['source_id'] and state.get('locale')=='ru'
                  and state.get('slug')==plan['binding']['slug'],'saved attempt identity differs')
            if state.get('target_id'):
                check(target and target['id']==state['target_id'],'saved target ID no longer resolves to expected RU identity')
            if state.get('status') in {'create_pending','create_ambiguous'}:
                check(target is not None,'ambiguous creation has no visible RU target; never repeat POST automatically')
                check(not target_errors(target,plan['payload']),'ambiguous creation target differs; refusing overwrite or duplicate')
        if not apply:
            return {'status':'PASS','mode':'dry_run','action':plan['action'],'source_id':plan['binding']['source_id'],
                'target_id':plan['target_id'],'locale':'ru','slug':plan['binding']['slug'],'publishedAt':None,
                'payload_sha256':plan['payload_sha256'],'preflight_id':plan['preflight_id'],
                'author':plan['payload']['author'],'editors':plan['payload']['editors'],'cover':None}
        # Recheck the exact authorization and inputs immediately before any write.
        check(validate_authorization(job)['binding']==plan['binding'],'approved artifacts changed during preflight')
        check(editorial_record(source_record(api_fn,plan['binding']['source_id']))==editorial_record(plan['source_before']),
              'EN source changed after preflight')
        if target:
            current_target=source_record(api_fn,target['id'])
            check(current_target.get('publishedAt') is None,'RU target was published after preflight; refusing mutation')
            check(editorial_record(current_target)==editorial_record(target),'RU target changed after preflight')
        else:
            check(find_target(api_fn,plan['binding']['slug']) is None,'RU target appeared after preflight; rerun identity checks')
            has_ru,_=group_predicate(api_fn,plan['binding']['source_id'],locale='ru')
            check(not has_ru,'RU localization appeared after preflight; refusing second creation')
        attempt_id=str(uuid.uuid4())
        state={'version':1,'attempt_id':attempt_id,'source_id':plan['binding']['source_id'],'locale':'ru',
            'slug':plan['binding']['slug'],'target_id':target['id'] if target else None,
            'payload_sha256':plan['payload_sha256'],'binding':plan['binding'],
            'status':'existing_unverified' if target else 'create_pending'}
        write_json(state_path,state)
        if not target or target_errors(target,plan['payload']):
            method='PUT' if target else 'POST'
            route='/articles/'+str(target['id']) if target else '/articles/'+str(plan['binding']['source_id'])+'/localizations'
            body={'data':plan['payload']} if target else plan['payload']
            write_json(folder(job)/'attempts'/(attempt_id+'.json'),{
                'started_at':translation.stamp(),'method':method,'route':route,'body':body,
                'source_before':plan['source_before'],'target_before':target,'binding':plan['binding']})
            try:
                response=api_fn(route,method,body)
                created=normalized(response)
                check(isinstance(created.get('id'),int),'CMS response has no durable target ID')
                state['target_id']=created['id'];state['status']='created_unverified' if not target else 'updated_unverified'
                write_json(state_path,state)  # Persist ID before any subsequent read.
                write_json(folder(job)/'responses'/(attempt_id+'.json'),response)
            except Exception as exc:
                if method=='POST':state['status']='create_ambiguous'
                else:state['status']='update_ambiguous'
                state['error_type']=type(exc).__name__
                write_json(state_path,state)
                raise DraftError('CMS draft request failed or outcome is ambiguous; inspect saved attempt and reconcile before retry') from None
        result=verify_readback(job,plan,state['target_id'],api_fn)
        state.update(status='complete',verified_at=result['checked_at'])
        write_json(state_path,state)
        tracking={'version':1,'id':state['target_id'],'source_id':state['source_id'],'locale':'ru',
            'slug':state['slug'],'published':False,'publishedAt':None,'review_round':plan['binding']['review_round'],
            'binding':plan['binding'],'draft_only':True,'cover':None,'readback_status':'PASS',
            'author':plan['payload']['author'],'editors':plan['payload']['editors'],
            'limitations':result['limitations']}
        write_json(folder(job)/'record.json',tracking)
        return {'status':'PASS','mode':'applied','id':state['target_id'],'source_id':state['source_id'],
            'locale':'ru','slug':state['slug'],'publishedAt':None,'draft_only':True,
            'readback_status':'PASS','author':plan['payload']['author'],'editors':plan['payload']['editors'],'cover':None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('authorize');p.add_argument('--job',required=True);p.add_argument('--round',type=int,required=True)
    p.add_argument('--by',required=True);p.add_argument('--reference',required=True);p.add_argument('--article-sha256',required=True)
    p=commands.add_parser('export');p.add_argument('--job',required=True);p.add_argument('--apply',action='store_true')
    args=parser.parse_args();job=translation.path(args.job)
    try:
        if args.command=='authorize':result=authorize(job,args.round,args.by,args.reference,args.article_sha256)
        else:result=export(job,apply=args.apply)
    except (DraftError,OSError,ValueError,KeyError,TypeError) as exc:
        result={'status':'BLOCK','error':str(exc)}
    except Exception as exc:
        result={'status':'BLOCK','error':'draft export unavailable; no automatic repeat; inspect permissions/receipts',
                'error_type':type(exc).__name__,'http_status':getattr(exc,'code',None)}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('status')=='BLOCK':raise SystemExit(2)


if __name__=='__main__':main()
