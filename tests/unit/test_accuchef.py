# SPDX-License-Identifier: MIT
"""Unit tests for AccuChef parser."""
from pathlib import Path
import pytest
from parsers.accuchef import AccuChefParser
from parsers.ingredients import RegexIngredientParser
from parsers.registry import ParserRegistry


@pytest.fixture
def parser():
    return AccuChefParser(ingredient_parser=RegexIngredientParser())


def test_registry_registration():
    """Verify AccuChefParser is registered with ParserRegistry."""
    format_ids = [p.format_id() for p in ParserRegistry._parsers]
    assert "accuchef" in format_ids
    assert AccuChefParser.format_id() == "accuchef"
    assert AccuChefParser.priority() == 15
    assert ".out" in AccuChefParser.supported_extensions()

    p = ParserRegistry.get_parser(Path("dummy.out"), RegexIngredientParser(), format_name="accuchef")
    assert isinstance(p, AccuChefParser)



def test_detect_header():
    """Verify detection score 0.99 when *****AccuChef header is present."""
    sample = "*****AccuChef V5.0 Import File (C)SIVART Software\nAA Some Recipe\n"
    assert AccuChefParser.detect("test.out", sample) == 0.99


def test_detect_structural_tags():
    """Verify detection score 0.85 when AA title and secondary tags are present without header."""
    sample = "AA Thai Green Curry\nBMain Dishes\nD4\nMServings\n"
    assert AccuChefParser.detect("test.txt", sample) == 0.85

    sample_yield = "AA Thai Green Curry\nD4\nMServings\n"
    assert AccuChefParser.detect("test.txt", sample_yield) == 0.85


def test_detect_negative():
    """Verify detection returns 0.0 for unrelated formats or empty samples."""
    assert AccuChefParser.detect("test.txt", "") == 0.0
    assert AccuChefParser.detect("test.txt", "Some random text without tags\n") == 0.0
    assert AccuChefParser.detect("test.mmf", "MMMMM----- Recipe via Meal-Master\n") == 0.0


def test_field_mapping(parser):
    """Verify complete field mapping for single recipe."""
    content = """*****AccuChef V5.0 Import File
AA Tom Yum Soup
BSoup, Thai
D4
MBowls
F Traditional family recipe from Chiang Mai
H1.50 Cup
IChicken broth
Kheated
H2.00 Tsp
IFish sauce
H1.00
ILime
Kjuiced
H
ISalt to taste
J1 Heat chicken broth in a saucepan.
J2 Stir in fish sauce and lime juice.
JBring to a gentle simmer.
J3 Season with salt to taste and serve hot.
Z.....End of recipe definition
"""
    recipes = list(parser.parse_content(content, "sample.out"))
    assert len(recipes) == 1
    r = recipes[0]

    assert r.title == "Tom Yum Soup"
    assert r.categories == ["Soup", "Thai"]
    assert r.yield_amount == "4 Bowls"
    assert "Traditional family recipe from Chiang Mai" in (r.description or "")

    assert len(r.ingredients) == 4
    # Ingredient 1
    assert r.ingredients[0].name == "Chicken broth"
    assert r.ingredients[0].quantity == "1.50"
    assert r.ingredients[0].unit == "cup"
    assert r.ingredients[0].comment == "heated"

    # Ingredient 2
    assert r.ingredients[1].name == "Fish sauce"
    assert r.ingredients[1].quantity == "2.00"
    assert r.ingredients[1].unit == "teaspoon"

    # Ingredient 3
    assert r.ingredients[2].name == "Lime"
    assert r.ingredients[2].quantity == "1.00"
    assert r.ingredients[2].unit is None
    assert r.ingredients[2].comment == "juiced"

    # Ingredient 4 (quantity-less)
    assert r.ingredients[3].name == "Salt to taste"
    assert r.ingredients[3].quantity is None
    assert r.ingredients[3].unit is None

    # Instructions
    assert len(r.instructions) == 3
    assert r.instructions[0] == "1 Heat chicken broth in a saucepan."
    assert r.instructions[1] == "2 Stir in fish sauce and lime juice. Bring to a gentle simmer."
    assert r.instructions[2] == "3 Season with salt to taste and serve hot."


