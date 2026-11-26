"""Prepare, execute and import approved OpenRouter blog writing and first-pass review."""
from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
import fcntl
import json
from pathlib import Path
import re
import sys
from urllib.request import urlopen

from article_materials import quote_markdown, source_list_only, writer_ready_errors
from assemble_sections import article_title, collect
from check_research_links import REQUIRED_VALUES, evidence_reference_errors, markdown_table_rows, source_policy_errors
from openrouter_blog_experiment import (
    ROOT, SAFE_ID, Experiment, ExperimentError, path_in_repo, read_json, redact, sha,
    validate_charge_reconciliation, write_json, write_text,
)
from package_article import _label, article_title as edited_title, extract_metadata, validate as validate_meta
from writer_dispatch import unit_errors, writing_units


BRIEF_FILES = ('brief.md', 'sections.json', 'serp.hybrid_outline.md')
JOB_INPUTS = (*BRIEF_FILES, 'job.yaml', 'evidence.md', 'visuals.json', 'expert_quotes.json')
POLICIES = ('blog-owned.md', 'positioning.md', 'legal.md', 'article-structure-rules.md',
            'editorial-owned.md', 'writer-style.md', 'answer-contract.md', 'delivery-contract.md')
WRITER = """Write the single requested complete H2 and its approved H3/H4 subtree.
Use the exact heading strings and levels, including capitalization, in the request. Start
with the H2 and finish at the end of this unit. Assembly adds H1. Return Markdown only.
Treat the packet as evidence and editorial context. Stay within supported populations,
jurisdictions, dates and qualifiers. Name the original beside consequential claims.
Use the public Example Co category and product wording only where the approved brief calls
for it. Answer the assigned reader question directly. Use exact quote blocks and visual
markers where supplied. Evidence IDs are internal. Sources contains each required
clickable URL once; keep external URLs out of prose, quotes and visual captions when
the final Sources policy applies. Keep later sections and earlier answers distinct.
"""
CRITIC = """Review the complete D0 against its approved brief, claims, exact quote and visual
plan, and editorial rules. Return only a JSON object with overall (PASS or BLOCK) and
findings (an array). For each concrete issue give section_id, severity (critical, major
or minor), category, an exact excerpt or heading, reference_ids and a concrete repair.
Check entailment, time and geographic scope, current prices versus promotions, decision
coverage and the product rules (positioning card). Evaluate the supplied draft. Leave final editorial and
independent publication QA to their own stages.
"""
HEADINGS = re.compile(r'^(#{1,6})[ \t]+([^\r\n]+?)[ \t]*$', re.M)
FENCES = re.compile(r'^(\x60{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$', re.M | re.S)


def require(condition, message):
    if not condition:
        raise ExperimentError(message)


def relative(path):
    return path.relative_to(ROOT).as_posix()


def freeze(path, content):
    if path.is_file():
        require(path.read_bytes() == content.encode(), f'Frozen file changed: {relative(path)}')
    else:
        write_text(path, content)
    return relative(path)


