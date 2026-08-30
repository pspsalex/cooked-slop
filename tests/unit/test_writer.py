# SPDX-License-Identifier: MIT
"""Unit tests for JSONStreamWriter."""
import json
from pathlib import Path
import pytest
from writer import JSONStreamWriter


def test_writer_empty_flush_creates_valid_empty_json(tmp_path: Path):
    """Closing a writer with zero recipes without chunking writes valid JSON []."""
    out_file = tmp_path / "empty.json"
    writer = JSONStreamWriter(base_output_path=out_file, chunk=False)
    writer.close()

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    data = json.loads(content)
    assert data == []


def test_writer_single_recipe(tmp_path: Path):
    """Writing a single recipe produces a valid JSON array with 1 object."""
    out_file = tmp_path / "single.json"
    writer = JSONStreamWriter(base_output_path=out_file, chunk=False)
    recipe = {"name": "Chocolate Chip Cookies", "yield": "24"}
    writer.write_recipe(recipe)
    writer.close()

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data == [recipe]


def test_writer_multiple_recipes_formatting(tmp_path: Path):
    """Writing multiple recipes produces a valid JSON array with properly placed commas."""
    out_file = tmp_path / "multi.json"
    writer = JSONStreamWriter(base_output_path=out_file, chunk=False)
    recipes = [{"name": f"Recipe {i}", "step": i} for i in range(1, 4)]
    for r in recipes:
        writer.write_recipe(r)
    writer.close()

    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert len(data) == 3
    assert data == recipes


def test_writer_chunking_by_count(tmp_path: Path):
    """Verify max_recipes_per_chunk=2 with 5 recipes produces 3 valid chunk files."""
    base_file = tmp_path / "chunked.json"
    writer = JSONStreamWriter(
        base_output_path=base_file,
        chunk=True,
        max_recipes_per_chunk=2,
    )
    recipes = [{"name": f"Recipe {i}"} for i in range(5)]
    for r in recipes:
        writer.write_recipe(r)
    writer.close()

    part1 = tmp_path / "chunked_part001.json"
    part2 = tmp_path / "chunked_part002.json"
    part3 = tmp_path / "chunked_part003.json"
    part4 = tmp_path / "chunked_part004.json"

    assert part1.exists()
    assert part2.exists()
    assert part3.exists()
    assert not part4.exists()

    data1 = json.loads(part1.read_text(encoding="utf-8"))
    data2 = json.loads(part2.read_text(encoding="utf-8"))
    data3 = json.loads(part3.read_text(encoding="utf-8"))

    assert len(data1) == 2
    assert len(data2) == 2
    assert len(data3) == 1

    assert data1 == recipes[0:2]
    assert data2 == recipes[2:4]
    assert data3 == recipes[4:5]


def test_writer_chunking_by_byte_size(tmp_path: Path):
    """Verify chunk rotation occurs when serialized byte limit is exceeded."""
    base_file = tmp_path / "size_chunked.json"
    # Set a tiny byte limit so each large recipe triggers rotation
    writer = JSONStreamWriter(
        base_output_path=base_file,
        chunk=True,
        max_recipes_per_chunk=1000,
        max_chunk_size_bytes=150,
    )
    r1 = {"name": "Long Recipe 1", "description": "X" * 120}
    r2 = {"name": "Long Recipe 2", "description": "Y" * 120}
    r3 = {"name": "Long Recipe 3", "description": "Z" * 120}

    writer.write_recipe(r1)
    writer.write_recipe(r2)
    writer.write_recipe(r3)
    writer.close()

    part1 = tmp_path / "size_chunked_part001.json"
    part2 = tmp_path / "size_chunked_part002.json"
    part3 = tmp_path / "size_chunked_part003.json"

    assert part1.exists()
    assert part2.exists()
    assert part3.exists()

    assert json.loads(part1.read_text(encoding="utf-8")) == [r1]
    assert json.loads(part2.read_text(encoding="utf-8")) == [r2]
    assert json.loads(part3.read_text(encoding="utf-8")) == [r3]


def test_writer_unicode_preservation(tmp_path: Path):
    """Verify non-ASCII characters are preserved without escaping (ensure_ascii=False)."""
    out_file = tmp_path / "unicode.json"
    writer = JSONStreamWriter(base_output_path=out_file, chunk=False)
    recipe = {
        "name": "Crème Brûlée",
        "ingredients": ["½ tsp vanilla bean", "1 shot café espresso", "100g sucre raffiné"],
        "emoji": "🍳",
    }
    writer.write_recipe(recipe)
    writer.close()

    raw_text = out_file.read_text(encoding="utf-8")
    # Non-ASCII characters must be stored directly, not escaped as \uXXXX
    assert "Crème Brûlée" in raw_text
    assert "½ tsp vanilla bean" in raw_text
    assert "café" in raw_text
    assert "🍳" in raw_text
    assert "\\u00" not in raw_text

    data = json.loads(raw_text)
    assert data[0] == recipe


def test_writer_exact_chunk_boundary_no_empty_file(tmp_path: Path):
    """Writing exactly max_recipes_per_chunk recipes should not create an extra empty chunk."""
    base_file = tmp_path / "boundary.json"
    writer = JSONStreamWriter(
        base_output_path=base_file,
        chunk=True,
        max_recipes_per_chunk=2,
    )
    writer.write_recipe({"name": "Recipe 1"})
    writer.write_recipe({"name": "Recipe 2"})
    writer.close()

    part1 = tmp_path / "boundary_part001.json"
    part2 = tmp_path / "boundary_part002.json"

    assert part1.exists()
    assert not part2.exists()
    assert len(json.loads(part1.read_text(encoding="utf-8"))) == 2
