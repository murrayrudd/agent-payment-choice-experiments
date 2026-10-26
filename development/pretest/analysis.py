"""Summarize completed Step 5 runs; never sends model requests."""
from pathlib import Path
from decimal import Decimal
from collections import Counter
import json,sys,importlib.util

ROOT=Path(__file__).resolve().parent
INPUT=ROOT/'frozen_inputs'
spec=importlib.util.spec_from_file_location('pretest_grade',INPUT/'grade_responses.py')
grader=importlib.util.module_from_spec(spec);spec.loader.exec_module(grader)
episodes=grader.read_jsonl(INPUT/'episodes.jsonl')
by_id={e['episode_id']:e for e in episodes}
answer_keys={a['case_id']:a for a in grader.read_jsonl(INPUT/'answer_key.jsonl')}

def summarize(slot):
    folder=ROOT/('results_'+slot)
    rows=grader.read_jsonl(folder/'responses.jsonl')
    configuration=slot+'_step5_v02_medium'
    scored=grader.grade(rows,configuration)
    assert scored['observed_episodes']==96 and not scored['missing_episodes']
    (folder/'scored.json').write_text(json.dumps(scored,indent=2))
    results={r['episode_id']:r for r in scored['episode_results']}
    cost=sum((Decimal(r['accounted_cost_usd']) for r in rows),Decimal(0))
    numeric=[r for r in results.values() if r['module']=='known_objective']
    factual=[r for r in results.values() if r['module']=='comprehension']
    required_pass=(scored['comprehension']['correct']==24 and scored['known_objective']['correct']==16)
    qual=[]
    for case in [e for e in episodes if e['repeat']==1 and e['module'] in ['refund_wording','presentation']]:
        qual.append({k:case[k] for k in ['case_id','module','mandate','target_seconds','frame','position','display_map']}|
            {'physical_choices':[results.get(case['case_id']+'_r'+str(rep),{}).get('profile_choice') for rep in [1,2]]})
    return {'configuration':configuration,'required_checks_pass':required_pass,
      'observed_episodes':scored['observed_episodes'],'statuses':scored['statuses'],
      'comprehension':scored['comprehension'],'known_objective':scored['known_objective'],
      'factual_fields_correct':sum(sum(r.get('field_scores',{}).values()) for r in factual),
      'factual_fields_expected':2*sum(len(a['expected']) for a in answer_keys.values() if a['scoring']=='factual'),
      'authority_violations':sum(r.get('permitted') is False for r in numeric),
      'numeric_regret_total_usd':str(sum((Decimal(r['regret_usd']) for r in numeric if r.get('regret_usd') is not None),Decimal(0))),
      'comparisons':{k:scored[k] for k in ['repeat_comparisons','wording_comparisons','position_comparisons','label_comparisons']},
      'qualitative_choices':qual,
      'failed_required_episodes':[r for r in scored['episode_results'] if r['module'] in ['comprehension','known_objective'] and r.get('correct') is not True],
      'accounted_cost_usd':str(cost),'started_utc':min(r['started_utc'] for r in rows),
      'ended_utc':max(r['ended_utc'] for r in rows),
      'models':dict(Counter(r.get('returned_model','unknown') for r in rows)),
      'providers':dict(Counter(r.get('provider','unknown') for r in rows)),
      'usage_totals':{k:sum(r['raw_response'].get('usage',{}).get(k,0) for r in rows) for k in ['prompt_tokens','completion_tokens','total_tokens']}}

slots=sys.argv[1:] or ['sol','qwen']
models={slot:summarize(slot) for slot in slots}
summary={'data_origin':'live_model','instrument_version':'0.2','models':models,
  'total_calls':sum(x['observed_episodes'] for x in models.values()),
  'total_accounted_cost_usd':str(sum((Decimal(x['accounted_cost_usd']) for x in models.values()),Decimal(0))),
  'scope':'Diagnostic evidence for named model configurations and tested profiles; not population WTP or operator-preference validation.'}
diag=ROOT/'scope_diagnostic'
if (diag/'summary.json').exists():
    plan=json.loads((diag/'plan.json').read_text())
    rows=[json.loads(p.read_text()) for p in diag.glob('*_r*.json')]
    assert len(rows)==4 and all(r['state']=='completed' for r in rows)
    for r in rows:
        assert r['prompt_sha256']==plan['prompt_sha256'] and r['request']['messages']==plan['messages']
        assert r['data_origin']=='live_model'
        r['derived_score']=grader.score(r,{}, {'scoring':'factual','expected':plan['expected']})
    ds={'data_origin':'live_model','diagnostic_id':plan['diagnostic_id'],'total_calls':len(rows),
      'models':{slot:{'observed':sum(r['model_slot']==slot for r in rows),
        'correct':sum(r['model_slot']==slot and r['derived_score'].get('correct') is True for r in rows),
        'accounted_cost_usd':str(sum((Decimal(r['accounted_cost_usd']) for r in rows if r['model_slot']==slot),Decimal(0)))} for slot in ['sol','qwen']},
      'accounted_cost_usd':str(sum((Decimal(r['accounted_cost_usd']) for r in rows),Decimal(0))),
      'original_qualification_scores_unchanged':True}
    ds['combined_spend_usd']=str(Decimal(ds['accounted_cost_usd'])+Decimal(summary['total_accounted_cost_usd']))
    (diag/'summary.json').write_text(json.dumps(ds,indent=2))
    summary['scope_diagnostic']=ds
    summary['total_calls_including_followup']=summary['total_calls']+ds['total_calls']
    summary['total_cost_including_followup_usd']=ds['combined_spend_usd']
(ROOT/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({slot:{k:v for k,v in x.items() if k not in ['qualitative_choices','comparisons']} for slot,x in models.items()},indent=2))
