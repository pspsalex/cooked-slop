# SPDX-License-Identifier: MIT
"""Unit tests for Info-Mac BBS recipe parser (SPEC-011)."""

from pathlib import Path
import pytest

from parsers.infomac import InfoMacParser
from parsers.ingredients import RegexIngredientParser
from parsers.registry import ParserRegistry


@pytest.fixture
def parser():
    return InfoMacParser(ingredient_parser=RegexIngredientParser())


def test_registry_registration():
    """Verify InfoMacParser is registered correctly in ParserRegistry."""
    format_ids = [p.format_id() for p in ParserRegistry._parsers]
    assert "infomac" in format_ids
    assert InfoMacParser.format_id() == "infomac"
    assert InfoMacParser.priority() == 10
    assert ".inf" in InfoMacParser.supported_extensions()
    assert ".txt" in InfoMacParser.supported_extensions()

    p = ParserRegistry.get_parser(Path("dummy.inf"), RegexIngredientParser(), format_name="infomac")
    assert isinstance(p, InfoMacParser)


def test_detect_header_and_title():
    """Verify detection score 0.95 when '%' header and backtick title are present."""
    sample = "%\n`AMANDA COCKERELL'S CORN PONE\nCorn meal\n-\nMix well.\n"
    assert InfoMacParser.detect("dummy.txt", sample) == 0.95
    assert InfoMacParser.detect("dummy.inf", sample) == 0.95


def test_detect_inf_extension_with_title():
    """Verify detection score 0.85 when .inf extension and backtick title are present without '%' header."""
    sample = "`SOME RECIPE\n1 cup flour\n-\nBake at 350.\n"
    assert InfoMacParser.detect("recipe.inf", sample) == 0.85


def test_detect_negative():
    """Verify detection returns 0.0 for unrelated formats or empty samples."""
    assert InfoMacParser.detect("dummy.inf", "") == 0.0
    assert InfoMacParser.detect("dummy.txt", "Some regular text\n") == 0.0
    assert InfoMacParser.detect("dummy.txt", "%\nNo backtick here\n") == 0.0
    assert InfoMacParser.detect("dummy.out", "*****AccuChef V5.0 Import File\n") == 0.0


def test_field_mapping(parser):
    """Verify field mapping for title, categories, yield, ingredients, instructions, and description."""
    content = """%
`SWEET CORN BREAD

Categories: Breads, Quick Breads
Makes 8 Servings
1 cup cornmeal
1 cup flour
2 Tbsp sugar
1 tsp salt
1 egg
1 cup milk
-
Preheat oven to 400 degrees.
Grease an 8-inch square pan.

Mix dry ingredients. Add egg and milk.
Bake for 20 minutes until golden brown.

From: Jane Baker
~
"""
    recipes = list(parser.parse_content(content, "test.inf"))
    assert len(recipes) == 1
    r = recipes[0]

    assert r.title == "SWEET CORN BREAD"
    assert r.categories == ["Breads", "Quick Breads"]
    assert r.yield_amount == "8 Servings"
    assert r.description == "From: Jane Baker"
    assert r.source_format == "Info-Mac"

    assert len(r.ingredients) == 6
    assert r.ingredients[0].name == "cornmeal"
    assert r.ingredients[0].quantity == "1"
    assert r.ingredients[0].unit == "cup"

    assert len(r.instructions) == 2
    assert "Preheat oven to 400 degrees." in r.instructions[0]
    assert "Bake for 20 minutes" in r.instructions[1]


def test_two_column_ingredients(parser):
    """Verify two-column ingredient layouts are split into separate ingredients."""
    content = """`BACONY CORN BREAD

  1 8oz package of bacon slices        2 C all purpose flour
  1 1/2 C cornmeal                     1/4 sugar
  2 Tbsp double acting baking powder   1 tsp salt
-
Mix and bake.
~
"""
    recipes = list(parser.parse_content(content, "two_col.inf"))
    assert len(recipes) == 1
    r = recipes[0]
    assert len(r.ingredients) == 6
    names = [ing.name for ing in r.ingredients]
    assert "all purpose flour" in names
    assert "cornmeal" in names
    assert "salt" in names


def test_stray_artifact_and_yield_in_instructions(parser):
    """Verify stray artifact line right after title is skipped and yield in instructions is extracted."""
    content = """`CORNBREAD STICKS
a
1/3 c. cornmeal
1/2 c. flour
-
Bake at 425 for 20 minutes.
Makes 12 sticks.

Jody Diehl
~
"""
    recipes = list(parser.parse_content(content, "artifact.inf"))
    assert len(recipes) == 1
    r = recipes[0]
    assert r.title == "CORNBREAD STICKS"
    assert len(r.ingredients) == 2
    assert all(ing.raw != "a" for ing in r.ingredients)
    assert r.yield_amount == "12 sticks"


def test_multi_recipe_extraction(parser):
    """Verify multi-recipe splitting with and without trailing tildes."""
    content = """%
`RECIPE ONE
1 cup flour
-
Mix and bake.
~
`RECIPE TWO
2 cups water
-
Boil water.
`RECIPE THREE
3 eggs
-
Scramble eggs.
~
"""
    recipes = list(parser.parse_content(content, "multi.inf"))
    assert len(recipes) == 3
    assert [r.title for r in recipes] == ["RECIPE ONE", "RECIPE TWO", "RECIPE THREE"]


def test_archive_files_if_available(parser):
    """Verify parsing real archive files if present on disk."""
    archive_dir = Path("/home/alex/junk/Recipes/Ingest/ToDo/TXT")
    expected_counts = {
        "CORNBRE.INF": 27,
        "DUCK.INF": 9,
        "SALAD.INF": 55,
        "SAVORY.INF": 17,
        "STEAK.INF": 12,
    }

    for filename, count in expected_counts.items():
        archive_file = archive_dir / filename
        if archive_file.exists():
            content = archive_file.read_text(encoding="latin-1")
            recipes = list(parser.parse_content(content, str(archive_file)))
            assert len(recipes) == count, f"Expected {count} recipes in {filename}, got {len(recipes)}"
            for r in recipes:
                assert r.title, f"Recipe in {filename} must have a title"
                assert r.source_format == "Info-Mac"
