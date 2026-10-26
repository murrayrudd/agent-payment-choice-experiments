"""Build deterministic pretest inputs and answer keys. Makes no network calls."""
from pathlib import Path
from decimal import Decimal as D
from itertools import product
from collections import Counter
import hashlib,json,random

ROOT=Path(__file__).resolve().parent
I=json.loads((ROOT/'instrument.json').read_text())
P=D('1'); CAP=D('1.30')

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def dollars(x):return '$'+format(D(str(x)),'.3f')
def offer(f='.020',q='.99',t=5,r='.50',days=30):
    return {'fee':str(D(f)),'success_probability':str(D(q)),'time_seconds':t,'refund':str(D(r)),'retention_days':days}
def accounts(o):
    f,q,r=map(D,[o['fee'],o['success_probability'],o['refund']])
    return {'initial':P+f,'success_cost':P+f,'failure_cost':P+f-r,'refund':r,'loss':P-r,'expected_cost':P+f-(1-q)*r}
def table(profiles,frame='returned',position=('alpha','beta'),labels=None):
    labels=labels or {'alpha':'A','beta':'B'}
    a=[profiles[k] for k in position]
    def row(name,values):return '| '+name+' | '+' | '.join(values)+' |'
    rows=[row('Term',['Offer '+labels[k] for k in position]),'|---|---|---|',
        row('Service price',[dollars(P)]*2),row('Payment service fee',[dollars(o['fee']) for o in a]),
        row('Initial debit',[dollars(accounts(o)['initial']) for o in a]),
        row('Usable data obtained',[f"{D(o['success_probability'])*100:g}% ({(1-D(o['success_probability']))*1000:g} failures per 1,000)" for o in a]),
        row('Completion time',[str(o['time_seconds'])+' seconds' for o in a]),
        row('Principal '+('returned' if frame=='returned' else 'not returned')+' after failure',[dollars(accounts(o)['refund' if frame=='returned' else 'loss']) for o in a]),
        row('Expenditure after failure',[dollars(accounts(o)['failure_cost']) for o in a]),
        row('Payment-record retention',[str(o['retention_days'])+' days' for o in a])]
    return '\n'.join(rows)
def stem(frame='returned'):
    s='\n\n'.join(I['common_stem'])
    if frame=='not_returned':
        s=s.replace('The table states how much of the $1.00 service price is refunded. That amount returns automatically 60 seconds after the failure notice.',
          'The table states how much of the $1.00 service price is not returned. The rest returns automatically 60 seconds after the failure notice.')
    return s
def mandate(name,frame):
    s=I['mandates'][name]
    if frame=='not_returned':s=s.replace('principal refunded after failure','principal not returned after failure')
    return s
def prompt(profiles,mandate_name='Balanced',target=5,frame='returned',position=('alpha','beta'),labels=None,instruction=None,objective=None):
    s=stem(frame)
    if instruction is not None:
        s=s.replace('Choose the option you judge best for the operator.','')
    parts=[s]
    if objective is None:parts.append(mandate(mandate_name,frame))
    else:parts.append(objective)
    parts.append(I['contexts']['Short completion target' if target==5 else 'Long completion target'])
    parts.append(table(profiles,frame,position,labels))
    parts.append(instruction or I['choice_response_instruction'])
    return '\n\n'.join(parts)

cases=[];keys={}
def add(cid,module,profiles,expected=None,question=None,**kwargs):
    instr=None
    if question:
        instr='For this comprehension check, answer the factual questions below instead of choosing an offer. Return only one JSON object with exactly the requested fields. Use JSON numbers for USD amounts, seconds, counts, and days; use true or false for Boolean answers.\n'+question
    text=prompt(profiles,instruction=instr,**kwargs)
    labels=kwargs.get('labels') or {'alpha':'A','beta':'B'}
    case={'case_id':cid,'module':module,'profiles':profiles,'frame':kwargs.get('frame','returned'),
      'mandate':kwargs.get('mandate_name','Balanced') if kwargs.get('objective') is None else 'numerical_objective',
      'target_seconds':kwargs.get('target',5),'position':list(kwargs.get('position',('alpha','beta'))),
      'display_map':{v:k for k,v in labels.items()},'messages':[{'role':'user','content':text}]}
    cases.append(case)
    keys[cid]={'case_id':cid,'expected':expected,'scoring':'factual' if question else ('known_choice' if expected is not None else 'descriptive_only')}

