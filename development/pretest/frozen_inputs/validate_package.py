"""Independent arithmetic and parser fixtures; these are not agent responses."""
from pathlib import Path
from decimal import Decimal as D
import json
from grade_responses import score,read_jsonl,grade
ROOT=Path(__file__).resolve().parent
E={e['episode_id']:e for e in read_jsonl(ROOT/'episodes.jsonl')}
K={k['case_id']:k for k in read_jsonl(ROOT/'answer_key.jsonl')}
manual={
 'N01':('A','.980','.965'),'N02':('B','.930','.979'),
 'N03':('A','.975','.970'),'N04':('B','.975','.982'),
 'N05':('B','.890','.970'),'N06':('A','.989','.970'),
 'N07':('DECLINE','-.500','-.515'),'N08':('B','98.591','93.800')}
for cid,(winner,a,b) in manual.items():
    assert K[cid]['expected']['choice']==winner
    assert D(K[cid]['payoffs']['A'])==D(a) and D(K[cid]['payoffs']['B'])==D(b)
assert K['N08']['eligible']['A'] is False
e=E['N07_r1'];k=K['N07']
fixtures=[({'raw_content':'{"choice":"DECLINE"}'},'valid'),
 ({'raw_content':'```json\n{"choice":"A"}\n```'},'malformed_json'),
 ({'raw_content':'{"choice":"A","choice":"B"}'},'malformed_json'),
 ({'raw_content':'{"choice":"A","explanation":"x"}'},'invalid_schema'),
 ({'raw_content':'{"choice":"decline"}'},'invalid_schema'),
 ({'raw_content':'{"choice":null}'},'invalid_schema'),
 ({'raw_content':''},'empty_response'),({'refusal':'refused'},'refusal'),
 ({'transport_error':'timeout'},'transport_error'),({'finish_reason':'length'},'truncated')]
for record,status in fixtures:assert score(record,e,k)['status']==status
assert score(fixtures[0][0],e,k)['correct'] is True
false_bool={k:0 for k in K['F06']['expected']}
assert score({'raw_content':json.dumps(false_bool)},E['F06_r1'],K['F06'])['correct'] is False
assert score({'raw_content':'{"choice":"B"}'},E['P1_labels_r1'],K['P1_labels'])['profile_choice']=='alpha'
assert score({'raw_content':'{"choice":"A"}'},E['P1_position_r1'],K['P1_position'])['profile_choice']=='alpha'
empty=grade([],'unrun')
assert empty['observed_episodes']==0 and len(empty['missing_episodes'])==96
assert empty['wording_comparisons']['paired']==0
result={'data_origin':'offline_validation_fixtures','model_calls':0,
 'independent_benchmark_answers_checked':8,'parser_and_mapping_checks':14,
 'result':'pass','interpretation':'Validates instrument arithmetic and scoring code only; no model behavior measured.'}
(ROOT/'package_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
