"""Verify the public distribution and its unchanged scientific source record."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(root=ROOT):
    manifest = json.loads((root / "PUBLIC_MANIFEST.json").read_text(encoding="utf-8"))
    errors = []
    for name, expected in manifest["files"].items():
        path = root / name
        if not path.is_file():
            errors.append("Missing file: " + name)
        elif digest(path) != expected["sha256"]:
            errors.append("Checksum mismatch: " + name)
    preservation = json.loads((root / "provenance/source_preservation.json").read_text(encoding="utf-8"))
    unchanged = 0
    for row in preservation["records"]:
        if row["status"] == "unchanged":
            if digest(root / row["path"]) != row["source_sha256"]:
                errors.append("Scientific/historical source changed: " + row["path"])
            unchanged += 1
        elif row["status"] == "omitted" and (root / row["path"]).exists():
            errors.append("Excluded administrative file present: " + row["path"])
    run = root / "study/run_20261025"
    episodes = [json.loads(x) for x in (run / "inputs/episodes.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    attempts = list((run / "results/attempts").glob("*.json"))
    if len(episodes) != 1280 or len(attempts) != 1280:
        errors.append("Expected exactly 1,280 scheduled episodes and attempt records")
    core = Counter((e["split"], e["repeat"]) for e in episodes if e["module"] == "core")
    if core != {("estimation", 1): 512, ("heldout", 1): 256, ("estimation", 2): 128, ("heldout", 2): 64}:
        errors.append("Core allocation differs from the frozen design")
    token_patterns = [
        rb"(?:sk-or-v1-|sk-proj-|sk-ant-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}",
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        rb"AKIA[0-9A-Z]{16}",
    ]
    for name in manifest["files"]:
        data = (root / name).read_bytes() if (root / name).is_file() else b""
        if any(re.search(pattern, data) for pattern in token_patterns):
            errors.append("Possible credential in " + name)
    if errors:
        raise RuntimeError("\n".join(errors))
    return {"status": "passed", "manifest_files": len(manifest["files"]),
            "unchanged_source_files": unchanged, "main_attempt_records": len(attempts),
            "credential_pattern_matches": 0}

if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
