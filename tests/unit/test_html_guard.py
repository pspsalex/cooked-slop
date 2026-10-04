# SPDX-License-Identifier: MIT
"""Unit tests for HTML parser blank recipe guard and XPath schema refinements."""

from pathlib import Path
import pytest
from parsers.html_parser import HtmlParser
from parsers.html_config import get_html_schema_registry, HtmlRecipeSchema, parse_html_recipes_with_schema
from parsers.ingredients import RegexIngredientParser
from parsers.models import Recipe


@pytest.fixture
def parser():
    return HtmlParser(ingredient_parser=RegexIngredientParser())


def test_blank_html_only_title_yields_zero_recipes(parser):
    """Verify that an HTML page with only a title and no ingredients/instructions is rejected by the guard."""
    html_content = """<!DOCTYPE html>
<html>
<head>
<title>Index of Recipes</title>
</head>
<body>
<h1>Index of Recipes</h1>
<p>Welcome to our recipe catalog. Click below to browse categories.</p>
<a href="/desserts">Desserts</a>
</body>
</html>"""
    recipes = list(parser.parse_content(html_content, "index.html"))
    assert len(recipes) == 0, f"Expected 0 recipes for title-only HTML, got {len(recipes)}"


def test_blank_html_with_schema_match_rejected(parser):
    """Verify that even if an HTML page matches schema detection keywords, it is rejected if 0 ing and 0 inst."""
    html_content = """<html>
<head>
<title>Garry's Home Cookin' - Recipe Index</title>
</head>
<body>
<h1>Garry's Home Cookin'</h1>
<p>Visit bbq.netrelief.com for more information.</p>
<p>Table of Contents</p>
</body>
</html>"""
    recipes = list(parser.parse_content(html_content, "index.shtml"))
    assert len(recipes) == 0, f"Expected 0 recipes for blank schema match, got {len(recipes)}"


def test_html_with_ingredients_is_accepted(parser):
    """Verify that an HTML page with ingredients is accepted even if instructions are empty."""
    html_content = """<html>
<head><title>Simple Salad</title></head>
<body>
<p align="center"><font size="5"><b>Simple Salad</b></font></p>
<blockquote>
  <p><b>1 head lettuce<br>
  2 tomatoes -- diced<br>
  1 cucumber -- sliced</b></p>
</blockquote>
<p>Garry's Home Cookin'</p>
<a href="http://bbq.netrelief.com">BBQ</a>
</body>
</html>"""
    recipes = list(parser.parse_content(html_content, "salad.shtml"))
    assert len(recipes) == 1
    assert recipes[0].title == "Simple Salad"
    assert len(recipes[0].ingredients) == 3


def test_html_with_instructions_is_accepted(parser):
    """Verify that an HTML page with instructions is accepted even if ingredients list is empty (e.g. cscmu)."""
    html_content = """<title>Boiled Water</title>
<h1>Boiled Water</h1>
<pre>
Bring 2 cups of water to a rolling boil over high heat for 5 minutes.
</pre>
<p><b><a href="http://www.scs.cmu.edu/">Carnegie Mellon's School of Computer Science</a></b> Recipe Archive</p>
"""
    recipes = list(parser.parse_content(html_content, "boiled_water.html"))
    assert len(recipes) == 1
    assert recipes[0].title == "Boiled Water"
    assert len(recipes[0].instructions) >= 1


def test_bbq_netrelief_blockquote_layout(parser):
    """Verify that bbq_recipes schema extracts from blockquote tableless layouts."""
    sample_path = Path(__file__).parent.parent / "samples" / "bbq_netrelief_sample.shtml"
    with open(sample_path, "r", encoding="utf-8") as f:
        content = f.read()

    recipes = list(parser.parse_content(content, str(sample_path)))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Artichoke Dip Appetizer"
    assert recipe.yield_amount == "10"
    assert len(recipe.ingredients) == 7
    assert len(recipe.instructions) == 1
    assert "Preheat oven to 350" in recipe.instructions[0]


def test_bbq_table_layout_regression(parser):
    """Verify that bbq_recipes schema still correctly extracts traditional table layouts."""
    sample_path = Path(__file__).parent.parent / "samples" / "bbq_sample.html"
    with open(sample_path, "r", encoding="utf-8") as f:
        content = f.read()

    recipes = list(parser.parse_content(content, str(sample_path)))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "La Parilla Traditional Achiote Recado"
    assert recipe.yield_amount == "Makes about 2 1/2 cups."
    assert len(recipe.ingredients) == 12
    assert len(recipe.instructions) == 2


def test_schema_mismatch_fallback():
    """Verify that when a schema produces a blank recipe, parse_html_recipes_with_schema does not yield it."""
    registry = get_html_schema_registry()
    schema = registry.get_schema("bbq_recipes")
    assert schema is not None

    blank_html = """<html>
<head><title>Garry's Home Cookin' - Blank Page</title></head>
<body>bbq.netrelief.com</body>
</html>"""
    recipes = list(parse_html_recipes_with_schema(blank_html, schema, RegexIngredientParser(), "blank.shtml"))
    assert len(recipes) == 0
