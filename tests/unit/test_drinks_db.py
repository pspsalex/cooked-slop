# SPDX-License-Identifier: MIT
"""Unit tests for Mr. Boston Drinks Database parser."""
from pathlib import Path
import pytest

from parsers.drinks_db import DrinksDbParser
from parsers.ingredients import RegexIngredientParser
from parsers.registry import ParserRegistry


@pytest.fixture
def parser():
    return DrinksDbParser(ingredient_parser=RegexIngredientParser())


def test_registry_registration():
    """Verify DrinksDbParser is registered with ParserRegistry."""
    format_ids = [p.format_id() for p in ParserRegistry._parsers]
    assert "drinks_db" in format_ids
    assert DrinksDbParser.format_id() == "drinks_db"
    assert DrinksDbParser.priority() == 8
    assert {".out", ".lst", ".txt"}.issubset(DrinksDbParser.supported_extensions())

    p = ParserRegistry.get_parser(Path("dummy.out"), RegexIngredientParser(), format_name="drinks_db")
    assert isinstance(p, DrinksDbParser)


def test_detection():
    """Verify detection scoring logic."""
    content_out = (
        "SAMPLE DRINK                    RUM            \n"
        "Drink type: Cocktail \n"
        "Season(s): Summer \n"
    )
    assert DrinksDbParser.detect("drinks.out", content_out) == 0.95
    assert DrinksDbParser.detect("DRINKS.OUT", content_out) == 0.95

    content_full = (
        "SAMPLE DRINK                    RUM            \n"
        "Drink type: Cocktail \n"
        "Temp: Cold \n"
        "Serve at: Evening \n"
        "Season(s): Summer \n"
    )
    assert DrinksDbParser.detect("drinks.txt", content_full) == 0.85
    assert DrinksDbParser.detect("drinks.lst", content_full) == 0.85

    # Negative detection
    assert DrinksDbParser.detect("drinks.out", "") == 0.0
    assert DrinksDbParser.detect("drinks.txt", "Random text without keys") == 0.0
    assert DrinksDbParser.detect("drinks.txt", "Drink type: Cocktail \n") == 0.0


def test_sample_file_field_mapping(parser):
    """Verify field mapping against sample fixture."""
    sample_path = Path("tests/samples/drinks.out")
    recipes = list(parser.parse_file(str(sample_path)))

    assert len(recipes) == 10

    # Recipe 0: Frozen Pineapple Daiquiri
    r0 = recipes[0]
    assert r0.title == "Frozen Pineapple Daiquiri"
    assert r0.categories == ["Rum", "Blender Cocktail"]
    assert r0.yield_amount == "1 drink"
    assert r0.source_format == "Mr. Boston Bartending Guide"
    assert r0.description == (
        "Temp: Cold Frozen | Serve at: Lunch Cocktails Party | "
        "Season(s): Spring Summer Fall | Glassware: 1 CHAMPAGNE GLASS"
    )
    # Glassware must be excluded from ingredients
    assert len(r0.ingredients) == 4
    raw_ings = [ing.raw for ing in r0.ingredients]
    assert not any("GLASS" in raw for raw in raw_ings)
    assert r0.instructions == [
        "Combine all ingredients with a cup of crushed ice in a blender. Blend at low speed and pour into champagne glass."
    ]


def test_multi_column_wrapped_ingredients(parser):
    """Verify multi-column continuation ingredients are properly merged."""
    sample_path = Path("tests/samples/drinks.out")
    recipes = list(parser.parse_file(str(sample_path)))

    # Recipe 1: Alexander Cocktail #One (CREME DE CACAO, + (WHITE))
    r1 = recipes[1]
    raw_ings_1 = [ing.raw for ing in r1.ingredients]
    assert "1 OZ. MR. BOSTON CREME DE CACAO, (WHITE)" in raw_ings_1
    assert "NUTMEG" in raw_ings_1
    assert len(r1.ingredients) == 4

    # Recipe 5: Black Russian (COFFEE FLAVORED + BRANDY)
    r5 = recipes[5]
    raw_ings_5 = [ing.raw for ing in r5.ingredients]
    assert "3/4 OZ. MR. BOSTON COFFEE FLAVORED BRANDY" in raw_ings_5
    assert len(r5.ingredients) == 2

    # Recipe 6: Bloody Mary (2 OR + 3 DROPS TABASCO SAUCE)
    r6 = recipes[6]
    raw_ings_6 = [ing.raw for ing in r6.ingredients]
    assert "2 OR 3 DROPS TABASCO SAUCE" in raw_ings_6
    assert len(r6.ingredients) == 6


def test_glassware_identification(parser):
    """Verify glassware detection and exclusion across sample recipes."""
    sample_path = Path("tests/samples/drinks.out")
    recipes = list(parser.parse_file(str(sample_path)))

    expected_glassware = [
        "1 CHAMPAGNE GLASS",
        "1 COCKTAIL GLASS",
        "1 COCKTAIL GLASS",
        "1 CHAMPAGNE GLASS",
        "1 COCKTAIL GLASS",
        "1 OLD-FASHIONED COCKTAIL GLASS",
        "1 OLD-FASHIONED GLASS",
        "1 COCKTAIL GLASS",
        "1 SOUR GLASS",
        "1 OLD-FASHIONED GLASS",
    ]

    for recipe, glass in zip(recipes, expected_glassware):
        assert f"Glassware: {glass}" in (recipe.description or "")
        # None of the ingredients should be the glassware entry
        for ing in recipe.ingredients:
            assert ing.raw != glass


def test_full_archive_parsing(parser):
    """Verify complete parsing of all 992 recipes from DRINKS.OUT archive."""
    archive_path = Path("/home/alex/junk/Recipes/Ingest/ToDo/TXT/DRINKS.OUT")
    if not archive_path.exists():
        pytest.skip(f"Archive file not found: {archive_path}")

    # Detection score on full archive
    with open(archive_path, "r", encoding="latin1") as f:
        content_sample = f.read(2048)
    assert DrinksDbParser.detect(str(archive_path), content_sample) >= 0.85

    recipes = list(parser.parse_file(str(archive_path)))
    assert len(recipes) == 992

    for r in recipes:
        assert r.title, "Recipe must have non-empty title"
        assert r.yield_amount == "1 drink"
        assert len(r.ingredients) >= 1, f"Recipe {r.title} has no ingredients"
        assert len(r.instructions) >= 1, f"Recipe {r.title} has no instructions"
        assert r.source_format == "Mr. Boston Bartending Guide"
