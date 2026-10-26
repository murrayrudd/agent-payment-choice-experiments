"""Independent frozen-design and request checks. Network-free."""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from decimal import Decimal
import numpy as np
from common import *

def validate(root):
    core=json.loads((root/'inputs/core_design.json').read_text());es=readl(root/'inputs/episodes.jsonl');req=readl(root/'inputs/requests.jsonl')
    cfg=json.loads((root/'inputs/configuration.json').read_text());instrument=json.loads((root/'inputs/instrument.json').read_text())
    exclude=set(json.loads((root/'development/excluded_pair_hashes.json').read_text()))
    assert len(core)==96 and len(es)==1280 and len(req)==len(es)
    assert Counter(p['split'] for p in core)=={'estimation':64,'heldout':32}
    assert len({e['episode_id'] for e in es})==len(es)
    hashes=[pairhash(p['profiles']) for p in core];assert len(set(hashes))==96 and not set(hashes)&exclude
    pairs={p['pair_id']:p for p in core};cases=defaultdict(list)
    for e,r in zip(es,req):
        cases[e['case_id']].append(e)
        assert r=={'episode_id':e['episode_id'],'request':request(e,cfg['model'])}
        assert digest(e['messages'])==e['prompt_sha256']
        assert e['messages']==[{'role':'user','content':prompt(e['profiles'],e['mandate'],e['target_seconds'],e['position'],{v:k for k,v in e['display_map'].items()},instrument)}]
        assert set(e['display_map'])=={'A','B'} and set(e['display_map'].values())=={'alpha','beta'}
        assert sorted(e['position'])==['alpha','beta']
        for o in e['profiles'].values():
            f,q,r=map(Decimal,[o['fee'],o['success_probability'],o['refund']])
            assert 0<=r<=1 and Decimal(1)+f<=Decimal('1.30')
            assert 1+f-(1-q)*r==q*(1+f)+(1-q)*(1+f-r)
        if e['module']=='core':
            p=pairs[e['pair_id']];assert e['profiles']==p['profiles'] and e['position']==p['position'] and e['display_map']=={v:k for k,v in p['labels'].items()}
        if e['module']=='presentation':
            p=pairs[e['pair_id']];base_map={v:k for k,v in p['labels'].items()}
            assert e['profiles']==p['profiles']
            if e['variant']=='labels':assert e['position']==p['position'] and e['display_map']!=base_map
            else:assert e['position']==p['position'][::-1] and e['display_map']==base_map
    for c,ss in cases.items():assert len({e['prompt_sha256'] for e in ss})==1
    counts=Counter((e['split'],e['repeat']) for e in es if e['module']=='core')
    assert counts=={('estimation',1):512,('heldout',1):256,('estimation',2):128,('heldout',2):64}
    for p in core:
        subset=[e for e in es if e['pair_id']==p['pair_id'] and e['module']=='core' and e['repeat']==1]
        assert {(e['mandate'],e['target_seconds']) for e in subset}==set(CELLS)
    presentations={}
    for split in ['estimation','heldout']:
        ss=[p for p in core if p['split']==split]
        presentations[split]=dict(Counter(canonical([p['position'],p['labels']]) for p in ss));assert len(set(presentations[split].values()))==1 and len(presentations[split])==4
        for key in ['fee',*LEVELS]:
            values={float(o[key]) for p in ss for o in p['profiles'].values()};assert len(values)==(9 if key=='fee' else 3)
    folds=Counter(p['cv_fold'] for p in core if p['split']=='estimation');assert folds=={0:16,1:16,2:16,3:16}
    rank=int(np.linalg.matrix_rank(np.array([features(p['profiles']['alpha'])-features(p['profiles']['beta']) for p in core if p['split']=='estimation'])))
    assert rank==12
    # Manifest is optional only during pre-freeze construction.
    manifest=root/'manifest.json'
    if manifest.exists():
        for name,value in json.loads(manifest.read_text())['files'].items():assert filehash(root/name)==value, 'Checksum mismatch: '+name
    out={'data_origin':'independent_offline_validation','passed':True,'episodes':len(es),'unique_core_pairs':96,'prior_pair_overlap':0,'conditional_rank':rank,'presentation_counts':presentations,'cv_fold_pair_counts':dict(folds),'checks':['counts','fresh_pair_exclusion','training_holdout_separation','same_presentation_across_eight_cells','balanced_core_presentation','single_factor_presentation_diagnostics','exact_repeat_prompt_identity','all_levels','financial_identities','positive_refund_frame','request_prompt_hashes','manifest_if_present']}
    print(json.dumps(out,indent=2));return out
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--save',action='store_true');a=ap.parse_args();out=validate(a.root)
    if a.save:write(a.root/'development/independent_validation.json',out)
