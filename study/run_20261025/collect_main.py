"""Main-study collector: offline by default, explicit --live required.

No retries or response repair. Saves intent before every external request, keeps
unresolved attempts, checks frozen hashes, and reserves all in-flight calls.
"""
import argparse,atexit,json,os,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from common import ROOT,readl,request,parse,filehash

BASE='https://openrouter.ai/api/v1/'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def now():return datetime.now(timezone.utc).isoformat()
def api(path,key=None,body=None):
    h={'Accept':'application/json'}
    if key:h['Authorization']='Bearer '+key
    b=None
    if body is not None:h['Content-Type']='application/json';b=json.dumps(body).encode()
    try:
        with urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(BASE+path,data=b,headers=h),timeout=180) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError('HTTP '+str(e.code)) from None
    except Exception as e:raise RuntimeError(type(e).__name__) from None
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');payload=json.dumps(x,indent=2).encode()
    with tmp.open('wb') as f:
        view=memoryview(payload)
        while view:
            n=f.write(view)
            if not n:raise OSError('Short file write')
            view=view[n:]
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)
def reserve(body,m,rates,fee):
    # Byte length plus 4096 framing tokens exceeds input size for this fixed ASCII-heavy prompt.
    return (D(len(json.dumps(body).encode())+4096)*rates['prompt']+D(m['max_output_tokens'])*rates['completion']+fee)*D('1.10')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--live',action='store_true');ap.add_argument('--key-file',type=Path);a=ap.parse_args()
    root=a.root
    manifest=json.loads((root/'manifest.json').read_text())
    for name,value in manifest['files'].items():
        if filehash(root/name)!=value:raise SystemExit('Frozen checksum mismatch: '+name)
    cfg=json.loads((root/'inputs/configuration.json').read_text());m=cfg['model'];es=readl(root/'inputs/episodes.jsonl')
    if not a.live:print(json.dumps({'mode':'offline','model_calls':0,'episodes':len(es),'maximum_stage_usd':cfg['stage_maximum_usd']}));return
    if not a.key_file or not a.key_file.is_file():raise SystemExit('External credential file required; no calls sent.')
    # Live mode belongs to the subsequent collection stage, after the frozen design is reviewed.
    key=a.key_file.read_text().strip();kd=api('key',key)['data'];credit=api('credits',key)['data']
    if kd.get('is_management_key') is not False or kd.get('is_provisioning_key') is True:raise SystemExit('Ordinary experiment key required.')
    if kd.get('limit_reset') is not None or kd.get('limit') is None or not 0<D(str(kd['limit']))<=D(cfg['maximum_key_limit_usd']):raise SystemExit('Key cap mismatch.')
    if not kd.get('expires_at') or datetime.fromisoformat(kd['expires_at'].replace('Z','+00:00'))<=datetime.now(timezone.utc):raise SystemExit('Key expired.')
    catalog=api('models');endpoints=api('models/'+m['model_id']+'/endpoints')
    if {x['id']:x for x in catalog['data']}.get(m['catalog_model_id'],{}).get('canonical_slug')!=m['canonical_model_id']:raise SystemExit('Model mapping changed.')
    matches=[x for x in endpoints['data']['endpoints'] if x.get('tag')==m['upstream_provider'] and x.get('name')==m['endpoint_name']]
    if len(matches)!=1:raise SystemExit('Provider mapping changed.')
    ep=matches[0];rates={k:D(str(ep['pricing'][k])) for k in ['prompt','completion']};fee=D(str(ep['pricing'].get('request','0')))
    if any(not x.is_finite() or x<0 for x in [*rates.values(),fee]) or fee!=0:raise SystemExit('Price basis changed.')
    if rates['prompt']*1000000>D(str(m['input_usd_per_million'])) or rates['completion']*1000000>D(str(m['output_usd_per_million'])):raise SystemExit('Price ceiling exceeded.')
    if not {'structured_outputs','response_format','max_tokens','reasoning'}<=set(ep['supported_parameters']):raise SystemExit('Required model parameters unavailable.')
    results=root/'results';results.mkdir(exist_ok=True);lock=results/'collection.lock'
    try:fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:raise SystemExit('Existing collector lock: inspect run state before resuming.')
    with os.fdopen(fd,'w') as f:json.dump({'pid':os.getpid(),'started_utc':now()},f)
    def cleanup():lock.unlink(missing_ok=True)
    atexit.register(cleanup)
    try:
        attempts=results/'attempts';attempts.mkdir(exist_ok=True);done=set();spent=D(0)
        for p in attempts.glob('*.json'):
            r=json.loads(p.read_text())
            if r.get('state')!='completed':raise SystemExit('Unresolved prior attempt: no automatic resubmission.')
            done.add(r['episode_id']);spent+=D(r['accounted_cost_usd'])
        if not done<={e['episode_id'] for e in es}:raise SystemExit('Unexpected prior episode IDs.')
        cap=D(cfg['stage_maximum_usd']);remaining=min(D(str(kd['limit_remaining'])),D(str(credit['total_credits']))-D(str(credit['total_usage'])))
        runfile=results/'run.json'
        if runfile.exists():
            if json.loads(runfile.read_text())['manifest_sha256']!=filehash(root/'manifest.json'):raise SystemExit('Prior run used different manifest.')
        else:save(runfile,{'started_utc':now(),'manifest_sha256':filehash(root/'manifest.json'),'key_usage_before':kd['usage'],'configuration':cfg})
        save(results/'connection.json',{'checked_utc':now(),'catalog':catalog,'endpoints':endpoints})
        def collect(e,body,res):
            path=attempts/(e['episode_id']+'.json');r={'state':'intent','data_origin':'live_main_study','episode_id':e['episode_id'],'prompt_sha256':e['prompt_sha256'],'started_utc':now(),'request':body,'reserved_cost_usd':str(res)};save(path,r)
            try:raw=api('chat/completions',key,body)
            except Exception as exc:
                r.update(state='unresolved_transport',error=str(exc),ended_utc=now(),accounted_cost_usd=str(res));save(path,r);return r
            r.update(raw_response=raw,ended_utc=now())
            state=None
            if raw.get('error') or raw.get('model') not in m['expected_returned_model_ids'] or raw.get('provider')!=m['upstream_provider_name']:state='unresolved_route'
            cost=raw.get('usage',{}).get('cost')
            try:cost=D(str(cost));valid=cost.is_finite() and cost>=0
            except Exception:valid=False
            if not valid:state=state or 'unresolved_billing'
            if state:r.update(state=state,accounted_cost_usd=str(res));save(path,r);return r
            c=(raw.get('choices') or [{}])[0];msg=c.get('message') or {}
            r.update(state='completed',accounted_cost_usd=str(cost),raw_content=msg.get('content'),refusal=msg.get('refusal'),finish_reason=c.get('finish_reason'))
            status,choice=parse(r,e);r['parsed']={'status':status,'physical_choice':choice};save(path,r);return r
        pending=[e for e in es if e['episode_id'] not in done];stop=None
        print(json.dumps({'status':'started','pending':len(pending),'stage_spent_usd':str(spent),'cap_usd':str(cap)}),flush=True)
        with ThreadPoolExecutor(max_workers=cfg['max_workers']) as pool:
            while pending:
                batch=[];reserved=D(0)
                for e in pending[:cfg['max_workers']]:
                    body=request(e,m);res=reserve(body,m,rates,fee)
                    if spent+reserved+res>cap or reserved+res>remaining:break
                    batch.append((e,body,res));reserved+=res
                if not batch:stop='budget_stop';break
                futures=[pool.submit(collect,*x) for x in batch];records=[f.result() for f in futures];pending=pending[len(batch):]
                for r,(_,_,res) in zip(records,batch):
                    cost=D(r['accounted_cost_usd']);spent+=cost;remaining-=cost
                    if r['state']=='completed':done.add(r['episode_id'])
                    else:stop=r['state']
                    if cost>res:stop='reserve_exceeded'
                    if r['state']=='completed' and r['parsed']['status']!='valid':stop='response_failure'
                if len(done)%20==0 or stop or not pending:print(json.dumps({'completed':len(done),'remaining':len(pending),'accounted_cost_usd':str(spent),'stop':stop}),flush=True)
                if stop:break
        rows=[json.loads(p.read_text()) for p in sorted(attempts.glob('*.json'))]
        save(results/'run_status.json',{'checked_utc':now(),'status':stop or 'complete','completed':len(done),'planned':len(es),'accounted_cost_usd':str(spent)})
        try:
            after=api('key',key)['data'];before=D(str(json.loads(runfile.read_text())['key_usage_before']))
            save(results/'billing_reconciliation.json',{'checked_utc':now(),'usage_delta':str(D(str(after['usage']))-before),'accounted_cost_usd':str(spent),'difference':str(D(str(after['usage']))-before-spent),'note':'Key usage may lag response usage; reconcile again before closing.'})
        except Exception:print('Billing recheck unavailable; attempts remain recorded.',flush=True)
        print(json.dumps({'status':stop or 'complete','completed':len(done),'accounted_cost_usd':str(spent)}),flush=True)
    finally:cleanup();atexit.unregister(cleanup)
if __name__=='__main__':main()
