import json
import subprocess
import sys
import pytest
from pathlib import Path

# Path to the conversion script
CONVERT_SCRIPT = Path(__file__).parent.parent / "convert.py"
SAMPLES_DIR = Path(__file__).parent / "samples"
EXPECTED_DIR = Path(__file__).parent / "expected"

def run_conversion(input_path: Path, output_path: Path):
    """Runs the convert.py script on a single file."""
    cmd = [
        sys.executable,
        str(CONVERT_SCRIPT),
        str(input_path),
        "--output", str(output_path),
        "--no-nlp"  # Use regex parser to be deterministic in tests
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Conversion failed for {input_path}\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"

def get_samples():
    """Finds all non-hidden files in the samples directory."""
    if not SAMPLES_DIR.exists():
        return []
    return [p for p in SAMPLES_DIR.iterdir() if p.is_file() and not p.name.startswith('.')]

@pytest.mark.parametrize("sample_path", get_samples(), ids=lambda p: p.name)
def test_regression(sample_path: Path, tmp_path: Path):
    """Test that conversion output matches expected JSON."""
    expected_path = EXPECTED_DIR / f"{sample_path.name}.json"

    if not expected_path.exists():
        pytest.fail(f"Expected output file not found: {expected_path}. Run with --generate-expected if implementing a new test.")

    actual_path = tmp_path / "actual.json"
    run_conversion(sample_path, actual_path)

    with open(expected_path, "r") as f:
        expected_json = json.load(f)

    with open(actual_path, "r") as f:
        actual_json = json.load(f)

    # Normalize dates and comments for comparison if they contain timestamps or absolute paths
    # (Though we try to keep them consistent in the converter)
    for recipe in actual_json:
        if "datePublished" in recipe:
            recipe["datePublished"] = "NORMALIZED_DATE"
        if "comment" in recipe:
             # Strip absolute paths from comments if they exist
             recipe["comment"] = "Imported from " + Path(recipe["comment"].split("Imported from ")[-1]).name
        if "url" in recipe:
             recipe["url"] = "file://" + Path(recipe["url"].replace("file://", "")).name

    for recipe in expected_json:
        if "datePublished" in recipe:
            recipe["datePublished"] = "NORMALIZED_DATE"
        if "comment" in recipe:
             recipe["comment"] = "Imported from " + Path(recipe["comment"].split("Imported from ")[-1]).name
        if "url" in recipe:
             recipe["url"] = "file://" + Path(recipe["url"].replace("file://", "")).name

    assert actual_json == expected_json