def test_ingredient_continuation(parser):
    """Verify I- continuation lines are appended to previous ingredient."""
    content = """AA Pad Thai
H
IVegetable oil for deep
H
I-frying
H
IJuice and
KFinely Grated Zest
H
I-of 1 lime
H1.00
IPinches ground cumin
Kginger
H
I-and chilli
H2.00
IFresh red chilies
Kseeded
H
I-and
KChopped
Z.....End of recipe definition
"""
    recipes = list(parser.parse_content(content, "continuation.out"))
    assert len(recipes) == 1
    r = recipes[0]

    assert len(r.ingredients) == 4
    assert r.ingredients[0].name == "Vegetable oil for deep frying"
    assert r.ingredients[1].name == "Juice and of 1 lime"
    assert r.ingredients[1].comment == "Finely Grated Zest"
    assert r.ingredients[2].name == "Pinches ground cumin and chilli"
    assert r.ingredients[2].comment == "ginger"
    assert r.ingredients[3].name == "Fresh red chilies and"
    assert r.ingredients[3].comment == "seeded, Chopped"


def test_ingredient_section_divider_skipping(parser):
    """Verify ingredient section headers like '------------ FOR THE FILLING -----------' are ignored."""
    content = """AA Stuffed Squid
H
I------------ FOR THE FILLING -----------
H125.00 Gr
IPork mince
H1.00 Clove
IGarlic
Kminced
H
I------------ FOR THE SAUCE -----------
H2.00 Tbl
ISoy sauce
Z.....End of recipe definition
"""
    recipes = list(parser.parse_content(content, "sections.out"))
    assert len(recipes) == 1
    r = recipes[0]

    assert len(r.ingredients) == 3
    assert r.ingredients[0].name == "Pork mince"
    assert r.ingredients[0].quantity == "125.00"
    assert r.ingredients[0].unit == "gr"
    assert r.ingredients[1].name == "Garlic"
    assert r.ingredients[2].name == "Soy sauce"


def test_multi_recipe_parsing(parser):
    """Verify multi-recipe parsing with Z terminators."""
    content = """*****AccuChef V5.0 Import File
AA First Recipe
BAppetizers
D2
MServings
H1.00 Cup
IFlour
J1 Mix flour with water.
Z.....End of recipe definition
AA Second Recipe
BDesserts
D4
MServings
H2.00 Cup
ISugar
J1 Sprinkle sugar on top.
Z.....End of recipe definition
"""
    recipes = list(parser.parse_content(content, "multi.out"))
    assert len(recipes) == 2
    assert recipes[0].title == "First Recipe"
    assert recipes[0].categories == ["Appetizers"]
    assert recipes[0].yield_amount == "2 Servings"
    assert recipes[0].ingredients[0].name == "Flour"

    assert recipes[1].title == "Second Recipe"
    assert recipes[1].categories == ["Desserts"]
    assert recipes[1].yield_amount == "4 Servings"
    assert recipes[1].ingredients[0].name == "Sugar"


def test_parse_archive_if_available(parser):
    """Verify parsing against real-world 544 recipe archive if present."""
    candidates = [
        Path("/home/alex/junk/Recipes/scripts/nux/Test/TXT/thai-converted-mmf.out"),
        Path("/home/alex/junk/Recipes/Ingest/ToDo/TXT/thai-converted-mmf.out"),
    ]
    archive_path = next((p for p in candidates if p.exists()), None)
    if not archive_path:
        pytest.skip("thai-converted-mmf.out archive not found in test environment")

    recipes = list(parser.parse_file(str(archive_path)))
    assert len(recipes) == 544
    assert recipes[0].title == "Shellfish Thai Wouldn't Share This With Anyone"
    assert recipes[1].title == "Taste Of Thailand"
    assert recipes[-1].title == "Young Thailand Lemon Grass-Shrimp Soup"
