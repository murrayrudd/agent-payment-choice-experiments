"""Offline Step 6 scoring and prediction checks. Makes no network requests."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import argparse,csv,json,math,hashlib
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

FEATURE_NAMES=['purchase_constant','fee_per_0_10','success_scaled_0_95_to_0_999','log_time_scaled_1_to_30','refund_dollars','expected_refund_per_0_05','log_retention_scaled_1_to_365','later_than_target']
def readl(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def features(o,target):
    q=float(o['success_probability']);r=float(o['refund'])
    return np.array([1,float(o['fee'])/.1,(q-.95)/.049,np.log(o['time_seconds'])/np.log(30),r,(1-q)*r/.05,np.log(o['retention_days'])/np.log(365),int(o['time_seconds']>target)])
def parse(r,e):
    if r.get('state')!='completed':return r.get('state'),None
    if r.get('refusal'):return 'refusal',None
    if r.get('finish_reason')=='length':return 'truncation',None
    try:x=json.loads(r.get('raw_content') or '')
    except (ValueError,TypeError):return 'invalid_json',None
    if not isinstance(x,dict) or set(x)!= {'choice'} or x['choice'] not in ('A','B','DECLINE'):return 'invalid_schema',None
    return 'valid',e['display_map'].get(x['choice'],'DECLINE')
def load(root):
    episodes=readl(root/'frozen_inputs/episodes.jsonl')
    for name in ['adaptive','confirmation']:
        if (root/name/'episodes.jsonl').exists():episodes+=readl(root/name/'episodes.jsonl')
    meta={e['episode_id']:e for e in episodes};rows=[]
    for path in sorted((root/'results/attempts').glob('*.json')):
        r=json.loads(path.read_text());e=meta[r['episode_id']]
        assert r['prompt_sha256']==e['prompt_sha256']
        assert hashlib.sha256(json.dumps(e['messages'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()==e['prompt_sha256']
        status,choice=parse(r,e)
        rows.append({**e,'status':status,'physical_choice':choice,'cost_usd':r.get('accounted_cost_usd'),
          'usage':r.get('raw_response',{}).get('usage',{}),'started_utc':r.get('started_utc'),'ended_utc':r.get('ended_utc')})
    return episodes,rows
def analyze(root):
    episodes,rows=load(root);valid=[r for r in rows if r['status']=='valid'];byid={r['episode_id']:r for r in rows}
    summary={'planned_calls':len(episodes),'recorded_calls':len(rows),'valid_responses':len(valid),'status_counts':dict(Counter(r['status'] for r in rows)),
      'accounted_cost_usd':str(sum((D(r['cost_usd']) for r in rows if r['cost_usd'] is not None),D(0))),
      'modules':dict(Counter(r['module'] for r in rows)),'started_utc':min((r['started_utc'] for r in rows),default=None),'ended_utc':max((r['ended_utc'] for r in rows),default=None)}
    reps=defaultdict(list)
    for r in rows:reps[r['case_id']].append(r)
    repeat_results=[]
    for case,rs in reps.items():
        if len(rs)!=2:continue
        rs=sorted(rs,key=lambda r:r['repeat'])
        assert rs[0]['prompt_sha256']==rs[1]['prompt_sha256']
        raw=[r['physical_choice'] for r in rs]
        choices=[('purchase' if x in ('alpha','beta') else x) for x in raw] if rs[0]['module']=='outside_anchor' else raw
        repeat_results.append({'case_id':case,'module':rs[0]['module'],'mandate':rs[0]['mandate'],'target_seconds':rs[0]['target_seconds'],
          'valid_pair':all(r['status']=='valid' for r in rs),'choices':choices,'physical_choices':raw,'disagree':choices[0]!=choices[1]})
    summary['repeat_consistency']={m:{'valid_pairs':sum(x['valid_pair'] for x in repeat_results if x['module']==m),
      'disagreements':sum(x['valid_pair'] and x['disagree'] for x in repeat_results if x['module']==m)} for m in sorted({x['module'] for x in repeat_results})}
    summary['repeat_disagreements']=[x for x in repeat_results if x['valid_pair'] and x['disagree']]
    presentation=[]
    for r in rows:
        if r['module']!='presentation':continue
        b=byid.get(r['base_case_id']+'_r1')
        if b:presentation.append({'case_id':r['case_id'],'variant':r['variant'],'mandate':r['mandate'],'target_seconds':r['target_seconds'],
             'choices':[b['physical_choice'],r['physical_choice']],'valid_pair':b['status']=='valid' and r['status']=='valid','disagree':b['physical_choice']!=r['physical_choice']})
    summary['presentation']={m:{'valid_pairs':sum(x['valid_pair'] for x in presentation if x['variant']==m),'disagreements':sum(x['valid_pair'] and x['disagree'] for x in presentation if x['variant']==m)} for m in ['labels','position']}
    summary['presentation_disagreements']=[x for x in presentation if x['valid_pair'] and x['disagree']]
    # Ladders are interpreted independently of held-out core responses.
    groups=defaultdict(list)
    for r in rows:
        if r['module']=='ladder':groups[(r['ladder'],r['target_seconds'],r['mandate'])].append(r)
    ladders=[]
    for (name,target,mandate),rs in sorted(groups.items()):
        levels=[]
        for premium in sorted({D(r['premium']) for r in rs}):
            obs=sorted([r for r in rs if D(r['premium'])==premium],key=lambda r:r['repeat'])
            ch=[r['physical_choice'] for r in obs]
            levels.append({'premium':str(premium),'improved_fee':obs[0]['fee_level'],'choices':ch,'episode_ids':[r['episode_id'] for r in obs],
              'agreement':len(obs)==2 and all(r['status']=='valid' for r in obs) and len(set(ch))==1})
        consensus=[x['choices'][0] if x['agreement'] else None for x in levels]
        eligible=False;bracket=None
        if len(levels)!=5 or None in consensus:category='repeat_disagreement_or_incomplete'
        elif 'DECLINE' in consensus:category='includes_decline'
        elif all(x=='beta' for x in consensus):category='improvement_at_maximum_premium'
        elif all(x=='alpha' for x in consensus):category='reference_at_equal_fee'
        elif consensus[0]=='beta' and all(consensus[i]!='alpha' or all(x=='alpha' for x in consensus[i:]) for i in range(5)):
            category='monotone_switch';ix=consensus.index('alpha');bracket=[levels[ix-1]['premium'],levels[ix]['premium']];eligible=True
        else:category='nonmonotone'
        ladders.append({'ladder':name,'target_seconds':target,'mandate':mandate,'levels':levels,'category':category,'initial_bracket_premium_usd':bracket,'eligible_for_refinement':eligible})
    summary['ladder_categories']=dict(Counter(x['category'] for x in ladders));summary['ladders']=ladders
    anchors=[]
    for r in valid:
        if r['module']=='outside_anchor':anchors.append({'anchor':r['anchor'],'mandate':r['mandate'],'target_seconds':r['target_seconds'],'repeat':r['repeat'],'choice':'DECLINE' if r['physical_choice']=='DECLINE' else 'PURCHASE'})
    summary['outside_anchors']=anchors
    core=[r for r in valid if r['module']=='core' and r['variant']=='base' and r['repeat']==1]
    summary['core_by_mandate']={m:dict(Counter(r['physical_choice'] for r in core if r['mandate']==m)) for m in sorted({r['mandate'] for r in core})}
    summary['core_target_changes']=[];summary['core_mandate_changes']=[]
    for pair in sorted({r['pair_id'] for r in core}):
        for m in sorted({r['mandate'] for r in core}):
            match=sorted([r for r in core if r['pair_id']==pair and r['mandate']==m],key=lambda r:r['target_seconds'])
            if len(match)==2:summary['core_target_changes'].append({'pair_id':pair,'mandate':m,'choices':[r['physical_choice'] for r in match],'changed':match[0]['physical_choice']!=match[1]['physical_choice']})
        for t in (5,60):
            match={r['mandate']:r['physical_choice'] for r in core if r['pair_id']==pair and r['target_seconds']==t}
            summary['core_mandate_changes'].append({'pair_id':pair,'target_seconds':t,'choices':match,'changed':len(set(match.values()))>1})
    fits=[]
    def arrays(rs):
        x=np.array([np.vstack([features(r['profiles']['alpha'],r['target_seconds']),features(r['profiles']['beta'],r['target_seconds']),np.zeros(8)]) for r in rs])
        y=np.array([['alpha','beta','DECLINE'].index(r['physical_choice']) for r in rs]);return x,y
    for m in sorted({r['mandate'] for r in core}):
        train=[r for r in core if r['mandate']==m and r['split']=='calibration'];test=[r for r in core if r['mandate']==m and r['split']=='heldout']
        if len(train)!=32 or len(test)!=8:continue
        x,y=arrays(train);xt,yt=arrays(test)
        for penalty in [.1,1,10]:
            def loss(beta):
                u=x@beta;lp=u-logsumexp(u,axis=1)[:,None];p=np.exp(lp)
                val=-lp[np.arange(len(y)),y].sum()+penalty*np.dot(beta,beta)/2
                grad=np.einsum('na,nak->k',p,x)-x[np.arange(len(y)),y].sum(axis=0)+penalty*beta
                return val,grad
            fit=minimize(loss,np.zeros(8),jac=True,method='BFGS',options={'gtol':1e-7,'maxiter':2000})
            u=xt@fit.x;lp=u-logsumexp(u,axis=1)[:,None];pr=np.argmax(u,axis=1)
            baseline=[];baseline_lp=[]
            for r,yy in zip(test,yt):
                counts=Counter(['alpha','beta','DECLINE'].index(s['physical_choice']) for s in train if s['target_seconds']==r['target_seconds'])
                baseline.append(max(range(3),key=lambda k:counts[k]));baseline_lp.append(math.log((counts[yy]+1)/(sum(counts.values())+3)))
            fits.append({'mandate':m,'penalty':penalty,'coefficients':dict(zip(FEATURE_NAMES,fit.x.tolist())),'converged':bool(fit.success or np.linalg.norm(fit.jac)<1e-5),
              'gradient_norm':float(np.linalg.norm(fit.jac)),'train_n':len(y),'test_n':len(yt),'heldout_correct':int(sum(pr==yt)),
              'heldout_log_loss':float(-lp[np.arange(len(yt)),yt].mean()),'baseline_correct':int(sum(np.array(baseline)==yt)),'baseline_log_loss':float(-np.mean(baseline_lp)),
              'predictions':[{'episode_id':r['episode_id'],'observed':r['physical_choice'],'predicted':['alpha','beta','DECLINE'][int(pp)],'probabilities':dict(zip(['alpha','beta','DECLINE'],np.exp(p).tolist()))} for r,pp,p in zip(test,pr,lp)]})
    summary['exploratory_fits']=fits
    summary['prediction_summary']=[{'penalty':p,'correct':sum(f['heldout_correct'] for f in fits if f['penalty']==p),'n':sum(f['test_n'] for f in fits if f['penalty']==p),
      'mean_log_loss':float(np.mean([f['heldout_log_loss'] for f in fits if f['penalty']==p])),'baseline_correct':sum(f['baseline_correct'] for f in fits if f['penalty']==p)} for p in [.1,1,10] if fits]
    adaptive=[]
    for (case,rs) in sorted(reps.items()):
        if rs[0]['module']!='adaptive_ladder':continue
        adaptive.append({'case_id':case,'ladder':rs[0]['ladder'],'mandate':rs[0]['mandate'],'target_seconds':rs[0]['target_seconds'],
          'initial_bracket':rs[0]['initial_bracket'],'premium':rs[0]['premium'],'choices':[r['physical_choice'] for r in sorted(rs,key=lambda r:r['repeat'])]})
    summary['adaptive_results']=adaptive
    summary['fixed_presentation_confirmation']=None
    if (root/'confirmation/plan.json').exists():
        plan=json.loads((root/'confirmation/plan.json').read_text())
        cells=[{**x,'choice':byid.get(x['episode_id'],{}).get('physical_choice'),'status':byid.get(x['episode_id'],{}).get('status')} for x in plan['comparison_cells']]
        if all(x['status']=='valid' for x in cells):
            target=[];mandate=[];recheck=[]
            for pair in sorted({x['pair_id'] for x in cells}):
                for m in sorted({x['mandate'] for x in cells}):
                    group=sorted([x for x in cells if x['pair_id']==pair and x['mandate']==m],key=lambda x:x['target_seconds'])
                    target.append({'pair_id':pair,'mandate':m,'choices':[x['choice'] for x in group],'changed':group[0]['choice']!=group[1]['choice']})
                for t in [5,60]:
                    choices={x['mandate']:x['choice'] for x in cells if x['pair_id']==pair and x['target_seconds']==t}
                    mandate.append({'pair_id':pair,'target_seconds':t,'choices':choices,'changed':len(set(choices.values()))>1})
            for x in cells:
                if x['origin']=='confirmation':recheck.append({'episode_id':x['episode_id'],'original_episode_id':x['original_episode_id'],'choices':[byid[x['original_episode_id']]['physical_choice'],x['choice']],'changed':byid[x['original_episode_id']]['physical_choice']!=x['choice']})
            summary['fixed_presentation_confirmation']={'new_calls':96,'reused_initial_calls':32,'cells':cells,'target_changes':target,'mandate_changes':mandate,'differences_from_original':recheck}
    summary['token_totals']={k:sum(r['usage'].get(k,0) or 0 for r in rows) for k in ['prompt_tokens','completion_tokens','total_tokens']}
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (root/'repeat_pairs.json').write_text(json.dumps(repeat_results,indent=2))
    out=root/'scored_choices.csv'
    fields=['episode_id','case_id','module','mandate','target_seconds','repeat','status','physical_choice','cost_usd']
    with out.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k) for k in fields} for r in rows)
    return summary
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'run_20261025');a=ap.parse_args()
    s=analyze(a.root)
    print(json.dumps({k:s[k] for k in ['planned_calls','recorded_calls','valid_responses','accounted_cost_usd','repeat_consistency','presentation','ladder_categories','prediction_summary']},indent=2))
