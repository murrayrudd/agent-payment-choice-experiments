"""Validate reported revision results against archived data and fitted models."""
from pathlib import Path
import hashlib,json,sys
import numpy as np

root=Path(__file__).resolve().parents[1]
run=root/"run_20261025"
out=root/"revision_analysis/results"
sys.path.insert(0,str(run))
from common import features, offer
data=json.loads((out/"revision_analysis.json").read_text())
release=json.loads((root/"release_manifest.json").read_text())
checked=0
for name,expected in release["files"].items():
    if name.startswith(("run_20261025/inputs/","run_20261025/results/attempts/")) or name in [
        "run_20261025/common.py","run_20261025/analyze_main.py","run_20261025/manifest.json"]:
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
        checked+=1
archived=json.loads((run/"analysis/training_fits.json").read_text())
for row in data["compensation_point_checks"]:
    b=np.array(row["coefficients"])
    if not row["conditional"] and row["penalty"]==.1:
        original=next(x for x in archived if x["specification"]==row["specification"] and x["mandate"]=="Balanced" and x["target_seconds"]==5)
        assert np.allclose(b,original["coefficients"],rtol=1e-7,atol=1e-7)
    linear=row["specification"]=="linear_fee"
    f0=offer(f=".001",q=".99",t=5,r=".50",days=30)
    for premium in row["interior_roots_usd"]:
        f1=offer(f=str(.001+premium),q=".999",t=5,r=".50",days=30)
        beta=b if row["conditional"] else b[1:]
        assert abs(float((features(f1,linear)-features(f0,linear))@beta))<1e-8
for row in data["compensation_bootstrap"]:
    fname="bootstrap_"+("conditional" if row["conditional"] else "full")+"_"+str(row["penalty"]).replace(".","p")+".json"
    records=json.loads((out/fname).read_text())
    assert len(records)==1000 and len({x["replicate"] for x in records})==1000
    vals=np.array([x["fee_premium_usd"] for x in records])
    assert np.isfinite(vals).all()
    assert np.allclose(np.quantile(vals,[.025,.975]),row["percentile_95_usd"])
    assert int(((vals>0)&(vals<.249)).sum())==row["interior"]
    assert sum(x["negative_fee"] for x in records)==row["negative_fee"]
matched=json.loads((run/"analysis/matched_contrasts.json").read_text())
for mandate in ["Balanced","Economy","Continuity","Data minimization"]:
    actual=next(x for x in matched if x["kind"]=="target" and x["mandate"]==mandate)
    expected={r["pair_id"]:bool(r["changed"]) for r in actual["entries"]}
    got={r["pair_id"]:r["changed"] for g in data["target_satisfaction"] if g["mandate"]==mandate for r in g["entries"]}
    assert got==expected
cont=next(x for x in data["target_satisfaction"] if x["mandate"]=="Continuity" and x["offers_meeting_5_seconds"]==1)
assert cont["pairs"]==52 and cont["short_choice_meets_5"]==52
assert cont["changed"]==cont["changes_from_meeting_to_missing"]==26
assert cont["changes_from_missing_to_meeting"]==0
result={"status":"passed","immutable_source_files_verified":checked,
    "selected_full_coefficients_match_main_archive":True,
    "reported_compensation_roots_satisfy_equal_utility":True,
    "all_bootstrap_records_retained_and_intervals_verified":True,
    "target_strata_reconcile_to_original_matched_contrasts":True,
    "new_model_calls":0}
(out/"validation.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result))

