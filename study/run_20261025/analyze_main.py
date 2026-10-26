"""Prespecified offline scoring, grouped CV, matched contrasts and held-out prediction.

Repeated calls and diagnostics never enter model estimation or held-out scoring.
No automatic monetary valuation is reported.
"""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from common import *

CHOICES=['alpha','beta','DECLINE']
def arrays(rows,linear=False,conditional=False):
    a=[]
    for r in rows:
        x=[np.r_[1,features(r['profiles'][k],linear)] for k in ['alpha','beta']]
        if conditional:x=[v[1:] for v in x]
        else:x.append(np.zeros(len(x[0])))
        a.append(x)
    return np.array(a),np.array([CHOICES.index(r['choice']) for r in rows])
def score(rows,probs):
    y=np.array([CHOICES.index(r['choice']) for r in rows])
    return {'n':len(rows),'accuracy':float(np.mean(probs.argmax(axis=1)==y)),'log_loss':float(np.mean(-np.log(np.clip(probs[np.arange(len(y)),y],1e-12,1))))}
def rule_probs(row,name,lapse):
    def val(o):
        f,q,r=D(o['fee']),D(o['success_probability']),D(o['refund']);t,d=o['time_seconds'],o['retention_days'];ex=1+f-(1-q)*r
        if name=='lowest_fee':return -f
        if name=='lowest_expected_expenditure':return -ex
        if name=='highest_success':return q
        if name=='shortest_retention':return -d
        return (int(t<=row['target_seconds']),q,-t)
    v=[val(row['profiles'][k]) for k in ['alpha','beta']];win=[i for i,x in enumerate(v) if x==max(v)]
    p=np.full(3,lapse/3)
    for i in win:p[i]+=(1-lapse)/len(win)
    return p
def bootstrap_mean(values,seed=72025):
    if not values:return None
    a=np.array(values,float);rng=np.random.default_rng(seed);z=np.mean(a[rng.integers(0,len(a),(1000,len(a)))],axis=1)
    return {'mean':float(a.mean()),'pairs':len(a),'finite_design_resampling_95_percentile':[float(x) for x in np.quantile(z,[.025,.975])]}

