"""Executor safety contracts. No network, key file, paid request, or production writes."""
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import openrouter_pilot as pilot

PROJECT = Path(__file__).resolve().parents[1]
FAKE_KEY = 'sk-or-test-only-not-a-real-credential'


def routing():
    return {'model': 'minimax/minimax-m3.1-flash',
            'expected_canonical_slug': 'minimax/minimax-m3.1-flash-20261019',
            'expected_provider_name': 'Minimax', 'provider_only': ['minimax'],
            'reasoning': {'effort': 'low', 'exclude': True}}


def endpoint():
    return {'tag': 'minimax', 'status': 0, 'provider_name': 'Minimax',
            'name': 'Minimax | minimax/minimax-m3.1-flash-20261019',
            'supported_parameters': ['reasoning', 'temperature', 'max_tokens'],
            'pricing': {'prompt': '0.000000075', 'completion': '0.0000003',
                        'overrides': [{'prompt': '0.00000015', 'completion': '0.0000006'}]}}


class PureContracts(unittest.TestCase):
    def test_unique_glossary_label_ignores_generic_and_geo(self):
        text = 'OPENROUTER_KEY=sk-or-generic\nGEO=sk-or-geo\n# glossary production\n'
        with self.assertRaises(pilot.PilotError):
            pilot.key_from(text)
        self.assertEqual(pilot.key_from(text + 'glossary: sk-or-glossary\n'), 'sk-or-glossary')
        self.assertEqual(pilot.key_from('глоссарий: sk-or-russian'), 'sk-or-russian')
        for bad in (text + 'glossary sk-or-a sk-or-b', text + 'glossary sk-or-a\nglossary sk-or-b'):
            with self.subTest(bad=bad), self.assertRaises(pilot.PilotError):
                pilot.key_from(bad)

    def test_explicit_glossary_environment_key_has_priority_and_shape(self):
        self.assertEqual(pilot.key_from('glossary sk-or-a\nglossary sk-or-b', FAKE_KEY), FAKE_KEY)
        with self.assertRaises(pilot.PilotError):
            pilot.key_from('glossary sk-or-valid', 'not-an-openrouter-key')

    def test_explicit_environment_key_does_not_depend_on_secret_file(self):
        with tempfile.TemporaryDirectory() as td, patch.object(pilot, 'KEY_FILE', Path(td) / 'missing.env'), patch.dict(pilot.os.environ, {'OPENROUTER_GLOSSARY_API_KEY': FAKE_KEY}):
            self.assertEqual(pilot.glossary_key(), FAKE_KEY)

    def test_technical_output_ceiling_cannot_disable_budget_reservation(self):
        for tokens in (0, -1, True, 1.5):
            with self.subTest(tokens=tokens), self.assertRaises(pilot.PilotError):
                pilot.request(routing(), [], tokens)

    def test_recursive_redaction(self):
        result = pilot.redact({'a': [FAKE_KEY, {'error': 'Bearer ' + FAKE_KEY}], 'n': 1})
        self.assertNotIn(FAKE_KEY, json.dumps(result))
        self.assertEqual(result['n'], 1)

    def test_request_pins_single_route_without_fallbacks_or_plugins(self):
        payload = pilot.request(routing(), [{'role': 'user', 'content': 'write'}], 32)
        self.assertEqual(payload['provider'], {'only': ['minimax'], 'allow_fallbacks': False, 'require_parameters': True})
        self.assertEqual(payload['reasoning'], {'effort': 'low', 'exclude': True})
        for field in ('models', 'plugins', 'tools', 'seed'):
            self.assertNotIn(field, payload)
        for family in ('openai', 'google', 'anthropic'):
            route = routing(); route['model'] = family + '/forbidden'
            with self.subTest(family=family), self.assertRaises(pilot.PilotError):
                pilot.request(route, [], 32)

    def test_multiple_pinned_endpoints_rejected(self):
        route = routing(); route['provider_only'] = ['minimax', 'other/variant']
        with self.assertRaises(pilot.PilotError):
            pilot.request(route, [], 32)

    def test_secret_shaped_prompt_rejected(self):
        with self.assertRaises(pilot.PilotError):
            pilot.request(routing(), [{'role': 'user', 'content': FAKE_KEY}], 32)

    def test_worst_live_tariff_reservation_without_cache_discount(self):
        payload = pilot.request(routing(), [{'role': 'user', 'content': 'é'}], 1000)
        self.assertAlmostEqual(pilot.reservation(payload, endpoint()), (2 + 128 + 256) * .00000015 + 1000 * .0000006)

    def test_mocked_catalog_canonical_and_endpoint_drift(self):
        model = {'id': routing()['model'], 'canonical_slug': routing()['expected_canonical_slug']}
        for change in ('canonical', 'tag', 'provider', 'version', 'status', 'parameters', None):
            m, ep = copy.deepcopy(model), endpoint()
            if change == 'canonical': m['canonical_slug'] = 'unapproved-version'
            if change == 'tag': ep['tag'] = 'other/variant'
            if change == 'provider': ep['provider_name'] = 'other'
            if change == 'version': ep['name'] = 'unapproved-version'
            if change == 'status': ep['status'] = 1
            if change == 'parameters': ep['supported_parameters'].remove('reasoning')
            with self.subTest(change=change), patch.object(pilot, 'http', side_effect=[(200, {'data': [m]}), (200, {'data': {'endpoints': [ep]}})]):
                if change is None:
                    self.assertEqual(pilot.preflight(routing())['endpoint'], ep)
                else:
                    with self.assertRaises(pilot.PilotError): pilot.preflight(routing())


