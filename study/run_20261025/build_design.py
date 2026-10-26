"""Rebuild frozen design deterministically, without network access or responses."""
import argparse,itertools,json,random
from collections import Counter
from pathlib import Path
import numpy as np
from scipy.special import expit
from common import *

SEED=2026102507
def coverage(pairs,profiles):
    return {k:dict(sorted(Counter(str(profiles[i][k]) for p in pairs for i in p).items())) for k in profiles[0]}
def build(root):
    if list((root/'results/attempts').glob('*.json')):raise SystemExit('Existing collection: design rebuild refused.')
    I=json.loads((root/'inputs/instrument.json').read_text());cfg=json.loads((root/'inputs/configuration.json').read_text())
    excluded=set(json.loads((root/'development/excluded_pair_hashes.json').read_text()))
    priors=json.loads((root/'development/pilot_priors.json').read_text())
    profiles=[offer(f,str(q),t,str(r),d) for f,q,t,r,d in itertools.product(FEES,*LEVELS.values())]
    rng=random.Random(SEED);pairs=[];seen=set()
    while len(pairs)<8000:
        i,j=sorted(rng.sample(range(len(profiles)),2))
        if (i,j) in seen:continue
        seen.add((i,j));a,b=profiles[i],profiles[j]
        if sum(float(a[k])!=float(b[k]) for k in a)<2:continue
        if pairhash({'alpha':a,'beta':b}) in excluded:continue
        pairs.append((i,j))
    # Reserve outcomes-free validation tasks before information-based selection.
    for draw in range(10000):
        holdout=rng.sample(pairs,32);c=coverage(holdout,profiles)
        if all(len(c[k])==(9 if k=='fee' else 3) and min(c[k].values())>=(3 if k=='fee' else 8) for k in c):break
    else:raise RuntimeError('Coverage-constrained holdout draw failed')
    hset=set(holdout);remaining=[p for p in pairs if p not in hset]
    simtest=remaining[:1000];candidates=remaining[1000:]
    x=np.array([features(o) for o in profiles]);delta=np.array([x[a]-x[b] for a,b in candidates])
    weights=[]
    for mandate,target in CELLS:
        pred=np.array([pilot_features(o,target) for o in profiles]);w=np.ones(len(candidates))*.25
        for lam in [.1,1,10]:
            row=next(v for v in priors if v['mandate']==mandate and v['penalty']==lam)
            b=np.array([row['coefficients'][k] for k in PILOT_FEATURES]);u=pred@b
            pp=expit(np.array([u[a]-u[b] for a,b in candidates]));w+=pp*(1-pp)
        weights.append(w/4)
    w=np.array(weights);info=np.tile(np.eye(12)*1e-6,(8,1,1));chosen=[];counts=Counter()
    required={(k,str(v)): (6 if k=='fee' else 12) for k in profiles[0] for v in sorted({o[k] for o in profiles},key=float)}
    additions=[Counter((k,str(profiles[i][k])) for i in p for k in profiles[i]) for p in candidates]
    for step in range(80):
        inv=np.linalg.inv(info)
        leverage=np.einsum('ik,ckl,il->ci',delta,inv,delta,optimize=True)
        scores=np.log1p(w*leverage).mean(axis=0)
        if any(counts[k]<v for k,v in required.items()):
            scores+=4*np.array([sum(min(max(v-counts[k],0),a[k]) for k,v in required.items()) for a in additions])
        if chosen:scores[chosen]=-np.inf
        idx=int(np.argmax(scores));chosen.append(idx);d=delta[idx]
        info+=w[:,idx,None,None]*np.outer(d,d)[None,:,:];counts.update(additions[idx])
    selected=[candidates[i] for i in chosen]
    def info_score(indices):
        inf=np.einsum('ci,ij,ik->cjk',w[:,indices],delta[indices],delta[indices])+np.eye(12)[None,:,:]*1e-6
        return float(np.linalg.slogdet(inf)[1].mean()),[float(np.linalg.cond(a)) for a in inf]
    score,conditions=info_score(chosen[:64]);random_scores=[]
    for rep in range(100):random_scores.append(info_score(rng.sample(range(len(candidates)),64))[0])
    designs=[];orient=random.Random(SEED+2)
    for split,ps,prefix in [('estimation',selected,'E'),('heldout',holdout,'H')]:
        combos=list(range(4))*(len(ps)//4);orient.shuffle(combos)
        for i,(pair,pres) in enumerate(zip(ps,combos),1):
            aa,bb=pair if orient.random()<.5 else pair[::-1]
            designs.append({'pair_id':f'{prefix}{i:03}','split':split,'profiles':{'alpha':profiles[aa],'beta':profiles[bb]},
              'position':['alpha','beta'] if pres<2 else ['beta','alpha'],
              'labels':{'alpha':'A','beta':'B'} if pres%2==0 else {'alpha':'B','beta':'A'}})
    # Rebalance presentation within the frozen 64-pair estimation subset.
    combos=list(range(4))*16;orient.shuffle(combos)
    for p,pres in zip(designs[:64],combos):
        p['position']=['alpha','beta'] if pres<2 else ['beta','alpha'];p['labels']={'alpha':'A','beta':'B'} if pres%2==0 else {'alpha':'B','beta':'A'}
    core=designs[:64]+[p for p in designs if p['split']=='heldout']
    rr=random.Random(SEED+3);repeat_e=sorted(rr.sample([p['pair_id'] for p in core if p['split']=='estimation'],16));repeat_h=sorted(rr.sample([p['pair_id'] for p in core if p['split']=='heldout'],8))
    diag_e=rr.sample([p['pair_id'] for p in core if p['split']=='estimation'],8);labels_ids=diag_e[:4];positions_ids=diag_e[4:]
    folds=list(range(4))*16;rr.shuffle(folds)
    for p,fold in zip(core[:64],folds):p['cv_fold']=fold
    episodes=[]
    def add(pair_id,module,profs,mandate,target,rep=1,position=None,labels=None,variant='base',**meta):
        position=position or ['alpha','beta'];labels=labels or {'alpha':'A','beta':'B'}
        case=f'{pair_id}_M{MANDATES.index(mandate)+1}_T{target}'+('' if variant=='base' else '_'+variant)
        messages=[{'role':'user','content':prompt(profs,mandate,target,position,labels,I)}]
        episodes.append({'episode_id':case+f'_r{rep}','case_id':case,'pair_id':pair_id,'module':module,'profiles':profs,'mandate':mandate,'target_seconds':target,'repeat':rep,'variant':variant,'position':position,'display_map':{v:k for k,v in labels.items()},'messages':messages,'prompt_sha256':digest(messages),**meta})
    for p in core:
      for m,t in CELLS:
        args=(p['pair_id'],'core',p['profiles'],m,t)
        meta={k:p[k] for k in ['split','cv_fold'] if k in p}
        add(*args,position=p['position'],labels=p['labels'],**meta)
        if p['pair_id'] in repeat_e+repeat_h:add(*args,rep=2,position=p['position'],labels=p['labels'],**meta)
        for variant,ids in [('labels',labels_ids),('position',positions_ids)]:
            if p['pair_id'] in ids:
                add(p['pair_id'],'presentation',p['profiles'],m,t,position=p['position'][::-1] if variant=='position' else p['position'],labels={k:('B' if v=='A' else 'A') for k,v in p['labels'].items()} if variant=='labels' else p['labels'],variant=variant,split='diagnostic',base_case_id=f"{p['pair_id']}_M{MANDATES.index(m)+1}_T{t}")
    for i,fee in enumerate(['.001','.013','.020','.080','.250'],1):
      profs={'alpha':offer(q='.99'),'beta':offer(f=fee,q='.999')}
      for m,t in CELLS:
       for rep in range(1,5):add(f'F{i}','fine_reliability',profs,m,t,rep,split='diagnostic',premium=str(D(fee)-D('.001')))
    for i,(name,a) in enumerate([('favorable',offer('.001','.999',1,'1',1)),('unfavorable',offer('.250','.95',30,'0',365))],1):
      for m,t in CELLS:
       for rep in [1,2]:add(f'A{i}','outside_anchor',{'alpha':a,'beta':a},m,t,rep,split='diagnostic',anchor=name)
    for i,(q,fee) in enumerate([('.99','.003'),('.99','.013'),('.95','.050'),('.95','.080')],1):
      for m,t in CELLS:
       for rep in [1,2]:add(f'R{i}','refund_success',{'alpha':offer(q=q,r='0'),'beta':offer(f=fee,q=q,r='1')},m,t,rep,split='diagnostic',premium=str(D(fee)-D('.001')))
    random.Random(SEED+4).shuffle(episodes)
    write(root/'inputs/core_design.json',core)
    write(root/'development/nested_designs.json',designs)
    write(root/'development/simulation_test_pairs.json',[{'alpha':profiles[a],'beta':profiles[b]} for a,b in simtest])
    write(root/'inputs/diagnostic_assignments.json',{'exact_estimation':repeat_e,'exact_heldout':repeat_h,'label_swaps':labels_ids,'position_swaps':positions_ids})
    for name,rows in [('episodes.jsonl',episodes),('requests.jsonl',[{'episode_id':e['episode_id'],'request':request(e,cfg['model'])} for e in episodes])]:
        (root/'inputs'/name).write_text(''.join(canonical(r)+'\n' for r in rows))
    ranks={str(n):int(np.linalg.matrix_rank(delta[chosen[:n]])) for n in [48,64,80]}
    audit={'data_origin':'offline_design','seed':SEED,'profiles':len(profiles),'candidate_pool':len(candidates),'heldout_random_draws':draw+1,'excluded_development_pairs':len(excluded),'episodes':len(episodes),'modules':dict(Counter(e['module'] for e in episodes)),
       'core_base_calls':dict(Counter(e['split'] for e in episodes if e['module']=='core' and e['repeat']==1)),
       'estimation_level_counts':coverage(selected[:64],profiles),'heldout_level_counts':coverage(holdout,profiles),'conditional_feature_rank':ranks,'information_condition_numbers':dict(zip([f'{m}|{t}' for m,t in CELLS],conditions)),
       'mean_logdet_64':score,'random_64_logdet_mean':float(np.mean(random_scores)),
       'geometric_information_ratio_vs_random_mean':float(np.exp((score-np.mean(random_scores))/12)),
       'random_designs_better_than_selected':int(sum(x>score for x in random_scores)),
       'criterion':'Greedy mean log determinant across eight cells of information with equally weighted zero and three pilot priors. Coverage bonus until each fee occurs six times and each nonfee level twelve times. Not global optimality or population power.'}
    assert len(episodes)==1280 and all(v==12 for v in ranks.values())
    write(root/'development/design_audit.json',audit)
    print(json.dumps({k:audit[k] for k in ['episodes','core_base_calls','conditional_feature_rank','geometric_information_ratio_vs_random_mean','random_designs_better_than_selected']}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);build(ap.parse_args().root)
