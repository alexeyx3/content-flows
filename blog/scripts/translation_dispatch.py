"""Persistent translator: title/preamble, then complete source H2 subtrees.

Parent prepares and loads the plan once; --next is recovery only. No prose is
written by this script. Assembly copies completed translator-owned unit files
only after all source/structure receipts pass, and never overwrites a draft.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re

if __package__:
    from . import blog_translation as translation
    from .article_materials import digest, read_json, write_json, PLACEHOLDERS
    from .md_to_strapi_html import convert
else:
    import blog_translation as translation
    from article_materials import digest, read_json, write_json, PLACEHOLDERS
    from md_to_strapi_html import convert

PLAN='translation.units.json'
ASSEMBLY='out/translation-units-assembly.json'
HEADING=re.compile(r'^(#{1,4})\s+(.+?)\s*$',re.M)
SUPPORT=('translated.meta.json','translation.links.json','translation.visuals.json',
         'translation.issues.md','translation.glossary.json')


def required(job):
    config=job/'job.yaml'
    return config.exists() and bool(re.search(r'^translation_units_version:\s*1\b',config.read_text(),re.M))


def unsealed(job):
    if any((job/name).exists() for name in ('translation.qa_receipt.json','out/translation-package.json',
                                           'review/translation-review.json')):
        raise ValueError('unit preparation/assembly is forbidden for sealed/reviewed jobs')


class H2Offsets(HTMLParser):
    def __init__(self,value):
        super().__init__(convert_charrefs=True)
        self.offsets=[];self.lines=[0]
        for line in value.splitlines(keepends=True):self.lines.append(self.lines[-1]+len(line))
        self.feed(value)
    def handle_starttag(self,tag,attrs):
        if tag=='h2':
            line,column=self.getpos();self.offsets.append(self.lines[line-1]+column)


def build_plan(job):
    if not translation.required(job):raise ValueError('translation job required')
    errors=translation.source_errors(job)
    if errors:raise ValueError('; '.join(errors))
    md=(job/'source/article.md').read_text();html=(job/'source/article.html').read_text()
    h2=list(re.finditer(r'^##\s+(.+?)\s*$',md,re.M));html_h2=H2Offsets(html).offsets
    if len(h2)!=len(html_h2):raise ValueError('source Markdown/HTML H2 boundaries differ')
    boundaries=[0]+[match.start() for match in h2]+[len(md)]
    html_boundaries=[0]+html_h2+[len(html)]
    units=[]
    for number in range(len(boundaries)-1):
        uid='preamble' if number==0 else f'h2-{number:03d}'
        source_md=md[boundaries[number]:boundaries[number+1]]
        source_html=html[html_boundaries[number]:html_boundaries[number+1]]
        headings=[{'level':len(m[1]),'title':m[2]} for m in HEADING.finditer(source_md)]
        if not headings or headings[0]['level']!=(1 if number==0 else 2):
            raise ValueError(uid+': source unit has no expected initial heading')
        if number==0 and [h['level'] for h in headings]!=[1]:
            raise ValueError('preamble must contain the source H1 and material before first H2')
        units.append({'number':number,'unit_id':uid,'requested_unit':uid,
            'source_title':headings[0]['title'],'kind':'title_preamble' if number==0 else 'complete_h2',
            'source_md':f'translation_units/source/{uid}.md','source_html':f'translation_units/source/{uid}.html',
            'path':f'translation_units/ru/{uid}.md','receipt':f'translation_units/ru/{uid}.complete.json',
            'headings':headings,'source_md_sha256':digest(source_md),'source_html_sha256':digest(source_html)})
    manifest=read_json(job/'translation.json')
    return {'version':1,'granularity':'title_preamble_then_complete_h2',
        'source_sha256':manifest['source_sha256'],'source_md_sha256':digest(md),
        'source_html_sha256':digest(html),'units':units},md,html,boundaries,html_boundaries


def prepare(job):
    unsealed(job)
    plan,md,html,bounds,hbounds=build_plan(job)
    if (job/PLAN).exists():
        if read_json(job/PLAN)!=plan:raise ValueError('existing unit plan differs; refusing overwrite')
        return load_plan(job)
    pending=[]
    for index,unit in enumerate(plan['units']):
        for name,value in ((unit['source_md'],md[bounds[index]:bounds[index+1]]),
                           (unit['source_html'],html[hbounds[index]:hbounds[index+1]])):
            p=job/name
            if p.exists() and p.read_text()!=value:raise ValueError('refusing to overwrite '+name)
            pending.append((p,value))
    for p,value in pending:
        p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            with p.open('x') as handle:handle.write(value)
    write_json(job/PLAN,plan)
    return plan


def load_plan(job):
    saved=read_json(job/PLAN);expected,*_=build_plan(job)
    if saved!=expected:raise ValueError('unit plan is stale/altered against immutable source')
    for unit in saved['units']:
        for path,key in (('source_md','source_md_sha256'),('source_html','source_html_sha256')):
            if digest((job/unit[path]).read_bytes())!=unit[key]:raise ValueError('source unit changed: '+unit[path])
    return saved


def select_unit(plan,value):
    matches=[unit for unit in plan['units'] if unit['requested_unit']==value]
    if len(matches)!=1:raise ValueError('unknown requested unit: '+value)
    return matches[0]


def unit_errors(job,unit,*,receipt=True):
    path=job/unit['path']
    if not path.exists() or not path.read_text().strip():return ['missing/empty '+unit['path']]
    text=path.read_text().strip();original=(job/unit['source_md']).read_text()
    actual=list(HEADING.finditer(text));levels=[len(m[1]) for m in actual]
    errors=[]
    if levels!=[h['level'] for h in unit['headings']] or not actual or actual[0].start()!=0:
        errors.append(unit['unit_id']+': incomplete/changed source heading hierarchy')
    if PLACEHOLDERS.search(text):errors.append(unit['unit_id']+': unresolved placeholder')
    for index,match in enumerate(actual):
        following=actual[index+1] if index+1<len(actual) else None
        body=text[match.end():following.start() if following else len(text)]
        source_matches=list(HEADING.finditer(original))
        source_match=source_matches[index] if index<len(source_matches) else None
        source_end=source_matches[index+1].start() if index+1<len(source_matches) else len(original)
        source_body=original[source_match.end():source_end].strip() if source_match else ''
        if source_body and not re.sub(r'<!--.*?-->','',body,flags=re.S).strip():
            errors.append(unit['unit_id']+': empty source-backed subsection')
    _,rendered=convert(text)
    before=translation.inventory((job/unit['source_html']).read_text(),None)
    after=translation.inventory(rendered,None)
    for key in ('heading_levels','table_shapes','lists'):
        if before[key]!=after[key]:errors.append(unit['unit_id']+': changed '+key)
    if [a['source_url'] for a in before['assets']]!=[a['source_url'] for a in after['assets']]:
        errors.append(unit['unit_id']+': omitted/changed body images')
    if translation.number_tokens(original)!=translation.number_tokens(text):
        errors.append(unit['unit_id']+': numeric-token mismatch')
    if unit['kind']=='title_preamble' and (job/'translated.meta.json').exists():
        if not actual or actual[0][2]!=read_json(job/'translated.meta.json').get('title'):
            errors.append('preamble H1 differs from translator metadata title')
    if receipt:
        expected=completion(job,unit)
        try:
            if read_json(job/unit['receipt'])!=expected:errors.append(unit['unit_id']+': stale/incomplete unit receipt')
        except (OSError,ValueError):errors.append(unit['unit_id']+': missing completion receipt')
    return errors


def completion(job,unit):
    return {'version':1,'status':'complete','unit_id':unit['unit_id'],
        'source_md_sha256':unit['source_md_sha256'],'source_html_sha256':unit['source_html_sha256'],
        'output_sha256':digest((job/unit['path']).read_bytes())}


def complete(job,value):
    unsealed(job)
    if not required(job):raise ValueError('translation_units_version:1 explicit opt-in required')
    unit=select_unit(load_plan(job),value)
    errors=unit_errors(job,unit,receipt=False)
    if errors:raise ValueError('; '.join(errors))
    result=completion(job,unit);write_json(job/unit['receipt'],result)
    return result


def check_all(job):
    plan=load_plan(job)
    errors=[error for unit in plan['units'] for error in unit_errors(job,unit)]
    return {'status':'BLOCK' if errors else 'PASS','errors':errors}


def assembly_value(job,plan):
    return '\n\n'.join((job/unit['path']).read_text().strip() for unit in plan['units'])+'\n'


def assemble(job):
    unsealed(job)
    if not required(job):raise ValueError('translation_units_version:1 explicit opt-in required')
    plan=load_plan(job);result=check_all(job)
    if result['errors']:return result
    for name in SUPPORT:
        if not (job/name).exists():raise ValueError('missing translator support output: '+name)
    value=assembly_value(job,plan);path=job/'translated.md'
    if path.exists() and path.read_text()!=value:raise ValueError('translated.md exists and differs; refusing overwrite')
    if not path.exists():
        with path.open('x') as handle:handle.write(value)
    receipt={'version':1,'status':'PASS','plan_sha256':digest((job/PLAN).read_bytes()),
        'translated_sha256':digest(value),'units':[completion(job,u) for u in plan['units']]}
    write_json(job/ASSEMBLY,receipt)
    return receipt


def assembly_errors(job):
    if not required(job):return []
    try:
        plan=load_plan(job);errors=check_all(job)['errors']
        receipt=read_json(job/ASSEMBLY)
        expected={'version':1,'status':'PASS','plan_sha256':digest((job/PLAN).read_bytes()),
            'translated_sha256':digest(assembly_value(job,plan)),'units':[completion(job,u) for u in plan['units']]}
        if receipt!=expected or digest((job/'translated.md').read_bytes())!=expected['translated_sha256']:
            errors.append('translation unit assembly is missing/stale')
        return errors
    except (OSError,ValueError,KeyError,TypeError) as exc:return ['translation unit assembly unavailable: '+str(exc)]


def fingerprint_paths(job):
    if not required(job):return []
    plan=load_plan(job)
    return [PLAN,ASSEMBLY,'translated.md','translated.meta.json']+[name for u in plan['units'] for name in (u['path'],u['receipt'])]


def sync_metrics_plan(job):
    if not required(job):raise ValueError('translation_units_version:1 explicit opt-in required')
    unsealed(job)
    if __package__:from . import codex_metrics as metrics
    else:import codex_metrics as metrics
    with metrics.manifest_lock(job):
        manifest=metrics.load_manifest(job)
        if manifest.get('finished_at') is not None:raise ValueError('cannot change a finished metrics run')
        required_stages=manifest.setdefault('required_stages',metrics.planned_stages(job,manifest.get('scope','full')))
        if 'translation-assemble' not in required_stages:required_stages.append('translation-assemble')
        metrics.save_manifest(job,manifest)
    return {'status':'PASS','required_stages':required_stages}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',required=True)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--check',action='store_true')
    mode.add_argument('--complete');mode.add_argument('--assemble',action='store_true')
    mode.add_argument('--next',action='store_true');mode.add_argument('--sync-metrics-plan',action='store_true')
    args=p.parse_args();job=translation.path(args.job)
    try:
        if args.prepare:result=prepare(job)
        elif args.check:result=check_all(job)
        elif args.complete:result=complete(job,args.complete)
        elif args.assemble:result=assemble(job)
        elif args.sync_metrics_plan:result=sync_metrics_plan(job)
        elif args.next:result=next((u for u in load_plan(job)['units'] if unit_errors(job,u)),None)
        else:result=load_plan(job)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if isinstance(result,dict) and result.get('status')=='BLOCK':raise SystemExit(2)
    except (OSError,ValueError,KeyError,TypeError) as exc:raise SystemExit(str(exc)) from exc


if __name__=='__main__':main()
