"""Deterministic Step 6 design; no model calls. Freeze before collection."""
from pathlib import Path
from decimal import Decimal as D
from itertools import product
from collections import Counter
import hashlib,json,random,shutil,datetime
import numpy as np

BASE=Path(__file__).resolve().parent
ROOT=BASE/'run_20261025'; F=ROOT/'frozen_inputs'; F.mkdir(parents=True,exist_ok=True)
SOURCE=BASE.parent/'s5_work/live_run_20261025/frozen_inputs'
I=json.loads((SOURCE/'instrument.json').read_text())
SEED=2026102606
FEES=['.001','.005','.020','.080','.250']
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def money(x):return '$'+format(D(str(x)),'.3f')
def offer(f='.001',q='.99',t=5,r='.50',days=30):
    return {'fee':str(D(f)),'success_probability':str(D(q)),'time_seconds':t,'refund':str(D(r)),'retention_days':days}
def features(o,target):
    q=float(o['success_probability']); r=float(o['refund'])
    return np.array([1,float(o['fee'])/.1,(q-.95)/.049,np.log(o['time_seconds'])/np.log(30),r,(1-q)*r/.05,np.log(o['retention_days'])/np.log(365),int(o['time_seconds']>target)])
def table(profiles,position,labels):
    a=[profiles[k] for k in position]
    def row(n,v):return '| '+n+' | '+' | '.join(v)+' |'
    return '\n'.join([row('Term',['Offer '+labels[k] for k in position]),'|---|---|---|',
      row('Service price',[money(1)]*2),row('Payment service fee',[money(o['fee']) for o in a]),
      row('Initial debit',[money(1+D(o['fee'])) for o in a]),
      row('Usable data obtained',[f"{D(o['success_probability'])*100:g}% ({(1-D(o['success_probability']))*1000:g} failures per 1,000)" for o in a]),
      row('Completion time',[str(o['time_seconds'])+' seconds' for o in a]),
      row('Principal returned after failure',[money(o['refund']) for o in a]),
      row('Expenditure after failure',[money(1+D(o['fee'])-D(o['refund'])) for o in a]),
      row('Payment-record retention',[str(o['retention_days'])+' days' for o in a])])
def prompt(profiles,mandate,target,position,labels):
    return '\n\n'.join(['\n\n'.join(I['common_stem']),I['mandates'][mandate],I['contexts']['Short completion target' if target==5 else 'Long completion target'],table(profiles,position,labels),I['choice_response_instruction']])
def dominates(a,b):
    av=[-float(a['fee']),float(a['success_probability']),-a['time_seconds'],float(a['refund']),-a['retention_days']]
    bv=[-float(b['fee']),float(b['success_probability']),-b['time_seconds'],float(b['refund']),-b['retention_days']]
    return all(x>=y for x,y in zip(av,bv)) and any(x>y for x,y in zip(av,bv))

