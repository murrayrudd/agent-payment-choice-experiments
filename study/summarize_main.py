"""Independent bookkeeping and descriptive summaries for the completed main run.

This report layer does not alter the frozen specification, fit models, or choose
new tests. All agent observations come from the completed live attempt records.
"""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
from datetime import datetime,timezone
import argparse,json,hashlib,sys
import numpy as np

def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def readl(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def bh(values,seed=72025):
    a=np.array(values,float);rng=np.random.default_rng(seed)
    if not len(a):return None
    z=a[rng.integers(0,len(a),(1000,len(a)))].mean(axis=1)
    return {'mean':float(a.mean()),'physical_pairs':len(a),'pair_resampling_95_percentile':np.quantile(z,[.025,.975]).tolist()}
def summarize(root,out):
    es=readl(root/'inputs/episodes.jsonl');meta={e['episode_id']:e for e in es};cfg=json.loads((root/'inputs/configuration.json').read_text());manifest=json.loads((root/'manifest.json').read_text())
    for name,h in manifest['files'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h,'Frozen file changed: '+name
    records=[json.loads(p.read_text()) for p in sorted((root/'results/attempts').glob('*.json'))]
    assert len({r['episode_id'] for r in records})==len(records)
    assert len(records)==len(es),'Main collection is incomplete.'
    assert all(r['state']=='completed' for r in records),'Resolve incomplete attempt accounting first.'
    generation_ids=[r['raw_response'].get('id') for r in records]
    assert None not in generation_ids and len(set(generation_ids))==len(records),'Missing or repeated generation ID.'
    rows=[];cost=D(0);tokens=Counter();models=Counter();providers=Counter()
    for r in records:
        e=meta[r['episode_id']];assert r['data_origin']=='live_main_study'
        assert r['prompt_sha256']==e['prompt_sha256']
        assert r['request']['messages']==e['messages']
        raw=r['raw_response'];assert raw['model'] in cfg['model']['expected_returned_model_ids'] and raw['provider']==cfg['model']['upstream_provider_name']
        rawcost=D(str(raw['usage']['cost']));assert rawcost==D(r['accounted_cost_usd']);cost+=rawcost
        for k in ['prompt_tokens','completion_tokens','total_tokens']:tokens[k]+=raw['usage'].get(k,0)
        models[raw['model']]+=1;providers[raw['provider']]+=1
        status='valid';choice=None
        if r.get('refusal'):status='refusal'
        elif r.get('finish_reason')=='length':status='truncation'
        else:
            try:
                x=json.loads(r.get('raw_content') or '')
                if not isinstance(x,dict) or set(x)!={'choice'} or x['choice'] not in ('A','B','DECLINE'):status='invalid_schema'
                else:choice='DECLINE' if x['choice']=='DECLINE' else e['display_map'][x['choice']]
            except (ValueError,TypeError):status='invalid_json'
        assert r['parsed']=={'status':status,'physical_choice':choice}
        rows.append({**e,'status':status,'choice':choice,'cost_usd':str(rawcost)})
    status=json.loads((root/'results/run_status.json').read_text());assert status['status']=='complete' and D(status['accounted_cost_usd'])==cost
    assert cost<=D(cfg['stage_maximum_usd'])
    valid=[r for r in rows if r['status']=='valid'];byid={r['episode_id']:r for r in rows};core=[r for r in valid if r['module']=='core' and r['repeat']==1]
    mandates=['Balanced','Economy','Continuity','Data minimization'];lookup={(r['pair_id'],r['mandate'],r['target_seconds']):r for r in core};pair_ids=sorted({r['pair_id'] for r in core})
    per_cell=[]
    for m in mandates:
      for t in [5,60]:
        rs=[r for r in core if (r['mandate'],r['target_seconds'])==(m,t)];selected=[r['profiles'][r['choice']] for r in rs if r['choice']!='DECLINE']
        per_cell.append({'mandate':m,'target_seconds':t,'n':len(rs),'declines':sum(r['choice']=='DECLINE' for r in rs),'mean_selected_attributes':{k:float(np.mean([float(o[k]) for o in selected])) for k in ['fee','success_probability','time_seconds','refund','retention_days']} if selected else None})
    mandate_changes=[]
    for m in mandates[1:]:
      differences=[];cell_results=[]
      for t in [5,60]:
        rs=[]
        for p in pair_ids:
            a,b=lookup.get((p,'Balanced',t)),lookup.get((p,m,t))
            if a and b:rs.append({'pair_id':p,'changed':int(a['choice']!=b['choice'])})
        cell_results.append({'target_seconds':t,'pairs':len(rs),'changes':sum(r['changed'] for r in rs)})
        differences.extend([{**r,'target_seconds':t} for r in rs])
      pair_rates=[np.mean([r['changed'] for r in differences if r['pair_id']==p]) for p in pair_ids if any(r['pair_id']==p for r in differences)]
      mandate_changes.append({'mandate':m,'paired_choices':len(differences),'changes':sum(r['changed'] for r in differences),'by_target':cell_results,'pair_resampling':bh(pair_rates)})
    target_changes=[]
    for m in mandates:
        rs=[int(lookup[(p,m,5)]['choice']!=lookup[(p,m,60)]['choice']) for p in pair_ids if (p,m,5) in lookup and (p,m,60) in lookup]
        target_changes.append({'mandate':m,'pairs':len(rs),'changes':sum(rs),'pair_resampling':bh(rs)})
    cases=defaultdict(list)
    for r in rows:cases[r['case_id']].append(r)
    rep_detail=[]
    for case,rs in cases.items():
        rs=sorted(rs,key=lambda r:r['repeat'])
        if len(rs)<2:continue
        assert len({r['prompt_sha256'] for r in rs})==1
        choices=[('PURCHASE' if r['choice'] in ('alpha','beta') else r['choice']) if r['module']=='outside_anchor' else r['choice'] for r in rs]
        module='core_'+rs[0]['split'] if rs[0]['module']=='core' else rs[0]['module']
        rep_detail.append({'case_id':case,'module':module,'n':len(rs),'valid':all(r['status']=='valid' for r in rs),'choices':choices,'disagree':len(set(choices))>1})
    repetition=[{'module':m,'valid_sets':sum(r['valid'] for r in rep_detail if r['module']==m),'disagreeing_sets':sum(r['valid'] and r['disagree'] for r in rep_detail if r['module']==m),'calls_per_set':sorted({r['n'] for r in rep_detail if r['module']==m})} for m in sorted({r['module'] for r in rep_detail})]
    presentation=[]
    for variant in ['labels','position']:
        rs=[]
        for r in rows:
            if r['module']=='presentation' and r['variant']==variant:
                a=byid.get(r['base_case_id']+'_r1')
                if a and a['status']=='valid' and r['status']=='valid':rs.append({'episode_id':r['episode_id'],'changed':a['choice']!=r['choice'],'base_choice':a['choice'],'variant_choice':r['choice']})
        presentation.append({'variant':variant,'valid_pairs':len(rs),'changes':sum(r['changed'] for r in rs),'details':rs})
    fine=[]
    for m in mandates:
      for t in [5,60]:
        rs=[r for r in rows if r['module']=='fine_reliability' and r['mandate']==m and r['target_seconds']==t];levels=[]
        for premium in sorted({D(r['premium']) for r in rs}):
            obs=sorted([r for r in rs if D(r['premium'])==premium],key=lambda r:r['repeat']);cc=[r['choice'] for r in obs]
            levels.append({'premium_usd':str(premium),'choice_counts':dict(Counter(cc)),'unanimous':len(obs)==4 and all(r['status']=='valid' for r in obs) and len(set(cc))==1,'consensus':cc[0] if len(set(cc))==1 else None})
        cs=[l['consensus'] if l['unanimous'] else None for l in levels];bracket=None
        if len(cs)!=5 or None in cs:category='repeat_variation_or_incomplete'
        elif 'DECLINE' in cs:category='includes_decline'
        elif cs==['alpha']*5:category='reference_selected_at_all_fees'
        elif cs==['beta']*5:category='higher_success_selected_at_maximum_fee'
        elif cs[0]=='beta' and all(cs[i]!='alpha' or all(x=='alpha' for x in cs[i:]) for i in range(5)):
            category='unanimous_monotone_switch';i=cs.index('alpha');bracket=[levels[i-1]['premium_usd'],levels[i]['premium_usd']]
        else:category='nonmonotone'
        fine.append({'mandate':m,'target_seconds':t,'category':category,'premium_bracket_usd':bracket,'levels':levels})
    refund=[]
    for m in mandates:
      for t in [5,60]:
       for pid in ['R1','R2','R3','R4']:
        obs=[r for r in rows if r['module']=='refund_success' and r['pair_id']==pid and r['mandate']==m and r['target_seconds']==t]
        if not obs:continue
        r=obs[0];q=D(r['profiles']['alpha']['success_probability']);premium=D(r['premium'])
        refund.append({'mandate':m,'target_seconds':t,'pair_id':pid,'success_probability':str(q),'premium_usd':str(premium),'expected_refund_gain_usd':str(1-q),'net_expected_expenditure_change_usd':str(premium-(1-q)),'choices':[r['choice'] for r in sorted(obs,key=lambda r:r['repeat'])]})
    frozen_summary=json.loads((root/'analysis/summary.json').read_text());fits=json.loads((root/'analysis/training_fits.json').read_text())
    predictions=json.loads((root/'analysis/predictions.json').read_text());prediction_comparison=[]
    for name in ['piecewise_fee','linear_fee','training_choice_share','lowest_fee','lowest_expected_expenditure','highest_success','meet_target_then_success','shortest_retention']:
        rs=[r for r in predictions if r['model']==name];assert len(rs)==256
        prediction_comparison.append({'model':name,'correct':sum(r['correct'] for r in rs),'n':len(rs),'mean_log_loss':float(np.mean([r['log_loss'] for r in rs]))})
    fee_gates=[]
    for fit in fits:
        m,t=fit['mandate'],fit['target_seconds'];model=fit['specification']
        rates=[x for r in fit['fee_sensitivity'] for x in r['fee_slopes_per_usd']]
        cr=[r['conditional_fee_slopes_per_usd'] for r in fit['fee_sensitivity']];cond=all(v is not None for v in cr) and all(x<0 for v in cr for x in v)
        def ll(name):return float(np.mean([r['log_loss'] for r in predictions if r['model']==name and (r['mandate'],r['target_seconds'])==(m,t)]))
        fee_gates.append({'specification':model,'mandate':m,'target_seconds':t,'penalty':fit['selected_penalty'],'all_full_fee_slopes_negative':all(x<0 for x in rates),'all_conditional_fee_slopes_negative':cond,'fee_slope_range_per_usd':[min(rates),max(rates)],'heldout_log_loss':ll(model),'share_baseline_log_loss':ll('training_choice_share'),'beats_share_baseline':ll(model)<ll('training_choice_share'),'valuation_status':'Additional unique-crossing and bounded-uncertainty gates not automatically evaluated; no monetary estimate reported.'})
    summ={'data_origin':'observed_live_main_study','checked_utc':datetime.now(timezone.utc).isoformat(),'planned_calls':len(es),'completed_calls':len(rows),'valid_responses':len(valid),'status_counts':dict(Counter(r['status'] for r in rows)),
       'total_cost_usd':str(cost),'max_cost_usd':cfg['stage_maximum_usd'],'tokens':dict(tokens),'models':dict(models),'providers':dict(providers),'started_utc':min(r['started_utc'] for r in records),'ended_utc':max(r['ended_utc'] for r in records),
       'module_counts':dict(Counter(r['module'] for r in rows)),'core_first_choices':len(core),'declines_all':sum(r['choice']=='DECLINE' for r in valid),'per_cell':per_cell,'mandate_changes':mandate_changes,'target_changes':target_changes,
       'repetition':repetition,'repetition_disagreements':[r for r in rep_detail if r['valid'] and r['disagree']],'presentation':presentation,'fine_reliability':fine,'refund_probes':refund,
       'outside_anchors':dict(Counter((r['anchor']+'|'+('DECLINE' if r['choice']=='DECLINE' else 'PURCHASE')) for r in valid if r['module']=='outside_anchor')),
       'prediction_comparison':prediction_comparison,'prediction_scores':frozen_summary['prediction_scores'],'fee_gates':fee_gates,'manifest_verified':True,'request_response_accounting_verified':True,'unique_generation_ids':len(set(generation_ids))}
    assert frozen_summary['valid_responses']==len(valid) and frozen_summary['declines']==summ['declines_all']
    write(out/'report_metrics.json',summ)
    print(json.dumps({k:summ[k] for k in ['completed_calls','valid_responses','total_cost_usd','declines_all','mandate_changes','target_changes','repetition','prediction_comparison']},indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).parent/'run_20261025');ap.add_argument('--output',type=Path);a=ap.parse_args();summarize(a.root,a.output or Path(__file__).parent/'assessment')
