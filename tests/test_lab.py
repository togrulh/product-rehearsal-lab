import json
from contextlib import closing
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rehearsal import Lab, LabError, OllamaVoice, discover_sources, load_catalog, run_panel


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


if __name__ == '__main__':
    unittest.main()
