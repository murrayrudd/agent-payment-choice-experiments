# Replication materials for Operator mandates and tradeoffs in AI agent payment choices

This supplement accompanies manuscript version 0.2. It preserves the complete
main-study archive and adds two explicitly exploratory analyses undertaken during
manuscript revision. No new model calls were made for these analyses.

## Contents

- `run_20261025/`: frozen design, original requests and responses, prespecified
  analysis code, and saved estimates.
- `assessment/`: original independent report summaries.
- `release_manifest.json`: original main-release checksums. All original
  files remain byte-for-byte unchanged.
- `development_sources/`: the complete Step 5 pretest and Step 6 pilot packages.
- `revision_analysis/analyze_revision.py`: timing-target decomposition and the
  Balanced, 5-second compensation analysis.
- `revision_analysis/results/`: all six sets of 1,000 bootstrap estimates,
  point fits, source hashes, and aggregate results.
- `revision_analysis/validate_revision.py`: source integrity and numerical
  checks, including reconciliation with the original matched-choice results.
- `supplement_manifest.json`: checksums for this complete supplement.

The original README and protocol retain their wording at the time they were
written. Their references to an unstarted collection or to monetary estimates
not being produced automatically describe the relevant historical stage. The
revision analysis is separate from that prespecified main analysis.

## Reproduction

Use Python 3.12 or later with NumPy and SciPy. Exact versions used for the
follow-up appear in `revision_analysis/results/revision_analysis.json`.

Work from a copy of this directory so stored outputs and checksum records remain
available for comparison. The commands below never contact a model provider.

```bash
python run_20261025/validate_design.py
python run_20261025/analyze_main.py
python summarize_main.py --root run_20261025 --output assessment_reproduced
python revision_analysis/analyze_revision.py
python revision_analysis/validate_revision.py
```

The follow-up defaults to 1,000 resamples for each of three penalties and both
outside-option treatments. It uses seed 2026102519, refits coefficients while
holding model and penalty fixed, and retains negative or out-of-range monetary
roots. It does not use withheld or diagnostic responses for fitting. Balanced at
5 seconds was selected after the diagnostic results were known, so its estimates
are exploratory.

For the selected conditional linear fit, the fee premium is 5.228972 cents and
the 95% finite-design resampling interval is 1.436307–10.308587 cents. The full
linear fit at penalty 10 has an interval extending beyond the tested fee range.
The exploratory result therefore does not satisfy the complete prespecified
robustness rule across full and conditional fits. No general WTP schedule or
operator valuation is established.

## Manuscript mapping

- Appendix B5: follow-up methods and estimand.
- Table C5: completed, unevaluated, and follow-up monetary checks.
- Table C6: target-satisfaction groups and observed choice changes.
- Table C7: linear fee compensation, slopes, and resampling sensitivity.
- Appendix D1: pretest qualification and pilot development outcomes.

The main empirical record consists of 1,280 original model calls, including 768
first core responses. Bootstrap refits are computations on those responses, not
additional empirical observations.

