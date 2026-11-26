"""Publish an explicitly authorized, existing linked RU translation.

Dry-run is the default. The only CMS mutation is a PUT of publishedAt/indexable
on the exact tracked RU record. Covers are rendered, checked and attached first
by the separately authorized cover workflow; this tool never uploads media.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
from pathlib import Path
import urllib.parse
import uuid

if __package__:
    from . import blog_translation as translation
    from . import strapi_translation_draft as draft
    from .article_materials import digest, read_json, write_json
    from .strapi_publish import api, html_survives_sanitizer, validate_meta
else:
    import blog_translation as translation
    import strapi_translation_draft as draft
    from article_materials import digest, read_json, write_json
    from strapi_publish import api, html_survives_sanitizer, validate_meta

DIRECTORY='out/strapi-translation-publication'
AUTH='authorization.json'
STATE='state.json'


class PublicationError(RuntimeError):
    pass


def check(condition, message):
    if not condition:
        raise PublicationError(message)


def folder(job):
    return job/DIRECTORY


def local_path(job, relative):
    check(isinstance(relative,str) and bool(relative),'local receipt path is required')
    check(not Path(relative).is_absolute(),'local receipt path must be job-relative')
    path=(job/relative).resolve()
    check(path.is_relative_to(job.resolve()),'local receipt path escapes job')
    return path


def media_record(value):
    if isinstance(value,dict) and 'data' in value:
        value=value['data']
    check(isinstance(value,dict),'a checked RU cover must be attached before publication')
    value=draft.normalized(value)
    check(type(value.get('id')) is int and value['id']>0 and isinstance(value.get('url'),str)
          and bool(value['url']),'attached cover needs an exact media ID and URL')
    return value


def relation_ids(value):
    """Do not coerce malformed string/bool IDs while validating attribution."""
    if isinstance(value,dict) and 'data' in value:value=value['data']
    if value is None:return []
    rows=value if isinstance(value,list) else [value]
    result=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('relation lacks integer ID')
        identity=draft.normalized(row).get('id')
        if type(identity) is not int or identity<=0:raise ValueError('relation lacks positive integer ID')
        result.append(identity)
    if len(result)!=len(set(result)):raise ValueError('duplicate relation IDs')
    return result


def inputs_binding(job, round_number, target_id):
    check(type(target_id) is int and target_id>0,'exact existing RU target ID required')
    check(not translation.export_errors(job,'review',remote=False),'translation QA/package/seal is not current')
    binding=draft.review_binding(job,round_number)
    tracked=read_json(job/draft.DIRECTORY/'record.json')
    check(tracked.get('id')==target_id and tracked.get('locale')=='ru'
          and tracked.get('slug')==binding['slug'] and tracked.get('source_id')==binding['source_id']
          and tracked.get('readback_status')=='PASS','tracked linked RU draft identity differs')
    check(tracked.get('binding')==binding,'tracked draft differs from the reviewed version')
    request=read_json(job/'publication/request.json')
    check(type(request.get('version')) is int and request.get('version')==1 and request.get('action')=='publish_linked_ru'
          and request.get('target_id')==target_id and request.get('locale')=='ru'
          and request.get('slug')==binding['slug'],'publication request identity/action differs')
    check(bool(request.get('by')) and bool(request.get('reference')),'actual publisher instruction is required')
    readiness=read_json(job/'publication/readiness.json')
    check(type(readiness.get('version')) is int and readiness.get('version')==1 and readiness.get('status')=='PASS'
          and readiness.get('source_policy_status')=='PASS'
          and readiness.get('unresolved_source_policy')==[],
          'independent publication readiness/source-policy gate is not PASS')
    for key in ('article_sha256','metadata_sha256','qa_receipt_sha256'):
        check(readiness.get(key)==binding[key],'publication readiness is stale: '+key)
    check(type(readiness.get('fresh_fact_verification')) is bool,
          'publication readiness must explicitly describe fresh fact verification')
    cover=read_json(job/'publication/cover.json')
    check(type(cover.get('version')) is int and cover.get('version')==1 and cover.get('status')=='PASS'
          and cover.get('target_id')==target_id and cover.get('locale')=='ru'
          and cover.get('slug')==binding['slug'],'checked cover identity/status differs')
    png=local_path(job,cover.get('png_path'))
    png_bytes=png.read_bytes()
    check(png_bytes.startswith(b'\x89PNG\r\n\x1a\n') and digest(png_bytes)==cover.get('png_sha256'),
          'rendered cover PNG is missing or changed')
    plan=read_json(job/'publication/cover-plan.json')
    meta=read_json(job/'translation.meta.json')
    check(type(plan.get('version')) is int and plan.get('version')==1
          and plan.get('target_id')==target_id and plan.get('locale')=='ru'
          and plan.get('slug')==binding['slug'] and plan.get('title')==meta.get('title')
          and plan.get('png_path')==cover['png_path'] and plan.get('png_sha256')==cover['png_sha256'],
          'localized cover plan identity/title/PNG differs')
    mobile=local_path(job,plan.get('mobile_path'));mobile_bytes=mobile.read_bytes()
    check(mobile_bytes.startswith(b'\x89PNG\r\n\x1a\n') and len(mobile_bytes)>=24
          and mobile_bytes[12:16]==b'IHDR' and int.from_bytes(mobile_bytes[16:20],'big')==390
          and digest(mobile_bytes)==plan.get('mobile_sha256'),
          '390px cover preview is missing or changed')
    for key in ('mobile_path','mobile_sha256'):
        if key in cover:check(cover[key]==plan[key],'cover receipt differs from preview plan: '+key)
    visual_path=local_path(job,cover.get('visual_qa_receipt_path'))
    check(digest(visual_path.read_bytes())==cover.get('visual_qa_receipt_sha256'),
          'cover visual QA receipt changed')
    visual=read_json(visual_path)
    check(cover.get('visual_qa_status')=='PASS' and type(visual.get('version')) is int
          and visual.get('version')==1 and visual.get('status')=='PASS'
          and visual.get('png_sha256')==cover['png_sha256']
          and visual.get('mobile_sha256')==plan['mobile_sha256']
          and all(visual.get(key) is True for key in ('viewed_full','viewed_mobile','title_exact')),
          'independent full/mobile cover visual QA is missing or stale')
    check(type(cover.get('media_id')) is int and cover['media_id']>0
          and isinstance(cover.get('media_url'),str) and bool(cover['media_url']),
          'checked cover lacks actual CMS media ID/URL')
    return {**binding,'target_id':target_id,
        'request_sha256':digest((job/'publication/request.json').read_bytes()),
        'readiness_sha256':digest((job/'publication/readiness.json').read_bytes()),
        'cover_receipt_sha256':digest((job/'publication/cover.json').read_bytes()),
        'cover_png_sha256':cover['png_sha256'],'cover_mobile_sha256':plan['mobile_sha256'],
        'cover_plan_sha256':digest((job/'publication/cover-plan.json').read_bytes()),'cover_id':cover['media_id'],
        'cover_url':cover['media_url'],'visual_qa_receipt_sha256':cover['visual_qa_receipt_sha256']}


def authorize(job, round_number, target_id, by, reference, article_sha256):
    check(bool(by.strip()) and bool(reference.strip()),'actual publisher by/reference required')
    binding=inputs_binding(job,round_number,target_id)
    request=read_json(job/'publication/request.json')
    check(request['by']==by and request['reference']==reference,'authorization differs from actual publication request')
    check(binding['article_sha256']==article_sha256,'authorization article hash differs')
    result={'version':1,'action':'publish_existing_linked_ru','authorized_at':translation.stamp(),
        'by':by,'reference':reference,'binding':binding,'publication_authorized':True,
        'cms_mutation_fields':['publishedAt','indexable'],'create_authorized':False,'media_upload':False}
    write_json(folder(job)/AUTH,result)
    return result


def validate_authorization(job):
    authorization=read_json(folder(job)/AUTH)
    check(type(authorization.get('version')) is int and authorization.get('version')==1 and authorization.get('action')=='publish_existing_linked_ru'
          and authorization.get('publication_authorized') is True
          and authorization.get('cms_mutation_fields')==['publishedAt','indexable']
          and authorization.get('create_authorized') is False and authorization.get('media_upload') is False,
          'explicit existing-RU publication authorization required')
    check(bool(authorization.get('by')) and bool(authorization.get('reference')),'actual publisher provenance required')
    old=authorization['binding']
    check(old==inputs_binding(job,old['review_round'],old['target_id']),
          'publication authorization is stale against review/readiness/cover')
    request=read_json(job/'publication/request.json')
    check(request['by']==authorization['by'] and request['reference']==authorization['reference'],
          'publication authorization provenance differs')
    return authorization


@contextmanager
def publication_lock(job):
    folder(job).mkdir(parents=True,exist_ok=True)
    with (folder(job)/'.publication.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(handle,fcntl.LOCK_UN)


def approved_target_errors(job,target,source,binding):
    meta=read_json(job/'translation.meta.json')
    errors=[]
    if target.get('id')!=binding['target_id'] or target.get('locale')!='ru' or target.get('slug')!=binding['slug']:
        errors.append('exact existing RU target identity differs')
    for key in ('title','slug','summary','metaTitle','metaDescription'):
        if target.get(key)!=meta.get(key):errors.append('approved RU metadata differs: '+key)
    if target.get('content')!=(job/'out/article.html').read_text():errors.append('approved RU HTML differs')
    for key in ('author','editors','tags'):
        try:
            if relation_ids(target.get(key))!=relation_ids(source.get(key)):
                errors.append('RU attribution/taxonomy differs: '+key)
        except (KeyError,TypeError,ValueError):errors.append('malformed RU attribution/taxonomy: '+key)
    try:
        cover=media_record(target.get('cover'))
        if cover['id']!=binding['cover_id'] or cover['url']!=binding['cover_url']:
            errors.append('attached RU cover differs from checked media')
    except PublicationError as exc:errors.append(str(exc))
    return errors


def preflight(job,api_fn):
    authorization=validate_authorization(job);binding=authorization['binding']
    errors=translation.export_errors(job,'review',remote=True)
    check(not errors,'translation review gate: '+'; '.join(errors))
    check(translation.verify_review(job,binding['review_round']).get('status')=='PASS',
          'fresh native review readback is not PASS')
    check(binding==inputs_binding(job,binding['review_round'],binding['target_id']),
          'review/readiness/cover changed during preflight')
    source=draft.source_record(api_fn,binding['source_id'])
    check(source.get('id')==binding['source_id'] and source.get('locale')=='en'
          and source.get('slug')==binding['slug'] and bool(source.get('publishedAt')),
          'exact published EN source required')
    check(translation.source_matches_snapshot(job,source),'live EN source differs from immutable snapshot')
    rendered,_=draft.source_render_record(api_fn,binding['source_id'],binding['slug'])
    positive,_=draft.group_predicate(api_fn,binding['source_id'])
    negative,_=draft.group_predicate(api_fn,binding['source_id'],target_id=-1)
    linked,link_response=draft.group_predicate(api_fn,binding['source_id'],target_id=binding['target_id'])
    check(positive and not negative and linked,'persisted EN→RU membership/control failed')
    target=draft.source_record(api_fn,binding['target_id'])
    by_slug=draft.find_target(api_fn,binding['slug'])
    check(by_slug and by_slug.get('id')==binding['target_id'],'RU locale+slug does not resolve to authorized ID')
    check(not approved_target_errors(job,target,source,binding),
          '; '.join(approved_target_errors(job,target,source,binding)))
    meta=read_json(job/'translation.meta.json')
    check(not validate_meta({k:v for k,v in meta.items() if v is not None}),'translated metadata invalid')
    check(html_survives_sanitizer((job/'out/article.html').read_text()),'approved HTML changes under sanitizer')
    if target.get('publishedAt'):
        check(target.get('indexable') is True,'already published RU is not indexable; refusing hidden changes')
    else:
        check(target.get('publishedAt') is None and target.get('indexable') is False,
              'draft publication/indexability differs from tracked draft')
    result={'version':1,'status':'PASS','checked_at':translation.stamp(),'preflight_id':str(uuid.uuid4()),
        'binding':binding,'source_before':source,'source_render_before':rendered,'target_before':target,
        'persisted_link_predicate':link_response,'action':'already_published' if target.get('publishedAt') else 'publish',
        'authorization_sha256':digest((folder(job)/AUTH).read_bytes())}
    write_json(folder(job)/'preflights'/(result['preflight_id']+'.json'),result)
    return result


def same_instant(left,right):
    try:
        before=datetime.fromisoformat(left.replace('Z','+00:00'))
        after=datetime.fromisoformat(right.replace('Z','+00:00'))
        return (before.utcoffset() is not None and after.utcoffset() is not None and before==after)
    except (AttributeError,TypeError,ValueError):return False


def verify_readback(job,plan,published_at,api_fn):
    b=plan['binding'];target=draft.source_record(api_fn,b['target_id'])
    errors=approved_target_errors(job,target,plan['source_before'],b)
    if not target.get('publishedAt') or not same_instant(target.get('publishedAt'),published_at):
        errors.append('RU publication timestamp differs from intended/preserved date')
    if target.get('indexable') is not True:errors.append('published RU is not indexable')
    before=draft.editorial_record(plan['target_before'])
    after=draft.editorial_record(target)
    # Strapi's article lifecycle derives these aliases during the publication PUT.
    # Ignore an alias only after proving the actual returned value is expected;
    # arbitrary/missing/malformed publication dates remain readback failures.
    for key,expected in (('datePublished',published_at),('dateModified',target.get('updatedAt'))):
        if key not in before and key not in after:
            continue  # Older API shapes have no lifecycle aliases.
        if key not in after or not same_instant(after.get(key),expected):
            errors.append('RU lifecycle-derived '+key+' differs from expected timestamp')
        else:
            before.pop(key,None);after.pop(key,None)
    for key in ('publishedAt','indexable','updatedAt'):before.pop(key,None);after.pop(key,None)
    if before!=after:errors.append('RU fields outside publication/indexability changed')
    source=draft.source_record(api_fn,b['source_id'])
    if draft.editorial_record(source)!=draft.editorial_record(plan['source_before']):errors.append('EN editorial record changed')
    rendered,_=draft.source_render_record(api_fn,b['source_id'],b['slug'])
    if draft.editorial_record(rendered)!=draft.editorial_record(plan['source_render_before']):errors.append('EN rendered record changed')
    linked,link_response=draft.group_predicate(api_fn,b['source_id'],target_id=b['target_id'])
    if not linked:errors.append('published RU lost localization membership')
    by_slug=draft.find_target(api_fn,b['slug'])
    if not by_slug or by_slug.get('id')!=b['target_id']:errors.append('published locale+slug differs')
    rows,query_response=draft.query(api_fn,{'locale':'ru','filters[slug][$eq]':b['slug'],'fields[0]':'slug'})
    if len(rows)!=1 or rows[0].get('id')!=b['target_id']:errors.append('RU published-only list differs')
    alternates=api_fn('/articles/'+urllib.parse.quote(b['slug'],safe='')+'/alternates?locale=en')
    variants=alternates.get('data')
    if not isinstance(variants,list) or not all(isinstance(v,dict) for v in variants):
        errors.append('public alternates unavailable')
    elif not all(any(v.get('locale')==locale and v.get('slug')==b['slug'] for v in variants) for locale in ('en','ru')):
        errors.append('public alternates omit published EN/RU')
    result={'version':1,'status':'BLOCK' if errors else 'PASS','checked_at':translation.stamp(),
        'binding':b,'publishedAt':target.get('publishedAt'),'indexable':target.get('indexable'),
        'target':target,'source_after':source,'source_render_after':rendered,'link_response':link_response,
        'published_ru_query':query_response,'public_alternates':alternates,'errors':errors,
        'fresh_fact_verification':read_json(job/'publication/readiness.json')['fresh_fact_verification']}
    write_json(folder(job)/'readbacks'/(str(uuid.uuid4())+'.json'),result)
    check(not errors,'; '.join(errors))
    return result


def publish(job, *, apply=False, api_fn=None):
    api_fn=api_fn or api
    with publication_lock(job):
        plan=preflight(job,api_fn);binding=plan['binding']
        state_path=folder(job)/STATE
        state=read_json(state_path) if state_path.exists() else None
        if state:
            check(state.get('target_id')==binding['target_id'] and state.get('binding')==binding,
                  'previous publication attempt identity/binding differs')
            if state.get('status') in {'publish_pending','publish_ambiguous'}:
                check(bool(plan['target_before'].get('publishedAt')),
                      'ambiguous publication is still unconfirmed; never blindly repeat PUT')
        if not apply:
            return {'status':'PASS','mode':'dry_run','action':plan['action'],'target_id':binding['target_id'],
                'source_id':binding['source_id'],'slug':binding['slug'],'locale':'ru','cover_id':binding['cover_id'],
                'preflight_id':plan['preflight_id'],'mutation_fields':['publishedAt','indexable']}
        check(validate_authorization(job)['binding']==binding,'publication inputs changed after preflight')
        check(draft.editorial_record(draft.source_record(api_fn,binding['source_id']))==draft.editorial_record(plan['source_before']),
              'EN source changed after preflight')
        current=draft.source_record(api_fn,binding['target_id'])
        check(draft.editorial_record(current)==draft.editorial_record(plan['target_before']),
              'RU target changed after preflight')
        linked,_=draft.group_predicate(api_fn,binding['source_id'],target_id=binding['target_id'])
        check(linked,'RU localization membership changed after preflight')
        attempt=str(uuid.uuid4());published_at=current.get('publishedAt') or translation.stamp()
        state={'version':1,'attempt_id':attempt,'target_id':binding['target_id'],'source_id':binding['source_id'],
            'binding':binding,'publishedAt':published_at,'status':'publish_pending' if not current.get('publishedAt') else 'published_unverified'}
        # Backups and a durable attempt precede any PUT; no CREATE or media mutation.
        write_json(folder(job)/'backups'/(attempt+'.json'),{'source':plan['source_before'],
            'source_render':plan['source_render_before'],'target':current,'binding':binding})
        write_json(state_path,state)
        if not current.get('publishedAt'):
            route='/articles/'+str(binding['target_id']);body={'data':{'publishedAt':published_at,'indexable':True}}
            write_json(folder(job)/'attempts'/(attempt+'.json'),{'started_at':translation.stamp(),
                'method':'PUT','route':route,'body':body,'binding':binding})
            try:
                response=api_fn(route,'PUT',body)
                returned=draft.normalized(response)
                check(returned.get('id')==binding['target_id'],'publication response returned another target ID')
                write_json(folder(job)/'responses'/(attempt+'.json'),response)
                state['status']='published_unverified';write_json(state_path,state)
            except Exception as exc:
                state.update(status='publish_ambiguous',error_type=type(exc).__name__)
                write_json(state_path,state)
                raise PublicationError('publication outcome may be ambiguous; inspect saved attempt/target before retry') from None
        receipt=verify_readback(job,plan,published_at,api_fn)
        state.update(status='complete',verified_at=receipt['checked_at']);write_json(state_path,state)
        tracking={'version':1,'id':binding['target_id'],'source_id':binding['source_id'],'locale':'ru',
            'slug':binding['slug'],'published':True,'publishedAt':receipt['publishedAt'],'indexable':True,
            'cover_id':binding['cover_id'],'cover':{'id':binding['cover_id'],'url':binding['cover_url']},
            'binding':binding,'readback_status':'PASS'}
        write_json(folder(job)/'record.json',tracking)
        write_json(job/'publication/record.json',tracking)
        return {'status':'PASS','mode':'applied','action':plan['action'],'id':binding['target_id'],
            'source_id':binding['source_id'],'locale':'ru','slug':binding['slug'],
            'publishedAt':receipt['publishedAt'],'indexable':True,'cover_id':binding['cover_id'],'readback_status':'PASS'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    auth=commands.add_parser('authorize')
    for name in ('job','by','reference','article-sha256'):auth.add_argument('--'+name,required=True)
    auth.add_argument('--round',type=int,required=True);auth.add_argument('--target-id',type=int,required=True)
    export=commands.add_parser('publish');export.add_argument('--job',required=True);export.add_argument('--apply',action='store_true')
    args=parser.parse_args();job=translation.path(args.job)
    try:
        result=authorize(job,args.round,args.target_id,args.by,args.reference,args.article_sha256) if args.command=='authorize' else publish(job,apply=args.apply)
    except (PublicationError,draft.DraftError,OSError,ValueError,KeyError,TypeError) as exc:
        result={'status':'BLOCK','error':str(exc)}
    except Exception as exc:
        result={'status':'BLOCK','error':'publication unavailable; inspect saved receipts, no blind retry',
            'error_type':type(exc).__name__,'http_status':getattr(exc,'code',None)}
    import json
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('status')=='BLOCK':raise SystemExit(2)


if __name__=='__main__':main()
