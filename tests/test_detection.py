# SPDX-License-Identifier: MIT
import pytest
from pathlib import Path
from parsers.base import get_context_window
from parsers.mastercook import MasterCookParser
from parsers.mealmaster import MealMasterParser
from parsers.compuchef import CompuChefParser
from parsers.nyc import NYCParser
from parsers.id_caps import IdCapsParser
from parsers.mixed import MixedFormatParser
from parsers import get_ingredient_parser


@pytest.fixture
def ingredient_parser():
    return get_ingredient_parser(use_nlp=False)


def test_get_context_window():
    lines = [f"line {i}" for i in range(30)]
    window = get_context_window(lines, 0, 15)
    window_lines = window.splitlines()
    assert len(window_lines) == 15
    assert window_lines[0] == "line 0"
    assert window_lines[14] == "line 14"

    # Window near end of list
    window_end = get_context_window(lines, 25, 15)
    assert len(window_end.splitlines()) == 5


def test_mastercook_sliding_window_detection():
    # MasterCook without top banner header, but structural markers inside 15-line window
    sample = """Some preamble line here
Second preamble line

Recipe By     : Chef Alex
Serving Size  : 4
  Amount  Measure       Ingredient -- Preparation Method
--------  ------------  --------------------------------
  1            c        Sugar
  2            tb       Butter

Directions:
Mix well.
"""
    lines = sample.splitlines()
    window = get_context_window(lines, 0, 15)
    score = MasterCookParser.detect("dummy.txt", window)
    assert score >= 0.75, f"Expected score >= 0.75 for MasterCook sliding window, got {score}"


def test_mealmaster_sliding_window_detection():
    # MealMaster header on line 3 of block
    sample = """Notes about the recipe:
This is a delicious recipe.

MMMMM----- Recipe via Meal-Master (tm) v8.05

      Title: Test Cake
 Categories: Baking
      Yield: 8 Servings

      2          c  Flour
      1          c  Sugar

MMMMM
"""
    lines = sample.splitlines()
    window = get_context_window(lines, 0, 15)
    score = MealMasterParser.detect("dummy.mmf", window)
    assert score >= 0.70, f"Expected score >= 0.70 for MealMaster sliding window, got {score}"


def test_multi_recipe_dash_separators(ingredient_parser):
    content = """Recipe Title 1

Recipe By     : Chef One
Serving Size  : 4
  Amount  Measure       Ingredient -- Preparation Method
--------  ------------  --------------------------------
  1            c        Sugar
  2            tb       Butter

Directions:
Mix ingredients.

----------------------------------------

MMMMM----- Recipe via Meal-Master (tm) v8.05

      Title: MealMaster Recipe 2
 Categories: Test
      Yield: 2 Servings

      1          c  Water

MMMMM

----------------------------------------

*** CompuChef Recipe 3 ***
Categories: Test
Number of Servings: 2

INGREDIENTS --------------------------------------

   1   lb   Beef

DIRECTIONS ---------------------------------------

Cook beef.

*** Recipe Via Compu-Chef (tm) ***
"""
    parser = MixedFormatParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "multi_dash.txt"))
    assert len(recipes) == 3
    titles = [r.title for r in recipes]
    assert "MealMaster Recipe 2" in titles or any("MealMaster" in t or "2" in t for t in titles)


def test_multi_recipe_equal_separators(ingredient_parser):
    content = """* Exported from MasterCook *

MasterCook Recipe Alpha

Recipe By     : Author Alpha
Serving Size  : 4
Categories    : Test
  Amount  Measure       Ingredient -- Preparation Method
--------  ------------  --------------------------------
  1            c        Sugar

Directions:
Mix.

- - - - - - - - - - - - - - - - - - 

========================================

@@@@@ Now You're Cooking! Export Format

NYC Recipe Beta

Test

1 cup milk

Mix milk.

Yield: 2 servings

** Exported from Now You're Cooking! v5.93 **
"""
    parser = MixedFormatParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "multi_equal.txt"))
    assert len(recipes) >= 2
    titles = [r.title for r in recipes]
    assert any("Alpha" in t for t in titles)
    assert any("Beta" in t for t in titles)


def test_ingredient_unit_normalization(ingredient_parser):
    # RegexIngredientParser unit normalization
    ing1 = ingredient_parser.parse("2 Tbsp olive oil")
    assert ing1.quantity == "2"
    assert ing1.unit == "tablespoon"
    assert ing1.name == "olive oil"

    ing2 = ingredient_parser.parse("1 c sugar")
    assert ing2.quantity == "1"
    assert ing2.unit == "cup"
    assert ing2.name == "sugar"

    # Direct Ingredient instantiation unit normalization via __post_init__
    from parsers.models import Ingredient
    ing3 = Ingredient(raw="1 T sugar", quantity="1", unit="T", name="sugar")
    assert ing3.unit == "tablespoon"

    ing4 = Ingredient(raw="1 t salt", quantity="1", unit="t", name="salt")
    assert ing4.unit == "teaspoon"


def test_id_caps_detection():
    sample = """ 461559 -- DIABETIC DATE DAINTIES

 2 eggs
1/2 c. flour

 Beat eggs and flour together. Bake for 12 minutes.

------------------------
"""
    score = IdCapsParser.detect("dummy.txt", sample)
    assert score >= 0.90, f"Expected score >= 0.90 for ID Caps format, got {score}"




def test_macropolis_html_detection(ingredient_parser):
    from parsers.html_config import get_html_schema_registry
    from parsers.html_parser import HtmlParser

    sample = """<html>
<head><title>TuttoCucina</title>
<link rel="SHORTCUT ICON" href="http://www.macropolis.org/fav/magcas.ico">
</head>
<body><b>Title: Test Recipe</b><br>Categories: Test<br>Yield: 2 servings<br><br>1 c Milk<br><br>Drink milk.</body>
</html>"""
    reg = get_html_schema_registry()
    schema = reg.detect_schema(sample, "macropolis/sample.htm")
    assert schema is not None
    assert schema.name == "macropolis"

    parser = HtmlParser(ingredient_parser)
    recipes = list(parser.parse_content(sample, "macropolis/sample.htm"))
    assert len(recipes) == 1
    assert recipes[0].title == "Test Recipe"
    assert recipes[0].categories == ["Test"]
    assert recipes[0].yield_amount == "2 servings"