def freeze_json(path, value):
    return freeze(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def hashes(paths):
    return {relative(p): sha(p.read_bytes()) for p in paths}


def approved_jobs(batch):
    path = batch / 'brief-approval.json'
    proposal = batch / 'publisher-proposal.json'
    approval = read_json(path)
    require(isinstance(approval, dict) and approval.get('status') == 'approved' and approval.get('publisher')
            and approval.get('items') == read_json(proposal)
            and approval.get('publisher_proposal_sha256') == sha(proposal.read_bytes()),
            'Exact publisher approval of the frozen brief package is required')
    amendments_file = batch / 'publisher-amendments.json'
    amendments = read_json(amendments_file) if amendments_file.is_file() else {}
    jobs = {}
    for item in approval['items']:
        cid = item['cluster_id']
        job = path_in_repo(item['job'])
        require(re.fullmatch(r'b-[0-9]{4}', cid) and cid not in jobs
                and job.parent == ROOT / 'jobs' and job.is_dir() and job not in jobs.values(),
                f'Invalid or duplicate approved job for {cid}')
        outline = read_json(job / 'sections.json')
        amend = amendments.get(cid)
        expected_title, expected_hashes = item['heading'], item['sha256']
        if amend:
            require(amend.get('status') == 'approved' and amend.get('publisher') == approval['publisher']
                    and amend.get('reference') and amend.get('original_heading') == expected_title
                    and amend.get('original_sha256') == expected_hashes
                    and amend.get('metaTitle') == extract_metadata((job / 'brief.md').read_text()).get('metaTitle'),
                    f'{cid}: title amendment needs the exact approved title and metaTitle')
            expected_title, expected_hashes = amend['heading'], amend['sha256']
        require(outline['title'] == expected_title and outline['sections'] == item['sections']
                and all(expected_hashes.get(name) == sha((job / name).read_bytes()) for name in BRIEF_FILES),
                f'{cid}: approved H1, outline or brief inputs changed')
        jobs[cid] = job
    require(jobs and not set(amendments) - jobs.keys(), 'Empty approval or out-of-batch amendment')
    return approval, jobs


def amend_title(batch, run, cid, receipt):
    require(re.fullmatch(r'b-[0-9]{4}', cid) and isinstance(receipt, dict), 'Invalid title approval reference')
    archive = run / 'title-amendments' / cid
    snapshot = archive / 'receipt.json'
    if snapshot.is_file():
        proof = read_json(snapshot)
        require(all(proof.get(k) == v for k, v in receipt.items()), 'Different title amendment already staged')
        return apply_title_replacements(batch, cid, archive, proof)
    approval, jobs = approved_jobs(batch)
    item = next((i for i in approval['items'] if i['cluster_id'] == cid), None)
    require(item and receipt.get('status') == 'approved' and receipt.get('publisher') == approval['publisher']
            and receipt.get('reference') and receipt.get('original_heading') == item['heading'],
            'Exact publisher approval of the old and new title is required')
    new_title, new_meta = receipt['heading'], receipt['metaTitle']
    require(all(isinstance(s, str) and s and s == s.strip() and '\n' not in s and '\r' not in s
                for s in (new_title, new_meta)) and new_title != item['heading'], 'Invalid approved replacement')
    job = jobs[cid]
    old_title = item['heading']
    amendment_file = batch / 'publisher-amendments.json'
    amendments = read_json(amendment_file) if amendment_file.exists() else {}
    if cid in amendments:
        require(all(amendments[cid].get(k) == receipt[k] for k in receipt), 'Different title amendment already recorded')
        return amendments[cid]
    edited = (job / 'edited.md').read_bytes().decode()
    old_line, separator, body = edited.partition('\n')
    require(edited_title(edited) == old_title and separator, 'Edited H1 differs from the original approved title')
    ending = '\r' if old_line.endswith('\r') else ''
    patched = '# ' + new_title + ending + separator + body
    outline = read_json(job / 'sections.json')
    outline['title'] = new_title
    sections = json.dumps(outline, ensure_ascii=False, indent=2) + '\n'
    brief = (job / 'brief.md').read_bytes().decode()
    lines = brief.splitlines(keepends=True)
    meta_lines = [n for n, line in enumerate(lines)
                  if (label := _label(line.rstrip('\r\n'))) and label[0] == 'metaTitle']
    require(meta_lines, 'Brief metaTitle field is missing')
    n = meta_lines[-1]
    line_end = lines[n][len(lines[n].rstrip('\r\n')):]
    lines[n] = '- **metaTitle:** ' + new_meta + line_end
    for n, line in enumerate(lines):
        if line.rstrip('\r\n') == '# ' + old_title:
            lines[n] = '# ' + new_title + line[len('# ' + old_title):]
        elif re.match(r'^\|\s*(?:Title|H1)\s*\|', line) and f'| {old_title} |' in line:
            lines[n] = line.replace(f'| {old_title} |', f'| {new_title} |', 1)
    brief = ''.join(lines)
    metadata = extract_metadata(brief)
    require(metadata.get('metaTitle') == new_meta and edited_title(patched) == new_title,
            'Proposed files do not produce the exact approved title and metaTitle')
    errors = validate_meta({**metadata, 'title': new_title}, item.get('article_type'))
    require(not errors, '; '.join(errors))
    changes = {'brief.md': brief, 'sections.json': sections, 'edited.md': patched}
    proof = {**receipt, 'original_sha256': item['sha256'],
             'sha256': {**item['sha256'], 'brief.md': sha(brief.encode()), 'sections.json': sha(sections.encode())},
             'body_sha256': sha(body.encode())}
    for name, after in changes.items():
        freeze(archive / (name + '.before'), (job / name).read_bytes().decode())
        freeze(archive / (name + '.after'), after)
    freeze_json(archive / 'receipt.json', proof)
    return apply_title_replacements(batch, cid, archive, proof)


def apply_title_replacements(batch, cid, archive, proof):
    approval = read_json(batch / 'brief-approval.json')
    item = next(i for i in approval['items'] if i['cluster_id'] == cid)
    job = path_in_repo(item['job'])
    require(job.parent == ROOT / 'jobs' and job.is_dir(), 'Title amendment target is outside jobs/')
    require(item['sha256'] == proof['original_sha256'] and proof['publisher'] == approval['publisher'],
            'Staged title amendment has a stale publisher approval')
    amendment_file = batch / 'publisher-amendments.json'
    amendments = read_json(amendment_file) if amendment_file.exists() else {}
    require(cid not in amendments or amendments[cid] == proof, 'Different title amendment already recorded')
    changes = {}
    for name in ('brief.md', 'sections.json', 'edited.md'):
        before = (archive / (name + '.before')).read_bytes()
        after = (archive / (name + '.after')).read_bytes()
        require((job / name).read_bytes() in (before, after), f'{cid}: {name} changed after title amendment staging')
        if name == 'edited.md':
            require(edited_title(after.decode()) == proof['heading']
                    and before.partition(b'\n')[2] == after.partition(b'\n')[2]
                    and sha(after.partition(b'\n')[2]) == proof['body_sha256'],
                    'Amendment changes article body bytes')
        else:
            require(sha(before) == proof['original_sha256'][name] and sha(after) == proof['sha256'][name],
                    f'{cid}: title amendment snapshot changed for {name}')
        changes[name] = after.decode()
    for name, text in changes.items():
        if (job / name).read_bytes() != text.encode():
            write_text(job / name, text)
    amendments[cid] = proof
    write_json(amendment_file, amendments)
    approved_jobs(batch)
    return proof


def headings(text):
    spans = [(match.start(), match.end()) for match in FENCES.finditer(text)]
    return [match for match in HEADINGS.finditer(text)
            if not any(start <= match.start() < end for start, end in spans)]


def chapter_spans(text, units):
    marks = [m for m in headings(text) if len(m[1]) == 2]
    require([m[2] for m in marks] == [u['requested_unit'] for u in units],
            'Edited H2s differ from the approved outline')
    starts = [0, *(m.start() for m in marks[1:]), len(text)]
    return list(zip(starts, starts[1:]))


def materialize(paths):
    return '\n\n'.join(f'FILE {path.name}\n{path.read_text(encoding="utf-8")}' for path in paths)


def chapter_packet(job, unit):
    sid = unit['section_id']
    visuals = read_json(job / 'visuals.json')['visuals']
    quotes = read_json(job / 'expert_quotes.json')['quotes']
    markers = [v['id'] for v in visuals if v['section_id'] == sid]
    blocks = [quote_markdown(q, sources_at_end=source_list_only(job)) for q in quotes
              if q['section_id'] == sid and q['status'] != 'rejected']
    return markers, blocks


def source_urls(job):
    rows = markdown_table_rows((job / 'evidence.md').read_text())
    urls = {row['source_url'] for row in rows if row['article_link'].lower() in REQUIRED_VALUES}
    for visual in read_json(job / 'visuals.json')['visuals']:
        urls.update(s['url'] for s in visual['sources'] if s.get('public', True))
    for quote in read_json(job / 'expert_quotes.json')['quotes']:
        if quote.get('speaker_kind') == 'external' and quote['status'] != 'rejected':
            urls.add(quote['source'])
    return sorted(urls)


def prepare(batch, run, phase, revision, cids, route_config):
    approval, jobs = approved_jobs(batch)
    cids = cids or list(jobs)
    require(len(set(cids)) == len(cids) and set(cids) <= jobs.keys(), 'Unknown or repeated cluster ID')
    route = route_config['critic' if phase == 'critic' else 'writer']
    directory = run / 'manifests' / revision
    policy_paths = [ROOT / 'knowledge' / name for name in POLICIES]
    system = freeze(directory / 'system.md',
                    (CRITIC if phase == 'critic' else WRITER) + '\n' + materialize(policy_paths))
    frozen = {ROOT / system}
    live = set(policy_paths)
    variants = []
    for cid in cids:
        job = jobs[cid]
        config = (job / 'job.yaml').read_text()
        require(re.search(r'^production_text_backend:\s*openrouter_hybrid\b', config, re.M)
                and re.search(rf'^temnik_cluster_id:\s*["\']?{cid}\b', config, re.M),
                f'{cid}: job configuration differs from the hybrid batch')
        errors = writer_ready_errors(job)
        require(not errors, f'{cid}: ' + '; '.join(errors))
        work = directory / cid
        paths = [job / name for name in JOB_INPUTS]
        if (job / 'company_cards.md').exists():
            paths.append(job / 'company_cards.md')
        packet = freeze(work / 'packet.md', materialize(paths))
        live.update(paths)
        frozen.add(ROOT / packet)
        inputs = [packet]
        stages = []
        if phase == 'critic':
            draft = job / 'out/draft.md'
            inputs.append(freeze(work / 'D0.md', draft.read_text()))
            live.add(draft)
            prompt = freeze(work / 'review.md', 'Review the attached complete D0. Return the required JSON.\n')
            stages.append({'id': 'review', 'prompt_file': prompt, 'output_format': 'json'})
        else:
            units = writing_units(job)
            repairs = {}
            if phase == 'repair':
                plan = job / 'raw/openrouter-rework-plan.json'
                repairs = read_json(plan)
                require(isinstance(repairs, dict) and repairs
                        and repairs.keys() <= {u['section_id'] for u in units}
                        and all(isinstance(d, str) and d.strip() for d in repairs.values()),
                        f'{cid}: repair plan must map approved H2 IDs to exact defects')
                baseline = (job / 'edited.md').read_bytes().decode()
                spans = chapter_spans(baseline, units)
                frozen.add(ROOT / freeze(work / 'edited-baseline.md', baseline))
                live.add(plan)
            for unit in units:
                n, sid = unit['number'], unit['section_id']
                if repairs and sid not in repairs:
                    continue
                marks, blocks = chapter_packet(job, unit)
                prompt = ['Exact assigned headings:', *('#' * h['level'] + ' ' + h['title'] for h in unit['headings'])]
                prompt += ['\nUse these exact visual markers and complete prepared quote blocks:',
                           *(f'[[VISUAL:{vid}]]' for vid in marks), *blocks]
                if unit['requested_unit'].casefold() in {'sources', 'источники'} and source_list_only(job):
                    prompt += ['\nLink each of these exact URLs once with an informative label:', *source_urls(job)]
                stage_inputs = []
                if repairs:
                    start, end = spans[n - 1]
                    previous = baseline[start:end]
                    offset = next(m.start() for m in headings(previous) if len(m[1]) == 2)
                    stage_inputs.append(freeze(work / f'section-{n:02}.md', previous[offset:]))
                    prompt += ['\nFix only this exact defect in the attached unit. Keep unaffected paragraphs verbatim:', repairs[sid]]
                stage_id = f'h2-{n:02}'
                path = freeze(work / f'{stage_id}.md', '\n'.join(prompt) + '\n')
                stages.append({'id': stage_id, 'prompt_file': path, 'input_files': stage_inputs, 'min_chars': 32})
                frozen.update(ROOT / name for name in stage_inputs)
        for stage in stages:
            stage['max_tokens'] = route['max_tokens']
            frozen.add(ROOT / stage['prompt_file'])
        frozen.update(ROOT / name for name in inputs)
        variants.append({**route['route'], 'id': f'{revision}-{cid}', 'cluster_id': cid,
                         'input_files': inputs, 'stages': stages})
    receipt = batch / 'brief-approval.json'
    budget = approval['api_budget_usd']
    manifest = {
        'schema_version': 1, 'experiment_id': run.name, 'revision': revision, 'blog_phase': phase,
        'run_dir': relative(run), 'request_mode': 'stable_conversation_v1',
        'max_workers': min(8, len(variants)), 'max_cost_usd': budget,
        'max_call_cost_usd': min(0.20, budget), 'timeout_seconds': 240,
        'batch_authorization': {'approval_file': relative(receipt), 'approval_sha256': sha(receipt.read_bytes())},
        'system_files': [system], 'input_sha256': hashes(sorted(frozen)),
        'live_input_sha256': hashes(sorted(live)), 'variants': variants,
    }
    return Experiment(ROOT / freeze_json(directory / 'manifest.json', manifest))


def check_endpoint(route, max_tokens):
    endpoint_url = 'https://openrouter.ai/api/v1/models/' + route['model'] + '/endpoints'
    with urlopen(endpoint_url, timeout=30) as response:
        endpoints = json.load(response)['data']['endpoints']
    matches = [e for e in endpoints if e['tag'] == route['provider']
               and e['provider_name'] == route['provider_name'] and e['model_id'] == route['model']
               and e['name'].endswith(' | ' + route['canonical_slug'])]
    require(len(matches) == 1 and matches[0]['status'] == 0
            and matches[0]['max_completion_tokens'] >= max_tokens, f'Pinned endpoint unavailable: {endpoint_url}')
    endpoint = matches[0]
    price = endpoint['pricing']
    for tariff in [price, *price.get('overrides', [])]:
        for unit, cap in route['price_cap'].items():
            require(Decimal(tariff[unit]) * 1_000_000 <= Decimal(str(cap)),
                    f'Pinned {unit} rate exceeds the configured cap: {endpoint_url}')
    return endpoint


def restore_headings(raw, unit, entries):
    actual = headings(raw)
    expected = unit['headings']
    require(len(actual) == len(expected), 'Heading restoration cannot add or remove a heading')
    approved = {'#' * h['level'] + ' ' + h['title'] for h in expected}
    replacements = {}
    for entry in entries:
        ordinal = entry['ordinal']
        require(type(ordinal) is int and 1 <= ordinal <= len(actual) and ordinal not in replacements,
                'Heading restoration requires a unique, exact ordinal')
        match, wanted = actual[ordinal - 1], expected[ordinal - 1]
        new = '#' * wanted['level'] + ' ' + wanted['title']
        require(entry['raw_sha256'] == sha(raw.encode()) and entry['old_heading'] == match[0]
                and len(match[1]) == wanted['level'] and entry['new_heading'] == new and match[0] not in approved,
                'Heading restoration must bind the exact raw output and approved heading at the same level')
        replacements[ordinal] = new
    text = raw
    for ordinal, new in sorted(replacements.items(), reverse=True):
        start, end = actual[ordinal - 1].span()
        text = text[:start] + new + text[end:]
    return text


def import_article(experiment, phase, variant, job, restorations):
    cid = variant['cluster_id']
    work = experiment.manifest_path.parent / cid
    units = {} if phase == 'critic' else {f'h2-{u["number"]:02}': u for u in writing_units(job)}
    units_out, audits = [], {}
    for stage in experiment.stages(variant):
        sid = stage['id']
        raw = experiment._verified_prior_output(variant, stage, experiment.build_request(variant, stage))
        if phase == 'critic':
            data = json.loads(raw)
            require(isinstance(data, dict) and data.get('overall') in {'PASS', 'BLOCK'}
                    and isinstance(data.get('findings'), list), f'{cid}: invalid DeepSeek verdict')
            # Different valid review attempts remain in their own run manifests.
            freeze(work / 'review-verified.json', raw)
            write_text(job / 'raw/openrouter-critic.json', raw)
            return
        unit = units[sid]
        entries = restorations.get((cid, sid), [])
        body = restore_headings(raw, unit, entries) if entries else raw
        errors = unit_errors(job, unit, body)
        require(not errors and all(len(m[1]) in {2, 3, 4} for m in headings(body)),
                f'{cid}/{sid}: ' + ('; '.join(errors) or 'unexpected heading level'))
        markers, blocks = chapter_packet(job, unit)
        require(sorted(re.findall(r'\[\[VISUAL:([^\]]+)\]\]', body)) == sorted(markers)
                and all(body.count(block) == 1 for block in blocks),
                f'{cid}/{sid}: missing or changed approved visual or quote block')
        if entries:
            audits[sid] = {'restorations': entries, 'output_sha256': sha(body.encode())}
        units_out.append((unit, body))
    if phase == 'writer':
        text = f'# {article_title(job)}\n\n' + '\n\n'.join(body.strip() for _, body in units_out) + '\n'
        evidence = (job / 'evidence.md').read_text()
        warnings = evidence_reference_errors(evidence, text)
        if source_list_only(job):
            warnings.extend(source_policy_errors(job, evidence, text))
        for unit, body in units_out:
            target = job / unit['path']
            require(not target.exists() or target.read_bytes() == body.encode(), f'Existing unit differs: {target}')
        for sid, audit in audits.items():
            freeze_json(work / f'{sid}-heading-restoration.json', audit)
        for unit, body in units_out:
            freeze(job / unit['path'], body)
        assembled, missing = collect(job)
        require(not missing and text == f'# {article_title(job)}\n\n{assembled}\n', 'Assembly differs from verified units')
        freeze(job / 'out/draft.md', text)
        freeze_json(work / 'draft-check.json', {'warnings': warnings})
        write_json(job / 'raw/openrouter-draft-check.json', {'warnings': warnings, 'draft_sha256': sha(text.encode())})
    else:
        path = work / 'edited-baseline.md'
        baseline = experiment._input_path(relative(path)).read_bytes().decode()
        spans = chapter_spans(baseline, list(units.values()))
        patched = baseline
        for unit, body in reversed(units_out):
            start, end = spans[unit['number'] - 1]
            previous = baseline[start:end]
            spacing = previous[len(previous.rstrip()):]
            # The first edited span includes the existing H1 and any front matter.
            first_h2 = next(m for m in headings(previous) if len(m[1]) == 2)
            patched = patched[:start + first_h2.start()] + body.rstrip() + spacing + patched[end:]
        edited = job / 'edited.md'
        require(edited.read_bytes().decode() in {baseline, patched}, f'{cid}: edited text changed since repair preparation')
        freeze(work / 'edited-repaired.md', patched)
        write_text(edited, patched)


def import_outputs(experiment, phase, jobs, restoration_path):
    restorations = defaultdict(list)
    if restoration_path:
        plan = read_json(path_in_repo(restoration_path, exists=True))
        require(phase == 'writer' and plan.get('schema_version') == 1
                and plan.get('audited_by') and plan.get('audit_reference') and plan.get('restorations'),
                'Heading changes require a parent-audited writer restoration plan')
        for entry in plan['restorations']:
            restorations[entry['cluster_id'], entry['unit_id']].append(entry)
        available = {(v['cluster_id'], s['id']) for v in experiment.variants for s in experiment.stages(v)}
        require(restorations.keys() <= available, 'Out-of-scope heading restoration')
        freeze_json(experiment.manifest_path.parent / 'heading-restorations.json', plan)
    failures = {}
    with (experiment.run_dir / '.executor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for variant in experiment.variants:
            cid = variant['cluster_id']
            try:
                import_article(experiment, phase, variant, jobs[cid], restorations)
            except (ExperimentError, OSError, ValueError, KeyError, TypeError) as exc:
                failures[cid] = str(exc)
    return {'imported': [v['cluster_id'] for v in experiment.variants if v['cluster_id'] not in failures],
            'blocked': failures}


def cost(run):
    require(run.is_dir(), 'No OpenRouter run directory for this batch')
    usd = defaultdict(Decimal)
    attempts = defaultdict(int)
    unknown = []
    for path in sorted(run.glob('variants/*/attempts/*/receipt.json')):
        receipt = read_json(path)
        match = re.search(r'(b-[0-9]{4})$', receipt['variant'])
        require(match, f'No cluster ID in receipt: {relative(path)}')
        cid = match[1]
        attempts[cid] += 1
        value = receipt['cost_usd']
        if value is None and (path.parent / 'cost-reconciliation.json').is_file():
            value = validate_charge_reconciliation(path, read_json(path.parent / 'cost-reconciliation.json'))
        if value is None:
            unknown.append(relative(path))
        else:
            usd[cid] += Decimal(str(value))
    unknown.extend(relative(p) for p in run.glob('variants/*/attempts/*/intent.json')
                   if not (p.parent / 'receipt.json').exists())
    return {'known_total_usd': str(sum(usd.values())), 'attempts': sum(attempts.values()),
            'articles': {cid: {'known_usd': str(usd[cid]), 'attempts': attempts[cid]} for cid in sorted(attempts)},
            'unreconciled': unknown}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'execute', 'import', 'cost', 'amend-title'))
    parser.add_argument('phase', nargs='?', choices=('writer', 'critic', 'repair'))
    parser.add_argument('--batch', required=True)
    parser.add_argument('--revision')
    parser.add_argument('--cid', action='append')
    parser.add_argument('--retry-failed', action='store_true')
    parser.add_argument('--heading-restorations')
    parser.add_argument('--amendment', help='Exact publisher-approved H1/metaTitle receipt')
    args = parser.parse_args(argv)
    if not SAFE_ID.fullmatch(args.batch) or (args.command in {'prepare', 'execute', 'import'} and
            (not args.phase or not args.revision or not SAFE_ID.fullmatch(args.revision))):
        parser.error('Use a safe batch ID and specify the phase and revision')
    if args.command == 'amend-title' and (not args.cid or len(args.cid) != 1 or not args.amendment):
        parser.error('Use one --cid and an exact --amendment approval receipt')
    batch = ROOT / 'docs/workflow-v2/batches' / args.batch
    run = ROOT / 'runs' / args.batch
    try:
        if args.command == 'cost':
            result = cost(run)
            success = not result['unreconciled']
        elif args.command == 'amend-title':
            run.mkdir(parents=True, exist_ok=True)
            with (run / '.executor.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = amend_title(batch, run, args.cid[0], read_json(path_in_repo(args.amendment, exists=True)))
            success = True
        else:
            routes = read_json(ROOT / 'config/blog-openrouter.json')
            if args.command == 'prepare':
                result = prepare(batch, run, args.phase, args.revision, args.cid, routes).dry_run()
                success = True
            else:
                _, jobs = approved_jobs(batch)
                experiment = Experiment(run / 'manifests' / args.revision / 'manifest.json')
                manifest = experiment.manifest
                require(manifest.get('blog_phase') == args.phase and experiment.run_dir == run,
                        'Prepared phase and batch must match the request')
                live = manifest['live_input_sha256']
                require(live == hashes(ROOT / path for path in live), 'Live job or editorial policy changed; prepare a new revision')
                if args.command == 'execute':
                    route = routes['critic' if args.phase == 'critic' else 'writer']
                    for variant in experiment.variants:
                        require(all(variant[key] == value for key, value in route['route'].items()), 'Pinned route differs')
                        if args.phase == 'repair':
                            frozen = experiment.manifest_path.parent / variant['cluster_id'] / 'edited-baseline.md'
                            require((jobs[variant['cluster_id']] / 'edited.md').read_bytes() ==
                                    experiment._input_path(relative(frozen)).read_bytes(), 'Edited baseline changed before execution')
                    cap = max(s['max_tokens'] for v in experiment.variants for s in experiment.stages(v))
                    require(cap == route['max_tokens'], 'Manifest token ceiling differs from configured route')
                    check_endpoint(route['route'], cap)
                    result = experiment.execute(retry_failed=args.retry_failed)
                    success = all(r['status'] in {'success', 'resumed'} for rows in result['results'] for r in rows)
                    success = success and not (result['usage']['unknown_cost_attempts'] or result['usage']['pending_intents'])
                else:
                    result = import_outputs(experiment, args.phase, jobs, args.heading_restorations)
                    success = not result['blocked']
        print(json.dumps(redact(result), ensure_ascii=False, indent=2))
        return 0 if success else 2
    except (ExperimentError, OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
