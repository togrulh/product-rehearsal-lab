"""Run a fully fictional multi-source demo in temporary databases."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from rehearsal import Lab, OllamaVoice, compare_panel, enable_utf8_stdout, load_catalog, run_panel, stress_panel


def run(model, topic, compare=False, audit=False, memory_check=False, stress=False):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        catalog = {'segments':['digital_first','help_seeker'], 'topics':{
            'onboarding':{'aliases':['onboarding','signup','registration'],'anchor':'journey',
                          'required_features':['journey.completed_steps'], 'memory_policy':{'max_features':3,'signals':{
                              'journey.completed_steps':{'role':'recent_event','relevance':3,'half_life_days':14},
                              'journey.help_requested':{'role':'recent_event','relevance':2,'half_life_days':14},
                              'account.prior_app_use':{'role':'recent_event','relevance':1,'half_life_days':60},
                          }}},
            'loyalty':{'aliases':['loyalty','rewards'],'anchor':'purchases'},
        }, 'sources':[]}
        for name, topics, definitions, values in [
            ('journey',['onboarding'],{'completed_steps':{'kind':'int','meaning':'Number of previously completed signup steps','max_age_days':30},'help_requested':{'kind':'bool','meaning':'Whether help was requested in the previous signup attempt','max_age_days':30}}, [(3,0),(1,1)]),
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
        example = ('choice_stress_en.json' if stress else 'evidence_sensitivity_en.json' if memory_check
                   else 'comparison_en.json' if compare else None)
        scenario = (json.loads(Path(__file__).with_name('examples').joinpath(example).read_text(encoding='utf-8'))
                    if example else scenarios[topic])
        lab = Lab(load_catalog(catalog_path))
        plan = lab.plan(scenario['question'])
        panel, evidence = lab.panel_with_audit(plan, '2026-02-01', size=2)
        if audit:
            return {'mode':'evidence_audit','plan':plan,'as_of':'2026-02-01T00:00:00+00:00','evidence':evidence}
        voice = OllamaVoice(model)
        digest = voice.verify()
        if stress:
            result = stress_panel(panel, scenario, voice, include_replies=True)
        elif compare or memory_check:
            result = compare_panel(panel, scenario, voice)
        else:
            result = run_panel(panel, scenario, voice)
        if voice.verify() != digest:
            raise RuntimeError('Model changed during demo')
        return {**result,'plan':plan,'model':model,'digest':digest,'evidence':evidence}


if __name__ == '__main__':
    enable_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model')
    parser.add_argument('--topic', choices=['onboarding','loyalty'], default='onboarding')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--compare', action='store_true', help='Compare two independent signup conditions')
    modes.add_argument('--audit', action='store_true', help='Report fixture evidence coverage without a model')
    modes.add_argument('--memory-check', action='store_true', help='Compare replies with and without a signup fact')
    modes.add_argument('--stress', action='store_true', help='Check choice order against a repeat control')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if (args.compare or args.memory_check or args.stress) and args.topic != 'onboarding':
        parser.error('--compare, --memory-check and --stress require the onboarding topic')
    if not args.audit and not args.model:
        parser.error('--model is required unless --audit is set')
    result = run(args.model, args.topic, args.compare, args.audit, args.memory_check, args.stress)
    body = json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:
        with args.output.open('x',encoding='utf-8') as handle:
            handle.write(body + '\n')
    else:
        print(body)
    if args.audit:
        raise SystemExit(0)
    complete = (result['coverage']['matched'] == result['coverage']['eligible'] if args.compare or args.memory_check or args.stress
                else result['completed_agents'] == len(result['agents']))
    raise SystemExit(0 if complete else 2)
