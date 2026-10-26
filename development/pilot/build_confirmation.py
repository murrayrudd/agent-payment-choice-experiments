"""Fix presentation within matched calibration comparisons, using no outcomes."""
from pathlib import Path
import copy,datetime,hashlib,json,random
B=Path(__file__).resolve().parent;R=B/'run_20261025';F=R/'frozen_inputs';O=R/'confirmation'
if (O/'plan.json').exists():raise SystemExit('Confirmation plan already frozen.')
initial=[json.loads(x) for x in (F/'episodes.jsonl').read_text().splitlines()]
I=json.loads((F/'instrument.json').read_text())
core=[e for e in initial if e['module']=='core' and e['repeat']==1 and e['split']=='calibration']
new=[];links=[]
for pair in sorted({e['pair_id'] for e in core}):
    template=next(e for e in core if e['pair_id']==pair and e['mandate']=='Balanced' and e['target_seconds']==5)
    for e in sorted([e for e in core if e['pair_id']==pair],key=lambda x:x['case_id']):
        if e['position']==template['position'] and e['display_map']==template['display_map']:
            id=e['episode_id'];origin='initial'
        else:
            n=copy.deepcopy(e);id='K_'+e['episode_id'];origin='confirmation'
            n.update(episode_id=id,case_id='K_'+e['case_id'],module='presentation_confirmation',variant='fixed_presentation',original_episode_id=e['episode_id'])
            n['position']=copy.deepcopy(template['position']);n['display_map']=copy.deepcopy(template['display_map'])
            # Same physical pair: start with the template, changing only mandate and target.
            text=template['messages'][0]['content']
            text=text.replace(I['mandates']['Balanced'],I['mandates'][e['mandate']])
            if e['target_seconds']==60:text=text.replace(I['contexts']['Short completion target'],I['contexts']['Long completion target'])
            n['messages']=[{'role':'user','content':text}]
            n['prompt_sha256']=hashlib.sha256(json.dumps(n['messages'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
            new.append(n)
        links.append({'pair_id':pair,'mandate':e['mandate'],'target_seconds':e['target_seconds'],'episode_id':id,'origin':origin,'original_episode_id':e['episode_id']})
assert len(new)==96 and len(links)==128
byid={e['episode_id']:e for e in initial+new}
for pair in sorted({x['pair_id'] for x in links}):
    group=[byid[x['episode_id']] for x in links if x['pair_id']==pair]
    assert len({json.dumps([e['profiles'],e['position'],e['display_map']],sort_keys=True) for e in group})==1
    for e in group:
        stripped=e['messages'][0]['content'].replace(I['mandates'][e['mandate']],'MANDATE').replace(I['contexts']['Short completion target' if e['target_seconds']==5 else 'Long completion target'],'TARGET')
        if e==group[0]:expected=stripped
        assert stripped==expected
random.Random(2026102608).shuffle(new);O.mkdir(exist_ok=True)
(O/'episodes.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in new))
(O/'plan.json').write_text(json.dumps({'prepared_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'additional diagnostic specified during collection before outcome analysis',
 'reason':'The initial core counterbalances presentation across conditions but does not hold it fixed within every matched mandate and target comparison. This block supplies fixed-presentation comparisons for the 16 calibration pairs.',
 'outcomes_used_to_design_block':False,'new_calls':96,'reused_initial_calls':32,'total_comparison_cells':128,'heldout_pairs_included':False,
 'spending_ceiling_unchanged_usd':2,'primary_analysis_unchanged':True,'comparison_cells':links},indent=2))
(O/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file()},indent=2))
print(json.dumps({'new_calls':96,'matched_cells':128,'fixed_presentation_verified':True,'heldout_pairs_used':False}))
