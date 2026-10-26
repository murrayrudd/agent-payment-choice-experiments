# Paper to repository map

This map follows manuscript version 0.2. All paths are relative to the repository root.

| Paper item | File or source |
| --- | --- |
| Table 1 Attribute levels | `study/run_20261025/common.py`, `inputs/core_design.json`, and `inputs/instrument.json` under the same run directory |
| Table 2 Call allocation | `study/run_20261025/inputs/episodes.jsonl`; allocation checked by `scripts/verify_package.py` |
| Figure 1 Matched changes | `figures/figure_1_choice_changes.png`, `.svg`, and `tables/figure_1_data.csv` |
| Table 3 Selected attributes | `tables/table_3_selected_attributes.csv` |
| Table 4 Overall prediction | `tables/table_4_prediction_overall.csv` |
| Appendix A Instrument and example | `study/run_20261025/inputs/instrument.json`, `episodes.jsonl`, and `core_design.json` |
| Table A1 Worked choice | Physical pair `E001` in `study/run_20261025/inputs/core_design.json` |
| Appendix B1 and Table B1 Design simulations | `study/run_20261025/development/design_audit.json`, `simulation_results.json`, and `simulate_design.py` in the run directory |
| Appendix B2 Model coding and fitting | `study/run_20261025/common.py` and `analyze_main.py` |
| Appendices B3–B4 Diagnostics and criteria | `study/run_20261025/inputs/protocol.json` and `diagnostic_assignments.json` |
| Appendix B5 Exploratory methods | `study/revision_analysis/analyze_revision.py` |
| Tables C1–C2 Prediction by condition | `tables/tables_C1_C2_prediction_by_condition.csv` |
| Table C3 Success switching | `tables/table_C3_success_switching.csv` |
| Table C4 Fee-sign checks | `tables/table_C4_fee_sensitivity.csv` and `study/run_20261025/analysis/training_fits.json` |
| Table C5 Interpretation checks | `study/assessment/report_metrics.json` and `study/revision_analysis/results/revision_analysis.json`; this table summarizes criteria rather than a separate estimator |
| Table C6 Timing decomposition | `tables/table_C6_target_satisfaction.csv` |
| Table C7 Compensation sensitivity | `tables/table_C7_compensation.csv`; all individual refits are in `study/revision_analysis/results/bootstrap_*.json` |
| Appendix D1 Qualification and pilot | `development/pretest/summary.json` and `development/pilot/run_20261025/summary.json` |
| Table D1 Main execution settings | `study/run_20261025/inputs/configuration.json` and `results/run.json` |
| Table D2 Replication records | Repository README and `provenance/source_preservation.json` |

`scripts/export_results.py` produces the CSV files and Figure 1. The paper's static instrument and execution tables are documented by their source records rather than duplicated as separately maintained numerical outputs.