def analyze(root,out):
    meta={r['episode_id']:r for r in readl(root/'inputs/episodes.jsonl')};rows=[]
    for p in sorted((root/'results/attempts').glob('*.json')):
        record=json.loads(p.read_text());e=meta[record['episode_id']]
        assert e['prompt_sha256']==record['prompt_sha256'] and digest(e['messages'])==e['prompt_sha256']
        status,choice=parse(record,e);rows.append({**e,'status':status,'choice':choice,'data_origin':record.get('data_origin','unspecified')})
    origins={r['data_origin'] for r in rows}
    if len(origins)>1:raise ValueError('Mixed data origins: do not combine synthetic and live observations.')
    summary={'planned_calls':len(meta),'recorded_calls':len(rows),'valid_responses':sum(r['status']=='valid' for r in rows),'status_counts':dict(Counter(r['status'] for r in rows)),
      'data_origin':next(iter(origins)) if rows else 'no_main_study_data','monetary_estimates':'Not produced automatically. Apply the preregistered interpretation gates.'}
    if not rows:write(out/'summary.json',summary);print(json.dumps(summary));return
    byid={r['episode_id']:r for r in rows};valid=[r for r in rows if r['status']=='valid'];cases=defaultdict(list)
    for r in rows:cases[r['case_id']].append(r)
    repeats=[]
    for case,rs in cases.items():
        rs=sorted(rs,key=lambda r:r['repeat'])
        if len(rs)>1:
            assert len({r['prompt_sha256'] for r in rs})==1
            choices=[('PURCHASE' if r['choice'] in ('alpha','beta') else r['choice']) if r['module']=='outside_anchor' else r['choice'] for r in rs]
            repeats.append({'case_id':case,'module':rs[0]['module'],'recorded':len(rs),'valid':all(r['status']=='valid' for r in rs),'choices':choices,'disagreement':len(set(choices))>1})
    presentation=[]
    for r in rows:
        if r['module']=='presentation':
            b=byid.get(r['base_case_id']+'_r1')
            presentation.append({'episode_id':r['episode_id'],'variant':r['variant'],'valid_pair':bool(b and b['status']=='valid' and r['status']=='valid'),'changed':bool(b and b['choice']!=r['choice'])})
    core=[r for r in valid if r['module']=='core' and r['repeat']==1]
    lookup={(r['pair_id'],r['mandate'],r['target_seconds']):r for r in core};contrasts=[]
    for kind in ['mandate','target']:
      for m in (MANDATES[1:] if kind=='mandate' else MANDATES):
       for target in (TARGETS if kind=='mandate' else [None]):
        entries=[]
        for pair in sorted({r['pair_id'] for r in core}):
            a=lookup.get((pair,'Balanced' if kind=='mandate' else m,target if kind=='mandate' else 5));b=lookup.get((pair,m,target if kind=='mandate' else 60))
            if not a or not b:continue
            entry={'pair_id':pair,'changed':int(a['choice']!=b['choice']),'both_purchase':a['choice']!='DECLINE' and b['choice']!='DECLINE'}
            if entry['both_purchase']:
                oa=a['profiles'][a['choice']];ob=b['profiles'][b['choice']]
                entry['selected_attribute_change']={k:float(ob[k])-float(oa[k]) for k in oa}
            entries.append(entry)
        contrasts.append({'kind':kind,'mandate':m,'target':target,'choice_change':bootstrap_mean([r['changed'] for r in entries]),'entries':entries})
    write(out/'diagnostics.json',{'exact_repeats':repeats,'presentation':presentation,'diagnostic_choices':[r for r in rows if r['split']=='diagnostic']})
    write(out/'matched_contrasts.json',contrasts)
    train=[r for r in core if r['split']=='estimation'];test=[r for r in core if r['split']=='heldout']
    fits=[];predictions=[];baseline=[]
    # Select a common penalty per specification from four folds grouped by physical pair.
    # All cell-specific coefficients remain separate; holdout labels are absent from this loop.
    for linear in [False,True]:
        spec='linear_fee' if linear else 'piecewise_fee';cv=[]
        if any(sum(r['mandate']==m and r['target_seconds']==t for r in train)<48 for m,t in CELLS):
            summary['fit_status']='insufficient_valid_estimation_data';continue
        for lam in [.1,1,10]:
            losses=[]
            for m,t in CELLS:
                cell=[r for r in train if (r['mandate'],r['target_seconds'])==(m,t)]
                for fold in range(4):
                    tr=[r for r in cell if r['cv_fold']!=fold];va=[r for r in cell if r['cv_fold']==fold]
                    if not va:continue
                    x,y=arrays(tr,linear);b=fit_logit(x,y,lam);xv,yv=arrays(va,linear);ps=probabilities(xv,b)
                    losses.extend(-np.log(np.clip(ps[np.arange(len(yv)),yv],1e-12,1)))
            cv.append({'penalty':lam,'mean_log_loss':float(np.mean(losses)),'validation_choices':len(losses)})
        chosen=min(cv,key=lambda z:(z['mean_log_loss'],-z['penalty']))['penalty']
        for m,t in CELLS:
            tr=[r for r in train if (r['mandate'],r['target_seconds'])==(m,t)];x,y=arrays(tr,linear);b=fit_logit(x,y,chosen)
            sensitivity=[]
            for lam in [.1,1,10]:
                bb=fit_logit(x,y,lam);slopes=[bb[1]/.1] if linear else [bb[1]/.02,bb[2]/.06,bb[3]/.17]
                pp=[r for r in tr if r['choice']!='DECLINE'];xc,yc=arrays(pp,linear,True);bc=fit_logit(xc,yc,lam) if len(pp)>=24 else None
                conditional_slopes=None if bc is None else ([bc[0]/.1] if linear else [bc[0]/.02,bc[1]/.06,bc[2]/.17])
                sensitivity.append({'penalty':lam,'fee_slopes_per_usd':slopes,'conditional_fee_slopes_per_usd':conditional_slopes})
            fits.append({'specification':spec,'mandate':m,'target_seconds':t,'training_choices':len(tr),'training_declines':sum(y==2).item(),'selected_penalty':chosen,'cross_validation':cv,'coefficients':b.tolist(),'fee_sensitivity':sensitivity})
    write(out/'training_fits.json',fits) # frozen training decisions written before held-out predictions
    for f in fits:
        te=[r for r in test if (r['mandate'],r['target_seconds'])==(f['mandate'],f['target_seconds'])]
        if not te:continue
        x,y=arrays(te,f['specification']=='linear_fee');ps=probabilities(x,np.array(f['coefficients']))
        for row,prob in zip(te,ps):predictions.append({'model':f['specification'],'episode_id':row['episode_id'],'pair_id':row['pair_id'],'mandate':row['mandate'],'target_seconds':row['target_seconds'],'observed':row['choice'],'probabilities':prob.tolist(),'correct':CHOICES[int(prob.argmax())]==row['choice'],'log_loss':float(-np.log(max(prob[CHOICES.index(row['choice'])],1e-12)))})
    for m,t in CELLS:
        tr=[r for r in train if (r['mandate'],r['target_seconds'])==(m,t)];te=[r for r in test if (r['mandate'],r['target_seconds'])==(m,t)]
        if not tr or not te:continue
        cc=Counter(r['choice'] for r in tr);constant=np.array([(cc[k]+.5)/(len(tr)+1.5) for k in CHOICES])
        methods=[('training_choice_share',None)]+[(n,min([.01,.025,.05,.1,.2,.4,.8,1],key=lambda z:sum(-np.log(rule_probs(r,n,z)[CHOICES.index(r['choice'])]) for r in tr))) for n in ['lowest_fee','lowest_expected_expenditure','highest_success','meet_target_then_success','shortest_retention']]
        for name,lapse in methods:
            baseline.append({'model':name,'mandate':m,'target_seconds':t,'training_lapse':lapse})
            for row in te:
                prob=constant if lapse is None else rule_probs(row,name,lapse)
                predictions.append({'model':name,'episode_id':row['episode_id'],'pair_id':row['pair_id'],'mandate':m,'target_seconds':t,'observed':row['choice'],'probabilities':prob.tolist(),'correct':CHOICES[int(prob.argmax())]==row['choice'],'log_loss':float(-np.log(max(prob[CHOICES.index(row['choice'])],1e-12)))})
    scores=[]
    for name in sorted({r['model'] for r in predictions}):
        rs=[r for r in predictions if r['model']==name]
        scores.append({'model':name,'choices':len(rs),'accuracy':float(np.mean([r['correct'] for r in rs])),'log_loss':float(np.mean([r['log_loss'] for r in rs])),
          'pair_resampling_log_loss':bootstrap_mean([np.mean([r['log_loss'] for r in rs if r['pair_id']==p]) for p in sorted({r['pair_id'] for r in rs})]),
          'by_cell':[{'mandate':m,'target_seconds':t,'n':len(cs),'accuracy':float(np.mean([r['correct'] for r in cs])),'log_loss':float(np.mean([r['log_loss'] for r in cs]))} for m,t in CELLS if (cs:=[r for r in rs if (r['mandate'],r['target_seconds'])==(m,t)])]})
    write(out/'predictions.json',predictions);write(out/'baseline_parameters.json',baseline);summary['prediction_scores']=scores
    summary['training_base_choices']=len(train);summary['heldout_base_choices']=len(test);summary['declines']=sum(r['choice']=='DECLINE' for r in valid)
    summary['limits']='Intervals resample the finite set of physical pairs, preserving mandate and target observations; they are not population intervals for human operators. No coefficient-scale comparisons across cells imply relative preference intensity.'
    write(out/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k!='prediction_scores'}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--output',type=Path);a=ap.parse_args();analyze(a.root,a.output or a.root/'analysis')
