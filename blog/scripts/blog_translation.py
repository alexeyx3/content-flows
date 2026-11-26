"""Read-only source snapshots and fail-closed review packages for translations.

No command mutates Strapi. Existing snapshots are never overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse

if __package__:
    from .article_materials import digest, read_json, write_json, PLACEHOLDERS
    from .strapi_publish import api, validate_meta
    from .md_to_strapi_html import convert
    from .translation_text_artifacts import errors as text_artifact_errors
else:
    from article_materials import digest, read_json, write_json, PLACEHOLDERS
    from strapi_publish import api, validate_meta
    from md_to_strapi_html import convert
    from translation_text_artifacts import errors as text_artifact_errors

ROOT = Path(__file__).resolve().parents[1]
META = ('title', 'slug', 'summary', 'metaTitle', 'metaDescription')
INPUTS = ('source/cms-record.json', 'source/article.html', 'source/article.md',
          'source/metadata.json', 'source/inventory.json', 'translation.json',
          'edited.md', 'translation.meta.json', 'translation.links.json',
          'translation.visuals.json', 'translation.issues.md', 'translation.glossary.json',
          'translation.editor.md', 'translation.qa.md')


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def required(job: Path) -> bool:
    p = job / 'job.yaml'
    return p.exists() and bool(re.search(r'^article_translation_version:\s*1\b', p.read_text(), re.M))


def style_review_required(job: Path) -> bool:
    """Explicit opt-in keeps previously sealed translation rounds compatible."""
    config = job / 'job.yaml'
    return config.exists() and bool(re.search(
        r'^translation_style_review_version:\s*1\b', config.read_text(), re.M))


def path(value: str) -> Path:
    p = (ROOT / value).resolve()
    if not p.is_relative_to(ROOT / 'jobs'):
        raise ValueError('translation job must be inside jobs/')
    return p


def record(data: dict) -> dict:
    data = data.get('data', data)
    return {'id': data.get('id'), **data.get('attributes', data)}


def source_hash(data: dict) -> str:
    """Content-bearing fields and relation identity; updatedAt alone is insufficient."""
    r = record(data)
    fields = ('id', 'locale', 'content', 'contentHtml', *META, 'publishedAt',
              'cover', 'author', 'editors', 'tags', 'indexable')
    return digest(json.dumps({k: r.get(k) for k in fields}, sort_keys=True, ensure_ascii=False))


def profile_relation_ids(value, *, many: bool) -> list[int]:
    """Profile identity is a positive integer ID; populated bios are not article input."""
    if isinstance(value, dict) and 'data' in value:
        value=value['data']
    if value is None:
        return []
    rows=value if many else [value]
    if not isinstance(rows,list):
        raise ValueError('profile relation must be a list')
    ids=[]
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError('profile relation lacks an integer ID')
        identity=row.get('id')
        if type(identity) is not int or identity<=0:
            raise ValueError('profile relation lacks a positive integer ID')
        ids.append(identity)
    if len(ids)!=len(set(ids)):
        raise ValueError('profile relation contains duplicate IDs')
    return ids


def source_projection(data: dict) -> dict:
    """Compare all legacy source fields, projecting only author/editor profiles to IDs.

    Keep source_hash unchanged: existing immutable snapshots and QA seals bind its
    legacy full-record digest. This projection is solely a live compatibility proof.
    """
    r=record(data)
    fields=('id','locale','content','contentHtml',*META,'publishedAt',
            'cover','author','editors','tags','indexable')
    result={key:r.get(key) for key in fields}
    for key,many in (('author',False),('editors',True)):
        if key not in r:
            raise ValueError('source lacks '+key+' relation')
        result[key]=profile_relation_ids(r[key],many=many)
    return result


def projection_hash(value: dict) -> str:
    return digest(json.dumps(value,sort_keys=True,ensure_ascii=False))


def source_matches_snapshot(job: Path, data: dict) -> bool:
    """Only populated author/editor attributes may differ; relation IDs/order may not."""
    try:
        return source_projection(read_json(job/'source/cms-record.json'))==source_projection(data)
    except (ValueError,TypeError,KeyError,AttributeError):
        return False


def drift_receipt_valid(job: Path, receipt: dict) -> bool:
    """Validate an explicit live profile-drift proof or an unchanged legacy receipt."""
    manifest=read_json(job/'translation.json')
    if (receipt.get('status')!='PASS' or receipt.get('source_sha256')!=manifest['source_sha256']
            or receipt.get('errors')):
        return False
    if 'source_comparison' not in receipt:
        return receipt.get('current_source_sha256')==manifest['source_sha256']
    proof=receipt['source_comparison']
    try:
        if (not isinstance(proof,dict) or type(proof.get('version')) is not int
                or proof['version']!=1 or proof.get('policy')!='author_editor_ids_v1'):
            return False
        current=proof['current_source_record']
        snapshot=read_json(job/'source/cms-record.json')
        before=source_projection(snapshot);after=source_projection(current)
        return (source_hash(snapshot)==manifest['source_sha256']
            and source_hash(current)==receipt.get('current_source_sha256')
            and before==after
            and proof.get('snapshot_projection_sha256')==projection_hash(before)
            and proof.get('current_projection_sha256')==projection_hash(after))
    except (ValueError,TypeError,KeyError,AttributeError):
        return False


def fetch(slug: str) -> dict:
    return api('/articles/' + urllib.parse.quote(slug, safe='') + '/findBySlug?locale=en&populate=*')


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []


class Tree(HTMLParser):
    def __init__(self, value: str):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'br', 'hr', 'img', 'input', 'meta', 'link'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def nodes(root, tag=None):
    for child in root.children:
        if isinstance(child, Node):
            if tag is None or child.tag == tag:
                yield child
            yield from nodes(child, tag)


def markdown(node) -> str:
    if isinstance(node, str):
        return node.replace('\xa0', ' ')
    children = ''.join(markdown(c) for c in node.children)
    tag = node.tag
    if re.fullmatch('h[1-6]', tag):
        return '\n\n' + '#' * int(tag[1]) + ' ' + children.strip() + '\n\n'
    if tag in {'p', 'div', 'section', 'article', 'figure'}:
        return '\n\n' + children.strip() + '\n\n'
    if tag in {'b', 'strong', 'em', 'i'}:
        marker='**' if tag in {'b','strong'} else '*'
        leading=' ' if children[:1].isspace() else ''
        trailing=' ' if children[-1:].isspace() else ''
        return leading + marker + children.strip() + marker + trailing
    if tag == 'br':
        return '\n'
    if tag == 'a':
        return '[' + children.strip() + '](' + node.attrs.get('href', '') + ')'
    if tag == 'img':
        return '\n\n![' + node.attrs.get('alt', '') + '](' + node.attrs.get('src', '') + ')\n\n'
    if tag in {'ul', 'ol'}:
        rows=[]
        for i, c in enumerate((c for c in node.children if isinstance(c, Node) and c.tag=='li'), 1):
            rows.append((f'{i}. ' if tag=='ol' else '- ') + markdown(c).strip())
        return '\n\n' + '\n'.join(rows) + '\n\n'
    if tag == 'table':
        rows=[]
        for tr in nodes(node, 'tr'):
            cells=[markdown(c).strip().replace('\n', ' ').replace('|', '\\|') for c in tr.children if isinstance(c, Node) and c.tag in {'td','th'}]
            rows.append('| ' + ' | '.join(cells) + ' |')
        if rows:
            rows.insert(1, '| ' + ' | '.join(['---']*len([c for c in next(nodes(node,'tr')).children if isinstance(c,Node) and c.tag in {'td','th'}])) + ' |')
        return '\n\n' + '\n'.join(rows) + '\n\n'
    if tag == 'blockquote':
        return '\n\n' + '\n'.join('> '+s for s in children.strip().splitlines()) + '\n\n'
    return children


def inventory(content: str, cover) -> dict:
    tree=Tree(content).root
    images=[{'id': f'body-{i}', 'kind': 'body', 'source_url': n.attrs.get('src',''), 'alt': n.attrs.get('alt','')} for i,n in enumerate(nodes(tree,'img'),1)]
    c=record(cover) if isinstance(cover,dict) and cover.get('data') else cover
    if isinstance(c,dict) and c.get('url'):
        images.append({'id':'cover','kind':'cover','source_url':c['url'],'alt':c.get('alternativeText'), 'name': c.get('name')})
    return {'assets':images, 'links':[n.attrs.get('href','') for n in nodes(tree,'a')],
            'heading_levels':[n.tag for n in nodes(tree) if re.fullmatch('h[1-6]',n.tag)],
            'table_shapes':[[len([c for c in row.children if isinstance(c,Node) and c.tag in {'td','th'}]) for row in nodes(t,'tr')] for t in nodes(tree,'table')],
            'lists':[{'kind':n.tag,'items':len([c for c in n.children if isinstance(c,Node) and c.tag=='li'])} for n in nodes(tree) if n.tag in {'ol','ul'}]}



def source_shape_errors(content: str) -> list[str]:
    """Version 1 fails closed on semantic HTML shapes it cannot round-trip."""
    errors=[]
    root=Tree(content).root
    allowed={'p','div','section','article','figure','figcaption','h2','h3','h4',
             'b','strong','em','i','br','a','img','ul','ol','li','table','thead',
             'tbody','tfoot','tr','td','th','blockquote','span'}
    for node in nodes(root):
        if node.tag not in allowed:
            errors.append('unsupported source HTML element: '+node.tag)
        if node.tag in {'td','th'} and any(k in node.attrs for k in ('rowspan','colspan','headers','scope')):
            errors.append('unsupported source table spanning/header semantics')
        if node.tag=='ol' and any(k in node.attrs for k in ('start','reversed','type')):
            errors.append('unsupported source ordered-list numbering attributes')
        if node.tag=='li' and 'value' in node.attrs:
            errors.append('unsupported source list-item value')
        if node.tag in {'ul','ol'} and any(n.tag in {'ul','ol'} for n in nodes(node)):
            errors.append('unsupported source nested list')
    return sorted(set(errors))


def text_tokens(root: Node) -> list[str]:
    def flatten(node):
        if isinstance(node,str):return node
        return ''.join(flatten(child) for child in node.children)
    return re.findall(r'[^\s]',flatten(root),re.UNICODE)


def conversion_errors(content: str, source_markdown: str) -> list[str]:
    _, converted=convert(source_markdown)
    errors=source_shape_errors(content)
    if text_tokens(Tree(content).root) != text_tokens(Tree(converted).root):
        errors.append('source HTML→Markdown conversion changed text; unsupported source conversion')
    source_inventory=inventory(content,None)
    converted_inventory=inventory(converted,None)
    for key in ('heading_levels','table_shapes','lists','links'):
        if source_inventory[key]!=converted_inventory[key]:
            errors.append('source HTML→Markdown conversion changed '+key)
    if [a['source_url'] for a in source_inventory['assets']] != [a['source_url'] for a in converted_inventory['assets']]:
        errors.append('source HTML→Markdown conversion changed body image sequence')
    return errors

def bootstrap(job: Path, slug: str, locale: str, data=None):
    if locale != 'ru' or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug):
        raise ValueError('version 1 supports EN→RU and a valid existing slug')
    if job.exists() and any(job.iterdir()):
        raise ValueError('refusing to overwrite existing translation job')
    data = fetch(slug) if data is None else data
    r=record(data)
    content=r.get('content') or r.get('contentHtml')
    if r.get('locale') != 'en' or r.get('slug') != slug or not r.get('publishedAt') or not content or not r.get('id'):
        raise ValueError('source must be exact current published EN record')
    body = re.sub(r'\n{3,}', '\n\n', markdown(Tree(content).root)).strip()
    source_markdown='# '+r['title']+'\n\n'+body+'\n'
    if errors := conversion_errors(content,source_markdown):
        raise ValueError('; '.join(errors))
    job.mkdir(parents=True,exist_ok=True)
    (job/'source').mkdir()
    write_json(job/'source/cms-record.json',data)
    (job/'source/article.html').write_text(content)
    (job/'source/article.md').write_text(source_markdown)
    write_json(job/'source/metadata.json',{key:r.get(key) for key in META})
    write_json(job/'source/inventory.json',inventory(content,r.get('cover')))
    source_files={str(p.relative_to(job)):digest(p.read_bytes()) for p in sorted((job/'source').iterdir())}
    write_json(job/'translation.json',{'version':1,'source_locale':'en','target_locale':locale,
       'slug':slug,'source_id':r['id'],'source_url':f'https://example.com/blog/{slug}/',
       'source_updatedAt':r.get('updatedAt'),'captured_at':stamp(), 'source_sha256':source_hash(data),
       'source_files':source_files,'scope':'translation_only','fresh_fact_verification':False,
       'placement_provenance':'Inherited unchanged from published source; no new ranking decision',
       'cms_authorized':False,'review_only':True,'metadata_policy':'derived_from_source',
       'text_artifact_check_version':1})
    (job/'job.yaml').write_text('workflow_version: 2\narticle_translation_version: 1\ntranslation_style_review_version: 1\n'+
        'topic: '+json.dumps(r['title'],ensure_ascii=False)+'\nlanguage: ru\nlocale: ru\nsource_locale: en\n'+
        'slug: '+slug+'\nstatus: translation_in_progress\n')
    (job/'progress.md').write_text('# Translation job\n\n'+
        'User selected one old published article, starting with Fabrikam Alternatives.\n'+
        'All prose/edition/QA through isolated specialists. Translator gpt-6-luna medium; editor/QA gpt-6-sol medium.\n'+
        'Immutable live Strapi source captured; no CMS changes authorized. Endpoint: QA-sealed review-only package and Google Doc.\n'+
        'No fresh factual verification or new ranking approval. Published source placement preserved with provenance.\n')
    return {'job':str(job),'source_id':r['id'],'source_sha256':source_hash(data)}


def fingerprint(job: Path) -> dict:
    names=list(INPUTS)
    config=(job/'job.yaml').read_text()
    if re.search(r'^translation_units_version:\s*1\b',config,re.M):
        if __package__:from .translation_dispatch import fingerprint_paths
        else:from translation_dispatch import fingerprint_paths
        names+=fingerprint_paths(job)
    return {name:digest((job/name).read_bytes()) for name in names}


def source_errors(job: Path) -> list[str]:
    manifest=read_json(job/'translation.json')
    errors=conversion_errors((job/'source/article.html').read_text(),(job/'source/article.md').read_text())
    for name,sha in manifest['source_files'].items():
        if digest((job/name).read_bytes()) != sha:
            errors.append('immutable source changed: '+name)
    if source_hash(read_json(job/'source/cms-record.json')) != manifest['source_sha256']:
        errors.append('source snapshot identity/content changed')
    return errors


def drift(job: Path, data=None) -> dict:
    manifest=read_json(job/'translation.json')
    data=fetch(manifest['slug']) if data is None else data
    current_hash=source_hash(data)
    errors=source_errors(job)
    if not source_matches_snapshot(job,data):
        errors.append('live source content or metadata/relations changed since snapshot')
    result={'status':'BLOCK' if errors else 'PASS','checked_at':stamp(),
        'source_sha256':manifest['source_sha256'],'current_source_sha256':current_hash,'errors':errors}
    if not errors:
        result['source_comparison']={'version':1,'policy':'author_editor_ids_v1',
            'snapshot_projection_sha256':projection_hash(source_projection(read_json(job/'source/cms-record.json'))),
            'current_projection_sha256':projection_hash(source_projection(data)),
            'current_source_record':data}
    write_json(job/'out/translation-source-drift.json',result)
    return result



def number_tokens(value: str) -> Counter:
    # Counts are a diagnostic fidelity gate, never a substitute for bilingual QA.
    # Strip list ordinals: publication converters can renumber list markup.
    value = re.sub(r'^\s*\d+\.\s+', '', value, flags=re.M)
    value = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', value)
    return Counter(re.findall(r'(?<![\w])\d+(?:[.,]\d+)*(?:[+%])?(?![\w])', value))


def check(job: Path) -> dict:
    errors = source_errors(job)
    manifest=read_json(job/'translation.json')
    source_meta=read_json(job/'source/metadata.json')
    meta=read_json(job/'translation.meta.json')
    article=(job/'edited.md').read_text()
    original=(job/'source/article.md').read_text()
    source=read_json(job/'source/inventory.json')
    # Opt-in lives in the fingerprinted manifest, not an unbound runtime flag.
    # Inspect raw final Markdown before conversion can consume tool markup.
    artifact_version=manifest.get('text_artifact_check_version')
    if 'text_artifact_check_version' in manifest:
        if type(artifact_version) is not int or artifact_version != 1:
            errors.append('unsupported translation text_artifact_check_version')
        else:
            visible_meta=('title','summary','metaTitle','metaDescription')
            final_fields={'edited.md':article, **{
                'translation.meta.json.'+key:str(meta.get(key) or '') for key in visible_meta}}
            source_fields={'edited.md':original, **{
                'translation.meta.json.'+key:str(source_meta.get(key) or '') for key in visible_meta}}
            errors+=text_artifact_errors(final_fields,source_fields)
    title, rendered=convert(article)
    current=inventory(rendered, None)
    errors += validate_meta({k:v for k,v in meta.items() if v is not None})
    if meta.get('slug') != manifest['slug'] or meta.get('locale') != 'ru':
        errors.append('translation metadata must preserve slug and set locale ru')
    if not title or title != meta.get('title') or len(re.findall(r'^# ',article,re.M)) != 1 or not article.startswith('# '):
        errors.append('exactly one initial H1 must match translated title')
    for key in ('summary','metaTitle','metaDescription'):
        if manifest.get('metadata_policy') == 'derived_from_source' and not str(meta.get(key) or '').strip():
            errors.append('derived metadata is required: '+key)
        if manifest.get('metadata_policy','preserve_null') == 'preserve_null' and source_meta.get(key) in (None,'') and meta.get(key) not in (None,''):
            errors.append('source-null metadata must remain null: '+key)
    if PLACEHOLDERS.search(article):
        errors.append('article contains unresolved placeholder')
    if current['heading_levels'] != source['heading_levels']:
        errors.append('heading hierarchy differs from immutable source')
    if current['table_shapes'] != source['table_shapes']:
        errors.append('table dimensions differ from immutable source')
    if current['lists'] != source['lists']:
        errors.append('list structure/item counts differ from immutable source')
    expected_images=[a['source_url'] for a in source['assets'] if a['kind']=='body']
    if [a['source_url'] for a in current['assets']] != expected_images:
        errors.append('body images omitted, reordered or changed without supported localization')
    before_numbers,after_numbers=number_tokens(original),number_tokens(article)
    if before_numbers != after_numbers:
        errors.append('numeric-token mismatch; compare missing/added counters')
    assets=read_json(job/'translation.visuals.json').get('assets')
    if not isinstance(assets,list) or [a.get('id') for a in assets] != [a['id'] for a in source['assets']]:
        errors.append('visual inventory differs from source (including cover)')
    else:
        for original_asset,asset in zip(source['assets'],assets):
            if asset.get('source_url') != original_asset['source_url'] or asset.get('kind') != original_asset['kind']:
                errors.append('visual provenance differs: '+original_asset['id'])
            if not isinstance(asset.get('text_inventory'),str) or not asset.get('rationale'):
                errors.append('visual needs explicit text inventory and rationale: '+original_asset['id'])
            if asset.get('status') not in {'reuse_review_only','translated_checked','needs_translation'}:
                errors.append('invalid visual readiness status: '+original_asset['id'])
            if asset.get('kind')=='body' and asset.get('status')=='needs_translation':
                errors.append('body visual still requires translation: '+original_asset['id'])
            if asset.get('status')=='translated_checked':
                errors.append('translated visual assets require a dedicated supported rendering/QA branch')
    links=read_json(job/'translation.links.json').get('links')
    if not isinstance(links,list) or Counter(row.get('source') for row in links) != Counter(source['links']):
        errors.append('link provenance must account for every source anchor')
    else:
        allowed={r['url']:r.get('lang') for r in read_json(ROOT/'config/site-urls.json')['urls']}
        targets=[]
        for row in links:
            target=row.get('target')
            origin=row.get('source','')
            if not row.get('reason'):
                errors.append('link decision needs reason')
            if target:
                targets.append(target)
                parsed=urllib.parse.urlparse(target)
                internal=parsed.hostname in {'example.com','www.example.com'} or not parsed.hostname
                if internal and allowed.get(target) != 'ru':
                    errors.append('internal target is not verified Russian URL: '+target)
                if not internal and target != origin:
                    errors.append('external source link changed')
            elif row.get('reason') not in {'no_verified_ru_target','source_policy_conflict'}:
                errors.append('removed link needs explicit policy/no-language decision')
        if Counter(current['links']) != Counter(targets):
            errors.append('article links do not match provenance decisions')
    if re.search(r'^translation_units_version:\s*1\b',(job/'job.yaml').read_text(),re.M):
        if __package__:from .translation_dispatch import assembly_errors
        else:from translation_dispatch import assembly_errors
        errors+=assembly_errors(job)
    # Every named role output must exist before independent QA and sealing.
    for name in INPUTS:
        if name == 'translation.qa.md':
            continue
        if not (job/name).is_file() or not (job/name).read_text().strip():
            errors.append('missing translation artifact: '+name)
    return {'status':'BLOCK' if errors else 'PASS','errors':errors,
            'numbers_missing':dict(before_numbers-after_numbers),
            'numbers_added':dict(after_numbers-before_numbers),
            'fresh_fact_verification':False,'publication_status':'NOT_ASSESSED'}


def qa_errors(job: Path) -> list[str]:
    qa=read_json(job/'translation.qa.json')
    errors=[]
    if qa.get('fidelity_status') != 'PASS' or qa.get('review_status') != 'PASS':
        errors.append('independent translation fidelity/review QA is not PASS')
    if qa.get('publication_status') != 'NOT_ASSESSED' or qa.get('fresh_fact_verification') is not False:
        errors.append('translation QA must not claim publication approval or fresh fact verification')
    if qa.get('hashes') != fingerprint(job):
        errors.append('independent translation QA hashes are stale')
    style_required=style_review_required(job)
    if style_required:
        for status in ('natural_ru_status','style_status'):
            if qa.get(status) != 'PASS':
                errors.append('independent translation '+status+' is not PASS')
    findings=qa.get('findings')
    if not isinstance(findings,list):
        errors.append('QA findings must be an explicit array')
    else:
        for finding in findings:
            if not all(finding.get(key) for key in ('id','kind','severity','explanation','resolution')):
                errors.append('QA finding missing required fields')
            if finding.get('kind')=='translation_error' and finding.get('resolution') != 'fixed':
                errors.append('unresolved translation error: '+str(finding.get('id')))
            if style_required and finding.get('kind')=='language_style' and finding.get('resolution') != 'fixed':
                errors.append('unresolved native-RU/style defect: '+str(finding.get('id')))
    return errors


def package(job: Path) -> dict:
    result=check(job)
    errors=result['errors']+qa_errors(job)
    receipt=read_json(job/'out/translation-source-drift.json')
    if not drift_receipt_valid(job,receipt):
        errors.append('current source drift check required')
    if errors:
        return {'status':'BLOCK','errors':errors}
    (job/'out').mkdir(exist_ok=True)
    article=(job/'edited.md').read_text()
    _,rendered=convert(article)
    (job/'out/article.md').write_text(article)
    (job/'out/article.html').write_text(rendered)
    meta=read_json(job/'translation.meta.json')
    (job/'out/meta.md').write_text('\n'.join(k+': '+str(meta[k]) for k in META if meta.get(k) is not None)+'\n')
    report={'version':1,'status':'PASS','review_only':True,'fresh_fact_verification':False,
        'hashes':fingerprint(job),'package_hashes':package_hashes(job),'qa_sha256':digest((job/'translation.qa.json').read_bytes())}
    write_json(job/'out/translation-package.json',report)
    return report


def package_hashes(job: Path) -> dict:
    return {name:digest((job/name).read_bytes()) for name in ('out/article.md','out/article.html','out/meta.md')}


def seal(job: Path) -> dict:
    errors=check(job)['errors']+qa_errors(job)
    package_report=read_json(job/'out/translation-package.json')
    if package_report.get('hashes')!=fingerprint(job) or package_report.get('package_hashes')!=package_hashes(job) or package_report.get('status')!='PASS' or package_report.get('qa_sha256')!=digest((job/'translation.qa.json').read_bytes()):
        errors.append('translation package is stale')
    if errors:
        return {'status':'BLOCK','errors':errors}
    result={'version':1,'status':'PASS','sealed_at':stamp(),'review_only':True,
            'hashes':fingerprint(job),'package_hashes':package_hashes(job),
            'qa_sha256':digest((job/'translation.qa.json').read_bytes())}
    write_json(job/'translation.qa_receipt.json',result)
    return result


def export_errors(job: Path, target: str, remote=True) -> list[str]:
    if target != 'review':
        return ['translation CMS export unsupported; dedicated linked-localization implementation and current authorization required']
    try:
        errors=check(job)['errors']+qa_errors(job)
        receipt=read_json(job/'translation.qa_receipt.json')
        package_report=read_json(job/'out/translation-package.json')
        expected=fingerprint(job)
        packaged=package_hashes(job)
        qa_hash=digest((job/'translation.qa.json').read_bytes())
        if receipt.get('status')!='PASS' or receipt.get('hashes')!=expected or receipt.get('package_hashes')!=packaged or receipt.get('qa_sha256')!=qa_hash:
            errors.append('missing or stale translation QA seal')
        if package_report.get('status')!='PASS' or package_report.get('hashes')!=expected or package_report.get('package_hashes')!=packaged or package_report.get('qa_sha256')!=qa_hash:
            errors.append('missing or stale translation package')
        if remote:
            errors += drift(job)['errors']
        return errors
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return ['translation review gate unavailable: '+str(exc)]
    except Exception:
        # Never print API request/auth errors that could contain credentials.
        return ['translation live source verification unavailable; no export performed']


def review_preface(job: Path) -> str:
    manifest=read_json(job/'translation.json')
    qa=read_json(job/'translation.qa.json')
    assets=read_json(job/'translation.visuals.json')['assets']
    lines=['## Перевод EN → RU — редакционная вычитка','',
        'Это перевод опубликованного исходника. Проверены полнота и точность перевода; свежая фактическая проверка и готовность к публикации не оценивались.',
        '', '[Английский оригинал]('+manifest['source_url']+')',
        'Снимок: '+manifest['captured_at']+'; SHA-256: '+manifest['source_sha256'],
        'Метаданные: '+manifest.get('metadata_policy','preserve_null')+'; новые RU поля при пустом оригинале составлены по содержанию исходника.',
        '', 'Порядок платформ и место Example Co унаследованы из опубликованного оригинала. Это не новое согласование рейтинга.','',
        '### Замечания для согласования','']
    for finding in qa['findings']:
        lines.append('- '+str(finding['id'])+' ['+finding['kind']+']: '+finding['explanation']+' Решение: '+finding['resolution'])
    if not qa['findings']:
        lines.append('Дополнительных замечаний переводческого QA нет. Исторические утверждения отдельно не перепроверялись.')
    lines+=['','### Изображения','']
    if not assets:
        lines.append('В исходнике нет обложки или изображений в теле.')
    for asset in assets:
        lines.append('- '+asset['id']+': '+asset['status']+'. '+asset['rationale']+' Текст: '+asset['text_inventory'])
    lines+=['','### Метаданные перевода','']
    for key,value in read_json(job/'translation.meta.json').items():
        lines.append('- '+key+': '+('не задано в исходнике' if value is None else str(value)))
    return '\n'.join(lines)+'\n'


def verify_review(job: Path, round_number: int, doc=None) -> dict:
    """Native Docs readback of the language-labelled review copy; no Sheet writes."""
    if __package__:
        from . import gdoc_review as review
        from .verify_refresh_review import doc_readback
    else:
        import gdoc_review as review
        from verify_refresh_review import doc_readback
    receipt=read_json(job/f'review/{round_number:02d}-document.json')
    sent=(job/f'review/{round_number:02d}-sent.md').read_text()
    preface=(job/f'review/{round_number:02d}-translation-preface.md').read_text()
    errors=export_errors(job,'review',remote=False)
    if preface != review_preface(job):
        errors.append('saved review preface is stale against current QA/source/visual limitations')
    tracking=read_json(job/'review/translation-review.json')
    if tracking.get('qa_receipt_sha256') != digest((job/'translation.qa_receipt.json').read_bytes()):
        errors.append('review tracking seal differs from current translation QA seal')
    if tracking.get('article_sha256') != digest(sent) or tracking.get('round') != round_number or review.doc_id(tracking.get('review_doc_url','')) != receipt['document_id']:
        errors.append('translation review tracking identity/round/article differs')
    if receipt.get('article_sha256') != digest(sent) or sent != (job/'edited.md').read_text():
        errors.append('review sent text differs from sealed translation')
    if doc is None:
        _,service=review.services()
        doc=service.documents().get(documentId=receipt['document_id']).execute()
    if doc.get('documentId') != receipt['document_id']:
        errors.append('native readback document identity differs')
    if 'RU translation' not in doc.get('title',''):
        errors.append('review title lacks explicit RU translation label')
    current,_,_,tables,_=doc_readback(doc,receipt.get('images',[]))
    if review.normalize_for_diff(sent) != review.normalize_for_diff(current):
        errors.append('native Docs article text/table readback differs from sealed translation')
    expected_tables=len(read_json(job/'source/inventory.json')['table_shapes'])
    if tables!=expected_tables:
        errors.append('native Docs table count differs from source')
    # Preface precedes the named article range. Inspect it directly in the same
    # native response; do not let an intact article hide omitted limitations.
    native_preface=''
    ranges=doc.get('namedRanges',{}).get('BLOG_ARTICLE_BODY',{}).get('namedRanges',[])
    start=ranges[-1]['ranges'][0]['startIndex'] if ranges else 0
    for el in doc.get('body',{}).get('content',[]):
        if el.get('startIndex',0)>=start:break
        for fragment in el.get('paragraph',{}).get('elements',[]):
            native_preface+=fragment.get('textRun',{}).get('content','')
    if review.normalize_for_diff(preface)!=review.normalize_for_diff(native_preface):
        errors.append('native Docs review preface/limitations differ')
    result={'version':1,'status':'BLOCK' if errors else 'PASS','checked_at':stamp(),
            'document_id':receipt['document_id'],'article_sha256':digest(sent),
            'preface_sha256':digest(preface),'tables':tables,'errors':errors,
            'temnik_sync':'not_applicable_translation_fields_not_defined'}
    write_json(job/f'review/{round_number:02d}-translation-delivery.json',result)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for command in ('bootstrap','fingerprint','check','drift','package','seal','verify-review'):
        p=sub.add_parser(command);p.add_argument('--job',required=True)
        if command=='bootstrap':p.add_argument('--slug',required=True);p.add_argument('--locale',default='ru')
        if command=='verify-review':p.add_argument('--round',type=int,required=True)
    args=parser.parse_args();job=path(args.job)
    try:
        if args.command=='bootstrap': result=bootstrap(job,args.slug,args.locale)
        elif args.command=='fingerprint':result=fingerprint(job)
        elif args.command=='drift':result=drift(job)
        elif args.command=='check':result=check(job)
        elif args.command=='package':result=package(job)
        elif args.command=='verify-review':result=verify_review(job,args.round)
        else:result=seal(job)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result={'status':'BLOCK','errors':[str(exc)]}
    except Exception:
        result={'status':'BLOCK','errors':['translation command unavailable; inspect inputs/access without printing credentials']}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('status')=='BLOCK':raise SystemExit(2)


if __name__=='__main__':main()
