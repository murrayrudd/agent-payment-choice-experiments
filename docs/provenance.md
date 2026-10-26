# Source provenance and public distribution

The source is `Agents_CE_Replication_Package_v02.zip`, SHA-256:

```text
bebbb9a351ef6754c241135c7e405e2d02d82497263c20416ad38761d9a534cb
```

The original archive remains unchanged. Its main-study contents are under `study/`. Its two nested development archives have been expanded into `development/pretest/` and `development/pilot/` so their code and records can be inspected directly on GitHub.

## Preserved scientific record

The public package preserves the bytes of all experimental prompts, schedules, model responses, response parsers, choice-model code, stored fits, predictions, and bootstrap estimates. This includes all 1,280 main-study attempt records and the original development response records. No choices were recollected, repaired, relabeled, or excluded during packaging.

`provenance/source_preservation.json` maps every source member to its public path and original hash. It separately identifies omitted administrative files, redacted metadata fields, expanded archives, and public manifest variants. It contains no removed field values.

## Administrative changes

The public distribution omits personal credit snapshots, account-level billing reconciliations, private authorization and internal storage references, and two original private packaging utilities. Four metadata files have account credit, key usage, remaining allowance, expiry, or authorization fields removed. Scientific execution settings, per-response usage and cost, study budget ceilings, and model endpoint records remain available. Configured key-limit ceilings remain because they are experimental spending safeguards used by the original collectors, rather than snapshots of account funds or usage.

One redacted file, the development budget preflight check, belonged to the frozen main package. The pretest configuration also contained private authorization text. Their original hash manifests are preserved under `provenance/original_manifests/`; public manifest variants describe the distributed files and allow the original offline validators to run. These variants are explicitly identified in the preservation record. The original design-freeze timestamps describe the original records, not the public packaging date.

Original collection records may retain a `manifest_sha256` referring to the historical frozen manifest. That identifier records what was used at collection; it was not rewritten to imply that the public administrative redaction preceded the experiment.

## Verification layers

`PUBLIC_MANIFEST.json` covers the files distributed in this repository. The source preservation record independently checks unchanged archived members against their original hashes. Historical stage manifests record the original experiment and supplement. Public stage-manifest variants cover their corresponding distributed stage directories.

The root `.gitattributes` preserves the exact bytes of the archived study and development files, including on Windows. New documentation and helper scripts use LF line endings. Reproduction writes to a separate directory and checks the repository again after all computations finish.

The public hash manifest can be refreshed with `python scripts/build_manifest.py` after author-approved changes to repository documentation or publication metadata. That command never edits the archived stage manifests or the source preservation record. Changing scientific source bytes requires a documented new research version, not a checksum refresh.
