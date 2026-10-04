# SPDX-License-Identifier: MIT
"""Unit tests for convert.py directory batch processing and multiprocessing."""

import json
from pathlib import Path
from convert import main as convert_main

SAMPLES_DIR = Path(__file__).parent / "samples"


def test_directory_conversion_to_single_json(tmp_path: Path):
    """Test convert.py on a directory streaming to a single output JSON file."""
    out_json = tmp_path / "all_recipes.json"

    ret = convert_main([
        str(SAMPLES_DIR),
        "-o", str(out_json),
        "--no-nlp",
        "-w", "2",
    ])
    assert ret == 0
    assert out_json.exists()

    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) >= 10, f"Expected at least 10 recipes in sample stream, got {len(data)}"
    # Verify standard schema.org structure
    for recipe in data:
        assert recipe.get("@context") == "https://schema.org"
        assert recipe.get("@type") == "Recipe"
        assert "name" in recipe


def test_directory_conversion_to_output_dir(tmp_path: Path):
    """Test convert.py on a directory writing individual JSON files to output directory."""
    out_dir = tmp_path / "recipe_files"

    ret = convert_main([
        str(SAMPLES_DIR),
        "-o", str(out_dir),
        "--no-nlp",
        "-w", "2",
    ])
    assert ret == 0
    assert out_dir.exists()
    json_files = list(out_dir.glob("*.json"))
    assert len(json_files) >= 10, f"Expected at least 10 recipe files in output dir, got {len(json_files)}"


def test_no_recursive_flag(tmp_path: Path):
    """Test --no-recursive only processes top-level files."""
    in_dir = tmp_path / "in"
    sub_dir = in_dir / "sub"
    in_dir.mkdir()
    sub_dir.mkdir()

    (in_dir / "top.txt").write_text("Title: Top Recipe\nIngredients:\n1 cup flour\nInstructions:\nBake it.\n", encoding="utf-8")
    (sub_dir / "sub.txt").write_text("Title: Sub Recipe\nIngredients:\n1 cup sugar\nInstructions:\nMix it.\n", encoding="utf-8")

    out_json = tmp_path / "top_only.json"
    ret = convert_main([
        str(in_dir),
        "-o", str(out_json),
        "--no-nlp",
        "--no-recursive",
        "-w", "1",
    ])
    assert ret == 0
    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    names = [r.get("name") for r in data]
    assert any("Top Recipe" in n for n in names)
    assert not any("Sub Recipe" in n for n in names)
