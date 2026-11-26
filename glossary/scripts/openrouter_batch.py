#!/usr/bin/env python3
"""Opt-in fixed-size MiniMax batch. Reuses the pilot transport and its global budget lock."""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path
import openrouter_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
# Example values: the batch ID, its approved case count and the global API cap (USD).
BATCH_ID = 'example-batch'
BATCH = ROOT / 'docs/batches' / BATCH_ID
BATCH_SIZE = 12
GLOBAL_CAP_USD = 3.0
PILOT_JOBS = tuple(pilot.ROUND1_JOBS + pilot.ROUND2_JOBS)

def configure(batch=BATCH):
    manifest = pilot.read(batch / 'manifest.json')
    cases = manifest.get('cases', [])
    if len(cases) != BATCH_SIZE or manifest.get('openrouter_global_cap_usd') != GLOBAL_CAP_USD:
        raise pilot.PilotError(f'Expected approved {BATCH_SIZE}-term manifest and global ${GLOBAL_CAP_USD:g} cap')
    names = []
    for case in cases:
        name = BATCH_ID + '-' + case['slug']
        if not re.fullmatch(re.escape(BATCH_ID) + r'-[a-z0-9]+(?:-[a-z0-9]+)*', name) or case['job'] != 'jobs/' + name:
            raise pilot.PilotError('Invalid batch job path')
        request = pilot.read(ROOT / case['job'] / 'request.json')
        if request.get('batch') != BATCH_ID or request.get('slug') != case['slug'] or request.get('term') != case['term']:
            raise pilot.PilotError('Job identity does not match approved batch')
        names.append(name)
    if len(names) != len(set(names)):
        raise pilot.PilotError('Duplicate batch jobs')
    # Pilot jobs and all their paid charges stay under the same cap.
    pilot.JOBS = list(dict.fromkeys([*PILOT_JOBS, *names]))
    pilot.ROUND2_JOBS = list(dict.fromkeys([*pilot.ROUND2_JOBS, *names]))
    pilot.CAP = GLOBAL_CAP_USD
    return {name: ROOT / 'jobs' / name for name in names}

def static_check(job, article=None, out=None):
    import markdown
    if markdown.__version__ != '3.10.2':
        raise pilot.PilotError('Static CMS checks require project-pinned Markdown3.10.2')
    from glossary_job import validate_body, validate_meta, sections
    article = article or job / 'pilot/arms/a/assembled.md'
    text = article.read_text().strip() + '\n'
    validate_meta(pilot.read(job / 'pilot/arms/a/meta.json'))
    validate_body(text, sections(job), allow_visual_markers=True)
    html = markdown.markdown(text, extensions=['tables', 'sane_lists']) + '\n'
    html = re.sub(r'(<img\b[^>]*?)\s+title="[^"]*"', r'\1', html)
    sanitized = subprocess.run(['node', str(ROOT / 'tools/sanitize/check.js')], input=html, text=True, capture_output=True, check=True).stdout
    bad_units = []
    for unit in pilot.units(job):
        part = (job / 'pilot/arms/a/units' / (unit['id'] + '.md')).read_text()
        rendered = markdown.markdown(part, extensions=['tables', 'sane_lists']) + '\n'
        rendered = re.sub(r'(<img\b[^>]*?)\s+title="[^"]*"', r'\1', rendered)
        checked = subprocess.run(['node', str(ROOT / 'tools/sanitize/check.js')], input=rendered, text=True, capture_output=True, check=True).stdout
        if rendered != checked:
            bad_units.append(unit['id'])
    result = {'article_sha256': pilot.sha(article.read_bytes()), 'markdown_version': markdown.__version__, 'metadata_and_hierarchy': 'PASS', 'sanitizer_equal': html == sanitized, 'unit_ids_with_sanitizer_changes': bad_units, 'style_attribute_count': html.count('style='), 'visual_markers_deferred_until_verified_media': re.findall(r'\[\[VISUAL:([^]]+)\]\]', text)}
    if out:
        pilot.write(out, result)
    return result

def snapshot_raw(job):
    dest = job / 'pilot/raw'; src = job / 'pilot/arms/a'
    if dest.exists():
        return
    dest.mkdir()
    for name in ('assembled.md', 'meta.json', 'history.json', 'stage.json'):
        shutil.copy2(src / name, dest / name)
    shutil.copytree(src / 'units', dest / 'units')
    pilot.write(dest / 'hashes.json', {str(p.relative_to(dest)): pilot.sha(p.read_bytes()) for p in dest.rglob('*') if p.is_file()})

def plain_table_separators(text):
    """Remove alignment syntax only from complete Markdown delimiter rows."""
    lines = []
    for line in text.splitlines(keepends=True):
        cells = line.strip().split('|')
        if cells and not cells[0].strip(): cells = cells[1:]
        if cells and not cells[-1].strip(): cells = cells[:-1]
        if '|' in line and cells and all(re.fullmatch(r'\s*:?-{3,}:?\s*', cell) for cell in cells):
            line = line.replace(':', '')
        lines.append(line)
    return ''.join(lines)

