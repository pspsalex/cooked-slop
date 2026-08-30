# SPDX-License-Identifier: MIT
import csv
import json
from pathlib import Path

import pytest
from batch_convert import is_skipped, run_batch_conversion, main as batch_main

SAMPLES_DIR = Path(__file__).parent / "samples"


def test_is_skipped():
    """Verify skip list rules (strictly extension-based)."""
    # Excluded extensions
    assert is_skipped(Path("foo/bar.jpg"))
    assert is_skipped(Path("foo/bar.JPEG"))
    assert is_skipped(Path("foo/bar.png"))
    assert is_skipped(Path("foo/bar.gif"))
    assert is_skipped(Path("foo/bar.bmp"))
    assert is_skipped(Path("foo/bar.mht"))
    assert is_skipped(Path("foo/bar.json"))
    assert is_skipped(Path("out.json"))

    # Processable extensions
    assert not is_skipped(Path("recipe.txt"))
    assert not is_skipped(Path("recipe.html"))
    assert not is_skipped(Path("recipe.mmf"))
    assert not is_skipped(Path("recipe.mxp"))
    assert not is_skipped(Path("recipe.csv"))
    assert not is_skipped(Path("recipe.xml"))
    assert not is_skipped(Path("recipe.md"))


def test_dry_run(capsys):
    """Test --dry-run functionality."""
    ret = batch_main(["--dir", str(SAMPLES_DIR), "--dry-run"])
    assert ret == 0

    captured = capsys.readouterr().out
    assert "Total files:" in captured
    assert "Skipped:" in captured
    assert "Success (≥1 recipe): 0" in captured


def test_batch_conversion_on_samples(tmp_path: Path):
    """Test converting sample files in tests/samples/."""
    out_dir = tmp_path / "batch_out"
    csv_path = tmp_path / "batch_results.csv"

    ret = run_batch_conversion(
        input_dir=SAMPLES_DIR,
        output_dir=out_dir,
        csv_path=csv_path,
        workers=2,
        dry_run=False,
    )
    assert ret == 0
    assert csv_path.exists()

    # Verify CSV structure
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["file", "parser", "recipes_extracted", "status", "error"]

        rows = list(reader)
        assert len(rows) > 0

        # Verify at least some files succeeded (status == ok)
        ok_rows = [r for r in rows if r[3] == "ok"]
        assert len(ok_rows) >= 5, f"Expected at least 5 successful sample conversions, got {len(ok_rows)}"


def test_resume_flag(tmp_path: Path):
    """Test --resume flag reuses pre-existing JSON output files."""
    out_dir = tmp_path / "batch_out"
    csv_path = tmp_path / "batch_results.csv"

    # Pre-create a dummy JSON file for GERMAN.MMF
    target_json = out_dir / "GERMAN.json"
    target_json.parent.mkdir(parents=True, exist_ok=True)
    dummy_data = [{"@type": "Recipe", "name": "Dummy Recipe"}]
    with open(target_json, "w", encoding="utf-8") as f:
        json.dump(dummy_data, f)

    ret = run_batch_conversion(
        input_dir=SAMPLES_DIR,
        output_dir=out_dir,
        csv_path=csv_path,
        workers=2,
        resume=True,
    )
    assert ret == 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        rows = {r[0]: r for r in reader}

    assert "GERMAN.MMF" in rows
    assert rows["GERMAN.MMF"][2] == "1"  # recipes_extracted = 1 from dummy
    assert rows["GERMAN.MMF"][3] == "ok"


def test_timeout_cli(tmp_path: Path):
    """Test --timeout CLI argument is accepted and passed through."""
    out_dir = tmp_path / "batch_out"
    csv_path = tmp_path / "batch_results.csv"

    ret = batch_main([
        "--dir", str(SAMPLES_DIR),
        "--output-dir", str(out_dir),
        "--csv", str(csv_path),
        "--timeout", "5",
        "-w", "2",
    ])
    assert ret == 0
    assert csv_path.exists()