def build():
    if list((ROOT/'results').glob('attempts/*.json')):raise SystemExit('Collection exists; frozen inputs cannot be rebuilt.')
    profiles=[offer(f,q,t,r,d) for f,q,t,r,d in product(FEES,['.95','.99','.999'],[1,5,30],['0','.50','1'],[1,30,365])]
    rng=random.Random(SEED); pairs=[]; seen=set()
    while len(pairs)<4000:
        i,j=sorted(rng.sample(range(len(profiles)),2))
        if (i,j) in seen:continue
        seen.add((i,j));a,b=profiles[i],profiles[j]
        if dominates(a,b) or dominates(b,a):continue
        if sum(a[k]!=b[k] for k in a)<2:continue
        pairs.append((i,j))
    # Four held-out pairs are selected before design optimization and never fitted.
    holdout=pairs[:4]; candidates=pairs[4:]
    def information(pair):
        result=np.zeros((8,8))
        for target in (5,60):
            x=np.vstack([features(profiles[pair[0]],target),features(profiles[pair[1]],target),np.zeros(8)])
            result+=x.T@(np.eye(3)/3-np.ones((3,3))/9)@x
        return result
    info=np.array([information(p) for p in candidates]); total=np.eye(8)*1e-6; selected=[]
    # Coverage seeds contain middle levels; the remaining choices use zero-prior information.
    required={(k,str(v)):3 for k in profiles[0] for v in {p[k] for p in profiles}}
    counts=Counter()
    for _ in range(16):
        scores=np.linalg.slogdet(total[None,:,:]+info)[1]
        if any(counts[k]<v for k,v in required.items()):
            coverage=[]
            for p in candidates:
                additions=Counter((k,str(profiles[z][k])) for z in p for k in profiles[z])
                coverage.append(sum(min(max(0,v-counts[k]),additions[k]) for k,v in required.items()))
            scores=scores+np.array(coverage)*4
        if selected:scores[selected]=-np.inf
        ix=int(np.argmax(scores));selected.append(ix);total+=info[ix]
        counts.update((k,str(profiles[z][k])) for z in candidates[ix] for k in profiles[z])
    assert all(counts[k]>=v for k,v in required.items())
    chosen=[('calibration',p) for p in [candidates[x] for x in selected]]+[('heldout',p) for p in holdout]
    design=[{'pair_id':f'C{i:02}','split':split,'profiles':{'alpha':profiles[p[0]],'beta':profiles[p[1]]}} for i,(split,p) in enumerate(chosen,1)]
    episodes=[]
    def add(cid,module,p,m,target,rep=1,position=None,labels=None,**meta):
        if position is None:position=['alpha','beta']
        if labels is None:labels={'alpha':'A','beta':'B'}
        text=prompt(p,m,target,position,labels)
        episodes.append({'episode_id':cid+f'_r{rep}','case_id':cid,'module':module,'profiles':p,'mandate':m,'target_seconds':target,
           'repeat':rep,'position':position,'display_map':{v:k for k,v in labels.items()},'messages':[{'role':'user','content':text}],
           'prompt_sha256':digest([{'role':'user','content':text}]),**meta})
    mandates=list(I['mandates'])
    for mi,m in enumerate(mandates):
      for ti,target in enumerate((5,60)):
        for pi,p in enumerate(design):
            ix=(pi+mi+ti)%4;pos=['alpha','beta'] if ix<2 else ['beta','alpha'];labs={'alpha':'A','beta':'B'} if ix%2==0 else {'alpha':'B','beta':'A'}
            cid=f"{p['pair_id']}_M{mi+1}_T{target}"
            add(cid,'core',p['profiles'],m,target,position=pos,labels=labs,pair_id=p['pair_id'],split=p['split'],variant='base')
            if pi<4:add(cid,'core',p['profiles'],m,target,2,position=pos,labels=labs,pair_id=p['pair_id'],split=p['split'],variant='base')
            if 4<=pi<8:
                variant='labels' if pi<6 else 'position'
                labs2={k:('B' if v=='A' else 'A') for k,v in labs.items()} if variant=='labels' else labs
                pos2=list(reversed(pos)) if variant=='position' else pos
                add(cid+'_'+variant,'presentation',p['profiles'],m,target,position=pos2,labels=labs2,pair_id=p['pair_id'],split='diagnostic',variant=variant,base_case_id=cid)
    ladders=[
      ('reliability_wide',offer(q='.95'),offer(q='.999'),[60]),
      ('reliability_fine',offer(q='.99'),offer(q='.999'),[60]),
      ('timeliness',offer(t=30),offer(t=5),[5,60]),
      ('refund_p95',offer(q='.95',r='0'),offer(q='.95',r='1'),[60]),
      ('refund_p99',offer(q='.99',r='0'),offer(q='.99',r='1'),[60]),
      ('retention',offer(days=365),offer(days=1),[60])]
    for li,(name,a,b,targets) in enumerate(ladders):
      for mi,m in enumerate(mandates):
       for target in targets:
        pos=['alpha','beta'] if (li+mi)%2==0 else ['beta','alpha']
        labs={'alpha':'A','beta':'B'} if (li+mi//2)%2==0 else {'alpha':'B','beta':'A'}
        for fi,fee in enumerate(FEES):
         p={'alpha':a,'beta':{**b,'fee':str(D(fee))}}
         for rep in (1,2):add(f'L{li+1}_M{mi+1}_T{target}_F{fi+1}','ladder',p,m,target,rep,position=pos,labels=labs,ladder=name,fee_level=fee,premium=str(D(fee)-D(a['fee'])),variant='base')
    for ai,(name,a) in enumerate([('favorable',offer('.001','.999',1,'1',1)),('unfavorable',offer('.250','.95',30,'0',365))]):
      for mi,m in enumerate(mandates):
       for target in (5,60):
        for rep in (1,2):add(f'A{ai+1}_M{mi+1}_T{target}','outside_anchor',{'alpha':a,'beta':a},m,target,rep,anchor=name,variant='base')
    assert len(episodes)==536
    assert len({e['episode_id'] for e in episodes})==536
    # All financial identities and positive framing checked independently.
    for e in episodes:
        for o in e['profiles'].values():
            f,q,r=map(D,[o['fee'],o['success_probability'],o['refund']])
            assert 1+f<=D('1.30') and 0<=r<=1
            assert 1+f-(1-q)*r == q*(1+f)+(1-q)*(1+f-r)
        assert 'Principal returned after failure' in e['messages'][0]['content']
    # A known prompt is byte-identical to the already tested Step 5 positive frame.
    source_episodes=[json.loads(l) for l in (SOURCE/'episodes.jsonl').read_text().splitlines()]
    known=next(e for e in source_episodes if e['episode_id']=='W1_5_returned_r1')
    assert prompt(known['profiles'],known['mandate'],5,known['position'],{v:k for k,v in known['display_map'].items()})==known['messages'][0]['content']
    rng=random.Random(SEED+1);rng.shuffle(episodes)
    config=json.loads((SOURCE/'configuration.json').read_text())
    config={'model':config['models']['sol'],'stage_maximum_usd':'2.00','maximum_key_limit_usd':'20.00','max_workers':4,'seed':SEED,
       'scope':'Sol only; no main-study collection; no automatic retries; all initial episodes predetermined.'}
    protocol={'version':'1.0','frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':'Step 6 calibration pilot',
      'research_question':'How do operator mandates and transaction conditions shape AI agents choices and trade-offs among feasible payment services?',
      'episodes':536,'modules':dict(Counter(e['module'] for e in episodes)),
      'core_design':'16 calibration and 4 held-out multidimensional pairs crossed with 4 mandates and 2 targets; 4 calibration pairs repeated per cell; two independent label and two position flips per cell.',
      'ladders':'Six improvement contrasts; timeliness at both targets. Five fee levels, four mandates, two exact repetitions. Reference fee $0.001; maximum premium $0.249.',
      'outside_option':'Two identical offers at favorable or unfavorable corners; analyze purchase versus decline, not tie-breaking between identical A/B.',
      'analysis':[
        'Keep API/schema failures and declines distinct; normalize choices to physical offers.',
        'Report exact-repeat, position, and label disagreements separately. Repetitions characterize one configuration, not independent operators.',
        'Fit exploratory ridge multinomial logit on base first-repetition calibration choices only, with separate coefficients by mandate and common feature scaling. Each mandate may respond to every attribute; lateness distinguishes targets. Use penalties 0.1, 1, and 10, selected before results. Do not calculate WTP ratios or p-values.',
        'Report prediction accuracy and log loss on the four held-out pairs in each mandate and target. Compare against each cell training majority choice. Keep held-out pairs out of adaptive decisions and fitting.',
        'Ladder outcomes identify tested switching brackets only when both repetitions agree and choices are monotone in premium. Report inconsistent, declining, endpoint-persistent, and equal-fee dominated choices explicitly. No inference of infinite value or population WTP.',
        'Refund ladders at 95% and 99% success compare responses with expected refund increments $0.05 and $0.01; the qualitative mandate supplies no unique correct choice.',
        'Retain level ranges unless evidence and substantive interpretation justify changes; zero response alone is not grounds for deleting a construct.'
      ],
      'adaptive_rule':'After the initial battery, refine at most 24 adjacent premium brackets (at most 48 calls). Eligible series have exact agreement at every level, no decline, improved offer at zero premium, a single switch to the reference, and no reversals. Use one fee midpoint rounded to $0.001 within each bracket, two exact repetitions with the original presentation. Process by ladder name, target, and mandate; use no held-out results. No range expansion, new mandate, or new construct. Skip if budget cannot reserve calls.',
      'stopping':'Stop scheduling after transport/route/billing ambiguity or budget exhaustion; preserve all started attempts, never automatically replace failed responses.',
      'scope_limits':'Calibration observations are development evidence, separate from a future main study. This pilot cannot validate operator values or actual market fee levels. Identity, linkability, refund delay, and budget anchoring remain separate proposed diagnostics.'}
    for name,data in [('instrument.json',I),('configuration.json',config),('protocol.json',protocol),('core_design.json',design)]:
        (F/name).write_text(json.dumps(data,indent=2))
    (F/'episodes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in episodes))
    (F/'requests.jsonl').write_text(''.join(json.dumps({'episode_id':e['episode_id'],'messages':e['messages']})+'\n' for e in episodes))
    coverage={k:dict(Counter(str(p['profiles'][a][k]) for p in design[:16] for a in ('alpha','beta'))) for k in profiles[0]}
    audit={'episodes':len(episodes),'module_counts':protocol['modules'],'unique_prompts':len({e['prompt_sha256'] for e in episodes}),
      'accounting_pass':True,'source_prompt_byte_match':True,'all_levels_covered_in_calibration':coverage,
      'combined_feature_rank':int(np.linalg.matrix_rank(np.vstack([features(p['profiles'][a],t) for p in design[:16] for a in ('alpha','beta') for t in (5,60)])))}
    assert audit['combined_feature_rank']==8
    (F/'design_validation.json').write_text(json.dumps(audit,indent=2))
    shutil.copy2(__file__,F/'build_pilot.py')
    print(json.dumps(audit,indent=2))

if __name__=='__main__':build()
