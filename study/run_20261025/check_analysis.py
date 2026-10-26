"""Synthetic end-to-end scoring and holdout isolation check; no model requests."""
import contextlib,io,json,tempfile
from pathlib import Path
import numpy as np
from common import *
from simulate_design import synthetic_p
from analyze_main import analyze

def run():
    with tempfile.TemporaryDirectory(prefix='agents_ce_analysis_fixture_') as temp:
        root=Path(temp);(root/'inputs').mkdir();attempts=root/'results/attempts';attempts.mkdir(parents=True)
        es=readl(ROOT/'inputs/episodes.jsonl');(root/'inputs/episodes.jsonl').write_bytes((ROOT/'inputs/episodes.jsonl').read_bytes())
        priors=json.loads((ROOT/'development/pilot_priors.json').read_text());rng=np.random.default_rng(270)
        for e in es:
            pp=synthetic_p(e['profiles'],e['mandate'],e['target_seconds'],'smooth_pilot',priors)
            physical='DECLINE' if rng.random()<.05 else ('alpha' if rng.random()<pp else 'beta')
            label='DECLINE' if physical=='DECLINE' else {v:k for k,v in e['display_map'].items()}[physical]
            write(attempts/(e['episode_id']+'.json'),{'data_origin':'synthetic_pipeline_fixture','episode_id':e['episode_id'],'prompt_sha256':e['prompt_sha256'],'state':'completed','raw_content':json.dumps({'choice':label}),'finish_reason':'stop'})
        with contextlib.redirect_stdout(io.StringIO()):analyze(root,root/'scored')
        first=filehash(root/'scored/training_fits.json');s=json.loads((root/'scored/summary.json').read_text());pr=json.loads((root/'scored/predictions.json').read_text())
        assert s['data_origin']=='synthetic_pipeline_fixture' and s['training_base_choices']==512 and s['heldout_base_choices']==256 and s['declines']>0
        assert len(pr)==2048 and all(abs(sum(r['probabilities'])-1)<1e-10 for r in pr)
        # Alter every outcome outside first-response estimation, including every test label.
        for e in es:
            if e['module']=='core' and e['split']=='estimation' and e['repeat']==1:continue
            path=attempts/(e['episode_id']+'.json');r=json.loads(path.read_text());old=json.loads(r['raw_content'])['choice'];new={'A':'B','B':'DECLINE','DECLINE':'A'}[old];r['raw_content']=json.dumps({'choice':new});write(path,r)
        with contextlib.redirect_stdout(io.StringIO()):analyze(root,root/'scored_changed_test')
        assert filehash(root/'scored_changed_test/training_fits.json')==first
        # An invalid estimation response is excluded even when an exact repeat is valid.
        repeated={e['case_id'] for e in es if e['module']=='core' and e['split']=='estimation' and e['repeat']==2}
        e=next(e for e in es if e['case_id'] in repeated and e['repeat']==1);path=attempts/(e['episode_id']+'.json');r=json.loads(path.read_text());r['raw_content']='{}';write(path,r)
        with contextlib.redirect_stdout(io.StringIO()):analyze(root,root/'scored_invalid')
        last=json.loads((root/'scored_invalid/summary.json').read_text());assert last['training_base_choices']==511 and last['status_counts']['invalid_schema']==1
        return {'data_origin':'synthetic_pipeline_fixture','network_calls':0,'fixture_responses':1280,'first_estimation_choices':512,'heldout_choices':256,'probability_vectors_checked':2048,'decline_path_checked':True,'training_fit_hash_unchanged_when_all_nontraining_outcomes_change':True,'invalid_first_response_not_replaced_by_repeat':True}
if __name__=='__main__':print(json.dumps(run(),indent=2))