def normalize_tables(job, round_id='raw'):
    """Audited technical normalization, with immutable API originals and no prose edit."""
    if not re.fullmatch(r'[a-z0-9-]+', round_id):
        raise pilot.PilotError('Invalid format round')
    if (job / 'pilot/editor-input-lock.json').exists() or (job / 'edited.md').exists():
        raise pilot.PilotError('Editor inputs locked; versioned handoff required')
    pilot.verify_frozen(job)
    src = job / 'pilot/arms/a'; article = src / 'assembled.md'
    dest = job / ('pilot/native-format-' + round_id); report = dest / 'report.json'
    if report.exists():
        result = pilot.read(report)
        if pilot.sha(article.read_bytes()) != result['after_article_sha256']:
            raise pilot.PilotError('Format round already recorded for another version')
        return result
    snapshot_raw(job)
    before = article.read_bytes().decode('utf-8'); parts = []; changes = []
    for unit in pilot.units(job):
        path = src / 'units' / (unit['id'] + '.md')
        original = path.read_bytes().decode('utf-8'); normalized = plain_table_separators(original)
        parts.append(normalized.strip())
        if normalized != original:
            changes.append({'unit_id': unit['id'], 'removed_alignment_colons': len(original) - len(normalized), 'before_sha256': pilot.sha(original.encode()), 'after_sha256': pilot.sha(normalized.encode()), 'original': original, 'normalized': normalized})
    after = '\n\n'.join(parts) + '\n'
    if plain_table_separators(before) != after:
        raise pilot.PilotError('Normalization would alter bytes beyond delimiter colons')
    dest.mkdir(parents=True)
    shutil.copy2(article, dest / 'before-assembled.md')
    for change in changes:
        path = src / 'units' / (change['unit_id'] + '.md')
        shutil.copy2(path, dest / path.name)
        path.write_bytes(change['normalized'].encode('utf-8'))
    article.write_bytes(after.encode('utf-8'))
    result = {'at': pilot.now(), 'attribution': 'Native deterministic CMS format normalization; not MiniMax repair credit', 'scope': 'Only colon characters in complete Markdown table separator rows; all other article bytes preserved', 'before_article_sha256': pilot.sha(before.encode()), 'after_article_sha256': pilot.sha(after.encode()), 'changes': [{k:v for k,v in c.items() if k not in {'original', 'normalized'}} for c in changes]}
    pilot.write(report, result)
    return result

def handoff(job):
    """Create editor inputs once, after all API repairs; never overwrite an active editor."""
    lock = job / 'pilot/editor-input-lock.json'
    if lock.exists() or (job / 'edited.md').exists():
        raise pilot.PilotError('Editor inputs locked; explicit versioned rework handoff required')
    src = job / 'pilot/arms/a'
    text = (src / 'assembled.md').read_text()
    for section in pilot.read(job / 'sections.json')['sections']:
        content = '\n\n'.join((src / 'units' / (u['id'] + '.md')).read_text().strip() for u in pilot.units(job) if u['section_id'] == section['id']) + '\n'
        (job / 'sections' / (section['id'] + '.md')).write_text(content)
    (job / 'assembled.md').write_text(text)
    (job / 'out').mkdir(exist_ok=True)
    (job / 'out/draft.md').write_text(text)
    meta = pilot.read(src / 'meta.json')
    meta['indexable'] = True  # Ordinary requested batch; experimental API staging remains immutable/noindex.
    if (job / 'meta.json').exists() and not (job / 'pilot/meta-before-writer-handoff.json').exists():
        shutil.copy2(job / 'meta.json', job / 'pilot/meta-before-writer-handoff.json')
    pilot.write(job / 'meta.json', meta)
    pilot.write(lock, {'source_article_sha256': pilot.sha(text.encode()), 'source_api_meta_sha256': pilot.sha((src / 'meta.json').read_bytes()), 'editor_meta_sha256': pilot.sha((job / 'meta.json').read_bytes()), 'metadata_transform': 'Only indexable false -> true for ordinary batch; generated definition/title/description unchanged', 'state': 'locked-for-editor'})

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'freeze', 'writer', 'repair', 'static-check', 'normalize-tables', 'snapshot-raw', 'handoff', 'usage'])
    parser.add_argument('--job')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--feedback', type=Path)
    parser.add_argument('--round', default='qa1')
    parser.add_argument('--retry-failed', action='store_true')
    args = parser.parse_args()
    jobs = configure()
    if args.action == 'usage':
        result = pilot.usage(); pilot.write(BATCH / 'usage.json', result); print(json.dumps(result)); return
    if args.action == 'preflight':
        result = pilot.preflight(pilot.route('writer')); pilot.glossary_key(); pilot.write(BATCH / 'live-preflight.json', result); print('Pinned MiniMax route and glossary-labelled key verified'); return
    if args.job not in jobs:
        parser.error('--job must identify one of the batch jobs')
    job = jobs[args.job]
    if args.action == 'freeze':
        pilot.freeze(job)
    elif args.action == 'writer':
        if (job / 'pilot/arms/a/stage.json').exists():
            raise pilot.PilotError('Raw writer already completed; do not replay after repairs')
        pilot.writer(job, args.execute, args.retry_failed)
        if args.execute: snapshot_raw(job)
    elif args.action == 'repair':
        if not args.feedback or not re.fullmatch(r'[a-z0-9-]+', args.round):
            parser.error('repair requires reviewed feedback and safe round ID')
        if (job / 'pilot/editor-input-lock.json').exists():
            raise pilot.PilotError('Editor input locked; preserve and explicitly version rework first')
        pilot.repair(job, 'a', execute=args.execute, retry=args.retry_failed, feedback=args.feedback, round_id=args.round)
    elif args.action == 'static-check':
        result = static_check(job, out=job / 'pilot/static-current.json'); print(json.dumps(result));
        if not result['sanitizer_equal']: raise pilot.PilotError('CMS format requires exact unit repair before semantic QA')
    elif args.action == 'normalize-tables':
        print(json.dumps(normalize_tables(job, args.round)))
    elif args.action == 'snapshot-raw': snapshot_raw(job)
    elif args.action == 'handoff': handoff(job)

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(pilot.redact(f'{type(exc).__name__}: {exc}'), file=sys.stderr); sys.exit(1)
