import json
from contextlib import closing, redirect_stdout
from io import StringIO
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from rehearsal import Lab, LabError, OllamaVoice, discover_sources, load_catalog, main, run_panel


class DemoOutputTests(unittest.TestCase):
    def test_demo_defaults_to_english_and_preserves_utf8(self):
        code = r'''
import rehearsal, runpy, sys
class LocalModelDouble:
    def __init__(self, model):
        assert model == 'test:local'
    def verify(self):
        return 'a' * 64
    def __call__(self, payload):
        assert payload['language'] == 'en'
        return {'answer':'I would continue \u2212 the next step is clear.', 'evidence_keys':[]}
rehearsal.OllamaVoice = LocalModelDouble
sys.argv = ['demo.py','--model','test:local']
runpy.run_path('demo.py', run_name='__main__')
'''
        run = subprocess.run([sys.executable,'-c',code], cwd=Path(__file__).resolve().parents[1], env={**os.environ,'PYTHONIOENCODING':'cp1252'}, capture_output=True, timeout=30)
        self.assertEqual(run.returncode,0,run.stderr.decode('ascii',errors='backslashreplace'))
        report = json.loads(run.stdout.decode('utf-8'))
        self.assertEqual(report['agents'][0]['turns'][0]['answer'],'I would continue \u2212 the next step is clear.')


class LabTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for name, column, rows in (
            ('events', 'touches', [('private-id-1','new',2,'2026-01-01','2026-01-02'), ('private-id-2','repeat',8,'2026-01-01','2026-01-02'), ('late-id','new',10,'2026-01-01','2026-02-01'), ('private-id-1','new',99,'2026-01-01','2026-02-03')]),
            ('core', 'held', [('private-id-1','new',1,'2026-01-01','2026-01-02'), ('orphan-id','new',1,'2026-01-01','2026-01-02')]),
        ):
            with closing(sqlite3.connect(root / f'{name}.db')) as db, db:
                db.execute(f'CREATE TABLE snapshot(profile_key, segment, {column}, event_at, available_at)')
                db.executemany('INSERT INTO snapshot VALUES (?, ?, ?, ?, ?)', rows)
        self.path = root / 'catalog.json'
        self.catalog = {'segments':['new','repeat'], 'topics': {'onboarding': {'aliases': ['signup','onboarding'], 'anchor': 'events'}, 'savings': {'aliases': ['deposit'], 'anchor': 'core'}}, 'sources': [
            {'id': 'events', 'engine': 'sqlite', 'path': 'events.db', 'view': 'snapshot', 'namespace': 'tenant_v1', 'topics': ['onboarding'], 'features': {'touches': {'kind': 'int', 'meaning': 'Observed step count'}}},
            {'id': 'core', 'engine': 'sqlite', 'path': 'core.db', 'view': 'snapshot', 'namespace': 'tenant_v1', 'topics': ['onboarding','savings'], 'features': {'held': {'kind': 'bool', 'meaning': 'Existing contract'}}},
        ]}
        self.write_catalog()

    def write_catalog(self):
        self.path.write_text(json.dumps(self.catalog), encoding='utf-8')

    def lab(self):
        return Lab(load_catalog(self.path))

    def panel(self):
        lab = self.lab()
        return lab.panel(lab.plan('Show the next signup step'), '2026-02-01', 8, 3)

    def test_routes_and_joins_without_future_rows_or_identifiers(self):
        panel = self.panel()
        by_segment = {x['segment']: x['facts'] for x in panel}
        self.assertEqual(set(by_segment), {'new','repeat'})
        self.assertEqual(by_segment['new']['events.touches']['value'], 2)
        self.assertIs(by_segment['new']['core.held']['value'], True)
        self.assertNotIn('core.held', by_segment['repeat'])
        self.assertNotIn('private-id', json.dumps(panel))

    def test_unknown_task_fails_closed(self):
        with self.assertRaisesRegex(LabError, 'topic_not_found'):
            self.lab().plan('Unmapped workflow')

    def test_catalog_cannot_read_identity_feature(self):
        self.catalog['sources'][0]['features']['phone_number'] = {'kind':'int', 'meaning':'Phone'}
        self.write_catalog()
        with self.assertRaisesRegex(LabError, 'forbidden_feature'):
            self.lab()

    def test_over_cap_does_not_return_arbitrary_partial_panel(self):
        lab = self.lab()
        with self.assertRaisesRegex(LabError, 'row_cap_exceeded:events'):
            lab.panel(lab.plan('Signup'), '2026-02-01', 2, max_rows=1)

    def test_metadata_discovery_requires_explicit_scope(self):
        lab = self.lab()
        with self.assertRaisesRegex(LabError, 'discovery_scope_or_terms_missing'):
            discover_sources(lab.catalog, lab.plan('Signup'))

    def test_remote_and_cloud_models_fail_closed(self):
        with self.assertRaisesRegex(LabError, 'loopback_only'):
            OllamaVoice('model:local','http://example.com')
        with self.assertRaisesRegex(LabError, 'invalid_model'):
            OllamaVoice('model:cloud')

    def test_conflicting_identity_namespaces_are_not_joined(self):
        self.catalog['sources'][1]['namespace'] = 'not_the_same'
        self.write_catalog()
        with self.assertRaisesRegex(LabError, 'identity_namespace'):
            self.panel()

    def test_duplicate_latest_record_rejected(self):
        with closing(sqlite3.connect(self.path.parent / 'events.db')) as db, db:
            db.execute("INSERT INTO snapshot VALUES ('private-id-1','new',5,'2026-01-01','2026-01-02')")
        with self.assertRaisesRegex(LabError, 'duplicate_latest'):
            self.panel()

    def test_identifier_cannot_be_sql(self):
        self.catalog['sources'][0]['view'] = 'snapshot; DROP TABLE snapshot'
        self.write_catalog()
        with self.assertRaisesRegex(LabError, 'invalid_identifier'):
            self.lab()

    def test_feature_types_do_not_silently_accept_free_text(self):
        with closing(sqlite3.connect(self.path.parent / 'events.db')) as db, db:
            db.execute("UPDATE snapshot SET touches='raw sensitive payload'")
        with self.assertRaisesRegex(LabError, 'invalid_feature_value'):
            self.panel()

    def test_dialogue_retains_conditions_and_rejects_unseen_evidence(self):
        class Voice:
            def __call__(self, payload):
                turn = len(payload['history'])
                if turn:
                    assert payload['conditions'] == {'fee': 0, 'duration': 3}
                    assert payload['history'][0]['answer'] == 'I would read the explanation first.'
                return {'answer': 'I would read the explanation first.', 'evidence_keys': ['not_in_profile'] if turn else ['events.touches']}
        result = run_panel(self.panel()[:1], {'language':'en', 'question':'How should signup work?', 'conditions':{'fee': 1, 'duration': 3}, 'followups':[{'question':'What about now?', 'changes':{'fee':0}}]}, Voice())
        self.assertEqual(result['agents'][0]['turns'][0]['status'], 'ok')
        self.assertEqual(result['agents'][0]['turns'][1]['status'], 'invalid_evidence')
        self.assertEqual(result['completed_agents'], 0)

    def test_compare_cli_uses_the_catalog_and_keeps_partial_results_without_replies(self):
        scenario = self.path.with_name('comparison.json')
        scenario.write_text(json.dumps({
            'language': 'en', 'question': 'Would you continue signup?', 'as_of': '2026-02-01',
            'conditions': {'help': False},
            'comparison': {'condition': 'help', 'value': True, 'choices': {'yes': 'Continue', 'no': 'Stop', 'unsure': 'Unsure'}},
        }), encoding='utf-8')

        class Voice:
            def __init__(self, model, endpoint):
                self.model = model

            def verify(self):
                return 'a' * 64

            def __call__(self, payload):
                choice = 'invalid' if payload['conditions']['help'] and payload['facts']['events.touches']['value'] == 8 else 'yes'
                return {'choice': choice, 'answer': 'Fictional reply.', 'evidence_keys': []}

        argv = ['product-rehearsal', 'compare', str(self.path), str(scenario), '--model', 'test:local']
        with patch.object(sys, 'argv', argv), patch('rehearsal.OllamaVoice', Voice), redirect_stdout(StringIO()) as out:
            self.assertEqual(main(), 2)
        report = json.loads(out.getvalue())
        self.assertEqual(report['coverage'], {'eligible': 2, 'baseline_valid': 2, 'variant_valid': 1, 'matched': 1})
        self.assertEqual(report['failure_reasons'], {'baseline': {}, 'variant': {'invalid_choice': 1}})
        self.assertEqual(report['digest'], 'a' * 64)
        self.assertNotIn('pairs', report)
        self.assertNotIn('private-id', out.getvalue())

    def test_point_in_time_evidence_freshness_and_required_signal(self):
        self.catalog['sources'][1]['features']['held']['max_age_days'] = 30
        self.catalog['topics']['onboarding']['required_features'] = ['core.held']
        self.write_catalog()
        lab = self.lab()
        plan = lab.plan('Signup')

        # Feb 1 sees Jan 1's observation, not a future revision of another source.
        panel, audit = lab.panel_with_audit(plan, '2026-02-01', size=8)
        self.assertEqual(panel, [])
        self.assertEqual(audit['profiles'], {'anchor': 2, 'no_evidence': 0, 'missing_required': 2, 'eligible': 0, 'sampled': 0})
        self.assertEqual(audit['features']['core.held']['anchor'], {'admitted': 0, 'stale': 1, 'null': 0, 'unmatched': 1})
        with self.assertRaisesRegex(LabError, 'empty_eligible_panel'):
            lab.panel(plan, '2026-02-01')

        # The observation exactly 30 days before the cutoff is still admitted.
        panel, audit = lab.panel_with_audit(plan, '2026-01-31', size=8)
        self.assertEqual(len(panel), 1)
        self.assertTrue(panel[0]['facts']['core.held']['value'])
        self.assertEqual(audit['features']['core.held']['sampled'], {'admitted': 1, 'stale': 0, 'null': 0, 'unmatched': 0})
        self.assertNotIn('private-id', json.dumps(audit))

    def test_explicit_zero_and_null_are_not_conflated(self):
        with closing(sqlite3.connect(self.path.parent / 'events.db')) as db, db:
            db.execute("UPDATE snapshot SET touches=0 WHERE profile_key='private-id-1' AND available_at='2026-01-02'")
            db.execute("UPDATE snapshot SET touches=NULL WHERE profile_key='private-id-2'")
        lab = self.lab()
        panel, audit = lab.panel_with_audit(lab.plan('Signup'), '2026-02-01', size=8)
        self.assertEqual(panel[0]['facts']['events.touches']['value'], 0)
        self.assertEqual(audit['features']['events.touches']['anchor'], {'admitted': 1, 'stale': 0, 'null': 1, 'unmatched': 0})
        self.assertEqual(audit['profiles']['no_evidence'], 1)

    def test_evidence_policy_cannot_reference_unmapped_signals(self):
        self.catalog['topics']['savings']['required_features'] = ['events.touches']
        self.write_catalog()
        with self.assertRaisesRegex(LabError, 'invalid_required_features'):
            self.lab()
        del self.catalog['topics']['savings']['required_features']
        self.catalog['sources'][0]['features']['touches']['max_age_days'] = True
        self.write_catalog()
        with self.assertRaisesRegex(LabError, 'invalid_max_age_days'):
            self.lab()

    def test_audit_cli_is_model_free_and_reports_empty_coverage(self):
        self.catalog['topics']['onboarding']['required_features'] = ['core.held']
        self.catalog['sources'][1]['features']['held']['max_age_days'] = 30
        self.write_catalog()
        scenario = self.path.with_name('audit.json')
        scenario.write_text(json.dumps({'language': 'en', 'question': 'Signup?', 'as_of': '2026-02-01'}), encoding='utf-8')
        with patch.object(sys, 'argv', ['rehearsal', 'audit', str(self.path), str(scenario)]), \
             patch('rehearsal.OllamaVoice', side_effect=AssertionError('model must not run')), redirect_stdout(StringIO()) as out:
            self.assertEqual(main(), 0)
        report = json.loads(out.getvalue())
        self.assertEqual(report['mode'], 'evidence_audit')
        self.assertEqual(report['evidence']['profiles']['eligible'], 0)
        self.assertNotIn('private-id', out.getvalue())

    def test_memory_ranks_by_task_weight_and_age_without_dropping_required_facts(self):
        self.catalog['topics']['onboarding']['memory_policy'] = {'max_features': 1, 'signals': {
            'events.touches': {'role': 'recent_event', 'relevance': 2, 'half_life_days': 7},
            'core.held': {'role': 'current_state', 'relevance': 1, 'half_life_days': None},
        }}
        self.write_catalog()
        lab = self.lab()
        plan = lab.plan('Signup')
        panel, audit = lab.panel_with_audit(plan, '2026-02-01', size=8)
        self.assertEqual(list(panel[0]['facts']), ['core.held'])
        self.assertEqual(panel[0]['facts']['core.held']['memory_role'], 'current_state')
        self.assertEqual(audit['memory']['sampled_retrieved'], {'events.touches': 1, 'core.held': 1})

        self.catalog['topics']['onboarding']['required_features'] = ['events.touches']
        self.write_catalog()
        panel = self.panel()
        self.assertEqual(list(panel[0]['facts']), ['events.touches'])

    def test_required_signals_must_fit_the_memory_budget(self):
        topic = self.catalog['topics']['onboarding']
        topic['required_features'] = ['events.touches', 'core.held']
        topic['memory_policy'] = {'max_features': 1, 'signals': {
            name: {'role': 'habit', 'relevance': 1, 'half_life_days': 30} for name in topic['required_features']
        }}
        self.write_catalog()
        with self.assertRaisesRegex(LabError, 'invalid_memory_policy'):
            self.lab()


if __name__ == '__main__':
    unittest.main()
