AGENTS CE — STEP 7 FROZEN MAIN-STUDY DESIGN v01

STATUS
No main-study model calls or main-study responses exist in this package.
The main design has 1,280 calls for one fixed Sol configuration. Step 6 supplied
development evidence only. Simulations and mock tests are explicitly labeled.

CONTENTS
inputs/instrument.json          Exact v0.2 task and mandate text.
inputs/configuration.json       Fixed model, generation settings and $3.50 cap.
inputs/core_design.json         64 estimation + 32 new withheld physical pairs.
inputs/episodes.jsonl           Complete randomized schedule and prompts.
inputs/requests.jsonl           Complete provider requests, without credentials.
inputs/protocol.json            Question roles, design rationale and analysis rules.
inputs/diagnostic_assignments.json  Prespecified repeats and presentation checks.
development/                   Priors, exclusions, design audit, synthetic checks.
manifest.json                  SHA-256 hashes of every frozen package member.

REQUIREMENTS
Python 3.12 or later; NumPy and SciPy. Verified with NumPy 2.3.5 and SciPy 1.17.0.
No network is used by the design, validation, simulation or analysis commands.

OFFLINE CHECKS (from this directory)
  python validate_design.py
  python collect_main.py
  python check_offline.py
  python check_analysis.py
  python analyze_main.py

The collector's default is offline and reports zero model calls. The analyzer
reports no main-study data until a results/attempts directory contains responses.
Mock collector checks create temporary fixture directories and never contact a
provider. They test successful completion, budget stop, transport ambiguity,
wrong route, invalid response, unresolved-run resumption and input corruption.

REPRODUCTION (use a copy of the package)
  python build_design.py
  python simulate_design.py --replicates 40
  python validate_design.py
Design outputs are deterministic for the included development inputs and seeds.
The final manifest is a frozen record. Do not edit it to make changed inputs pass
validation. Floating-point simulation summaries can vary slightly with libraries.

SUBSEQUENT MAIN COLLECTION
After the main-collection stage is instructed, use an external credential file:
  python collect_main.py --live --key-file /absolute/path/to/credential
The credential is never included in this archive. Do not put it in inputs/.
The collector rechecks the snapshot mapping, provider, prices, key expiry, funds
and hashes. It permits four concurrent calls and reserves their bounded costs.
There are no automatic retries, response repair, route fallbacks or adaptations.
Stop signals do not erase previously started attempts. Inspect unresolved calls
before resuming. A surviving lock requires inspection; do not blindly delete it.

ANALYSIS
  python analyze_main.py
Only first scheduled core responses enter estimation and withheld prediction.
An invalid first response is not replaced by its repeat. Diagnostics remain
separate. Four-fold model selection uses estimation pairs only; no test tuning.
The executable covers response accounting, repeats, presentation checks, matched
contrasts, conditional fee sensitivity, model fitting and baseline predictions.
Task-specific monetary estimates are intentionally not produced automatically;
the interpretation gates in protocol.json apply to any later valuation analysis.
No human/operator-population inference is licensed by the number of model calls.

DESIGN LIMITS
The greedy information criterion is a heuristic using four equally weighted
prior scenarios, not a proof of global optimality. Simulation compares 48, 64
and 80 estimation pairs under three assumed purchase-conditioned mechanisms.
It is not a statistical power calculation and does not simulate declines.
New withheld pairs test new combinations within these levels, not extrapolation
to other tasks, services, models or operators.

See the accompanying Step 7 design document for the study rationale and budget.
