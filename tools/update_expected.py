# SPDX-License-Identifier: MIT
"""Regenerate expected test outputs using --no-nlp."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "tools" else Path(__file__).resolve().parent
CONVERT_SCRIPT = REPO_ROOT / "convert.py"
SAMPLES_DIR = REPO_ROOT / "tests/samples"
EXPECTED_DIR = REPO_ROOT / "tests/expected"


def update_expected():
    if not SAMPLES_DIR.exists():
        print("Samples directory not found")
        return

    for sample_path in SAMPLES_DIR.iterdir():
        if not sample_path.is_file() or sample_path.name.startswith('.'):
            continue

        expected_path = EXPECTED_DIR / f"{sample_path.name}.json"
        print(f"Updating {expected_path} from {sample_path}")

        cmd = [
            sys.executable,
            str(CONVERT_SCRIPT),
            str(sample_path),
            "--output", str(expected_path),
            "--no-nlp"
        ]

        subprocess.run(cmd, check=True)


def main():
    update_expected()


if __name__ == "__main__":
    main()