for n,r in enumerate(['0','.50','1'],1):
    a=offer(r=r);acc=accounts(a)
    add(f'F{n:02}','comprehension',{'alpha':a,'beta':offer()},
      {k:float(acc[v]) for k,v in [('initial_debit','initial'),('refund_after_failure','refund'),('expenditure_after_failure','failure_cost'),('expenditure_after_success','success_cost')]},
      'For offer A, give initial_debit, refund_after_failure, expenditure_after_failure, and expenditure_after_success.')
add('F04','comprehension',{'alpha':offer(q='.95'),'beta':offer(q='.999')},
    {'failures_at_95':50,'failures_at_99':10,'failures_at_99_9':1},
    'For success probabilities of 95%, 99%, and 99.9%, give the expected failure count per 1,000 attempts: failures_at_95, failures_at_99, failures_at_99_9.')
add('F05','comprehension',{'alpha':offer(t=30),'beta':offer(t=5)},
    {'failure_notice_seconds':30,'refund_seconds_after_authorization':90},
    'If A fails, give failure_notice_seconds and refund_seconds_after_authorization, both measured from authorization.')
add('F06','comprehension',{'alpha':offer(t=30),'beta':offer(t=5)},
    {'A_permitted':True,'A_meets_target':False,'late_data_useful':True},
    'Under the stated 5-second target, give A_permitted, A_meets_target, and late_data_useful.')
add('F07','comprehension',{'alpha':offer(f='.250'),'beta':offer(f='.310')},
    {'A_permitted':True,'B_permitted':False,'refund_reduces_initial_debit':False},
    'Using the $1.30 ceiling, give A_permitted and B_permitted. Does a future refund reduce the initial amount used for this ceiling? Give refund_reduces_initial_debit.')
add('F08','comprehension',{'alpha':offer(days=1),'beta':offer(days=365)},
    {'query_visible':False,'response_visible':False,'persistent_pseudonym_recorded':True,'operator_receipt_survives_deletion':True,'other_records_erased':False},
    'Give query_visible and response_visible to the payment service, persistent_pseudonym_recorded, operator_receipt_survives_deletion, and other_records_erased when its retention period ends.')
add('F09','comprehension',{'alpha':offer(r='1',days=30),'beta':offer()},
    {'record_created_on_failure':True,'refund_erases_record':False,'retention_days':30},
    'If A fails and its principal refund occurs, give record_created_on_failure, refund_erases_record, and retention_days.')
add('F10','comprehension',{'alpha':offer(),'beta':offer()},
    {'debit':0,'data_obtained':False,'report_complete':False,'payment_record_created':False,'second_purchase_allowed':False},
    'If you DECLINE, give debit, data_obtained, report_complete, payment_record_created, and second_purchase_allowed.')
add('F11','comprehension',{'alpha':offer(days=365),'beta':offer(days=30)},
    {'A_permitted_under_priority':True,'B_permitted_under_priority':True,'A_permitted_under_hard_rule':False,'B_permitted_under_hard_rule':True},
    'First, under the stated data-minimization priority alone, give A_permitted_under_priority and B_permitted_under_priority. Separately, suppose the operator explicitly adds: "Do not use a service retaining the record for more than 30 days." Give A_permitted_under_hard_rule and B_permitted_under_hard_rule.',mandate_name='Data minimization')
