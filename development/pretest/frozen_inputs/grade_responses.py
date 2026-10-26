"""Score archived responses without model calls or response repair."""
from pathlib import Path
from decimal import Decimal
from collections import Counter
import argparse,json

ROOT=Path(__file__).resolve().parent
def read_jsonl(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]

def equal(a,b):
    if isinstance(b,bool):return isinstance(a,bool) and a==b
    if isinstance(b,(int,float,Decimal)):
        return not isinstance(a,bool) and isinstance(a,(int,float,Decimal)) and Decimal(str(a))==Decimal(str(b))
    if isinstance(b,dict):return isinstance(a,dict) and set(a)==set(b) and all(equal(a[k],b[k]) for k in b)
    return type(a)==type(b) and a==b

def score(record,episode,key):
    if record.get('transport_error') is not None:return {'status':'transport_error'}
    if record.get('refusal'):return {'status':'refusal'}
    if record.get('finish_reason')=='length':return {'status':'truncated'}
    raw=record.get('raw_content')
    if not isinstance(raw,str) or not raw.strip():return {'status':'empty_response'}
    try:
        def pairs(items):
            d={}
            for k,v in items:
                if k in d:raise ValueError('Duplicate key')
                d[k]=v
            return d
        parsed=json.loads(raw,parse_float=Decimal,object_pairs_hook=pairs,
                          parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite number')))
    except (ValueError,TypeError):return {'status':'malformed_json'}
    if not isinstance(parsed,dict):return {'status':'invalid_schema'}
    if key['scoring']=='factual':
        expected=key['expected']
        if set(parsed)!=set(expected):return {'status':'invalid_schema'}
        field_scores={k:equal(parsed[k],expected[k]) for k in expected}
        return {'status':'valid','correct':all(field_scores.values()),'field_scores':field_scores}
    if set(parsed)!={'choice'} or not isinstance(parsed['choice'],str) or parsed['choice'] not in ['A','B','DECLINE']:
        return {'status':'invalid_schema'}
    selected=parsed['choice']
    result={'status':'valid','choice':selected,'profile_choice':episode['display_map'].get(selected,'DECLINE')}
    if key['scoring']=='known_choice':
        result['correct']=equal(parsed,key['expected'])
        result['permitted']=key['eligible'][selected]
        if result['permitted']:
            best=max(Decimal(v) for k,v in key['payoffs'].items() if key['eligible'][k])
            result['regret_usd']=str(best-Decimal(key['payoffs'][selected]))
        else:result['regret_usd']=None
    return result

def grade(records,configuration,allow_fixtures=False):
    episodes=read_jsonl(ROOT/'episodes.jsonl');by_id={e['episode_id']:e for e in episodes}
    keys={k['case_id']:k for k in read_jsonl(ROOT/'answer_key.jsonl')}
    records=[r for r in records if r.get('configuration')==configuration]
    seen={};results=[]
    for r in records:
        if r.get('data_origin')!='live_model' and not(allow_fixtures and r.get('data_origin')=='parser_fixture'):
            raise ValueError('Origin must be live_model; fixtures require --allow-fixtures.')
        eid=r['episode_id']
        if eid not in by_id:raise ValueError('Unknown episode '+eid)
        if eid in seen:raise ValueError('Duplicate episode; separate attempts explicitly before scoring.')
        e=by_id[eid]
        if r.get('prompt_sha256')!=e['prompt_sha256']:raise ValueError('Prompt hash mismatch '+eid)
        ans=score(r,e,keys[e['case_id']]);seen[eid]=ans
        results.append({'episode_id':eid,'module':e['module'],**ans})
    missing=[e['episode_id'] for e in episodes if e['episode_id'] not in seen]
    def compare(a,b):
        x,y=seen.get(a),seen.get(b)
        if not x or not y or x.get('status')!='valid' or y.get('status')!='valid':return None
        return x.get('profile_choice')==y.get('profile_choice')
    repeat_checks={e['case_id']:compare(e['case_id']+'_r1',e['case_id']+'_r2') for e in episodes if e['repeat']==1 and e['module'] in ['refund_wording','presentation']}
    frame_checks={f'W{m}_{target}_r{rep}':compare(f'W{m}_{target}_returned_r{rep}',f'W{m}_{target}_not_returned_r{rep}') for m in range(1,5) for target in [5,60] for rep in [1,2]}
    position_checks={f'P{m}_r{rep}':compare(f'P{m}_base_r{rep}',f'P{m}_position_r{rep}') for m in range(1,5) for rep in [1,2]}
    label_checks={f'P{m}_r{rep}':compare(f'P{m}_base_r{rep}',f'P{m}_labels_r{rep}') for m in range(1,5) for rep in [1,2]}
    def tally(d):return {'paired':sum(v is not None for v in d.values()),'disagreements':sum(v is False for v in d.values()),'unpaired':sum(v is None for v in d.values()),'cases':d}
    return {'configuration':configuration,'data_origin':sorted({r['data_origin'] for r in records}),
       'expected_episodes':len(episodes),'observed_episodes':len(records),'missing_episodes':missing,
       'statuses':dict(Counter(r['status'] for r in results)),
       'comprehension':{'valid':sum(r['module']=='comprehension' and r['status']=='valid' for r in results),
                        'correct':sum(r['module']=='comprehension' and r.get('correct') is True for r in results),'expected':24},
       'known_objective':{'valid':sum(r['module']=='known_objective' and r['status']=='valid' for r in results),
                          'correct':sum(r['module']=='known_objective' and r.get('correct') is True for r in results),'expected':16},
       'repeat_comparisons':tally(repeat_checks),'wording_comparisons':tally(frame_checks),
       'position_comparisons':tally(position_checks),'label_comparisons':tally(label_checks),'episode_results':results}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('responses');a.add_argument('--configuration',required=True)
    a.add_argument('--allow-fixtures',action='store_true');a.add_argument('--output',required=True);args=a.parse_args()
    result=grade(read_jsonl(args.responses),args.configuration,args.allow_fixtures)
    Path(args.output).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['configuration','data_origin','observed_episodes','statuses']}))
