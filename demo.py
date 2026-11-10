"""Run a fully fictional multi-source demo in temporary databases."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from rehearsal import Lab, OllamaVoice, enable_utf8_stdout, load_catalog, run_panel


def run(model, topic):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        catalog = {'segments':['digital_first','help_seeker'], 'topics':{
            'onboarding':{'aliases':['onboarding','signup','registration'],'anchor':'journey'},
            'loyalty':{'aliases':['loyalty','rewards'],'anchor':'purchases'},
        }, 'sources':[]}
        for name, topics, definitions, values in [
            ('journey',['onboarding'],{'completed_steps':{'kind':'int','meaning':'Number of previously completed signup steps'},'help_requested':{'kind':'bool','meaning':'Previously requested help on the signup journey'}}, [(3,0),(1,1)]),
            ('purchases',['loyalty'],{'online_orders':{'kind':'int','meaning':'Number of completed online orders in the observation period'}}, [(9,),(1,)]),
            ('account',['onboarding','loyalty'],{'prior_app_use':{'kind':'bool','meaning':'Used the mobile app on a previous occasion, unrelated to completion of the current signup'}}, [(1,),(0,)]),
        ]:
            catalog['sources'].append({'id':name,'engine':'sqlite','path':f'{name}.db','view':'features','namespace':'fiction_v1','topics':topics,'features':definitions})
            with closing(sqlite3.connect(root / f'{name}.db')) as db, db:
                db.execute('CREATE TABLE features(profile_key, segment, event_at, available_at,' + ','.join(definitions) + ')')
                for idx, segment in enumerate(catalog['segments']):
                    row = (f'fixture-private-{idx}',segment,'2026-01-10','2026-01-11',*values[idx])
                    db.execute('INSERT INTO features VALUES (' + ','.join('?' for _ in row) + ')', row)
        catalog_path = root / 'catalog.json'
        catalog_path.write_text(json.dumps(catalog), encoding='utf-8')
        scenarios = {
            'onboarding':{'language':'en','question':'If the signup screen showed you the next step, how would you react?', 'conditions':{'next_step_visible':True,'human_help':False}, 'followups':[{'question':'Would a help button on the same screen change your mind?', 'changes':{'human_help':True}}]},
            'loyalty':{'language':'en','question':'Which loyalty reward would you choose: a discount on purchases or free delivery?', 'conditions':{'offer_a':'purchase discount','offer_b':'free delivery'}},
        }
        scenario = scenarios[topic]
        lab = Lab(load_catalog(catalog_path))
        plan = lab.plan(scenario['question'])
        panel = lab.panel(plan, '2026-02-01', size=2)
        voice = OllamaVoice(model)
        digest = voice.verify()
        result = run_panel(panel, scenario, voice)
        if voice.verify() != digest:
            raise RuntimeError('Model changed during demo')
        return {**result,'plan':plan,'model':model,'digest':digest}


if __name__ == '__main__':
    enable_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--topic', choices=['onboarding','loyalty'], default='onboarding')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = run(args.model, args.topic)
    body = json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        with args.output.open('x',encoding='utf-8') as handle:
            handle.write(body + '\n')
    else:
        print(body)
    raise SystemExit(0 if result['completed_agents'] == len(result['agents']) else 2)
