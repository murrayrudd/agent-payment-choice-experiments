"""Reproduce the archived analyses in a fresh, separate output directory."""
from pathlib import Path
import argparse
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from verify_package import verify

ROOT = Path(__file__).resolve().parents[1]

def compare(a, b, trail="", skipped=()):
    """Require identical structure/counts and tightly matching floating results."""
    if isinstance(a, dict):
        keys_a, keys_b = set(a) - set(skipped), set(b) - set(skipped)
        if keys_a != keys_b:
            raise AssertionError("Different fields at " + trail)
        for key in sorted(keys_a):
            compare(a[key], b[key], trail + "/" + key, skipped)
    elif isinstance(a, list):
        if len(a) != len(b):
            raise AssertionError("Different list length at " + trail)
        for index, (x, y) in enumerate(zip(a, b)):
            compare(x, y, trail + "/" + str(index), skipped)
    elif isinstance(a, float) or isinstance(b, float):
        if not math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-8):
            raise AssertionError("Numerical mismatch at " + trail)
    elif a != b:
        raise AssertionError("Value mismatch at " + trail)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["quick", "full"], default="full")
    parser.add_argument("--output", type=Path, default=ROOT / "_reproduced")
    parser.add_argument("--development", action="store_true", help="Also rerun pretest and pilot summaries in copied directories")
    args = parser.parse_args()
    started = time.monotonic()
    verification = verify()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists. Choose a new --output path so prior results are preserved.")
    if output == ROOT or ROOT.is_relative_to(output):
        raise SystemExit("Output must not be the repository or one of its parent directories.")
    output.mkdir(parents=True)
    study = output / "study"
    shutil.copytree(ROOT / "study", study)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", MPLBACKEND="Agg")
    commands = []
    def run(label, script, *extra):
        print(label, flush=True)
        command = [sys.executable, "-X", "utf8", str(ROOT / "scripts/offline_runner.py"), str(script), *map(str, extra)]
        log = output / (label + ".log")
        with log.open("w", encoding="utf-8") as handle:
            result = subprocess.run(command, cwd=output, env=env, stdout=handle, stderr=subprocess.STDOUT)
        commands.append({"step": label, "returncode": result.returncode, "log": log.name})
        if result.returncode:
            raise RuntimeError("Step failed: " + label + "; see " + str(log))
    run("01_frozen_design", study / "run_20261025/validate_design.py")
    run("02_main_analysis", study / "run_20261025/analyze_main.py")
    run("03_independent_summary", study / "summarize_main.py")
    expected_main = ROOT / "study/run_20261025/analysis"
    for expected in sorted(expected_main.glob("*.json")):
        compare(json.loads(expected.read_text(encoding="utf-8")),
                json.loads((study / "run_20261025/analysis" / expected.name).read_text(encoding="utf-8")), expected.name)
    compare(json.loads((ROOT / "study/assessment/report_metrics.json").read_text(encoding="utf-8")),
            json.loads((study / "assessment/report_metrics.json").read_text(encoding="utf-8")),
            "report_metrics", skipped=("checked_utc",))
    if args.mode == "full":
        run("04_compensation_refits", study / "revision_analysis/analyze_revision.py")
        for expected in sorted((ROOT / "study/revision_analysis/results").glob("*.json")):
            if expected.name == "validation.json":
                continue
            compare(json.loads(expected.read_text(encoding="utf-8")),
                    json.loads((study / "revision_analysis/results" / expected.name).read_text(encoding="utf-8")),
                    expected.name, skipped=("software", "source_hashes"))
    run("05_compensation_validation", study / "revision_analysis/validate_revision.py")
    run("06_synthetic_analysis_check", study / "run_20261025/check_analysis.py")
    run("07_mock_collector_check", study / "run_20261025/check_offline.py")
    if args.development:
        dev = output / "development"
        shutil.copytree(ROOT / "development", dev)
        run("08_pretest_validation", dev / "pretest/frozen_inputs/validate_package.py")
        run("09_pretest_summary", dev / "pretest/analysis.py")
        compare(json.loads((ROOT / "development/pretest/summary.json").read_text(encoding="utf-8")),
                json.loads((dev / "pretest/summary.json").read_text(encoding="utf-8")), "pretest_summary")
        run("10_pilot_summary", dev / "pilot/analyze_pilot.py")
        compare(json.loads((ROOT / "development/pilot/run_20261025/summary.json").read_text(encoding="utf-8")),
                json.loads((dev / "pilot/run_20261025/summary.json").read_text(encoding="utf-8")), "pilot_summary")
    run("11_public_exports", ROOT / "scripts/export_results.py", "--study", study, "--output", output / "exports")
    verification_after = verify()
    report = {"status": "passed", "mode": args.mode, "python": platform.python_version(),
              "elapsed_seconds": round(time.monotonic() - started, 2), "commands": commands,
              "new_model_calls": 0, "python_network_connections_blocked": True,
              "main_results_match_archive": True, "bootstrap_refits_recomputed": 6000 if args.mode == "full" else 0,
              "development_summaries_recomputed": args.development,
              "comparison_tolerance": {"relative": 1e-6, "absolute": 1e-8},
              "source_verified_before": verification, "source_verified_after": verification_after}
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)

if __name__ == "__main__":
    main()
