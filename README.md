# Operator mandates and tradeoffs in AI agent payment choices

Replication materials for the working paper by **Murray A. Rudd**. The experiment examines how operator instructions change an AI agent's choices among payment contracts for the same API data response.

The main study contains **1,280 hypothetical decisions** by one Sol 6.1 configuration, collected October 25, 2026. Four mandates—Balanced, Economy, Continuity, and Data minimization—were crossed with desired completion targets of 5 and 60 seconds. Contract attributes were service fee, success probability, completion time, principal returned after failure, and payment record retention.

Changing the mandate altered 21.9–32.3% of matched choices. Relaxing the completion target changed 28.1% of Continuity choices. The two fitted choice models predicted approximately 90% of withheld choices, while simple priority rules performed better in several conditions.

The exploratory Balanced comparison estimated a conditional fee premium of 5.23 cents for increasing success from 99% to 99.9%. Its selected-penalty resampling interval was 1.44–10.31 cents. The full model's interval exceeded the tested premium range at the strongest penalty, so the follow-up **did not meet the complete prespecified robustness rule**. The result describes compensation for this specified comparison; it does not establish an operator's valuation or a general willingness-to-pay schedule.

[![Offline replication](https://github.com/murrayrudd/agent-payment-choice-experiments/actions/workflows/replication.yml/badge.svg)](https://github.com/murrayrudd/agent-payment-choice-experiments/actions/workflows/replication.yml)

## Start here

Use **Python 3.12.14** and the pinned packages in `requirements.txt` for the tested environment. Installation requires internet access; reproduction uses archived responses and makes no model-provider calls.

```bash
python -m pip install -r requirements.txt
python scripts/verify_package.py
python scripts/reproduce.py --mode full --development
```

On Windows, `py -3.12` can replace `python`. See [reproduction instructions](docs/reproduction.md) for an isolated environment and a faster check.

The command copies the research archive to `_reproduced/`, rebuilds the main results and 6,000 monetary bootstrap fits, checks the pretest and pilot summaries, and compares regenerated values with the saved results. It also regenerates CSV exports and Figure 1. Python network connections are disabled for the study scripts. An existing output directory is never overwritten.

## Repository contents

| Path | Contents |
| --- | --- |
| `study/run_20261025/inputs/` | Frozen instrument, protocol, physical pairs, episode schedule, and exact provider requests |
| `study/run_20261025/results/attempts/` | All 1,280 main-study requests, responses, usage records, and parsed choices |
| `study/run_20261025/analysis/` | Prespecified fits, predictions, matched comparisons, and diagnostics |
| `study/assessment/` | Independently checked report summaries |
| `study/revision_analysis/` | Exploratory timing decomposition and monetary compensation analysis, including all bootstrap estimates |
| `development/pretest/` | Pretest instruments, Sol and Qwen responses, grading, and diagnostics |
| `development/pilot/` | Sol pilot, presentation-confirmation block, midpoint probes, and analysis |
| `data/` | Main choices, offered contracts, and withheld predictions in CSV format |
| `tables/` | CSV exports corresponding to the paper's quantitative results |
| `figures/` | Figure 1 as PNG and SVG |
| `scripts/` | Offline reproduction, export, and verification commands |
| `docs/` | Reproduction guide, data dictionary, paper-to-file map, and reuse status |
| `provenance/` | Source preservation record and original historical manifests |

The [paper-to-file map](docs/manuscript_map.md) identifies the sources for each table and figure. The [data dictionary](docs/data_dictionary.md) defines the CSV variables and units.

## Analytical separation

Only the first responses to the 64 estimation pairs enter model fitting: 512 decisions across eight conditions. The first responses to 32 different pairs supply 256 withheld choices. Exact repetitions and other diagnostics remain separate. Pretest and pilot responses are development evidence, not main-study observations.

The main protocol was fixed before collection and retained in the project record; it was not registered externally. The target-satisfaction decomposition and compensation follow-up were added during manuscript revision and remain labeled exploratory. Resampling describes sensitivity within this finite design, not uncertainty across a population of human operators.

## Provenance

This public distribution derives from `Agents_CE_Replication_Package_v02.zip`. All scientific prompts, schedules, raw responses, parsing and analysis code, and saved scientific results retain their original bytes. Administrative account balances, key usage baselines, and internal authorization details were removed. Public manifest variants account for those changes; the original manifests remain available for comparison. See [provenance](docs/provenance.md).

Some archived READMEs and records describe the earlier precollection or private-supplement stage. They are historical records. This README describes the public distribution and the completed study.

## Citation and manuscript

Rudd, Murray A. (2026). *Operator mandates and tradeoffs in AI agent payment choices*. Working paper.

Release **v0.2.0** provides the replication materials at [murrayrudd/agent-payment-choice-experiments](https://github.com/murrayrudd/agent-payment-choice-experiments). `CITATION.cff` supplies machine-readable citation metadata. The manuscript will be posted on SSRN. Its DOI link will be added here and to the preferred citation when assigned; the full paper will remain on SSRN. The replication results correspond to manuscript version 0.2, including the clarified monetary analysis.

## Reuse

No reuse license is specified for this release. See [reuse status](docs/reuse.md).
