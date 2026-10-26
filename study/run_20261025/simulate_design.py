"""Synthetic conditional-choice sensitivity study; never observed agent responses."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.special import expit
from common import *

def synthetic_p(profs,mandate,target,scenario,priors):
    if scenario in ['smooth_pilot','sharp_pilot']:
        lam=1 if scenario=='smooth_pilot' else .1
        b=next(p['coefficients'] for p in priors if p['mandate']==mandate and p['penalty']==lam)
        u=[pilot_features(profs[k],target)@np.array([b[n] for n in PILOT_FEATURES]) for k in ['alpha','beta']]
        return float(expit((u[0]-u[1])*(1 if scenario=='smooth_pilot' else 2)))
    def priority(o):
        f,q,r=float(o['fee']),float(o['success_probability']),float(o['refund']);t,d=o['time_seconds'],o['retention_days'];exp=1+f-(1-q)*r
        if mandate=='Economy':return (-exp,q,-t,-d)
        if mandate=='Continuity':return (int(t<=target),q,-t,-exp,-d)
        if mandate=='Data minimization':return (-d,-exp,q,-t)
        return (q,int(t<=target),-exp,-d,-t)
    a,b=priority(profs['alpha']),priority(profs['beta'])
    return .975 if a>b else (.025 if a<b else .5) # 5% lapse, choosing either offer equally.

def run(root,reps):
    designs=json.loads((root/'development/nested_designs.json').read_text());train=[d['profiles'] for d in designs if d['split']=='estimation']
    test=json.loads((root/'development/simulation_test_pairs.json').read_text());priors=json.loads((root/'development/pilot_priors.json').read_text())
    # No intercept in binary differences: purchase propensity is not simulated.
    xt=np.array([[features(p['alpha'])-features(p['beta']),np.zeros(12)] for p in train]);xv=np.array([[features(p['alpha'])-features(p['beta']),np.zeros(12)] for p in test])
    rng=np.random.default_rng(2026102517);records=[]
    for scenario in ['smooth_pilot','sharp_pilot','priority_with_lapse']:
      for cell,(m,t) in enumerate(CELLS):
        pt=np.array([synthetic_p(p,m,t,scenario,priors) for p in train]);pv=np.array([synthetic_p(p,m,t,scenario,priors) for p in test])
        for rep in range(reps):
            y=(rng.random(80)>=pt).astype(int)
            for n in [48,64,80]:
                b=fit_logit(xt[:n],y[:n],1);p=np.clip(probabilities(xv,b)[:,0],1e-12,1-1e-12)
                records.append({'scenario':scenario,'cell':cell,'replicate':rep,'estimation_pairs':n,
                  'expected_log_loss':float(np.mean(-pv*np.log(p)-(1-pv)*np.log1p(-p))),
                  'probability_rmse':float(np.sqrt(np.mean((p-pv)**2))),
                  'expected_accuracy':float(np.mean(np.where(p>=.5,pv,1-pv)))})
    summaries=[]
    for scenario in ['smooth_pilot','sharp_pilot','priority_with_lapse']:
      for n in [48,64,80]:
        rs=[r for r in records if r['scenario']==scenario and r['estimation_pairs']==n];v={k:float(np.mean([r[k] for r in rs])) for k in ['expected_log_loss','probability_rmse','expected_accuracy']}
        # Monte Carlo error of replicate mean across eight cells, not sampling uncertainty for operators.
        avg=[np.mean([r['expected_log_loss'] for r in rs if r['replicate']==i]) for i in range(reps)]
        summaries.append({'scenario':scenario,'estimation_pairs':n,**v,'log_loss_monte_carlo_se':float(np.std(avg,ddof=1)/np.sqrt(reps))})
    write(root/'development/simulation_results.json',{'data_origin':'synthetic_only','seed':2026102517,'replicates_per_cell_scenario':reps,'cells':8,'test_pairs':1000,'ridge_penalty':1,'purchase_conditioned':True,'summary':summaries,'records':records,
      'limits':'Illustrative conditional-choice sensitivity, not power or operator-population precision. Priors and priority rules are assumptions. Diagnostic repetitions are not fitted. Declines are not simulated.'})
    print(json.dumps(summaries,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--replicates',type=int,default=40);a=ap.parse_args();run(a.root,a.replicates)
