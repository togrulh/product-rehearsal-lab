import json
import unittest
from copy import deepcopy

import rehearsal


SCENARIO = {
    'language': 'en', 'question': 'Would you continue signup now?',
    'conditions': {'help_available': False, 'progress_visible': True},
    'comparison': {'condition': 'help_available', 'value': True, 'choices': {
        'continue': 'Continue now', 'stop': 'Stop now', 'unsure': 'Not enough information',
    }},
}


class PairedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.panel = [
            {'agent': 'A001', 'segment': 'new', 'facts': {'steps': {'value': 1}}},
            {'agent': 'A002', 'segment': 'repeat', 'facts': {'steps': {'value': 2}}},
            {'agent': 'A003', 'segment': 'new', 'facts': {'steps': {'value': 3}}},
        ]
        self.scenario = deepcopy(SCENARIO)

    def test_same_panel_one_change_independent_answers_and_matched_denominator(self):
        calls = []

        def voice(payload):
            step = payload['facts']['steps']['value']
            help_available = payload['conditions']['help_available']
            calls.append((step, help_available))
            self.assertEqual(payload['question'], SCENARIO['question'])
            self.assertTrue(payload['conditions']['progress_visible'])
            self.assertEqual(payload['history'], [])
            self.assertEqual(payload['choices'], SCENARIO['comparison']['choices'])
            self.assertNotIn('agent', payload)
            pick = {1: 'continue' if help_available else 'stop', 2: 'invented' if help_available else 'continue', 3: 'unsure'}[step]
            return {'answer': 'Fictional reply.', 'choice': pick, 'evidence_keys': ['steps']}

        report = rehearsal.compare_panel(self.panel, self.scenario, voice)
        self.assertEqual(calls, [(1, False), (1, True), (2, True), (2, False), (3, False), (3, True)])
        self.assertEqual(report['coverage'], {'eligible': 3, 'baseline_valid': 3, 'variant_valid': 2, 'matched': 2})
        self.assertEqual(report['matched_choices']['baseline'], {'continue': 0, 'stop': 1, 'unsure': 1})
        self.assertEqual(report['matched_choices']['variant'], {'continue': 1, 'stop': 0, 'unsure': 1})
        self.assertEqual(report['transitions'], [{'baseline': 'stop', 'variant': 'continue', 'count': 1}, {'baseline': 'unsure', 'variant': 'unsure', 'count': 1}])
        self.assertEqual(report['pairs'][1]['variant']['status'], 'invalid_choice')
        self.assertEqual(report['by_segment']['repeat']['coverage']['matched'], 0)
        self.assertEqual(self.scenario, SCENARIO)
        self.assertNotIn('Fictional reply.', json.dumps(rehearsal.compare_panel(self.panel, self.scenario, voice, include_replies=False)))

    def test_rejects_ambiguous_or_noop_comparisons_before_calling_model(self):
        changes = [
            ('followups', [{'question': 'Why?'}]),
            ('comparison', {**SCENARIO['comparison'], 'condition': 'missing'}),
            ('comparison', {**SCENARIO['comparison'], 'value': False}),
            ('comparison', {**SCENARIO['comparison'], 'choices': {'yes': 'Yes', 'no': 'No'}}),
            ('comparison', {**SCENARIO['comparison'], 'also_change': 'progress_visible'}),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value), self.assertRaises(rehearsal.LabError):
                rehearsal.compare_panel(self.panel, {**self.scenario, key: value}, lambda _: self.fail('model called'))

    def test_ollama_uses_an_enum_and_same_comparison_temperature(self):
        class Voice(rehearsal.OllamaVoice):
            def request(self, path, body=None):
                self.call = (path, body)
                return {'model': self.model, 'done_reason': 'stop', 'message': {'content': '{"answer":"Maybe.","choice":"unsure","evidence_keys":[]}'}}

        voice = Voice('test:local')
        result = voice({'facts': {}, 'choices': SCENARIO['comparison']['choices']})
        path, body = voice.call
        self.assertEqual(path, '/api/chat')
        self.assertEqual(body['format']['properties']['choice']['enum'], ['continue', 'stop', 'unsure'])
        self.assertIn('choice', body['format']['required'])
        self.assertEqual(body['options']['temperature'], 0)
        self.assertEqual(result['choice'], 'unsure')
