"""Offline revision analyses for the agent payment manuscript.

Adds a target-satisfaction breakdown and one exploratory compensation check.
No API calls. Frozen requests, responses, and prespecified analyses are read-only.
"""
import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
import numpy as np
import scipy

def main(root, output, draws):
    sys.path.insert(0, str(root / "run_20261025"))
    from common import parse, readl, features, offer, fit_logit, probabilities, filehash
    from analyze_main import arrays, score, rule_probs

    run = root / "run_20261025"
    meta = {r["episode_id"]: r for r in readl(run / "inputs/episodes.jsonl")}
    core = []
    for eid, e in meta.items():
        if e["module"] != "core" or e["repeat"] != 1:
            continue
        record = json.loads((run / "results/attempts" / (eid + ".json")).read_text())
        status, choice = parse(record, e)
        assert status == "valid"
        core.append({**e, "choice": choice})
    assert len(core) == 768
    assert all(r["choice"] in ("alpha", "beta") for r in core)
    lookup = {(r["pair_id"], r["mandate"], r["target_seconds"]): r for r in core}
    mandates = ["Balanced", "Economy", "Continuity", "Data minimization"]
    pair_ids = sorted({r["pair_id"] for r in core})
    target_rows = []
    for m in mandates:
        for n_meet in [0, 1, 2]:
            rows = []
            for pair in pair_ids:
                a, b = lookup[pair, m, 5], lookup[pair, m, 60]
                n = sum(o["time_seconds"] <= 5 for o in a["profiles"].values())
                if n != n_meet:
                    continue
                oa, ob = a["profiles"][a["choice"]], b["profiles"][b["choice"]]
                rows.append({"pair_id": pair, "changed": a["choice"] != b["choice"],
                    "short_choice_meets_5": oa["time_seconds"] <= 5,
                    "long_choice_meets_5": ob["time_seconds"] <= 5,
                    "short_choice": a["choice"], "long_choice": b["choice"]})
            target_rows.append({"mandate": m, "offers_meeting_5_seconds": n_meet,
                "pairs": len(rows), "changed": sum(r["changed"] for r in rows),
                "short_choice_meets_5": sum(r["short_choice_meets_5"] for r in rows),
                "long_choice_meets_5": sum(r["long_choice_meets_5"] for r in rows),
                "changes_from_meeting_to_missing": sum(r["changed"] and r["short_choice_meets_5"] and not r["long_choice_meets_5"] for r in rows),
                "changes_from_missing_to_meeting": sum(r["changed"] and not r["short_choice_meets_5"] and r["long_choice_meets_5"] for r in rows),
                "entries": rows})
    assert [sum(r["changed"] for r in target_rows if r["mandate"] == m) for m in mandates] == [9, 1, 27, 1]

    tr = [r for r in core if r["mandate"] == "Balanced" and r["target_seconds"] == 5 and r["split"] == "estimation"]
    te = [r for r in core if r["mandate"] == "Balanced" and r["target_seconds"] == 5 and r["split"] == "heldout"]
    assert len(tr) == 64 and len(te) == 32
    reference = offer(f=".001", q=".99", t=5, r=".50", days=30)
    improved = offer(f=".001", q=".999", t=5, r=".50", days=30)
    origin = {"analysis_status": "Exploratory follow-up after manuscript review; not part of prespecified main analysis",
        "case_selection": "Balanced at 5 seconds was selected because it alone showed a unanimous interior switch in the fine success diagnostic.",
        "estimation_data": "64 first-response estimation pairs only; diagnostics and withheld outcomes do not enter fitting",
        "estimand": "Extra fee on the 99.9% offer that equates its fitted utility with the 99% reference; all other contract attributes fixed",
        "reference": reference, "improved_at_equal_fee": improved,
        "tested_premium_interval_usd": [0.0, 0.249],
        "observed_switch_bracket_usd": [0.019, 0.079],
        "expected_expenditure_increment_over_fee_premium_usd": 0.0045,
        "selected_penalty": 0.1, "sensitivity_penalties": [0.1, 1.0, 10.0],
        "bootstrap": {"draws": draws, "seed": 2026102519, "unit": "physical estimation pair", "sample_size": 64,
            "refit": True, "penalties_fixed": True, "parameterization_fixed": True,
            "notes": "Finite-design resampling sensitivity, not operator-population intervals; same resample indices for every fit"},
        "software": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}}
    # Fixed resamples, chosen before any follow-up results are examined.
    samples = np.random.default_rng(2026102519).integers(0, len(tr), (draws, len(tr)))
    checks = []
    bootstrap = []
    for linear in [False, True]:
        for conditional in [False, True]:
            x, y = arrays(tr, linear=linear, conditional=conditional)
            xt, yt = arrays(te, linear=linear, conditional=conditional)
            for lam in [0.1, 1.0, 10.0]:
                b = fit_logit(x, y, lam)
                offset = 0 if conditional else 1
                fx0 = features(reference, linear)
                d = features(improved, linear) - fx0
                db = float(d @ b[offset:])
                slopes = [float(b[offset] / .1)] if linear else [float(b[offset] / .02), float(b[offset+1] / .06), float(b[offset+2] / .17)]
                def delta(premium):
                    o = {**improved, "fee": str(.001 + premium)}
                    return float((features(o, linear)-fx0) @ b[offset:])
                # Exact roots on each linear segment of the implemented fee specification.
                cuts = [0., .249] if linear else [0., .019, .079, .249]
                roots = []
                for a, z in zip(cuts[:-1], cuts[1:]):
                    va, vz = delta(a), delta(z)
                    if abs(va) < 1e-12:
                        roots.append(a)
                    if va * vz < 0:
                        roots.append(a - va * (z-a)/(vz-va))
                    if abs(vz) < 1e-12:
                        roots.append(z)
                roots = sorted(set(round(v, 12) for v in roots))
                entry = {"specification": "linear_fee" if linear else "piecewise_fee",
                    "conditional": conditional, "penalty": lam,
                    "fee_gradients_per_usd": slopes, "all_fee_gradients_negative": all(g < 0 for g in slopes),
                    "equal_fee_utility_increment": db, "interior_roots_usd": [v for v in roots if 0 < v < .249],
                    "heldout": score(te, probabilities(xt,b)), "coefficients": b.tolist()}
                if linear:
                    entry["unrestricted_fee_premium_usd"] = -db / slopes[0]
                checks.append(entry)
                if not linear:
                    continue
                values = []
                for i, ix in enumerate(samples):
                    bb = fit_logit(x[ix], y[ix], lam)
                    slope = float(bb[offset] / .1)
                    du = float(d @ bb[offset:])
                    premium = -du / slope if slope != 0 else None
                    values.append({"replicate": i + 1, "fee_gradient_per_usd": slope,
                        "fee_premium_usd": premium, "negative_fee": slope < 0,
                        "interior": premium is not None and 0 < premium < .249})
                finite = [v["fee_premium_usd"] for v in values if v["fee_premium_usd"] is not None and np.isfinite(v["fee_premium_usd"])]
                boot = {"conditional": conditional, "penalty": lam, "draws": draws,
                    "finite": len(finite), "negative_fee": sum(v["negative_fee"] for v in values),
                    "interior": sum(v["interior"] for v in values),
                    "both_negative_and_interior": sum(v["negative_fee"] and v["interior"] for v in values),
                    "percentile_95_usd": np.quantile(finite,[.025,.975]).tolist(),
                    "median_usd": float(np.median(finite)),
                    "minimum_usd": min(finite), "maximum_usd": max(finite)}
                bootstrap.append(boot)
                output.mkdir(parents=True,exist_ok=True)
                filename = "bootstrap_" + ("conditional" if conditional else "full") + "_" + str(lam).replace(".","p") + ".json"
                (output / filename).write_text(json.dumps(values,indent=2)+"\n")
                print(json.dumps({"finished": {"conditional": conditional, "penalty": lam}, "bootstrap": boot}),flush=True)
    # Direct implementation check for the comparator's treatment of DECLINE.
    for r in core:
        prob = rule_probs(r, "lowest_expected_expenditure", .01)
        assert abs(prob[2] - .01/3) < 1e-12
        assert min(1+float(o["fee"])-(1-float(o["success_probability"]))*float(o["refund"]) for o in r["profiles"].values()) > 0
    out = {"provenance": origin, "target_satisfaction": target_rows, "compensation_point_checks": checks,
        "compensation_bootstrap": bootstrap,
        "source_hashes": {str(p.relative_to(root)): filehash(p) for p in [
            run/"common.py", run/"analyze_main.py", run/"inputs/protocol.json", run/"inputs/episodes.jsonl",run/"analysis/training_fits.json"]}}
    output.mkdir(parents=True,exist_ok=True)
    (output/"revision_analysis.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({"target_satisfaction": [{k:v for k,v in r.items() if k!="entries"} for r in target_rows],
        "point_checks": [{k:v for k,v in r.items() if k!="coefficients"} for r in checks]},indent=2),flush=True)

if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output",type=Path)
    ap.add_argument("--draws",type=int,default=1000)
    a=ap.parse_args()
    main(a.root,a.output or a.root/"revision_analysis"/"results",a.draws)

