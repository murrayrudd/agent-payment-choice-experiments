AGENTS CE MAIN RUN — STEP 8

This release records the live main study specified in the frozen Step 7 design.
See assessment/report_metrics.json and the accompanying results document for
the completion status, observed findings, costs, and interpretation.

DIRECTORY MAP
run_20261025/inputs/             Frozen instrument, prompts, requests and protocol.
run_20261025/manifest.json       Original Step 7 file checksums, unchanged.
run_20261025/results/attempts/   Raw live responses, requests, usage, and scoring.
run_20261025/results/run.json    Configuration and collection start record.
run_20261025/results/run_status.json  Final collector status and cost accounting.
run_20261025/results/billing_reconciliation.json  Initial billing reconciliation.
run_20261025/analysis/           Prespecified fitted models and prediction results.
assessment/                    Independent bookkeeping and report summaries.
documentation/                 Result report source and interpretation notes.
release_manifest.json          Checksums of this complete main-run release.

PROVENANCE
The original README and design-document source inside run_20261025 remain the
unaltered Step 7 precollection record. Their statements that main collection
had not started describe the time of design freeze. The main-run records and
assessment in this release provide the subsequent status.

The Step 7 design was fixed before main collection. "Prespecified" here means
fixed and retained in the project record; it does not imply registration in an
external registry. Development priors and synthetic design simulations remain
in the frozen subdirectory and are not main-study observations.

REPRODUCE WITHOUT MODEL CALLS
Python 3.12 or later, NumPy, SciPy; tested versions are recorded in the release.
  python run_20261025/validate_design.py
  python run_20261025/analyze_main.py
  python summarize_main.py --root run_20261025 --output assessment_reproduced

Use a copy for reproduction so the saved assessment remains unchanged.
The frozen collector is offline by default. Existing completed episodes must
never be submitted again. The raw response archive is the empirical record.
No credential is included in this release.

INTERPRETATION
Only first scheduled core responses enter estimation and withheld prediction.
Repetitions, presentation variants, and interpretation probes remain separate.
All responses, including failures and declines if present, are retained.
Models describe one Sol configuration acting under supplied task conditions.
Neither model-call counts nor finite-design resampling represent a population
sample of human operators. Monetary estimates require the protocol's additional
conditions and are never produced automatically from coefficient ratios.
