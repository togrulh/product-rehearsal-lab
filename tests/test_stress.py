import json
import unittest
from copy import deepcopy

import rehearsal


CHOICES = {'monthly': 'Monthly billing', 'annual': 'Annual billing', 'unsure': 'Not enough information'}
SCENARIO = {
    'language': 'en', 'question': 'Which billing option would you choose?',
    'conditions': {'monthly_price': 10, 'annual_price': 120},
    'stress_test': {'kind': 'order', 'choices': CHOICES},
}


class StressTests(unittest.TestCase):
    def setUp(self):
        self.scenario = deepcopy(SCENARIO)
        self.panel = [{'agent': f'A{i:03}', 'segment': 'trial' if i < 3 else 'active',
                       'facts': {'activity.days': {'value': i}}} for i in range(1, 4)]

    def test_order_control_holds_terms_and_compares_only_complete_triples(self):
        calls = {}

        def voice(payload):
            self.assertEqual(payload['question'], SCENARIO['question'])
            self.assertEqual(payload['conditions'], SCENARIO['conditions'])
            self.assertEqual(payload['history'], [])
            self.assertNotIn('arm', payload)
            self.assertEqual(payload['choices'], CHOICES)
            i = payload['facts']['activity.days']['value']
            orders = calls.setdefault(i, [])
            order = list(payload['choices'])
            self.assertEqual(order[-1], 'unsure')
            orders.append(order)
            choice = 'invalid' if i == 3 and order[0] == 'annual' else order[0]
            return {'answer': 'Fictional response.', 'evidence_keys': [], 'choice': choice}

        result = rehearsal.stress_panel(self.panel, self.scenario, voice, include_replies=True)
        self.assertEqual(result['coverage'], {'eligible': 3, 'reference_valid': 3, 'repeat_valid': 3, 'perturbed_valid': 2, 'matched': 2})
        self.assertEqual(result['repeat_switches'], 0)
        self.assertEqual(result['perturbation_switches'], 2)
        self.assertEqual(result['excess_switch_percentage_points'], 100)
        self.assertEqual(result['by_segment']['active']['coverage']['matched'], 0)
        self.assertIsNone(result['by_segment']['active']['excess_switch_percentage_points'])
        self.assertEqual(calls[1], [['monthly', 'annual', 'unsure'], ['monthly', 'annual', 'unsure'], ['annual', 'monthly', 'unsure']])
        self.assertEqual(calls[2], [['annual', 'monthly', 'unsure'], ['monthly', 'annual', 'unsure'], ['annual', 'monthly', 'unsure']])
        self.assertEqual(result['trials'][2]['perturbed']['status'], 'invalid_choice')
        self.assertEqual(self.scenario, SCENARIO)

    def test_framing_changes_only_question_and_reports_repeat_instability(self):
        variant = 'How would you prefer to pay for the same product?'
        self.scenario['stress_test'] = {'kind': 'framing', 'question': variant, 'choices': CHOICES}
        calls = []
        picks = iter(('monthly', 'annual', 'monthly'))

        def voice(payload):
            calls.append(payload)
            return {'answer': 'Fictional response.', 'evidence_keys': [], 'choice': next(picks)}

        report = rehearsal.stress_panel(self.panel[:1], self.scenario, voice, include_replies=False)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(calls[2], {**calls[0], 'question': variant})
        self.assertEqual(report['repeat_switches'], 1)
        self.assertEqual(report['perturbation_switches'], 0)
        self.assertEqual(report['excess_switch_percentage_points'], -100)
        self.assertNotIn('trials', report)
        self.assertNotIn('Fictional response.', json.dumps(report))

    def test_rejects_no_op_framing_and_combined_interventions(self):
        for update in (
            {'stress_test': {'kind': 'framing', 'question': SCENARIO['question'].lower(), 'choices': CHOICES}},
            {'stress_test': {'kind': 'order', 'question': 'Other question?', 'choices': CHOICES}},
            {'comparison': {}},
            {'followups': [{'question': 'Why?'}]},
        ):
            with self.subTest(update=update), self.assertRaises(rehearsal.LabError):
                rehearsal.stress_panel(self.panel, {**self.scenario, **update}, lambda _: self.fail('model called'))

    def test_schema_order_does_not_follow_display_order(self):
        class Voice(rehearsal.OllamaVoice):
            def request(self, path, body=None):
                self.body = body
                return {'model': self.model, 'done_reason': 'stop', 'message': {'content': '{"answer":"Maybe.","choice":"unsure","evidence_keys":[]}'}}

        voice = Voice('test:local')
        orders = [CHOICES, dict(reversed(list(CHOICES.items())))]
        schemas = []
        for options in orders:
            voice({'facts': {}, 'choices': options})
            schemas.append(voice.body['format'])
            self.assertEqual(list(json.loads(voice.body['messages'][-1]['content'])['choices']), list(options))
        self.assertEqual(schemas[0], schemas[1])

    def test_full_block_crosses_every_call_order_with_each_reference_rotation(self):
        from collections import Counter
        from itertools import permutations

        choices = {**CHOICES, 'quarterly': 'Quarterly billing'}
        scenario = {**SCENARIO, 'stress_test': {'kind': 'order', 'choices': choices}}
        panel = [{'agent': str(i), 'segment': 'all', 'facts': {}} for i in range(18)]
        actual = []

        def voice(payload):
            actual.append(tuple(payload['choices']))
            return {'answer': 'Fictional response.', 'evidence_keys': [], 'choice': 'unsure'}

        report = rehearsal.stress_panel(panel, scenario, voice)
        self.assertEqual(report['coverage']['matched'], 18)
        for index, call_order in enumerate(permutations(('reference', 'repeat', 'perturbed'))):
            refs = Counter(actual[3 * i + call_order.index('reference')][0] for i in range(index, 18, 6))
            self.assertEqual(refs, {'monthly': 1, 'annual': 1, 'quarterly': 1})
