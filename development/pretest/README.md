# Agent payment Step 5 live pretest

Version 0.2 of the instrument uses **principal returned after failure**. This archive contains 192 main pretest responses collected on October 25, 2026: 96 each for the dated Sol and Qwen configurations. Four additional API calls checked a clarified record-scope question, for 196 total calls. Total billed model cost was **$0.937766**. See `summary.json` and each model's `scored.json` for results.

## Experimental record

- `frozen_inputs/`: the exact precollection instrument, 96-episode schedule, prompt hashes, answer keys, collector, configuration, deterministic checks, and input manifest.
- `results_sol/` and `results_qwen/`: configuration records, every raw request and response, usage and billing, the combined response file, and scoring. The initial response is retained without response repair or automatic retries.
- `summary.json`: required checks, qualitative comparisons, normalized physical choices, cost, dates, and actual model/provider identities.
- `scope_diagnostic/`: a post hoc clarification of the ambiguous F08 field name, its exact prompts, four fresh responses, and separate scores. The common contract, offers, mandates, and generation settings are unchanged. Original qualification scores remain unchanged.
- `billing_reconciliation.json` and `verification.json`: API-reported experimental usage and archive integrity checks. Credentials are excluded.
- `catalog_snapshots/`: selected public model and endpoint metadata obtained before collection.
- `analysis.py`: offline scoring and summary reconstruction.
- `archive_manifest.json`: SHA-256 checksums for all other archive members.

The frozen input README and audit contain precollection status text, including a static `not_run_no_active_connection` audit label. Those fields are provenance from the pretest builder, not a description of the completed live run. The live observation status is recorded in the response files and `summary.json`. Frozen inputs have not been edited after collection began.

## Interpretation

Each configuration received 12 factual cases, 8 explicit numerical-objective cases, 16 wording cases, and 12 presentation cases, with two fresh repetitions of each. Repeated calls characterize the named configuration; they are not independent human respondents. The factual and numerical gate requires 24/24 and 16/16 correct episodes, respectively. Qualitative choices have no prescribed correct answer.

Sol passed the original required checks. Qwen did not pass the original all-correct rule. Its record-scope answer prompted a narrower diagnostic: rename `other_records_erased` to `other_parties_records_erased` and explicitly identify whose records the question concerns. Report the new item separately; do not substitute its responses into the original score or present it as a complete rerun of the battery. This clarification belongs in future comprehension checks.

Refund framing is compared across four mandates and two desired completion targets. Both wordings retain the displayed expenditure after failure. The position and label checks independently change order and labels and are scored after mapping choices back to the physical offers. Their profile pair differs from the wording pair in offer A's refund amount. The small comparison counts cannot establish general framing invariance or monetary valuation.

Sol was assessed first. Qwen collection began only after Sol passed the required checks. Both configurations retained medium reasoning, an 8,192-token output ceiling, provider-default sampling, and strict structured output. No browsing, tools, model/provider fallback, or response healing were enabled. Each configuration had a $1 software spending cap.

## Offline reproduction

From this directory, using Python 3.10 or newer:

```bash
python analysis.py
python frozen_inputs/validate_package.py
python frozen_inputs/collect_pretest.py
```

These commands make no model calls. Regrading may overwrite derived summary and score files; preserve the original archive. A new live experiment requires an active credential supplied through `OPENROUTER_API_KEY` and a fresh output directory. Do not reuse an archived result directory for a new run or change its prompts.

## Research boundary

The pretest checks interpretation of supplied terms, execution of explicit numerical objectives, and presentation sensitivity on a small battery. It does not validate the market plausibility of the fee levels, representativeness of operator mandates, the substantive value of record retention, or operator WTP. The next stage is a small calibration pilot; no Step 6 or main-study calls are included here.
