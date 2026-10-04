# SPDX-License-Identifier: MIT
"""Unit tests for From Scratch parser."""
from pathlib import Path
import pytest
from parsers.fromscratch import FromScratchParser
from parsers.ingredients import RegexIngredientParser
from parsers.registry import ParserRegistry


@pytest.fixture
def parser():
    return FromScratchParser(ingredient_parser=RegexIngredientParser())


def test_registry_registration():
    """Verify FromScratchParser is registered with ParserRegistry."""
    format_ids = [p.format_id() for p in ParserRegistry._parsers]
    assert "fromscratch" in format_ids
    assert FromScratchParser.format_id() == "fromscratch"
    assert FromScratchParser.priority() == 10
    assert {".fs", ".fsx", ".txt"}.issubset(FromScratchParser.supported_extensions())

    p = ParserRegistry.get_parser(Path("dummy.fs"), RegexIngredientParser(), format_name="fromscratch")
    assert isinstance(p, FromScratchParser)


def test_detect_header():
    """Verify detection score 0.99 when FROM SCRATCH header is present."""
    sample_v2 = "********** FROM SCRATCH V 2.0  RECIPE BEGINS ********\n\nTitle    :Amy's Cornbread\n"
    assert FromScratchParser.detect("test.txt", sample_v2) == 0.99

    sample_no_ver = "********** FROM SCRATCH RECIPE BEGINS ********\n\nTitle    :Simple Cake\n"
    assert FromScratchParser.detect("test.txt", sample_no_ver) == 0.99


def test_detect_extension_fallback():
    """Verify detection score 0.85 when extension in {.fs, .fsx} and Title: is present."""
    sample = "Title    :Secret Recipe\nServes   :4\n"
    assert FromScratchParser.detect("my_recipe.fs", sample) == 0.85
    assert FromScratchParser.detect("my_recipe.FS", sample) == 0.85
    assert FromScratchParser.detect("my_recipe.fsx", sample) == 0.85
    assert FromScratchParser.detect("my_recipe.FSX", sample) == 0.85
    # Without Title:
    assert FromScratchParser.detect("my_recipe.fs", "Random text without title") == 0.0
    # Other extension without header
    assert FromScratchParser.detect("my_recipe.txt", sample) == 0.0


def test_detect_negative():
    """Verify detection returns 0.0 for unrelated formats or empty samples."""
    assert FromScratchParser.detect("test.fs", "") == 0.0
    assert FromScratchParser.detect("test.txt", "") == 0.0
    assert FromScratchParser.detect("test.txt", "Some random text without tags\n") == 0.0
    assert FromScratchParser.detect("test.mmf", "MMMMM----- Recipe via Meal-Master\n") == 0.0


def test_field_mapping(parser):
    """Verify complete field mapping for single recipe."""
    content = """********** FROM SCRATCH V 2.0  RECIPE BEGINS ********

Title    :Amy's Cornbread
Serves   :4
KeyWords :Breads Quick-Breads
Minutes  :35
Origin   :Grandma's Kitchen
Calories :
Protein  :
Oven Temp:
Ingredients:
  1.00     pkg.         Frozen broccoli
  2.00     cup          Grated cheddar sharp cheese
  1.00     ea.         Med. onion
  1.00     ea.         Box jiffy cornbread mix

Instructions:
Bake in glass pan for 25-30 minutes at 400 degree.

Allow to cool before slicing.

Notes:
Serve warm with soup or chili.
********** RECIPE ENDS ********
"""
    recipes = list(parser.parse_content(content, "sample.fs"))
    assert len(recipes) == 1
    r = recipes[0]

    assert r.title == "Amy's Cornbread"
    assert r.yield_amount == "4"
    assert r.categories == ["Breads", "Quick-Breads"]
    assert "Grandma's Kitchen" in (r.description or "")
    assert "35" in (r.description or "")
    assert "Serve warm with soup or chili." in (r.description or "")
    assert r.source_format == "From Scratch"

    assert len(r.ingredients) == 4
    assert r.ingredients[0].name == "Frozen broccoli"
    assert r.ingredients[0].quantity == "1.00"
    assert r.ingredients[0].unit == "package"

    assert r.ingredients[1].name == "Grated cheddar sharp cheese"
    assert r.ingredients[1].quantity == "2.00"
    assert r.ingredients[1].unit == "cup"

    assert r.ingredients[2].name == "Med. onion"
    assert r.ingredients[2].quantity == "1.00"
    assert r.ingredients[2].unit == "ea."

    assert r.ingredients[3].name == "Box jiffy cornbread mix"
    assert r.ingredients[3].quantity == "1.00"
    assert r.ingredients[3].unit == "ea."

    assert len(r.instructions) == 2
    assert r.instructions[0] == "Bake in glass pan for 25-30 minutes at 400 degree."
    assert r.instructions[1] == "Allow to cool before slicing."


