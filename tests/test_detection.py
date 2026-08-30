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
    assert recipes[0].categories == ['Test']
    assert recipes[0].yield_amount == "2 servings"


def test_html_garry_howard_and_coffeeshop_detection():
    from parsers.html_config import get_html_schema_registry
    reg = get_html_schema_registry()

    cases = [
        ('mexican/salsa.shtml', "Garry's Home Cookin' mexicancooking.netrelief.com", 'mexican_recipes'),
        ('netrelief/dip.shtml', "Garry's Home Cookin' cooking.netrelief.com", 'netrelief_recipes'),
        ('netrelief/basic_all_american_bbq_sauce_recipe.shtml', "Garry's Home Cookin' cooking.netrelief.com", 'netrelief_recipes'),
        ('netrelief/garrys_green_chile_recipe.shtml', "Garry's Home Cookin' cooking.netrelief.com", 'netrelief_recipes'),
        ('netrelief/garrys_mexican_rice_recipe.shtml', "Garry's Home Cookin' cooking.netrelief.com", 'netrelief_recipes'),
        ('bbq/rub.htm', "Garry's Home Cookin' bbq.netrelief.com", 'bbq_recipes'),
        ('chile/chili.shtml', "Garry's Home Cookin' chile.netrelief.com", 'chile_recipes'),
        ('The Coffee Shop Recipe Book/000001-cool.html', 'The Coffee Shoppe RocketLibrarian', 'coffeeshop_recipes'),
    ]

    for filepath, sample_text, expected_name in cases:
        schema = reg.detect_schema(sample_text, filepath)
        assert schema is not None, f'Failed to detect schema for {filepath}'
        assert schema.name == expected_name, f'Expected {expected_name}, got {schema.name} for {filepath}'


def test_macropolis_upenn_html_detection(ingredient_parser):
    from parsers.html_config import get_html_schema_registry
    from parsers.html_parser import HtmlParser

    sample = """<! **SAS Computing, University of Pennsylvania** >
<! HTML Generated from DCCS's Penninfo Node: 19185.TXT >
<! by "pips2html" written by Peter Kitchin >
<html><head><title>TuttoCucina</title>
<link rel="SHORTCUT ICON" href="http://www.macropolis.org/fav/magcas.ico">
</head>
<body>
<H2><A name=SHORBA></a>SHORBA</H2>
<UL>Puree of Lamb Khartoum Yield: 2 quarts of soup (8 1-cup portions)</UL>
<P>This is a most interesting soup.</P>
<P>In a 6-quart saucepan:</P>
<P><B>Simmer:</B> 3 Ibs. LAMB BONES in</P>
<DT>2 quarts WATER
<DT>2 tsp. SALT for one hour.
<P><B>Add:</B> 1/2 Ib. WHOLE ONIONS, peeled</P>
<P><B>Simmer</B> for 1 hour until vegetables are thoroughly cooked.</P>
</body>
</html>"""
    reg = get_html_schema_registry()
    schema = reg.detect_schema(sample, "macropolis/sudan.htm")
    assert schema is not None
    assert schema.name == "macropolis_upenn"

    parser = HtmlParser(ingredient_parser)
    recipes = list(parser.parse_content(sample, "macropolis/sudan.htm"))
    assert len(recipes) == 1
    assert recipes[0].title == "SHORBA"
    assert recipes[0].yield_amount == "2 quarts of soup (8 1-cup portions)"
    assert recipes[0].description == "Puree of Lamb Khartoum"
    assert len(recipes[0].ingredients) == 4
    # Check unit normalization for Ibs.
    lamb = next(i for i in recipes[0].ingredients if "LAMB BONES" in i.name)
    assert lamb.unit == "pound"
    assert lamb.quantity == "3"


def test_all_html_schemas_content_only_detection():
    """Verify that all HTML schemas are detected solely from content patterns without relying on filepaths."""
    from parsers.html_config import get_html_schema_registry
    reg = get_html_schema_registry()

    test_cases = [
        ("<html><body>Welcome to garvick recipe page</body></html>", "garvick"),
        ("<html><head><link rel='stylesheet' href='Rally.css'></head><body>Recipe</body></html>", "mcnalley"),
        ("<html><body>Garry's Home Cookin' mexicancooking.netrelief.com</body></html>", "mexican_recipes"),
        ("<html><body>Garry's Home Cookin' cooking.netrelief.com</body></html>", "netrelief_recipes"),
        ("<html><body>Garry's Home Cookin' bbq.netrelief.com</body></html>", "bbq_recipes"),
        ("<html><body>Garry's Home Cookin' chile.netrelief.com</body></html>", "chile_recipes"),
        ("<html><body>The Coffee Shoppe by RocketLibrarian</body></html>", "coffeeshop_recipes"),
        ("<html><body>CMU SCS Recipe Archive</body></html>", "cscmu"),
        ("<html><body><li class='recipe-ingredients__list-item'>1 cup flour</li><li class='recipe-method__list-item'>Mix</li></body></html>", "bbc_food"),
        ("<html><body>Top Secret Recipes by Todd Wilbur</body></html>", "top_secret_recipes"),
        ("<html><head><title>TuttoCucina</title><link rel='icon' href='http://www.macropolis.org/icon'></head></html>", "macropolis"),
        ("<html><!-- Penninfo pips2html --><body>Recipe</body></html>", "macropolis_upenn"),
    ]

    for sample_content, expected_schema in test_cases:
        # Pass empty filepath or dummy filepath to prove path independence
        schema = reg.detect_schema(sample_content, "")
        assert schema is not None, f"Failed to detect schema for content: {sample_content}"
        assert schema.name == expected_schema, f"Expected {expected_schema}, got {schema.name}"

        # detect_schemas without filepath
        candidates = reg.detect_schemas(sample_content)
        assert len(candidates) >= 1
        assert candidates[0].name == expected_schema


