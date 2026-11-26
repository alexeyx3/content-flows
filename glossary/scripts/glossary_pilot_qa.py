#!/usr/bin/env python3
"""Opt-in glossary pilot QA registry; no prose edits, network, or legacy QA changes.

Input JSON requires protocol_version=1, term, arm, stage, round (integer),
base_draft_sha256, Verdict (PASS|BLOCK), fingerprints, findings, and decisions.
Fingerprints require article_sha256/meta_sha256/materials_sha256 plus
policy_sha256/prompt_sha256/input_sha256; additional glossary fingerprints are
preserved. --fingerprints can bind all fields to an independently computed map.

Each finding: id (Q-*), severity (minor|major|critical), category, rule_id,
unit_ids, contract_ids, hybrid_ids, evidence_ids, description,
acceptance_condition, and either passage (exact article substring) or
coverage_anchor {heading (exact Markdown heading), contract_id, description}.
Every prior registry ID needs a decision {id,status,explanation,passage OR
coverage_anchor}; status is open|resolved|withdrawn|reopened. A withdrawn
decision needs reversal_reason instead of a current passage. Reversing a prior
resolved/withdrawn decision also needs reversal_reason. Original findings and
conditions cannot change. New findings have fresh IDs and default to open.

The sealed result preserves all input fields, adds cumulative registry with
current statuses, deterministic findings_sha256/decisions_sha256/review_sha256,
and binds rechecks using parent_review_sha256. This validates provenance and
completeness; an independent QA reviewer still judges factual entailment and
whether acceptance conditions are actually satisfied. No GEO style quotas.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import re
from pathlib import Path


class QAError(ValueError):
    pass


HASH = re.compile(r'[0-9a-f]{64}')
ID = re.compile(r'Q-[A-Za-z0-9][A-Za-z0-9._-]*')
STATUSES = {'open', 'resolved', 'withdrawn', 'reopened'}
REQUIRED_FINGERPRINTS = {'article_sha256', 'meta_sha256', 'materials_sha256',
                         'policy_sha256', 'prompt_sha256', 'input_sha256'}
SEALED_FIELDS = {'registry', 'findings_sha256', 'decisions_sha256', 'review_sha256'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition, message):
    if not condition:
        raise QAError(message)


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + ' must be nonempty text')


def location(value, article, label):
    """Require a genuine quote or a specific existing heading/contract anchor."""
    passage = value.get('passage')
    anchor = value.get('coverage_anchor')
    require(bool(passage) != bool(anchor), label + ' needs exactly one passage or coverage_anchor')
    if passage:
        text(passage, label + '.passage')
        require(passage in article, label + ' passage is absent from current article')
    else:
        require(isinstance(anchor, dict), label + ' coverage_anchor must be an object')
        for field in ('heading', 'contract_id', 'description'):
            text(anchor.get(field), label + '.coverage_anchor.' + field)
        headings = re.findall(r'^#{2,4} .+$', article, re.M)
        require(anchor['heading'] in headings, label + ' coverage heading is absent from current article')
        if 'contract_ids' in value:
            require(anchor['contract_id'] in value['contract_ids'], label + ' coverage contract not in contract_ids')


def finding(value, article):
    require(isinstance(value, dict), 'finding must be an object')
    require(isinstance(value.get('id'), str) and ID.fullmatch(value['id']), 'finding needs canonical Q-ID')
    for field in ('category', 'rule_id', 'description', 'acceptance_condition'):
        text(value.get(field), value['id'] + '.' + field)
    require(value.get('severity') in {'minor', 'major', 'critical'}, value['id'] + ' invalid severity')
    for field in ('unit_ids', 'contract_ids', 'hybrid_ids', 'evidence_ids'):
        entries = value.get(field)
        require(isinstance(entries, list) and all(isinstance(x, str) and x.strip() for x in entries), value['id'] + '.' + field + ' must be a string list')
        require(len(entries) == len(set(entries)), value['id'] + '.' + field + ' has duplicate IDs')
    require(value['unit_ids'], value['id'] + ' needs at least one unit_id')
    require('status' not in value, value['id'] + ' status belongs in decisions')
    location(value, article, value['id'])


def sorted_ids(values):
    return sorted(values, key=lambda x: x['id'])


def content_for_hash(report):
    return {k: v for k, v in report.items() if k != 'review_sha256'}


def verify_seal(report):
    require(isinstance(report, dict), 'prior report must be an object')
    for field in SEALED_FIELDS:
        require(field in report, 'prior report missing ' + field)
    require(report['findings_sha256'] == digest(report['registry']), 'prior findings hash mismatch')
    require(report['decisions_sha256'] == digest(sorted_ids(report['decisions'])), 'prior decisions hash mismatch')
    require(report['review_sha256'] == digest(content_for_hash(report)), 'prior review hash mismatch')
    ids = [x.get('id') for x in report['registry']]
    require(len(ids) == len(set(ids)) and all(isinstance(x, str) and ID.fullmatch(x) for x in ids), 'prior registry IDs invalid')
    require(all(x.get('status') in STATUSES for x in report['registry']), 'prior registry status invalid')


def validate_report(report, article_text, *, prior=None, fingerprints=None):
    require(isinstance(report, dict), 'report must be an object')
    require(isinstance(article_text, str), 'article must be text')
    output = copy.deepcopy(report)
    supplied_seals = {k: output.pop(k) for k in SEALED_FIELDS if k in output}
    require(output.get('protocol_version') == 1, 'protocol_version must be 1')
    for field in ('term', 'arm', 'stage'):
        text(output.get(field), field)
    require(type(output.get('round')) is int and output['round'] >= 0, 'round must be a nonnegative integer')
    require(isinstance(output.get('base_draft_sha256'), str) and HASH.fullmatch(output['base_draft_sha256']), 'invalid base_draft_sha256')
    require(output.get('Verdict') in {'PASS', 'BLOCK'}, 'Verdict must be PASS or BLOCK')
    fp = output.get('fingerprints')
    require(isinstance(fp, dict) and REQUIRED_FINGERPRINTS <= fp.keys(), 'required glossary fingerprints missing')
    require(all(isinstance(k, str) and isinstance(v, str) and HASH.fullmatch(v) for k, v in fp.items()), 'fingerprints must contain SHA-256 values')
    require(fp['article_sha256'] == hashlib.sha256(article_text.encode()).hexdigest(), 'article fingerprint mismatch')
    if fingerprints is not None:
        require(fp == fingerprints, 'current fingerprints differ from independent fingerprints')
    require(isinstance(output.get('findings'), list), 'findings must be a list')
    require(isinstance(output.get('decisions'), list), 'decisions must be a list')
    prior_registry = {}
    if prior is not None:
        verify_seal(prior)
        for field in ('term', 'arm', 'base_draft_sha256'):
            require(output[field] == prior[field], 'recheck changed branch identity: ' + field)
        require(output['round'] > prior['round'], 'recheck round must advance')
        require(output.get('parent_review_sha256') == prior['review_sha256'], 'parent review hash mismatch')
        require(fp.keys() == prior['fingerprints'].keys(), 'recheck must preserve glossary fingerprint fields')
        require(fp['materials_sha256'] == prior['fingerprints']['materials_sha256'], 'common materials changed; fork/version the experiment')
        prior_registry = {x['id']: copy.deepcopy(x) for x in prior['registry']}
    else:
        require(output.get('parent_review_sha256') in (None, ''), 'initial report cannot name a parent review')
        require(not output['decisions'], 'initial report cannot decide prior findings')
    current = copy.deepcopy(prior_registry)
    new_ids = set()
    seen = set()
    for value in output['findings']:
        require(isinstance(value, dict), 'finding must be an object')
        fid = value.get('id')
        require(isinstance(fid, str) and fid not in seen, 'duplicate or invalid finding ID')
        seen.add(fid)
        if fid in prior_registry:
            original = {k: v for k, v in prior_registry[fid].items() if k != 'status'}
            require(value == original, fid + ' changed original finding or acceptance condition')
        else:
            finding(value, article_text)
            current[fid] = {**copy.deepcopy(value), 'status': 'open'}
            new_ids.add(fid)
    decisions = {}
    for value in output['decisions']:
        require(isinstance(value, dict), 'decision must be an object')
        fid = value.get('id')
        require(isinstance(fid, str) and fid in prior_registry, 'decision must refer to a prior canonical ID')
        require(fid not in decisions, 'duplicate decision for ' + fid)
        status = value.get('status')
        require(status in STATUSES, fid + ' invalid decision status')
        text(value.get('explanation'), fid + '.explanation')
        before = prior_registry[fid]['status']
        if status in {'withdrawn', 'reopened'} or (before in {'resolved', 'withdrawn'} and status != before):
            text(value.get('reversal_reason'), fid + '.reversal_reason')
        require(not (before in {'resolved', 'withdrawn'} and status == 'open'), fid + ' must use reopened to reverse closure')
        if status != 'withdrawn':
            location(value, article_text, fid + ' decision')
            if value.get('coverage_anchor'):
                require(value['coverage_anchor']['contract_id'] in prior_registry[fid]['contract_ids'], fid + ' decision coverage contract differs from original finding')
        current[fid]['status'] = status
        decisions[fid] = value
    require(decisions.keys() == prior_registry.keys(), 'each prior ID requires exactly one decision, including closed IDs')
    # Current evidence is mandatory for every live item, even if its immutable
    # original quote no longer occurs after a repair.
    for fid in new_ids:
        location(current[fid], article_text, fid)
    blockers = [x['id'] for x in current.values() if x['status'] in {'open', 'reopened'} and x['severity'] in {'major', 'critical'}]
    require(output['Verdict'] != 'PASS' or not blockers, 'PASS has open blockers: ' + ', '.join(blockers))
    output['findings'] = sorted_ids(output['findings'])
    output['decisions'] = sorted_ids(output['decisions'])
    output['registry'] = sorted_ids(list(current.values()))
    output['findings_sha256'] = digest(output['registry'])
    output['decisions_sha256'] = digest(output['decisions'])
    output['review_sha256'] = digest(content_for_hash(output))
    for key, value in supplied_seals.items():
        require(output[key] == value, 'supplied ' + key + ' mismatch')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--article', type=Path, required=True)
    parser.add_argument('--prior', type=Path)
    parser.add_argument('--fingerprints', type=Path, help='Independent current fingerprint map JSON')
    parser.add_argument('--out', type=Path, help='New immutable sealed JSON destination; default stdout')
    args = parser.parse_args()
    load = lambda p: json.loads(p.read_text())
    try:
        result = validate_report(load(args.report), args.article.read_text(), prior=load(args.prior) if args.prior else None,
                                 fingerprints=load(args.fingerprints) if args.fingerprints else None)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open('x') as stream:
                stream.write(rendered)
        else:
            print(rendered, end='')
    except (QAError, OSError, ValueError) as exc:
        parser.exit(1, 'QA registry BLOCK: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
