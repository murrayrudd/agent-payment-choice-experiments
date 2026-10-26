"""Bounded Sol-only collector. Offline unless --live; never logs credentials."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import argparse,atexit,hashlib,json,os,urllib.request,urllib.error

BASE='https://openrouter.ai/api/v1/'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readl(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w') as f:json.dump(x,f,indent=2);f.flush();os.fsync(f.fileno())
def api(path,key=None,body=None):
    h={'Accept':'application/json'}
    if key:h['Authorization']='Bearer '+key
    b=None
    if body is not None:h['Content-Type']='application/json';b=json.dumps(body).encode()
    try:
        with urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(BASE+path,data=b,headers=h),timeout=180) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError('HTTP '+str(e.code)) from None
    except Exception as e:raise RuntimeError(type(e).__name__) from None
def request(e,m):
    return {'model':m['model_id'],'messages':e['messages'],'stream':False,'max_tokens':m['max_output_tokens'],
      'response_format':{'type':'json_schema','json_schema':{'name':'pilot_response','strict':True,'schema':{'type':'object','properties':{'choice':{'type':'string','enum':['A','B','DECLINE']}},'required':['choice'],'additionalProperties':False}}},
      'provider':{'only':[m['upstream_provider']],'allow_fallbacks':False,'require_parameters':True,'data_collection':'deny',
         'max_price':{'prompt':m['input_usd_per_million'],'completion':m['output_usd_per_million']}},
      'plugins':[{'id':x,'enabled':False} for x in ['web','response-healing','file-parser']],
      'transforms':[],'usage':{'include':True},**m['generation']}
def parse(record,e):
    if record.get('state')!='completed':return {'status':record.get('state'),'physical_choice':None}
    if record.get('refusal'):return {'status':'refusal','physical_choice':None}
    if record.get('finish_reason')=='length':return {'status':'truncation','physical_choice':None}
    try:x=json.loads(record.get('raw_content') or '')
    except (ValueError,TypeError):return {'status':'invalid_json','physical_choice':None}
    if not isinstance(x,dict) or set(x)!={'choice'} or x['choice'] not in ['A','B','DECLINE']:return {'status':'invalid_schema','physical_choice':None}
    return {'status':'valid','physical_choice':e['display_map'].get(x['choice'],'DECLINE'),'display_choice':x['choice']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'run_20261025')
    ap.add_argument('--live',action='store_true');ap.add_argument('--key-file',type=Path);ap.add_argument('--adaptive',action='store_true');a=ap.parse_args()
    root=a.root;f=root/'frozen_inputs';cfg=json.loads((f/'configuration.json').read_text());m=cfg['model']
    manifest=json.loads((f/'manifest.json').read_text())
    for name,value in manifest['files'].items():
        if sha(f/name)!=value:raise SystemExit('Frozen input checksum changed: '+name)
    infile=root/'adaptive/episodes.jsonl' if a.adaptive else f/'episodes.jsonl'
    episodes=readl(infile)
    if not a.live:print(json.dumps({'mode':'offline','model_calls':0,'episodes':len(episodes),'stage_maximum_usd':cfg['stage_maximum_usd']}));return
    if not a.key_file or not a.key_file.is_file():raise SystemExit('Credential file unavailable; no calls sent.')
    key=a.key_file.read_text().strip();kd=api('key',key)['data'];credits=api('credits',key)['data']
    if kd.get('is_management_key') is not False or kd.get('is_provisioning_key') is True:raise SystemExit('Ordinary experiment key required.')
    if kd.get('limit_reset') is not None or kd.get('limit') is None or not 0<D(str(kd['limit']))<=D(cfg['maximum_key_limit_usd']):raise SystemExit('Key cap mismatch.')
    if not kd.get('expires_at') or datetime.fromisoformat(kd['expires_at'].replace('Z','+00:00'))<=datetime.now(timezone.utc):raise SystemExit('Key expired.')
    catalog=api('models');endpoints=api('models/'+m['model_id']+'/endpoints')
    if {x['id']:x for x in catalog['data']}.get(m['catalog_model_id'],{}).get('canonical_slug')!=m['canonical_model_id']:raise SystemExit('Model mapping changed.')
    matches=[x for x in endpoints['data']['endpoints'] if x.get('tag')==m['upstream_provider'] and x.get('name')==m['endpoint_name']]
    if len(matches)!=1:raise SystemExit('Provider mapping changed.')
    ep=matches[0];rates={k:D(str(ep['pricing'][k])) for k in ['prompt','completion']};fee=D(str(ep['pricing'].get('request','0')))
    if any(not x.is_finite() or x<0 for x in [*rates.values(),fee]):raise SystemExit('Invalid prices.')
    if rates['prompt']*1000000>D(str(m['input_usd_per_million'])) or rates['completion']*1000000>D(str(m['output_usd_per_million'])):raise SystemExit('Price ceiling exceeded.')
    if not {'structured_outputs','response_format','max_tokens','reasoning'}<=set(ep['supported_parameters']):raise SystemExit('Parameters unavailable.')
    result=root/'results';result.mkdir(exist_ok=True);lock=result/'collection.lock'
    try:fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:raise SystemExit('Prior collector lock exists; inspect before resuming.')
    with os.fdopen(fd,'w') as h:h.write(json.dumps({'pid':os.getpid(),'started_utc':now()}))
    atexit.register(lambda:lock.unlink(missing_ok=True))
    attempts=result/'attempts';attempts.mkdir(exist_ok=True)
    done=set();spent=D(0)
    for p in attempts.glob('*.json'):
        old=json.loads(p.read_text())
        if old['state']!='completed':raise SystemExit('Unresolved prior attempt; no automatic retry: '+p.name)
        done.add(old['episode_id']);spent+=D(old['accounted_cost_usd'])
    cap=D(cfg['stage_maximum_usd']);remaining=min(D(str(kd['limit_remaining'])),D(str(credits['total_credits']))-D(str(credits['total_usage'])))
    runfile=result/'run.json'
    if not runfile.exists():save(runfile,{'started_utc':now(),'configuration':cfg,'manifest_sha256':sha(f/'manifest.json'),'key_usage_before':kd['usage'],'initial_episodes':len(episodes)})
    elif json.loads(runfile.read_text())['manifest_sha256']!=sha(f/'manifest.json'):raise SystemExit('Run manifest mismatch.')
    suffix='adaptive' if a.adaptive else 'initial'
    save(root/'connection'/('models_'+suffix+'.json'),catalog);save(root/'connection'/('endpoints_'+suffix+'.json'),endpoints)
    pending=[e for e in episodes if e['episode_id'] not in done]
    def reserve(body):return (D(len(json.dumps(body).encode())+4096)*rates['prompt']+D(m['max_output_tokens'])*rates['completion']+fee)*D('1.10')
    def collect(e,body,res):
        path=attempts/(e['episode_id']+'.json')
        record={'state':'intent','data_origin':'live_model','episode_id':e['episode_id'],'configuration':'sol_step6_v01_medium',
          'prompt_sha256':e['prompt_sha256'],'started_utc':now(),'request':body,'reserved_cost_usd':str(res)};save(path,record)
        try:response=api('chat/completions',key,body)
        except Exception as err:
            record.update(state='unresolved_transport',transport_error=str(err),accounted_cost_usd=str(res),ended_utc=now());save(path,record);return record
        record.update(raw_response=response,ended_utc=now())
        if response.get('error') or response.get('model') not in m['expected_returned_model_ids'] or response.get('provider')!=m['upstream_provider_name']:
            record.update(state='unresolved_route',accounted_cost_usd=str(res));save(path,record);return record
        cost=response.get('usage',{}).get('cost')
        if cost is None or not D(str(cost)).is_finite() or D(str(cost))<0:
            record.update(state='unresolved_billing',accounted_cost_usd=str(res));save(path,record);return record
        c=(response.get('choices') or [{}])[0];msg=c.get('message') or {}
        record.update(state='completed',accounted_cost_usd=str(cost),raw_content=msg.get('content'),refusal=msg.get('refusal'),finish_reason=c.get('finish_reason'),returned_model=response.get('model'),provider=response.get('provider'))
        record['parsed']=parse(record,e);save(path,record);return record
    stopped=None
    print(json.dumps({'status':'started','pending':len(pending),'stage_spent_usd':str(spent),'cap_usd':str(cap),'workers':cfg['max_workers']}),flush=True)
    with ThreadPoolExecutor(max_workers=cfg['max_workers']) as pool:
      while pending:
        batch=[];reserved=D(0)
        for e in pending[:cfg['max_workers']]:
            body=request(e,m);res=reserve(body)
            if spent+reserved+res>cap or reserved+res>remaining:break
            batch.append((e,body,res));reserved+=res
        if not batch:stopped='budget_stop';break
        futures=[pool.submit(collect,*args) for args in batch]
        records=[f.result() for f in futures]
        pending=pending[len(batch):]
        for record,(_,_,res) in zip(records,batch):
            cost=D(record['accounted_cost_usd']);spent+=cost;remaining-=cost
            if record['state']=='completed':done.add(record['episode_id'])
            else:stopped=record['state']
            if cost>res:stopped='reserve_exceeded'
        if len(done)%20==0 or stopped or not pending:print(json.dumps({'completed_total':len(done),'remaining_in_module':len(pending),'accounted_cost_usd':str(spent),'stop':stopped}),flush=True)
        if stopped:break
    rows=[json.loads(p.read_text()) for p in sorted(attempts.glob('*.json'))]
    (result/'responses.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    after=api('key',key)['data'];before=D(str(json.loads(runfile.read_text())['key_usage_before']))
    save(root/'billing_reconciliation.json',{'checked_utc':now(),'key_usage_before':str(before),'key_usage_after':str(after['usage']),
       'usage_delta':str(D(str(after['usage']))-before),'accounted_cost_usd':str(spent),'difference':str(D(str(after['usage']))-before-spent),'completed_calls':len(done),'status':stopped or 'complete'})
    print(json.dumps({'status':stopped or 'complete','completed_total':len(done),'accounted_cost_usd':str(spent)}),flush=True)

if __name__=='__main__':main()
