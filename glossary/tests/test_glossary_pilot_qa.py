"""Deterministic registry contracts; content truth remains independent QA's job."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import glossary_pilot_qa as qa

ARTICLE = '## Meaning\nThe gross amount is owed minus paid.\n\n### Timing\nCheck the applicable entitlement date.\n'
REPAIRED = '## Meaning\nThe gross amount is the gross owed minus gross paid.\n\n### Timing\nCheck the applicable entitlement date.\n'


def fingerprints(article=ARTICLE):
    result = {k: hashlib.sha256(k.encode()).hexdigest() for k in qa.REQUIRED_FINGERPRINTS}
    result['article_sha256'] = hashlib.sha256(article.encode()).hexdigest()
    result['evidence.md'] = hashlib.sha256(b'evidence').hexdigest()
    return result


def finding(fid='Q-001', missing=False, severity='major'):
    value = {'id': fid, 'severity': severity, 'category': 'coverage', 'rule_id': 'GLOSSARY-DEPTH',
             'unit_ids': ['meaning-01'], 'contract_ids': ['C-01'], 'hybrid_ids': ['H-01'],
             'evidence_ids': ['PAY-01'], 'description': 'Explain the gross calculation explicitly.',
             'acceptance_condition': 'State gross owed minus gross paid, keeping net payment separate.'}
    if missing:
        value['coverage_anchor'] = {'heading': '## Meaning', 'contract_id': 'C-01', 'description': 'Gross basis missing.'}
    else:
        value['passage'] = 'The gross amount is owed minus paid.'
    return value


def report(article=ARTICLE, findings=None):
    return {'protocol_version': 1, 'term': 'Wage Arrears', 'arm': 'b', 'stage': 'raw', 'round': 0,
            'base_draft_sha256': hashlib.sha256(ARTICLE.encode()).hexdigest(), 'Verdict': 'BLOCK',
            'fingerprints': fingerprints(article), 'findings': [finding()] if findings is None else findings,
            'decisions': []}


def recheck(prior, article=REPAIRED, status='resolved'):
    value = report(article, findings=[])
    value.update(stage='recheck', round=prior['round'] + 1, Verdict='PASS', parent_review_sha256=prior['review_sha256'])
    value['decisions'] = [{'id': 'Q-001', 'status': status, 'explanation': 'The calculation now explicitly uses gross amounts.',
                           'passage': 'The gross amount is the gross owed minus gross paid.'}]
    return value


class RegistryTests(unittest.TestCase):
    def test_initial_preserves_verdict_fingerprints_and_has_deterministic_seals(self):
        source = report()
        sealed = qa.validate_report(source, ARTICLE, fingerprints=fingerprints())
        self.assertNotIn('registry', source)
        self.assertEqual(sealed['Verdict'], 'BLOCK')
        self.assertEqual(sealed['fingerprints'], source['fingerprints'])
        self.assertEqual(sealed['registry'][0]['status'], 'open')
        self.assertEqual(qa.validate_report(sealed, ARTICLE), sealed)
        qa.verify_seal(sealed)

    def test_pass_rejects_open_major_but_optional_polish_is_not_blocker(self):
        value = report(); value['Verdict'] = 'PASS'
        with self.assertRaisesRegex(qa.QAError, 'open blockers'): qa.validate_report(value, ARTICLE)
        value['findings'][0]['severity'] = 'minor'
        self.assertEqual(qa.validate_report(value, ARTICLE)['Verdict'], 'PASS')
        value['findings'] = []
        self.assertEqual(qa.validate_report(value, ARTICLE)['registry'], [])

    def test_quote_must_be_exact_and_missing_coverage_needs_real_heading_contract(self):
        value = report(); value['findings'][0]['passage'] = 'An invented sentence.'
        with self.assertRaisesRegex(qa.QAError, 'absent'): qa.validate_report(value, ARTICLE)
        value['findings'] = [finding(missing=True)]
        qa.validate_report(value, ARTICLE)
        for field, bad in (('heading', '## Invented'), ('contract_id', 'C-unknown'), ('description', '')):
            changed = copy.deepcopy(value); changed['findings'][0]['coverage_anchor'][field] = bad
            with self.subTest(field=field), self.assertRaises(qa.QAError): qa.validate_report(changed, ARTICLE)

    def test_initial_unique_canonical_ids_and_scope_arrays(self):
        for change in ('duplicate', 'critic-id', 'empty-unit', 'missing-condition'):
            value = report()
            if change == 'duplicate': value['findings'].append(finding())
            if change == 'critic-id': value['findings'][0]['id'] = 'K-001'
            if change == 'empty-unit': value['findings'][0]['unit_ids'] = []
            if change == 'missing-condition': del value['findings'][0]['acceptance_condition']
            with self.subTest(change=change), self.assertRaises(qa.QAError): qa.validate_report(value, ARTICLE)

    def test_current_article_and_external_fingerprints_bound(self):
        value = report()
        with self.assertRaisesRegex(qa.QAError, 'article fingerprint'): qa.validate_report(value, REPAIRED)
        bad = fingerprints(); bad['meta_sha256'] = '0' * 64
        with self.assertRaisesRegex(qa.QAError, 'independent'): qa.validate_report(value, ARTICLE, fingerprints=bad)
        for field in qa.REQUIRED_FINGERPRINTS:
            changed = copy.deepcopy(value); del changed['fingerprints'][field]
            with self.subTest(field=field), self.assertRaises(qa.QAError): qa.validate_report(changed, ARTICLE)

    def test_recheck_resolves_and_inherits_original_condition_and_old_quote(self):
        first = qa.validate_report(report(), ARTICLE)
        second = qa.validate_report(recheck(first), REPAIRED, prior=first)
        self.assertEqual(second['registry'][0]['status'], 'resolved')
        self.assertEqual(second['registry'][0]['acceptance_condition'], first['registry'][0]['acceptance_condition'])
        self.assertEqual(second['registry'][0]['passage'], first['registry'][0]['passage'])
        self.assertEqual(second['findings'], [])
        self.assertEqual(second['parent_review_sha256'], first['review_sha256'])

    def test_every_prior_id_including_closed_requires_current_decision(self):
        first = qa.validate_report(report(), ARTICLE)
        second = qa.validate_report(recheck(first), REPAIRED, prior=first)
        third = recheck(second)
        third['decisions'] = []
        with self.assertRaisesRegex(qa.QAError, 'each prior ID'): qa.validate_report(third, REPAIRED, prior=second)
        third['decisions'] = copy.deepcopy(second['decisions'])
        self.assertEqual(qa.validate_report(third, REPAIRED, prior=second)['registry'][0]['status'], 'resolved')

    def test_no_rewrite_of_prior_acceptance_condition_or_rule(self):
        first = qa.validate_report(report(), ARTICLE)
        for field in ('acceptance_condition', 'rule_id', 'severity'):
            value = recheck(first)
            value['findings'] = [finding()]
            value['findings'][0][field] = 'changed'
            with self.subTest(field=field), self.assertRaisesRegex(qa.QAError, 'changed original'):
                qa.validate_report(value, REPAIRED, prior=first)

    def test_reversal_requires_reason_and_explicit_reopened(self):
        first = qa.validate_report(report(), ARTICLE)
        second = qa.validate_report(recheck(first), REPAIRED, prior=first)
        third = recheck(second, status='reopened'); third['Verdict'] = 'BLOCK'
        with self.assertRaisesRegex(qa.QAError, 'reversal_reason'): qa.validate_report(third, REPAIRED, prior=second)
        third['decisions'][0]['reversal_reason'] = 'Prior acceptance missed a net/gross ambiguity.'
        self.assertEqual(qa.validate_report(third, REPAIRED, prior=second)['registry'][0]['status'], 'reopened')
        third['decisions'][0]['status'] = 'open'
        with self.assertRaisesRegex(qa.QAError, 'must use reopened'): qa.validate_report(third, REPAIRED, prior=second)

    def test_withdrawal_needs_reason_and_is_retained_in_later_rounds(self):
        first = qa.validate_report(report(), ARTICLE)
        value = recheck(first, status='withdrawn'); del value['decisions'][0]['passage']
        with self.assertRaisesRegex(qa.QAError, 'reversal_reason'): qa.validate_report(value, REPAIRED, prior=first)
        value['decisions'][0]['reversal_reason'] = 'The original condition did not match the scoped rule.'
        sealed = qa.validate_report(value, REPAIRED, prior=first)
        self.assertEqual(sealed['registry'][0]['status'], 'withdrawn')

    def test_new_findings_retained_with_earlier_resolved_items(self):
        first = qa.validate_report(report(), ARTICLE)
        value = recheck(first)
        new = finding('Q-002', missing=True)
        value['findings'] = [new]; value['Verdict'] = 'BLOCK'
        second = qa.validate_report(value, REPAIRED, prior=first)
        self.assertEqual([(x['id'], x['status']) for x in second['registry']], [('Q-001', 'resolved'), ('Q-002', 'open')])

    def test_parent_hash_branch_round_materials_and_fingerprint_fields_bound(self):
        first = qa.validate_report(report(), ARTICLE)
        for change in ('parent', 'arm', 'term', 'base', 'round', 'materials', 'fields'):
            value = recheck(first)
            if change == 'parent': value['parent_review_sha256'] = '0' * 64
            if change in ('arm', 'term'): value[change] = 'different'
            if change == 'base': value['base_draft_sha256'] = '0' * 64
            if change == 'round': value['round'] = first['round']
            if change == 'materials': value['fingerprints']['materials_sha256'] = '0' * 64
            if change == 'fields': del value['fingerprints']['evidence.md']
            with self.subTest(change=change), self.assertRaises(qa.QAError): qa.validate_report(value, REPAIRED, prior=first)

    def test_seal_detects_altered_prior_registry_and_supplied_hashes(self):
        first = qa.validate_report(report(), ARTICLE)
        altered = copy.deepcopy(first); altered['registry'][0]['acceptance_condition'] = 'weakened'
        with self.assertRaisesRegex(qa.QAError, 'hash mismatch'): qa.validate_report(recheck(first), REPAIRED, prior=altered)
        first['decisions_sha256'] = '0' * 64
        with self.assertRaisesRegex(qa.QAError, 'mismatch'): qa.validate_report(first, ARTICLE)

    def test_hashes_are_independent_of_finding_and_decision_order(self):
        value = report(findings=[finding('Q-002'), finding('Q-001')])
        one = qa.validate_report(value, ARTICLE)
        value['findings'].reverse()
        self.assertEqual(qa.validate_report(value, ARTICLE), one)
        next_value = recheck(one); next_value['Verdict'] = 'PASS'
        next_value['decisions'].append({**next_value['decisions'][0], 'id': 'Q-002'})
        two = qa.validate_report(next_value, REPAIRED, prior=one)
        next_value['decisions'].reverse()
        self.assertEqual(qa.validate_report(next_value, REPAIRED, prior=one), two)

    def test_cli_writes_new_file_and_refuses_overwrite(self):
        script = Path(qa.__file__)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); article = root / 'article.md'; source = root / 'review.json'; dest = root / 'sealed.json'
            article.write_text(ARTICLE); source.write_text(json.dumps(report()))
            cmd = [sys.executable, str(script), '--report', str(source), '--article', str(article), '--out', str(dest)]
            first = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            before = dest.read_bytes(); second = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(dest.read_bytes(), before)
            self.assertEqual(json.loads(before)['Verdict'], 'BLOCK')


if __name__ == '__main__': unittest.main()
