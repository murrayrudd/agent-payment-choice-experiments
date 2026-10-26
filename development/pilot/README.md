# Agents CE Step 6 Sol calibration pilot

This is development evidence for the rebuilt instrument, separate from Step 5 and any future main study.
The archive contains 672 live API responses: 536 initial calls, 96 presentation-confirmation calls, and 40 midpoint follow-ups.
Total billed cost: USD 1.387236. The account-key usage delta reconciles exactly.

## Read the results

- `run_20261025/summary.json`: scores, repeat and presentation comparisons, fee series, midpoint responses, and held-out prediction checks.
- `run_20261025/scored_choices.csv`: every normalized physical choice with case, mandate, target, module, and cost.
- `run_20261025/frozen_inputs/protocol.json`: design and adaptive rule fixed before collection.
- `run_20261025/frozen_inputs/episodes.jsonl`: exact initial model-visible prompts plus design metadata.
- `run_20261025/adaptive/plan.json`: later eligible-bracket selection, separate from the original protocol.
- `run_20261025/confirmation/plan.json`: additional fixed-presentation block specified during collection before outcome analysis, separate from the original protocol.
- `run_20261025/results/attempts/`: actual requests and raw responses, one record per call.
- `run_20261025/connection/`: dated live catalog and endpoint snapshots; no credentials.
- `run_20261025/billing_reconciliation.json`: billed usage versus the sum of response charges.

The initial billing snapshot can precede completion of the provider's usage aggregation. The final
billing reconciliation is authoritative; the earlier snapshot is preserved rather than overwritten.

Offer choices are normalized to alpha and beta using each episode's display map. DECLINE is a valid choice.
The favorable and unfavorable outside anchors offer identical A/B profiles; their consistency score compares
purchase with decline, not arbitrary labels. Exact repeats do not represent independent people or operators.

## Reproduce the analysis without API access

Requires Python 3 with NumPy and SciPy. From the archive root:

    python analyze_pilot.py

This regenerates the summary and scored choices from stored responses without making model calls.
The predictive model uses original first-repetition calibration choices only. Four held-out pairs remain excluded
from fitting, adaptive selection, and presentation confirmation. Penalties 0.1, 1, and 10 are reported without choosing one on held-out results.
The confirmation block supplies identical label and position settings across mandates and targets for the
16 calibration pairs. It does not replace or retrospectively modify the original core observations.
The frozen `build_pilot.py` is the original workspace design-builder snapshot; its source paths refer to
the earlier Step 5 package. Exact generated design inputs are retained and sufficient to rerun collection.

## Collection is offline by default

    python collect_pilot.py

prints a dry-run summary and makes zero API calls. Live collection requires an explicit `--live` flag and
an external credential file. Never put a credential into this archive. Existing completed requests are not
resent; any unresolved attempt requires manual reconciliation. Four requests may run concurrently.
The original dated model, provider, generation settings, USD 2 stage ceiling, and price ceilings remain fixed.
This archive is complete and does not require additional model calls.

## Interpretation

Switching brackets describe this model's choices under specified contracts and mandates. Persistent choices,
repeat variation, and presentation differences remain visible. These data do not establish operator WTP,
real payment demand, or market plausibility of the experimental levels. No Qwen calls occur in Step 6.

`archive_manifest.json` lists the SHA-256 digest of every other member.