def test_keywords_comma_separated(parser):
    """Verify keywords split on commas as well as spaces."""
    content = """********** FROM SCRATCH V 2.0  RECIPE BEGINS ********
Title    :Berry Pie
KeyWords :Desserts, Pies, Summer
Ingredients:
  1.00     cup          Berries
Instructions:
Bake pie.
********** RECIPE ENDS ********
"""
    recipes = list(parser.parse_content(content, "pie.fs"))
    assert len(recipes) == 1
    assert recipes[0].categories == ["Desserts", "Pies", "Summer"]


def test_multi_recipe_parsing(parser):
    """Verify multi-recipe parsing with delimiter splits."""
    content = """********** FROM SCRATCH V 2.0  RECIPE BEGINS ********

Title    :First Recipe
Serves   :2
KeyWords :Appetizers
Ingredients:
  1.00     c          Flour
Instructions:
Mix well.
Notes:
********** RECIPE ENDS ********
********** FROM SCRATCH V 2.0  RECIPE BEGINS ********

Title    :Second Recipe
Serves   :4
KeyWords :Desserts
Ingredients:
  2.00     c          Sugar
Instructions:
Sprinkle sugar.
Notes:
********** RECIPE ENDS ********
"""
    recipes = list(parser.parse_content(content, "multi.fs"))
    assert len(recipes) == 2
    assert recipes[0].title == "First Recipe"
    assert recipes[0].categories == ["Appetizers"]
    assert recipes[0].yield_amount == "2"
    assert recipes[0].ingredients[0].name == "Flour"
    assert recipes[0].instructions == ["Mix well."]

    assert recipes[1].title == "Second Recipe"
    assert recipes[1].categories == ["Desserts"]
    assert recipes[1].yield_amount == "4"
    assert recipes[1].ingredients[0].name == "Sugar"
    assert recipes[1].instructions == ["Sprinkle sugar."]


def test_parse_archive_if_available(parser):
    """Verify parsing against real-world 95-recipe archive if present."""
    candidates = [
        Path("/home/alex/junk/Recipes/Ingest/ToDo/TXT/BONUSREC.FS"),
        Path("/home/alex/junk/Recipes/Ingest/ToDo/TXT/BONUSREC.FSX"),
    ]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        pytest.skip("BONUSREC archives not found in test environment")

    for archive_path in existing:
        recipes = list(parser.parse_file(str(archive_path)))
        assert len(recipes) == 95, f"Expected 95 recipes from {archive_path}, got {len(recipes)}"
        assert recipes[0].title == "Amy's Cornbread"
        assert recipes[1].title == "Apple Cobbler"
        assert recipes[-1].title == "Zucchini Casserole"
        # All recipes must have a non-empty title
        assert all(r.title for r in recipes)
        # Verify detection score on actual file content
        sample = archive_path.read_text(encoding="latin-1")[:1000]
        assert parser.detect(str(archive_path), sample) == 0.99
