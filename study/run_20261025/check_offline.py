"""Meaningful offline checks for budget stops, unresolved calls, and frozen inputs.

All provider responses are synthetic fixtures. No network connection is made.
"""
import contextlib,io,json,sys,tempfile,threading
from pathlib import Path
from unittest.mock import patch
from common import *
import collect_main

def collector_check(mode):
    with tempfile.TemporaryDirectory(prefix='agents_ce_offline_') as temp:
        root=Path(temp);(root/'inputs').mkdir()
        cfg=json.loads((ROOT/'inputs/configuration.json').read_text());cfg['stage_maximum_usd']='0.23' if mode=='budget' else '3.50'
        write(root/'inputs/configuration.json',cfg);eps=readl(ROOT/'inputs/episodes.jsonl')[:8]
        (root/'inputs/episodes.jsonl').write_text(''.join(canonical(e)+'\n' for e in eps))
        write(root/'manifest.json',{'files':{str(p.relative_to(root)):filehash(p) for p in (root/'inputs').glob('*')}})
        key=root/'fixture_credential';key.write_text('offline-fixture-no-valid-credential');m=cfg['model'];calls=[];lock=threading.Lock()
        def api(path,key=None,body=None):
            if path=='key':return {'data':{'is_management_key':False,'is_provisioning_key':False,'limit_reset':None,'limit':20,'limit_remaining':20,'expires_at':'2099-01-01T00:00:00Z','usage':0}}
            if path=='credits':return {'data':{'total_credits':20,'total_usage':0}}
            if path=='models':return {'data':[{'id':m['catalog_model_id'],'canonical_slug':m['canonical_model_id']}]}
            if path.endswith('/endpoints'):return {'data':{'endpoints':[{'tag':m['upstream_provider'],'name':m['endpoint_name'],'pricing':{'prompt':.000002,'completion':.000010,'request':0},'supported_parameters':['structured_outputs','response_format','max_tokens','reasoning']}]}}
            assert path=='chat/completions'
            with lock:calls.append(body);n=len(calls)
            if mode=='transport' and n==1:raise RuntimeError('Synthetic transport failure')
            return {'model':m['model_id'],'provider':'WrongRoute' if mode=='route' and n==1 else m['upstream_provider_name'],'usage':{'cost':.1 if mode=='budget' else .002},'choices':[{'message':{'content':'{}' if mode=='schema' and n==1 else '{"choice":"A"}'},'finish_reason':'stop'}]}
        argv=['collect_main.py','--root',str(root),'--live','--key-file',str(key)]
        with patch.object(collect_main,'api',api),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):collect_main.main()
        records=[json.loads(p.read_text()) for p in (root/'results/attempts').glob('*.json')];status=json.loads((root/'results/run_status.json').read_text())
        assert not (root/'results/collection.lock').exists()
        assert len(calls)==len(records) and len({r['episode_id'] for r in records})==len(records)
        assert sum(float(r['accounted_cost_usd']) for r in records)<=float(cfg['stage_maximum_usd'])
        if mode=='success':assert len(calls)==8 and status['status']=='complete'
        elif mode=='budget':assert 0<len(calls)<8 and status['status']=='budget_stop'
        else:assert len(calls)==4 and status['status']!='complete'
        if mode in ['transport','route']:
            before=len(calls)
            with patch.object(collect_main,'api',api),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
                try:collect_main.main()
                except SystemExit as exc:assert 'Unresolved' in str(exc)
                else:raise AssertionError('Unresolved attempt was resubmitted')
            assert len(calls)==before and not (root/'results/collection.lock').exists()
        # Corruption blocks the offline entrypoint too.
        (root/'inputs/configuration.json').write_text('{}')
        with patch.object(sys,'argv',['collect_main.py','--root',str(root)]),patch.object(collect_main,'api',side_effect=AssertionError('Unexpected network request')):
            try:collect_main.main()
            except SystemExit as exc:assert 'checksum' in str(exc)
            else:raise AssertionError('Corrupt input accepted')
        return {'fixture':mode,'synthetic_calls':len(calls),'status':status['status'],'network_calls':0,'lock_removed':True}
if __name__=='__main__':
    result={'data_origin':'mock_provider_fixtures','checks':[collector_check(m) for m in ['success','budget','transport','route','schema']]}
    print(json.dumps(result,indent=2))
