"""Four post hoc checks of one clarified comprehension field; original scores stay fixed."""
from pathlib import Path
from decimal import Decimal as D
import json,os,hashlib,importlib.util,copy,argparse

parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
if not args.live:
    print(json.dumps({'mode':'offline','planned_diagnostic_calls':4,'model_calls':0}));raise SystemExit

RUN=Path(__file__).resolve().parent
FROZEN=RUN/'frozen_inputs'
spec=importlib.util.spec_from_file_location('collector',FROZEN/'collect_pretest.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
spec=importlib.util.spec_from_file_location('grader',FROZEN/'grade_responses.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
main=json.loads((RUN/'summary.json').read_text())
assert set(main['models'])=={'sol','qwen'} and main['total_calls']==192
assert all(x['observed_episodes']==96 for x in main['models'].values())
key=os.environ.get('OPENROUTER_API_KEY')
if not key:raise SystemExit('An active experiment credential is required.')
kd=c.api('key',key)['data']
assert kd['is_management_key'] is False and kd['limit_reset'] is None and D(str(kd['limit']))<=D('20')
config=json.loads((FROZEN/'configuration.json').read_text())
original=next(x for x in g.read_jsonl(FROZEN/'episodes.jsonl') if x['episode_id']=='F08_r1')
answer=next(x for x in g.read_jsonl(FROZEN/'answer_key.jsonl') if x['case_id']=='F08')
expected={('other_parties_records_erased' if k=='other_records_erased' else k):v for k,v in answer['expected'].items()}
old='Give query_visible and response_visible to the payment service, persistent_pseudonym_recorded, operator_receipt_survives_deletion, and other_records_erased when its retention period ends.'
new=('Give query_visible and response_visible to the payment service, persistent_pseudonym_recorded, operator_receipt_survives_deletion, and other_parties_records_erased. '
     'For other_parties_records_erased, answer whether deletion of the payment service’s own record also erases records held by other parties. Do not include the payment service’s own record in that field.')
messages=copy.deepcopy(original['messages']);assert old in messages[0]['content'];messages[0]['content']=messages[0]['content'].replace(old,new)
digest=hashlib.sha256(json.dumps(messages,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
folder=RUN/'scope_diagnostic';folder.mkdir(exist_ok=True)
if any(folder.glob('*_r*.json')):raise SystemExit('Diagnostic responses already exist; no automatic rerun.')
plan={'diagnostic_id':'F08_scope_clarification_v01','data_origin':'post_hoc_diagnostic_plan','created_utc':c.now(),
 'trigger':'Qwen F08_r1 failed the original other_records_erased field. The field name did not identify the record holder.',
 'change':'Factual question and field name only. The common contract stem, mandates, offers, and model settings are unchanged.',
 'original_results_remain_unchanged':True,'models':['sol','qwen'],'repeats_per_model':2,
 'messages':messages,'prompt_sha256':digest,'expected':expected,
 'interpretation':'A targeted diagnostic of the clarified question; not retrospective rescoring or a repeat of the complete qualification battery.'}
c.save(folder/'plan.json',plan)
total=D(main['total_accounted_cost_usd']);per_model={s:D(x['accounted_cost_usd']) for s,x in main['models'].items()}
rows=[]
for slot in ['sol','qwen']:
    m=config['models'][slot]
    for repeat in [1,2]:
        body=copy.deepcopy(json.loads((RUN/('results_'+slot)/'attempts/F08_r1.json').read_text())['request'])
        body['messages']=messages
        body['response_format']['json_schema']['schema']=c.schema({'scoring':'factual','expected':expected})
        reserve=(D(len(json.dumps(body).encode())+4096)*D(str(m['input_usd_per_million']))/1000000+D(m['max_output_tokens'])*D(str(m['output_usd_per_million']))/1000000)*D('1.10')
        if total+reserve>D('2') or per_model[slot]+reserve>D('1'):
            raise SystemExit('Diagnostic would exceed the previously stated software caps; no call sent.')
        eid=slot+'_F08_scope_r'+str(repeat);path=folder/(eid+'.json')
        rec={'episode_id':eid,'configuration':slot+'_scope_clarification_v01_medium','data_origin':'live_model',
          'state':'intent','model_slot':slot,'repeat':repeat,'prompt_sha256':digest,'started_utc':c.now(),
          'request':body,'reserved_cost_usd':str(reserve)}
        c.save(path,rec)
        try:r=c.api('chat/completions',key,body)
        except Exception as e:
            rec.update(state='unresolved_transport',transport_error=str(e),ended_utc=c.now());c.save(path,rec)
            raise SystemExit('Transport uncertainty preserved; no automatic retry.')
        rec.update(raw_response=r,ended_utc=c.now())
        if r.get('error') or r.get('model') not in m['expected_returned_model_ids'] or r.get('provider')!=m['upstream_provider_name']:
            rec['state']='unresolved_route';c.save(path,rec);raise SystemExit('Unexpected diagnostic route; stopped.')
        cost=D(str(r.get('usage',{}).get('cost','NaN')))
        if not cost.is_finite() or cost<0:
            rec['state']='unresolved_billing';c.save(path,rec);raise SystemExit('Invalid diagnostic cost; stopped.')
        choice=r['choices'][0];message=choice['message']
        rec.update(state='completed',accounted_cost_usd=str(cost),raw_content=message.get('content'),
          refusal=message.get('refusal'),finish_reason=choice.get('finish_reason'),returned_model=r.get('model'),provider=r.get('provider'))
        rec['score']=g.score(rec,{}, {'scoring':'factual','expected':expected})
        c.save(path,rec);rows.append(rec);total+=cost;per_model[slot]+=cost
        print(json.dumps({'episode_id':eid,'correct':rec['score'].get('correct'),'cost_usd':str(cost),'combined_spend_usd':str(total)}),flush=True)
        if cost>reserve:raise SystemExit('Charge exceeded reserve; stopped.')
summary={'data_origin':'live_model','diagnostic_id':plan['diagnostic_id'],'total_calls':len(rows),
 'models':{slot:{'observed':sum(r['model_slot']==slot for r in rows),
   'correct':sum(r['model_slot']==slot and r['score'].get('correct') is True for r in rows),
   'accounted_cost_usd':str(sum((D(r['accounted_cost_usd']) for r in rows if r['model_slot']==slot),D(0)))} for slot in ['sol','qwen']},
 'accounted_cost_usd':str(sum((D(r['accounted_cost_usd']) for r in rows),D(0))),
 'combined_spend_usd':str(total),'original_qualification_scores_unchanged':True}
c.save(folder/'summary.json',summary)
