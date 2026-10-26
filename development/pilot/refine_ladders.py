"""Prepare only the fee midpoints specified by the frozen adaptive rule; offline."""
from pathlib import Path
from decimal import Decimal as D,ROUND_HALF_UP
import argparse,copy,datetime,hashlib,json,random
def readl(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def money(x):return '$'+format(D(str(x)),'.3f')
def main(root):
    out=root/'adaptive'
    if (out/'episodes.jsonl').exists():raise SystemExit('Adaptive plan already exists; do not regenerate.')
    s=json.loads((root/'summary.json').read_text())
    assert s['recorded_calls']==536 and s['valid_responses']==536,'Complete valid initial battery required for this refinement.'
    sources={e['episode_id']:e for e in readl(root/'frozen_inputs/episodes.jsonl')}
    selected=[x for x in s['ladders'] if x['eligible_for_refinement']][:24]
    episodes=[];decisions=[]
    for ix,series in enumerate(selected,1):
        lower,upper=map(D,series['initial_bracket_premium_usd'])
        mid=((lower+upper)/2).quantize(D('.001'),rounding=ROUND_HALF_UP)
        if not lower<mid<upper:continue
        source=sources[next(x['episode_ids'][0] for x in series['levels'] if D(x['premium'])==lower)]
        e=copy.deepcopy(source);old=D(e['profiles']['beta']['fee']);new=D(e['profiles']['alpha']['fee'])+mid
        e['profiles']['beta']['fee']=str(new)
        # Edit only the beta column in the three affected accounting rows.
        col=e['position'].index('beta')+2;lines=e['messages'][0]['content'].splitlines()
        replacements={'Payment service fee':money(new),'Initial debit':money(1+new),'Expenditure after failure':money(1+new-D(e['profiles']['beta']['refund']))}
        changed=[]
        for li,line in enumerate(lines):
            if not line.startswith('|'):continue
            cells=line.split('|');term=cells[1].strip()
            if term in replacements:
                cells[col]=' '+replacements[term]+' ';lines[li]='|'.join(cells);changed.append(term)
        assert set(changed)==set(replacements)
        e['messages'][0]['content']='\n'.join(lines)
        e.update(case_id=f'R{ix:02}',module='adaptive_ladder',fee_level=str(new),premium=str(mid),initial_bracket=[str(lower),str(upper)],source_case_id=source['case_id'])
        e['prompt_sha256']=hashlib.sha256(json.dumps(e['messages'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        for rep in (1,2):episodes.append({**copy.deepcopy(e),'episode_id':e['case_id']+f'_r{rep}','repeat':rep})
        decisions.append({'case_id':e['case_id'],'ladder':e['ladder'],'mandate':e['mandate'],'target_seconds':e['target_seconds'],'bracket':[str(lower),str(upper)],'midpoint_premium':str(mid),'improved_fee':str(new)})
    random.Random(2026102607).shuffle(episodes)
    out.mkdir(exist_ok=True)
    (out/'episodes.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in episodes))
    (out/'plan.json').write_text(json.dumps({'prepared_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rule_source':'frozen_inputs/protocol.json adaptive_rule','initial_summary_sha256':hashlib.sha256((root/'summary.json').read_bytes()).hexdigest(),'eligible_series':sum(x['eligible_for_refinement'] for x in s['ladders']),'selected_series':decisions,'calls':len(episodes),'uses_heldout_outcomes':False},indent=2))
    (out/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file()},indent=2))
    print(json.dumps({'eligible_series':sum(x['eligible_for_refinement'] for x in s['ladders']),'selected_series':len(decisions),'calls':len(episodes)}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent/'run_20261025');main(p.parse_args().root)
