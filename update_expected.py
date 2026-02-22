import subprocess
import sys
from pathlib import Path

CONVERT_SCRIPT = Path("convert.py")
SAMPLES_DIR = Path("tests/samples")
EXPECTED_DIR = Path("tests/expected")

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

if __name__ == "__main__":
    update_expected()
