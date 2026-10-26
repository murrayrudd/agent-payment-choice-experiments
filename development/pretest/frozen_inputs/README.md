# Agent payment Step 5 pretest

The instrument uses **principal returned after failure**. This package contains exact prompts, independent numerical answers, a bounded collector, and an offline grader. This is the frozen input package immediately before the October 25, 2026 live pretest. Do not treat the answer key or validation fixtures as model observations; live responses and scored results are stored separately.

The 48 distinct prompts are each presented twice in fresh conversations: 12 comprehension cases, 8 numerical objective cases, 16 refund wording cases, and 12 presentation cases. That gives 96 calls per model configuration. Repeated calls characterize a configuration; they are not independent human respondents. The qualitative cases have no correct purchase choice and no imposed WTP.

## Contents

- `instrument.json`: exact common stem and mandates extracted from version 0.2 of the instrument.
- `episodes.jsonl`: full schedule, prompt hashes, offer identities, and independent position and label mappings.
- `requests.jsonl`: model-visible messages only, with no answers.
- `answer_key.jsonl` and `benchmark_answers.json`: factual answers and exact numerical payoff maxima, kept outside prompts.
- `build_pretest.py`: deterministic construction and exhaustive accounting checks.
- `grade_responses.py`: strict scoring and within-configuration comparison of repeated, reframed, repositioned, and relabeled choices.
- `collect_pretest.py`: optional sequential OpenRouter collector, disabled unless `--live` is provided.
- `configuration.json`: dated Sol and Qwen settings recovered from the earlier study. Canonical identities, specified endpoints, parameter support, and prices were checked against the live catalog on October 25, 2026.
- `audit_results.json` and `package_validation.json`: completed offline checks, explicitly labeled as nonbehavioral evidence.
- `validate_package.py`: independent numerical answers and parser fixtures.

## Offline verification

Use Python 3.10 or newer. This package uses only the standard library.

```bash
python build_pretest.py
python validate_package.py
python collect_pretest.py
```

These commands make no model calls. Rebuilding the files changes the manifest; freeze a copy before collection. Never edit an instrument after responses have accumulated in its output folder.

## Controlled live collection

Provide an ordinary OpenRouter experiment credential through the `OPENROUTER_API_KEY` environment variable. Do not put it in code or the archive. The collector accepts an active temporary, nonresetting key capped at no more than the newly authorized **$20.00 total** and enforces a separate **$1.00 software cap per model pretest**. It never raises the key limit or enables billing. The shared key also limits combined spending. The authorized key expires November 1, 2026 at 17:33 UTC; credentials are excluded from all saved artifacts.

```bash
python collect_pretest.py --model sol --live --output results_sol
python grade_responses.py results_sol/responses.jsonl --configuration sol_step5_v02_medium --output results_sol/scored.json
```

The historical Sol configuration is `openai/gpt-6.1-sol-20260929` through OpenAI; Qwen is `qwen/qwen3.8-max-20260902` through `alibaba/us-east-1`. Both retain medium reasoning, an 8,192-token output ceiling, and provider-default sampling. Sol retains explicit caching without cache breakpoints. Structured response schemas vary only to accommodate factual fields versus the choice field. No tools, browsing, model/provider fallback, or response healing are enabled.

The launch check verifies the current canonical model, endpoint identity, parameter support, key allowance, and pricing against the historical ceilings. Unavailable models are not silently replaced. The collector stops on transport uncertainty, missing billing, route changes, or exhausted budget. Every attempted request and raw response is archived; no automatic retries or response repairs occur. A lock prevents two processes from using the same run folder. An unresolved attempt requires reconciliation before resumption. The live collection path has not been exercised in this session.

The Qwen configuration is available for the previously envisaged robustness check by using `--model qwen` and a separate output folder. Score it separately. Start with Sol and resolve interpretation problems before expanding collection.

## Prespecified interpretation

1. Require all critical factual answers and all eight numerical optima in both repetitions before advancing a configuration. A failure triggers diagnosis, a versioned prompt correction where justified, and new pretests. Preserve the failed version and responses.
2. Treat malformed JSON, invalid schema, refusal, empty output, truncation, transport failure, and explicit DECLINE separately. Unobserved episodes remain missing, not correct.
3. Report wording disagreement beside repeat disagreement within each wording. Report position and label disagreement separately after mapping back to physical offers. With this small diagnostic battery, do not infer population effects or set WTP values.
4. The refund comparison changes the consistent wording package in the stem, mandate, and attribute row. Fees, probabilities, actual refunds, and the expenditure-after-failure row stay fixed. It is not an isolated single-word intervention.
5. The presentation block changes physical order and label assignment independently. Its first offer has a $0.50 refund; the wording block uses the worked example with a $0 refund for the first offer.
6. Numerical benchmarks have explicit success benefits and delay penalties. Their answers validate execution of those objectives, not the qualitative mandates or operator valuations. N04 uses an intermediate fee and N08 uses an above-cap offer deliberately; they are diagnostics outside the main level grid.
7. Step 5 is not complete until live responses have been scored and the contract definitions have passed substantive review. Fee calibration, price ladders, wider context tests, and efficient design belong to later stages.

## Sources and provenance

The revised design is `Agents_CE_Steps_3_4_Attributes_and_Instrument_v02.docx`. Historical execution settings come from `Sol_Qwen_qualification_results.md` and `Sol_main_study_results.zip`, dated October 18, 2026. Earlier experimental observations are not reused as new pretest results.

OpenRouter primary documentation: [API reference](https://openrouter.ai/docs/api/reference/overview), [authentication](https://openrouter.ai/docs/api/reference/authentication), and [provider selection](https://openrouter.ai/docs/guides/routing/provider-selection). The collector uses the existing project's request pattern and current documented routing controls.

Framing rationale: [Howard and Salkeld 2009](https://www.ispor.org/publications/journals/value-in-health/abstract/Volume-12--Issue-2/Does-Attribute-Framing-in-Discrete-Choice-Experiments-Influence-Willingness-to-Pay--Results-from-a-Discrete-Choice-Experiment-in-Screening-for-Colorectal-Cancer). Human DCE findings justify checking the wording; they do not predict our agents' framing response.
