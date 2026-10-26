# Reproducing the study

## Environment

The tested environment is Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0, and Matplotlib 3.10.8. The first two packages reproduce the statistical analysis; Matplotlib regenerates the figure. The original document-building scripts are retained as historical source and are not required for numerical replication.

From the repository directory on Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\verify_package.py
.\.venv\Scripts\python.exe scripts\reproduce.py --mode full --development
```

On macOS or Linux:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/verify_package.py
.venv/bin/python scripts/reproduce.py --mode full --development
```

## Commands and outputs

| Command | Work performed |
| --- | --- |
| `python scripts/verify_package.py` | Check public file hashes, preserved source bytes, allocation counts, and credential patterns |
| `python scripts/reproduce.py --mode quick --development` | Refit the main models, rebuild summaries, validate saved monetary refits, run synthetic and mock-collector checks, and rebuild development summaries |
| `python scripts/reproduce.py --mode full --development` | Perform the quick checks and recompute all six sets of 1,000 monetary bootstrap fits |
| `python scripts/export_results.py --output _reproduced_exports` | Export archived choices, offers, predictions, result tables, and Figure 1 |

Choose a new directory with `--output _reproduced_second` for another run. The default reproduction directory is `_reproduced/`. Each step writes a numbered log, and successful completion writes `validation.json`. Figure and CSV outputs appear under `exports/` in that directory.

The reproduction wrapper uses a fresh copy of `study/`. It uses one numerical-library thread and UTF-8 text handling, then checks the source repository again at completion. Counts and categorical results must match exactly. Floating-point comparisons use relative tolerance `1e-6` and absolute tolerance `1e-8`; only execution timestamps, software-version strings, and regenerated-output hashes are excluded where appropriate.

The quick mode validates the saved 6,000 bootstrap records but does not recompute them. Full mode refits every bootstrap model and compares the full sets of estimates with the archive. The `--development` option additionally rebuilds the pretest and pilot summaries in copied directories.

No API credential is needed. The reproduction commands disable Python network connections and never invoke live collection. Historical collectors remain in the source archive to document the experiment. A new model study requires a separately planned run, configuration, and credential.

## Automated checks

The GitHub Actions workflow runs quick reproduction with development checks on pushes and pull requests. A manual workflow run can select all monetary refits. The workflow has read-only repository permission and does not require a model API secret. Its first hosted run will occur after the repository is uploaded.

The manuscript and the original report-building scripts are not rebuilt by these commands. Those scripts include historical local paths and document dependencies; the portable result exports provide the numerical tables and figure needed for the paper.
