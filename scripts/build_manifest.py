"""Refresh only the public distribution manifest after repository maintenance."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]

def main():
    files = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if path.name == "PUBLIC_MANIFEST.json" or any(
            part in {".git", ".venv", "venv", "__pycache__", ".pytest_cache"} or part.startswith("_reproduced")
            for part in relative.parts
        ) or path.suffix in {".pyc", ".pyo"}:
            continue
        data = path.read_bytes()
        files[relative.as_posix()] = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    manifest = {"distribution_version": "0.2.0", "hash_algorithm": "sha256",
                "scope": "Public repository files; excludes this manifest, Git internals, environments, bytecode, and _reproduced output directories",
                "files": files}
    (ROOT / "PUBLIC_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_files": len(files)}))

if __name__ == "__main__":
    main()