def test_parser_display_names(ingredient_parser):
    from parsers.html_parser import HtmlParser
    from parsers.sqlite.sqlite_parser import SqliteRecipeParser
    from parsers.mealmaster import MealMasterParser
    from parsers.cookware import CookwareCSVParser

    mm = MealMasterParser(ingredient_parser)
    assert mm.get_display_name() == "MealMaster Parser"

    cw = CookwareCSVParser(ingredient_parser)
    assert cw.get_display_name() == "Cookware CSV Parser"

    html_p = HtmlParser(ingredient_parser)
    assert html_p.get_display_name("tests/samples/garvick_sample.html") == "HTML Parser, config garvick.yaml"
    assert html_p.get_display_name("tests/samples/sample_recipe.html") == "HTML Parser"

    html_cfg = HtmlParser(ingredient_parser, config_path="configs/garvick.yaml")
    assert html_cfg.get_display_name() == "HTML Parser, config garvick.yaml"

    sql_p = SqliteRecipeParser(ingredient_parser)
    assert sql_p.get_display_name("tests/samples/test_recipes.db") == "SQLite Parser, config cc-rec.yaml"


def test_verbose_conversion_output(capsys, tmp_path):
    from convert import main as convert_main

    out_file = tmp_path / "out.json"
    ret = convert_main([
        "tests/samples/garvick_sample.html",
        "-o", str(out_file),
        "-v",
        "--no-nlp"
    ])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "garvick_sample.html" in captured
    assert "HTML Parser, config garvick.yaml" in captured


def test_two_col_excludes_markdown_and_tables():
    from parsers.two_col import TwoColParser

    md_table_sample = """+-----------------------------+-----------------------+
| **Potato-Pan Burger**\\                              |
+-----------------------------+-----------------------+
| **2 lb. ground beef**       | **1/4 cup butter**    |
+-----------------------------+-----------------------+"""
    # Excludes .md extension
    assert TwoColParser.detect("recipe.md", md_table_sample) == 0.0
    # Excludes table borders even without .md extension
    assert TwoColParser.detect("recipe.txt", md_table_sample) == 0.0


def test_generic_md_detection_and_table_parsing(ingredient_parser):
    from pathlib import Path
    from parsers.generic_md import GenericMdParser
    from parsers.registry import ParserRegistry

    sample_path = Path("nux/Test/DOCX/Potato beef casserole.docx.md")
    if not sample_path.exists():
        sample_path = Path("nux/llm-samples/Potato beef casserole.docx.md")
    if not sample_path.exists():
        pytest.skip("Potato beef casserole sample not found")

    content = sample_path.read_text(encoding="utf-8")

    # Detection check
    score = GenericMdParser.detect(str(sample_path), content[:2000])
    assert score >= 0.70, f"Expected GenericMdParser score >= 0.70, got {score}"

    # Auto-detection from registry should resolve to GenericMdParser
    parser = ParserRegistry.get_parser(sample_path, ingredient_parser)
    assert isinstance(parser, GenericMdParser)

    # Parse content check
    parser = GenericMdParser(ingredient_parser)
    recipes = list(parser.parse_content(content, str(sample_path)))
    assert len(recipes) == 1
    r = recipes[0]
    assert r.title == "Potato-Pan Burger"
    assert "Mounds of golden potatoes top this easy casserole" in (r.description or "")
    assert r.yield_amount == "8 servings"
    assert len(r.ingredients) == 15
    assert len(r.instructions) == 3
    assert "In an extra-large skillet" in r.instructions[0]
    assert "Meanwhile, in a medium saucepan" in r.instructions[1]
    assert "Transfer beef mixture" in r.instructions[2]


def test_llm_client_fallback_url():
    """Verify that LLMClient chat() 404 fallback derives URL from base_url origin instead of hardcoded localhost."""
    from unittest.mock import MagicMock, patch
    import requests
    from parsers.llm_parser import LLMClient

    client = LLMClient({"base_url": "http://myserver:11434/v1", "model": "test-model"})

    resp_404 = MagicMock()
    resp_404.status_code = 404
    err_404 = requests.HTTPError(response=resp_404)

    resp_200 = MagicMock()
    resp_200.raise_for_status.return_value = None
    resp_200.json.return_value = {"message": {"content": "fallback success"}}

    def mock_post(url, json, headers, timeout):
        if "chat/completions" in url:
            raise err_404
        elif url == "http://myserver:11434/api/chat":
            return resp_200
        raise ValueError(f"Unexpected URL called: {url}")

    with patch("requests.post", side_effect=mock_post) as patched_post:
        result = client.chat(system="sys prompt", user="user prompt")
        assert result == "fallback success"
        assert patched_post.call_count == 2
        fallback_call_url = patched_post.call_args_list[1][0][0]
        assert fallback_call_url == "http://myserver:11434/api/chat"