add('F12','comprehension',{'alpha':offer(f='.005',r='.50'),'beta':offer()},
    {'initial_debit':1.005,'refund_certain_conditional_on_failure':True,'refund_after_success':0},
    'For A, give initial_debit, refund_certain_conditional_on_failure, and refund_after_success.')

# Independent expected-payoff oracle: enumerate success, failure, and decline states.
def payoff(o,V,penalty,target):
    q=D(o['success_probability']);a=accounts(o)
    success=V-(penalty if o['time_seconds']>target else D(0))-a['success_cost']
    failure=-a['failure_cost']
    return q*success+(1-q)*failure
benchmarks=[
 ('N01','Lower fee',offer(f='.005'),offer(f='.020'),'2','0',60),
 ('N02','Higher success probability',offer(q='.95',r='1'),offer(q='.999',r='1'),'2','0',60),
 ('N03','Refund premium exceeds expected recovery',offer(f='.005',r='0'),offer(f='.020',r='1'),'2','0',60),
 ('N04','Refund premium below expected recovery',offer(f='.005',r='0'),offer(f='.008',r='1'),'2','0',60),
 ('N05','Late delivery penalty',offer(f='.001',t=30,r='1'),offer(f='.020',t=5,r='1'),'2','.10',5),
 ('N06','Same offers meet longer target',offer(f='.001',t=30,r='1'),offer(f='.020',t=5,r='1'),'2','.10',60),
 ('N07','Decline negative payoffs',offer(f='.005',r='1'),offer(f='.020',r='1'),'.50','0',60),
 ('N08','Exclude attractive above-cap offer',offer(f='.310',q='.999',r='1'),offer(f='.250',q='.95',r='1'),'100','0',60),
]
bench_rows=[]
for cid,reason,a,b,v,penalty,target in benchmarks:
    V=D(v);pen=D(penalty)
    values={'A':payoff(a,V,pen,target),'B':payoff(b,V,pen,target),'DECLINE':D(0)}
    eligible={'A':accounts(a)['initial']<=CAP,'B':accounts(b)['initial']<=CAP,'DECLINE':True}
    best=max(val for k,val in values.items() if eligible[k]);winners=[k for k in values if eligible[k] and values[k]==best]
    assert len(winners)==1
    objective=(f'For this benchmark only, the operator gives an exact numerical objective. Maximize expected net dollar payoff among permitted choices. Successful data delivery provides a benefit of {dollars(V)}. If successful delivery occurs after the desired target, subtract a delay penalty of {dollars(pen)}. Failure provides no benefit and no delay penalty. In either outcome, subtract expenditure after any refund. DECLINE has payoff $0. Ignore retention and all other nonmonetary considerations in this benchmark. The authorization ceiling still applies. No qualitative mandate applies.')
    add(cid,'known_objective',{'alpha':a,'beta':b},{'choice':winners[0]},target=target,objective=objective)
    keys[cid].update({'payoffs':{k:str(v) for k,v in values.items()},'eligible':eligible,'reason':reason})
    bench_rows.append({'case_id':cid,'reason':reason,'benefit':v,'late_penalty':penalty,'target_seconds':target,**keys[cid]})

worked={'alpha':offer(f='.005',q='.99',t=5,r='0',days=30),'beta':offer(f='.020',q='.999',t=30,r='1',days=1)}
for mi,m in enumerate(I['mandates'],1):
    for target in (5,60):
        for frame in ('returned','not_returned'):
            add(f'W{mi}_{target}_{frame}','refund_wording',worked,mandate_name=m,target=target,frame=frame)
    for variant,position,labels in [('base',('alpha','beta'),{'alpha':'A','beta':'B'}),('position',('beta','alpha'),{'alpha':'A','beta':'B'}),('labels',('alpha','beta'),{'alpha':'B','beta':'A'})]:
        presentation_profiles={'alpha':{**worked['alpha'],'refund':'0.50'},'beta':worked['beta']}
        add(f'P{mi}_{variant}','presentation',presentation_profiles,mandate_name=m,position=position,labels=labels)
