# Data dictionary

The empirical records are hypothetical model choices. No human respondents or real purchases are represented. The CSV files are derived conveniences; exact prompts, raw provider responses, and scoring remain in the archived JSON files.

## Main choice records

`data/choices.csv` contains one row per scheduled main-study episode: 1,280 rows. `data/offers.csv` contains the two purchase offers per episode: 2,560 rows. Join these files on `episode_id`.

| Field | Meaning |
| --- | --- |
| `episode_id` | Unique scheduled call identifier; matches the attempt JSON filename |
| `case_id` | Exact-prompt case identifier shared across repetitions |
| `pair_id` | Physical offer-pair identifier |
| `module` | Core, presentation, fine reliability, refund/success, or outside-anchor task |
| `split` | Estimation, heldout, or diagnostic role |
| `repeat` | Scheduled repetition index; only first core responses enter fitting and withheld scoring |
| `mandate` | Balanced, Economy, Continuity, or Data minimization |
| `target_seconds` | Desired completion target, 5 or 60 seconds |
| `status` | Parsed response status; all main responses are valid |
| `physical_choice` | `alpha`, `beta`, or `DECLINE`; physical identifiers remain stable under label changes |
| `displayed_choice` | The corresponding displayed label, `A`, `B`, or `DECLINE` |
| `physical_offer` | `alpha` or `beta` in the offer file |
| `displayed_label` | `A` or `B` assigned to the physical offer |
| `column_position` | 1 for left, 2 for right |
| `fee_usd` | Nonrefundable service fee, in US dollars |
| `success_probability` | Probability of usable data on a 0–1 scale |
| `time_seconds` | Time to usable data or a definitive failure notice |
| `principal_return_usd` | Amount of the $1.00 principal returned after failure |
| `retention_days` | Duration of the payment service's private transaction record |
| `expected_expenditure_usd` | `1 + fee − (1 − success_probability) × principal_return` |
| `selected` | Whether the agent selected that physical offer |

Attribute columns in `choices.csv` describe the selected contract and are blank for DECLINE. Attribute columns in `offers.csv` describe all offered contracts. Principal return is conditional on failure; it is not an unconditional payment. The instrument fixes refund delay at 60 seconds after the failure notice.

## Predictions and result tables

`data/withheld_predictions.csv` contains 2,048 rows: 256 withheld choices for each of eight fitted models or comparator rules. `probability_alpha`, `probability_beta`, and `probability_decline` sum to one. `correct` records whether the most probable choice matched the observed response. `log_loss` is the negative logarithm of the probability assigned to that observed choice.

Table exports retain more precision than the manuscript. Fields ending in `_cents` or `_percent` use those units; other monetary fields ending in `_usd` use dollars. Accuracy in the condition-level prediction file is on a 0–1 scale. Boolean fields use `True` and `False`.

In Table C7, `conditional` means a fit over the two purchase offers. `full` includes DECLINE. `penalty` is the ridge penalty fixed for that fit and its resamples. `interior_resamples` counts premiums strictly between 0 and 24.9 cents. Every finite premium, including negative or out-of-range values, enters the percentile interval. All 1,000 premiums per fit were finite.

Pretest and pilot records use their own original schemas and remain under `development/`. Their READMEs describe those stages. They must not be pooled with main-study records.