class IsolatedExecutor(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.jobs = ['term-one', 'term-two']
        self.job = self.root / 'jobs' / self.jobs[0]
        self.job.mkdir(parents=True)
        for key, value in {'ROOT': self.root, 'EXP': self.root / 'experiment', 'JOBS': self.jobs}.items():
            p = patch.object(pilot, key, value); p.start(); self.addCleanup(p.stop)
        key_patch = patch.object(pilot, 'glossary_key', return_value=FAKE_KEY)
        key_patch.start(); self.addCleanup(key_patch.stop)
        self.out = redirect_stdout(io.StringIO()); self.out.__enter__(); self.addCleanup(self.out.__exit__, None, None, None)
        self.transport = Mock(return_value=(200, {'id': 'gen-test', 'model': routing()['model'], 'provider': 'Minimax',
            'usage': {'cost': .01}, 'choices': [{'message': {'content': '## Body\nUseful answer.\n'}, 'finish_reason': 'stop'}]}))
        self.check = Mock(return_value={'at': 'test', 'endpoint': endpoint()})

    def call(self, call_id='write-one', **kw):
        opts = dict(execute=True, transport=self.transport, check=self.check, max_tokens=100)
        opts.update(kw)
        return pilot.call(self.job, call_id, routing(), [{'role': 'user', 'content': 'write'}], **opts)

    def prior(self, *, cost=.1, pending=False):
        d = self.root / 'jobs' / self.jobs[1] / 'pilot/api/old-call/attempt-001'
        pilot.write(d / 'intent.json', {'reserved_usd': .5})
        if not pending: pilot.write(d / 'receipt.json', {'cost_usd': cost, 'status': 'failed'})

    def test_global_settled_cost_blocks_before_transport(self):
        self.prior(cost=2.99999)
        with self.assertRaisesRegex(pilot.PilotError, 'budget'): self.call()
        self.transport.assert_not_called()
        self.assertEqual(pilot.usage()['cost_usd'], 2.99999)

    def test_continuation_jobs_share_prior_round_budget(self):
        self.prior(cost=2.99999)
        more = self.jobs + ['continuation-one', 'continuation-two']
        later = self.root / 'jobs' / more[2]
        later.mkdir(parents=True)
        with patch.object(pilot, 'JOBS', more):
            with self.assertRaisesRegex(pilot.PilotError, 'budget'):
                pilot.call(later, 'writer-metadata', routing(), [{'role': 'user', 'content': 'write'}],
                           execute=True, transport=self.transport, check=self.check, max_tokens=100)
            self.assertEqual(pilot.usage()['cost_usd'], 2.99999)
            self.assertEqual(pilot.usage()['attempts'], 1)
        self.transport.assert_not_called()
        self.assertFalse((later / 'pilot/api/writer-metadata').exists())

    def test_freeze_rejects_invalid_materials_or_unresolved_source_ids(self):
        pilot.write(self.job / 'pilot/input-status.json', {'status': 'ready'})
        (self.job / 'evidence.md').write_text('### Claim FACT-01\n- **Verdict:** supports.\n- **Article link:** required.\n')
        for errors, expected in [(['visual invalid caption'], 'visual invalid caption'), ([], 'directly resolved')]:
            with self.subTest(errors=errors), patch('glossary_materials.validate', return_value=errors):
                with self.assertRaisesRegex(pilot.PilotError, expected):
                    pilot.freeze(self.job)
                self.assertFalse((self.job / 'pilot/frozen').exists())

    def test_round_two_disallows_api_critic_before_reading_inputs(self):
        with self.assertRaisesRegex(pilot.PilotError, 'no critic stage'):
            pilot.critique(self.root / 'jobs' / pilot.ROUND2_JOBS[0], 'kimi', execute=True)
        self.transport.assert_not_called()

    def test_unknown_and_pending_charges_in_other_term_block(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                self.prior(cost=None, pending=pending)
                if pending:
                    receipt = self.root / 'jobs' / self.jobs[1] / 'pilot/api/old-call/attempt-001/receipt.json'
                    receipt.unlink(missing_ok=True)
                with self.assertRaisesRegex(pilot.PilotError, 'Unreconciled'): self.call()
        self.transport.assert_not_called(); self.check.assert_not_called()

    def test_timeout_has_one_post_and_blocks_implicit_or_explicit_retry_until_reconciled(self):
        self.transport.side_effect = TimeoutError('ambiguous timeout ' + FAKE_KEY)
        with self.assertRaises(pilot.PilotError): self.call()
        self.assertEqual(self.transport.call_count, 1)
        receipt = pilot.read(self.job / 'pilot/api/write-one/attempt-001/receipt.json')
        self.assertIsNone(receipt['cost_usd'])
        self.assertNotIn(FAKE_KEY, json.dumps(receipt))
        for retry in (False, True):
            with self.assertRaises(pilot.PilotError): self.call(retry=retry)
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(pilot.usage()['unknown_cost_attempts'], 1)

    def test_complete_resume_is_offline_and_bound_to_payload_and_output(self):
        answer = self.call()
        self.assertEqual(self.call(), answer)
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(self.check.call_count, 1)
        with self.assertRaisesRegex(pilot.PilotError, 'Changed request'):
            self.call(max_tokens=101)
        p = self.job / 'pilot/api/write-one/attempt-001/content.txt'
        p.write_text('tampered')
        with self.assertRaisesRegex(pilot.PilotError, 'output changed'): self.call()

    def test_complete_resume_rejects_changed_route_manifest(self):
        self.call()
        changed = routing(); changed['expected_canonical_slug'] = 'minimax/unapproved'
        with self.assertRaises(pilot.PilotError):
            pilot.call(self.job, 'write-one', changed, [{'role': 'user', 'content': 'write'}], max_tokens=100)

    def test_model_returned_secret_is_redacted_in_every_retained_artifact(self):
        self.transport.return_value[1]['choices'][0]['message']['content'] = 'Example ' + FAKE_KEY
        answer = self.call()
        self.assertNotIn(FAKE_KEY, answer)
        for artifact in self.root.rglob('*'):
            if artifact.is_file():
                self.assertNotIn(FAKE_KEY, artifact.read_text(), str(artifact))

    def test_removed_structured_output_support_stops_before_post_or_intent(self):
        # The pinned route still accepts reasoning/temp/max_tokens, but no
        # longer advertises the response_format used by this exact request.
        self.assertNotIn('response_format', self.check.return_value['endpoint']['supported_parameters'])
        with self.assertRaisesRegex(pilot.PilotError, 'structured output'):
            self.call(structured=True)
        self.check.assert_called_once()
        self.transport.assert_not_called()
        self.assertFalse((self.job / 'pilot/api').exists())
        self.assertEqual(pilot.usage()['attempts'], 0)

    def writer_fixture(self, metadata_responses):
        pilot.write(self.job / 'request.json', {'term': 'Wage Arrears', 'slug': 'wage-arrears-example'})
        rows = [{'id': 'meaning-01', 'section_id': 'meaning', 'heading': 'Meaning',
                 'required_headings': ['## Meaning'], 'first_in_h2': True}]
        self.check.return_value['endpoint']['supported_parameters'].append('response_format')
        response_contents = [json.dumps(x) for x in metadata_responses] + ['## Meaning\nGross owed minus gross paid.\n']
        captured = []

        def respond(url, key, payload, **kwargs):
            captured.append(copy.deepcopy(payload))
            n = len(captured) - 1
            response = copy.deepcopy(self.transport_template)
            response.update(id='gen-fixture-' + str(n), usage={'cost': .01 * (n + 1)})
            response['choices'][0]['message']['content'] = response_contents[n]
            return 200, response

        self.transport_template = copy.deepcopy(self.transport.return_value[1])
        self.transport.side_effect = respond
        original_call = pilot.call

        def isolated_call(*args, **kwargs):
            kwargs.setdefault('transport', self.transport)
            kwargs.setdefault('check', self.check)
            return original_call(*args, **kwargs)

        patches = [patch.object(pilot, 'messages', side_effect=lambda job: [{'role': 'system', 'content': 'Frozen verified inputs.'}]),
                   patch.object(pilot, 'route', return_value=routing()),
                   patch.object(pilot, 'units', return_value=rows),
                   patch.object(pilot, 'call', side_effect=isolated_call)]
        for p in patches:
            p.start(); self.addCleanup(p.stop)
        return captured

    def test_invalid_metadata_keeps_first_response_then_new_call_corrects_in_same_history(self):
        invalid = {'definition': 'x' * 354, 'metaTitle': 'Wage Arrears', 'metaDescription': 'How wage arrears work.'}
        valid = {**invalid, 'definition': 'Gross wages owed for an earlier period.'}
        captured = self.writer_fixture([invalid, valid])
        pilot.writer(self.job, execute=True)
        arm = self.job / 'pilot/arms/a'
        self.assertEqual(pilot.read(arm / 'metadata-first-response.json')['definition'], invalid['definition'])
        self.assertEqual(pilot.read(arm / 'meta.json')['definition'], valid['definition'])
        call_ids = sorted(p.name for p in (self.job / 'pilot/api').iterdir())
        self.assertEqual(call_ids, ['writer-meaning-01', 'writer-metadata', 'writer-metadata-format-01'])
        self.assertEqual(self.transport.call_count, 3)
        self.assertEqual(captured[1]['messages'][-2], {'role': 'assistant', 'content': json.dumps(invalid)})
        self.assertIn('354', captured[1]['messages'][-1]['content'])
        self.assertIn('limit 300', captured[1]['messages'][-1]['content'])
        self.assertTrue(any(x['role'] == 'assistant' and x['content'] == json.dumps(valid) for x in captured[2]['messages']))
        history = pilot.read(arm / 'history.json')
        self.assertTrue(any(x['content'] == json.dumps(invalid) for x in history))
        self.assertTrue(any(x['content'] == json.dumps(valid) for x in history))
        summary = pilot.usage()
        self.assertEqual(summary['attempts'], 3)
        self.assertAlmostEqual(summary['cost_usd'], .06)
        self.assertEqual(summary['unknown_cost_attempts'], 0)
        # All successful API responses count, including the format-invalid one.
        # The next paid request must reserve against that full settled total.
        with patch.object(pilot, 'CAP', .06001), self.assertRaisesRegex(pilot.PilotError, 'budget'):
            self.call(call_id='next-paid-call')
        self.assertEqual(self.transport.call_count, 3)
        self.assertFalse((self.job / 'pilot/api/next-paid-call').exists())

    def test_metadata_format_corrections_stop_after_two_and_all_costs_remain(self):
        invalid = {'definition': 'x' * 354, 'metaTitle': 'Wage Arrears', 'metaDescription': 'How wage arrears work.'}
        self.writer_fixture([invalid, invalid, invalid])
        with self.assertRaisesRegex(ValueError, '354 characters; limit 300'):
            pilot.writer(self.job, execute=True)
        self.assertEqual(self.transport.call_count, 3)
        ids = sorted(p.name for p in (self.job / 'pilot/api').iterdir())
        self.assertEqual(ids, ['writer-metadata', 'writer-metadata-format-01', 'writer-metadata-format-02'])
        self.assertAlmostEqual(pilot.usage()['cost_usd'], .06)
        self.assertEqual(pilot.usage()['attempts'], 3)
        arm = self.job / 'pilot/arms/a'
        self.assertEqual(pilot.read(arm / 'metadata-first-response.json')['definition'], invalid['definition'])
        self.assertFalse((arm / 'meta.json').exists())
        self.assertFalse((arm / 'assembled.md').exists())

    def test_heading_correction_uses_one_new_call_keeps_original_context_and_all_costs(self):
        unit = {'id': 'calculation-02', 'required_headings': ['### Calculate the difference']}
        invalid = '### Calculate the difference\n#### Unplanned example\nGross owed minus gross paid; retain the example.\n'
        corrected = '### Calculate the difference\nUnplanned example: gross owed minus gross paid; retain the example.\n'
        original_call = pilot.call
        captured = []
        template = copy.deepcopy(self.transport.return_value[1])
        responses = [invalid, corrected, invalid, invalid]

        def respond(url, key, payload, **kwargs):
            captured.append(copy.deepcopy(payload))
            response = copy.deepcopy(template)
            response.update(id='gen-heading-' + str(len(captured)), usage={'cost': .01})
            response['choices'][0]['message']['content'] = responses[len(captured) - 1]
            return 200, response

        def isolated_call(*args, **kwargs):
            kwargs.setdefault('transport', self.transport)
            kwargs.setdefault('check', self.check)
            return original_call(*args, **kwargs)

        self.transport.side_effect = respond
        with patch.object(pilot, 'call', side_effect=isolated_call):
            for case in ('corrected', 'still-invalid'):
                history = [{'role': 'system', 'content': 'Frozen evidence.'},
                           {'role': 'user', 'content': 'Write the calculation unit.'}]
                call_id = 'writer-calculation-' + case
                with self.subTest(case=case):
                    if case == 'corrected':
                        answer = pilot.unit_answer(self.job, call_id, routing(), history, unit, execute=True, retry=False)
                        self.assertEqual(answer, corrected)
                        pilot.check_unit(pilot.clean_markdown(answer), unit)
                    else:
                        with self.assertRaisesRegex(pilot.PilotError, 'Heading contract mismatch'):
                            pilot.unit_answer(self.job, call_id, routing(), history, unit, execute=True, retry=False)
                    self.assertEqual(history[-2], {'role': 'assistant', 'content': invalid})
                    self.assertIn('Preserve useful explanations, examples, qualifications and links', history[-1]['content'])
                    self.assertIn(json.dumps(unit['required_headings']), history[-1]['content'])
                    base = self.job / 'pilot/api' / call_id
                    correction = self.job / 'pilot/api' / (call_id + '-format-01')
                    self.assertEqual((base / 'attempt-001/content.txt').read_text(), invalid)
                    self.assertTrue((correction / 'attempt-001/receipt.json').exists())
                    self.assertFalse((self.job / 'pilot/api' / (call_id + '-format-02')).exists())
            self.assertEqual(self.transport.call_count, 4)
            self.assertEqual(pilot.usage()['attempts'], 4)
            self.assertAlmostEqual(pilot.usage()['cost_usd'], .04)
            for request in (captured[1], captured[3]):
                self.assertEqual(request['messages'][-2]['content'], invalid)
                self.assertIn('Deterministic heading validation failed', request['messages'][-1]['content'])
            with patch.object(pilot, 'CAP', .04001), self.assertRaisesRegex(pilot.PilotError, 'budget'):
                self.call(call_id='after-heading-corrections')
            self.assertEqual(self.transport.call_count, 4)

    def test_dry_run_makes_no_network_or_attempt(self):
        self.assertIsNone(self.call(execute=False))
        self.transport.assert_not_called(); self.check.assert_not_called()
        self.assertFalse((self.job / 'pilot/api').exists())

    def test_mocked_response_unknown_cost_and_model_mismatch_never_complete(self):
        for kind in ('cost', 'model', 'provider', 'truncation'):
            data = copy.deepcopy(self.transport.return_value[1])
            if kind == 'cost': data['usage'] = {}
            if kind == 'model': data['model'] = 'other/model'
            if kind == 'provider': data['provider'] = 'Other provider'
            if kind == 'truncation': data['choices'][0]['finish_reason'] = 'length'
            self.transport.return_value = (200, data)
            with self.subTest(kind=kind), self.assertRaises(pilot.PilotError): self.call(call_id='bad-' + kind)
            self.assertFalse((self.job / ('pilot/api/bad-' + kind) / 'success.json').exists())
            # Deliberately reconcile fixture so other independent cases can execute.
            receipt = self.job / ('pilot/api/bad-' + kind) / 'attempt-001/receipt.json'
            if receipt.exists():
                result = pilot.read(receipt); result['cost_usd'] = .01; pilot.write(receipt, result)

    def test_writer_hierarchy_is_nine_plus_ten_and_keeps_all_h4_children(self):
        sources = [('outline-9-units', 9, 0), ('outline-10-units', 10, 8)]
        for source, count, h4 in sources:
            shutil.copyfile(PROJECT / 'tests' / 'fixtures' / (source + '.sections.json'), self.job / 'sections.json')
            rows = pilot.units(self.job)
            self.assertEqual(len(rows), count)
            headings = [h for unit in rows for h in unit['required_headings']]
            self.assertEqual(sum(h.startswith('## ') for h in headings), 5)
            self.assertEqual(sum(h.startswith('#### ') for h in headings), h4)
            self.assertEqual(len({u['id'] for u in rows}), count)
            for unit in rows:
                pilot.check_unit('\n'.join(unit['required_headings']) + '\nanswer', unit)
                with self.assertRaises(pilot.PilotError):
                    pilot.check_unit('\n'.join(unit['required_headings']) + '\n### Unexpected', unit)

    def test_continuation_writer_units_preserve_both_full_outlines(self):
        for source, count, h4 in [('outline-13-units', 13, 2), ('outline-15-units', 15, 5)]:
            with self.subTest(source=source):
                shutil.copyfile(PROJECT / 'tests' / 'fixtures' / (source + '.sections.json'), self.job / 'sections.json')
                rows = pilot.units(self.job)
                headings = [h for unit in rows for h in unit['required_headings']]
                self.assertEqual(len(rows), count)
                self.assertEqual(sum(h.startswith('## ') for h in headings), 6)
                self.assertEqual(sum(h.startswith('#### ') for h in headings), h4)
                self.assertEqual(len({u['id'] for u in rows}), count)


if __name__ == '__main__': unittest.main()
