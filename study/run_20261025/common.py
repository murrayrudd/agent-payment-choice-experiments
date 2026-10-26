"""Shared, deterministic main-study definitions. Importing makes no API requests."""
from pathlib import Path
from decimal import Decimal as D
import hashlib, json
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

ROOT=Path(__file__).resolve().parent
MANDATES=['Balanced','Economy','Continuity','Data minimization']
TARGETS=[5,60]
CELLS=[(m,t) for m in MANDATES for t in TARGETS]
FEES=['.001','.003','.005','.013','.020','.050','.080','.165','.250']
LEVELS={'success_probability':[.95,.99,.999],'time_seconds':[1,5,30],'refund':[0,.5,1],'retention_days':[1,30,365]}
FEATURE_NAMES=['fee_0_to_020','fee_020_to_080','fee_080_to_250','success_mid','success_high','time_mid','time_high','refund_mid','refund_high','retention_mid','retention_high','expected_refund_per_050']
PILOT_FEATURES=['purchase_constant','fee_per_0_10','success_scaled_0_95_to_0_999','log_time_scaled_1_to_30','refund_dollars','expected_refund_per_0_05','log_retention_scaled_1_to_365','later_than_target']
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def filehash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def readl(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def pairhash(profs):
    v=sorted([json.dumps({k:float(v) for k,v in o.items()},sort_keys=True,separators=(',',':')) for o in profs.values()])
    return hashlib.sha256(json.dumps(v,separators=(',',':')).encode()).hexdigest()
def offer(f='.001',q='.99',t=5,r='.50',days=30):
    return {'fee':str(D(f)),'success_probability':str(D(q)),'time_seconds':t,'refund':str(D(r)),'retention_days':days}
def features(o,linear=False):
    f=float(o['fee']);r=float(o['refund']);q=float(o['success_probability'])
    v=[f/.1] if linear else [min(f,.02)/.02,max(min(f,.08)-.02,0)/.06,max(f-.08,0)/.17]
    for key,levels in LEVELS.items():v+=([[-1,-1],[1,0],[0,1]][levels.index(float(o[key]))])
    return np.array(v+[(1-q)*r/.05],float)
def pilot_features(o,target):
    q=float(o['success_probability']);r=float(o['refund'])
    return np.array([1,float(o['fee'])/.1,(q-.95)/.049,np.log(o['time_seconds'])/np.log(30),r,(1-q)*r/.05,np.log(o['retention_days'])/np.log(365),int(o['time_seconds']>target)])
def money(x):return '$'+format(D(str(x)),'.3f')
def prompt(profiles,mandate,target,position,labels,instrument):
    a=[profiles[k] for k in position]
    def row(n,v):return '| '+n+' | '+' | '.join(v)+' |'
    table='\n'.join([row('Term',['Offer '+labels[k] for k in position]),'|---|---|---|',
      row('Service price',[money(1)]*2),row('Payment service fee',[money(o['fee']) for o in a]),
      row('Initial debit',[money(1+D(o['fee'])) for o in a]),
      row('Usable data obtained',[f"{D(o['success_probability'])*100:g}% ({(1-D(o['success_probability']))*1000:g} failures per 1,000)" for o in a]),
      row('Completion time',[str(o['time_seconds'])+' seconds' for o in a]),
      row('Principal returned after failure',[money(o['refund']) for o in a]),
      row('Expenditure after failure',[money(1+D(o['fee'])-D(o['refund'])) for o in a]),
      row('Payment-record retention',[str(o['retention_days'])+' days' for o in a])])
    return '\n\n'.join(['\n\n'.join(instrument['common_stem']),instrument['mandates'][mandate],instrument['contexts']['Short completion target' if target==5 else 'Long completion target'],table,instrument['choice_response_instruction']])
def request(e,m):
    return {'model':m['model_id'],'messages':e['messages'],'stream':False,'max_tokens':m['max_output_tokens'],
      'response_format':{'type':'json_schema','json_schema':{'name':'pilot_response','strict':True,'schema':{'type':'object','properties':{'choice':{'type':'string','enum':['A','B','DECLINE']}},'required':['choice'],'additionalProperties':False}}},
      'provider':{'only':[m['upstream_provider']],'allow_fallbacks':False,'require_parameters':True,'data_collection':'deny','max_price':{'prompt':m['input_usd_per_million'],'completion':m['output_usd_per_million']}},
      'plugins':[{'id':x,'enabled':False} for x in ['web','response-healing','file-parser']],
      'transforms':[],'usage':{'include':True},**m['generation']}
def parse(r,e):
    if r.get('state')!='completed':return r.get('state','missing'),None
    if r.get('refusal'):return 'refusal',None
    if r.get('finish_reason')=='length':return 'truncation',None
    try:x=json.loads(r.get('raw_content') or '')
    except (ValueError,TypeError):return 'invalid_json',None
    if not isinstance(x,dict) or set(x)!={'choice'} or x['choice'] not in ('A','B','DECLINE'):return 'invalid_schema',None
    return 'valid',e['display_map'].get(x['choice'],'DECLINE')
def fit_logit(x,y,penalty=1):
    """Sum log likelihood plus half penalty times squared coefficients, all penalized."""
    def fg(b):
        u=x@b;lp=u-logsumexp(u,axis=1,keepdims=True);p=np.exp(lp);p[np.arange(len(y)),y]-=1
        return -lp[np.arange(len(y)),y].sum()+penalty*b@b/2,np.einsum('na,nak->k',p,x)+penalty*b
    z=minimize(fg,np.zeros(x.shape[-1]),jac=True,method='L-BFGS-B',options={'maxiter':1500,'ftol':1e-12,'gtol':1e-7})
    if not z.success:raise RuntimeError('Logit fit failed: '+z.message)
    return z.x
def probabilities(x,b):
    u=x@b;return np.exp(u-logsumexp(u,axis=1,keepdims=True))
