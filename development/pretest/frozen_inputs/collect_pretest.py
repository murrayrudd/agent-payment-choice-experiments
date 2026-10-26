"""Sequential bounded OpenRouter collector. Offline by default; never stores credentials."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import argparse,atexit,hashlib,json,os,urllib.request,urllib.error

ROOT=Path(__file__).resolve().parent
BASE='https://openrouter.ai/api/v1/'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readl(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def save(p,x):
    with p.open('w') as f:json.dump(x,f,indent=2);f.flush();os.fsync(f.fileno())
def api(path,key=None,body=None):
    headers={'Accept':'application/json'}
    if key:headers['Authorization']='Bearer '+key
    data=None
    if body is not None:headers['Content-Type']='application/json';data=json.dumps(body).encode()
    req=urllib.request.Request(BASE+path,data=data,headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=180) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError('HTTP '+str(e.code)) from None
    except Exception as e:raise RuntimeError(type(e).__name__) from None
def schema(answer):
    if answer['scoring']!='factual':props={'choice':{'type':'string','enum':['A','B','DECLINE']}}
    else:props={k:{'type':'boolean' if isinstance(v,bool) else 'number'} for k,v in answer['expected'].items()}
    return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}

def main():
    a=argparse.ArgumentParser();a.add_argument('--model',choices=['sol','qwen'],default='sol');a.add_argument('--live',action='store_true')
    a.add_argument('--output',type=Path);args=a.parse_args()
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for name,expected in manifest['files'].items():
        if sha(ROOT/name)!=expected:raise SystemExit('Input checksum mismatch: '+name)
    episodes=readl(ROOT/'episodes.jsonl');answers={k['case_id']:k for k in readl(ROOT/'answer_key.jsonl')}
    config=json.loads((ROOT/'configuration.json').read_text());m=config['models'][args.model]
    if not args.live:
        print(json.dumps({'mode':'offline','model_calls':0,'episodes':len(episodes),'model':m['model_id'],'live_requires':'--live, --output, and OPENROUTER_API_KEY'}));return
    key=os.environ.get('OPENROUTER_API_KEY')
    if not key:raise SystemExit('No active OPENROUTER_API_KEY. No model calls sent.')
    if not args.output:raise SystemExit('--output is required for live collection.')
    cap=D(str(config['pretest_maximum_usd']))
    kd=api('key',key)['data']
    if kd.get('is_management_key') is not False or kd.get('is_provisioning_key') is True:raise SystemExit('Use an ordinary experiment key.')
    key_cap=D(str(config['maximum_key_limit_usd']))
    if kd.get('limit_reset') is not None or kd.get('limit') is None or not 0<D(str(kd['limit']))<=key_cap:
        raise SystemExit('Use a nonresetting key within the authorized account-key cap; no inference sent.')
    if kd.get('expires_at') is None or datetime.fromisoformat(kd['expires_at'].replace('Z','+00:00'))<=datetime.now(timezone.utc):
        raise SystemExit('Use an active temporary experiment key; no inference sent.')
    remaining=D(str(kd.get('limit_remaining',0)))
    catalog={x['id']:x for x in api('models')['data']}
    if catalog.get(m['catalog_model_id'],{}).get('canonical_slug')!=m['canonical_model_id']:
        raise SystemExit('Historical model mapping unavailable or changed; no substitution permitted.')
    es=api('models/'+m['model_id']+'/endpoints')['data']['endpoints']
    matches=[x for x in es if x.get('tag')==m['upstream_provider'] and x.get('name')==m['endpoint_name']]
    if len(matches)!=1:raise SystemExit('Historical provider endpoint unavailable or changed.')
    ep=matches[0];rates={k:D(str(ep['pricing'][k])) for k in ['prompt','completion']}
    for k,field in [('prompt','input_usd_per_million'),('completion','output_usd_per_million')]:
        if rates[k]*1000000>D(str(m[field])):raise SystemExit('Current pricing exceeds the historical ceiling.')
    if not {'structured_outputs','response_format','max_tokens'}<=set(ep.get('supported_parameters',[])):
        raise SystemExit('Required endpoint parameters unavailable.')
    request_fee=D(str(ep['pricing'].get('request','0')))
    if any(not x.is_finite() or x<0 for x in [*rates.values(),request_fee]):raise SystemExit('Invalid endpoint prices.')
    args.output.mkdir(parents=True,exist_ok=True)
    lock=args.output/'collection.lock'
    try:fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:raise SystemExit('Another or interrupted collector owns this folder; inspect the lock before resuming.')
    with os.fdopen(fd,'w') as f:f.write(json.dumps({'pid':os.getpid(),'started_utc':now()}))
    atexit.register(lambda:lock.unlink(missing_ok=True))
    run={'model_slot':args.model,'model':m,'instrument_manifest_sha256':sha(ROOT/'manifest.json'),'episode_count':len(episodes),
         'pretest_maximum_usd':str(cap),'maximum_key_limit_usd':str(key_cap)}
    runfile=args.output/'run.json'
    if runfile.exists() and json.loads(runfile.read_text())!=run:raise SystemExit('Output folder belongs to another configuration.')
    if not runfile.exists():save(runfile,run)
    intents=args.output/'attempts';intents.mkdir(exist_ok=True)
    spent=D(0);done=set()
    for p in intents.glob('*.json'):
        old=json.loads(p.read_text())
        if old.get('state')!='completed':raise SystemExit('Unresolved prior attempt; reconcile it before resuming: '+p.name)
        spent+=D(old['accounted_cost_usd']);done.add(old['episode_id'])
    configuration=args.model+'_step5_v02_medium'
    for e in episodes:
        if e['episode_id'] in done:continue
        body={'model':m['model_id'],'messages':e['messages'],'stream':False,'max_tokens':m['max_output_tokens'],
          'response_format':{'type':'json_schema','json_schema':{'name':'pretest_response','strict':True,'schema':schema(answers[e['case_id']])}},
          'provider':{'only':[m['upstream_provider']],'allow_fallbacks':False,'require_parameters':True,'data_collection':'deny',
                      'max_price':{'prompt':m['input_usd_per_million'],'completion':m['output_usd_per_million']}},
          'plugins':[{'id':x,'enabled':False} for x in ['web','response-healing','file-parser']],
          'transforms':[],'usage':{'include':True},**m['generation']}
        reserve=(D(len(json.dumps(body).encode())+4096)*rates['prompt']+D(m['max_output_tokens'])*rates['completion']+request_fee)*D('1.10')
        if spent+reserve>cap or reserve>remaining:
            print(json.dumps({'status':'budget_stop','completed':len(done),'accounted_cost_usd':str(spent)}));break
        path=intents/(e['episode_id']+'.json')
        record={'state':'intent','data_origin':'live_model','configuration':configuration,'episode_id':e['episode_id'],
          'prompt_sha256':e['prompt_sha256'],'started_utc':now(),'request':body,'reserved_cost_usd':str(reserve)}
        save(path,record)
        try:response=api('chat/completions',key,body)
        except Exception as err:
            record.update(state='unresolved_transport',transport_error=str(err),accounted_cost_usd=str(reserve),ended_utc=now())
            save(path,record);raise SystemExit('Transport failure preserved. Stop; no automatic retry.')
        record['raw_response']=response;record['ended_utc']=now()
        if response.get('error') or response.get('model') not in m['expected_returned_model_ids'] or response.get('provider')!=m['upstream_provider_name']:
            record.update(state='unresolved_route',accounted_cost_usd=str(reserve));save(path,record)
            raise SystemExit('Response error or route mismatch preserved; collection stopped.')
        cost=response.get('usage',{}).get('cost')
        if cost is None or not D(str(cost)).is_finite() or D(str(cost))<0:
            record.update(state='unresolved_billing',accounted_cost_usd=str(reserve));save(path,record)
            raise SystemExit('Missing or invalid billing; collection stopped.')
        choices=response.get('choices') or [{}];choice=choices[0];message=choice.get('message') or {}
        record.update(state='completed',accounted_cost_usd=str(cost),raw_content=message.get('content'),
          refusal=message.get('refusal'),finish_reason=choice.get('finish_reason'),returned_model=response.get('model'),provider=response.get('provider'))
        save(path,record);spent+=D(str(cost));remaining-=D(str(cost));done.add(e['episode_id'])
        print(json.dumps({'episode_id':e['episode_id'],'completed':len(done),'accounted_cost_usd':str(spent)}),flush=True)
        if D(str(cost))>reserve:raise SystemExit('Actual charge exceeded reserve; stopped.')
    rows=[json.loads(p.read_text()) for p in sorted(intents.glob('*.json'))]
    (args.output/'responses.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    print(json.dumps({'status':'collection_finished' if len(done)==len(episodes) else 'collection_partial','completed':len(done),'configuration':configuration}))

if __name__=='__main__':main()