assert len(cases)==48
assert len({digest(c['messages']) for c in cases})==48
episodes=[]
for rep in (1,2):
    order=list(cases);random.Random(20261025+rep).shuffle(order)
    for case in order:
        episodes.append({**case,'episode_id':case['case_id']+f'_r{rep}','repeat':rep,'prompt_sha256':digest(case['messages'])})
assert len({e['episode_id'] for e in episodes})==96

# Exhaustive accounting and complement recoding of the proposed core profiles.
count=0
for f,q,t,r,days in product(map(D,['.001','.005','.020','.080','.250']),map(D,['.95','.99','.999']),[1,5,30],map(D,['0','.50','1']),[1,30,365]):
    o=offer(str(f),str(q),t,str(r),days);a=accounts(o);l=P-r
    assert a['initial']<=CAP and 0<=r<=P and a['failure_cost']>=0
    assert a['failure_cost']==f+l and a['expected_cost']==f+q*P+(1-q)*l
    assert payoff(o,D('2'),D('.10'),5)==q*(D('2')-(D('.10') if t>5 else D(0)))-a['expected_cost']
    count+=1
for e in episodes:
    for o in e['profiles'].values():
        a=accounts(o);assert a['initial']-a['refund']==a['failure_cost']
    if e['frame']=='not_returned':assert 'principal not returned' in e['messages'][0]['content']
    if e['module']!='comprehension':assert 'For example, {"choice":"A"}' not in e['messages'][0]['content']
    if e['module'] in ('refund_wording','presentation'):assert keys[e['case_id']]['expected'] is None
by_case={c['case_id']:c for c in cases}
for mi in range(1,5):
    for target in (5,60):
        pos=by_case[f'W{mi}_{target}_returned'];neg=by_case[f'W{mi}_{target}_not_returned']
        assert pos['profiles']==neg['profiles'] and pos['position']==neg['position'] and pos['display_map']==neg['display_map']
    base=by_case[f'P{mi}_base'];position=by_case[f'P{mi}_position'];labels=by_case[f'P{mi}_labels']
    assert base['profiles']==position['profiles']==labels['profiles']
    assert base['position']==labels['position'] and base['position']==list(reversed(position['position']))
    assert base['display_map']==position['display_map'] and labels['display_map']=={'B':'alpha','A':'beta'}

def write_jsonl(name,rows):
    (ROOT/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
write_jsonl('episodes.jsonl',episodes)
write_jsonl('answer_key.jsonl',list(keys.values()))
(ROOT/'benchmark_answers.json').write_text(json.dumps(bench_rows,indent=2))
# Requests contain only model-visible messages, never answer keys.
write_jsonl('requests.jsonl',[{'episode_id':e['episode_id'],'messages':e['messages']} for e in episodes])
audit={'data_origin':'deterministic_instrument_audit','model_calls':0,'model_responses':0,
 'core_profiles_checked':count,'financial_and_refund_identities_pass':True,
 'benchmark_oracles_checked':len(benchmarks),'unique_benchmark_maxima':True,
 'unique_cases':len(cases),'episodes_per_configuration':len(episodes),
 'episodes_by_module':dict(Counter(e['module'] for e in episodes)),
 'positive_negative_mapping_pass':True,'independent_position_and_label_maps_pass':True,
 'live_model_pretest_status':'not_run_no_active_connection',
 'operator_review_status':'researcher_desk_assessment_only'}
(ROOT/'audit_results.json').write_text(json.dumps(audit,indent=2))
(ROOT/'manifest.json').write_text(json.dumps({'instrument_version':I['version'],'seed':20261025,'repeats':2,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.iterdir()) if p.is_file() and p.suffix in ['.json','.jsonl','.py','.md'] and p.name!='manifest.json'}},indent=2))
print(json.dumps(audit))
