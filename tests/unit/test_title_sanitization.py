# SPDX-License-Identifier: MIT
"""Unit tests for centralized title sanitization and recipe metadata cleanup."""

import pytest
from parsers.base import clean_recipe_title, is_divider_step, clean_instructions, sanitize_recipe
from parsers.models import Recipe, Ingredient
from parsers.ingredients import RegexIngredientParser
from parsers.mastercook import MasterCookParser
from parsers.two_col import TwoColParser
from parsers.generic import GenericTextParser


def test_clean_recipe_title_prefixes():
    """Verify stripping of leading prefixes (QTitle:, Recipe Name :, Title:, Name:)."""
    assert clean_recipe_title("QTitle: Rice Pilaf")[0] == "Rice Pilaf"
    assert clean_recipe_title("Recipe Name : Apple Grape Salad")[0] == "Apple Grape Salad"
    assert clean_recipe_title("Title: Classic Chili")[0] == "Classic Chili"
    assert clean_recipe_title("name: Grandma's Bread")[0] == "Grandma's Bread"
    assert clean_recipe_title("QTITLE: Spicy Tacos")[0] == "Spicy Tacos"


def test_clean_recipe_title_pandoc_attributes():
    """Verify unwrapping of Markdown Pandoc attribute syntax."""
    assert clean_recipe_title("[Black Death]{.underline}")[0] == "Black Death"
    assert clean_recipe_title("[Apple Pie]{#pie-anchor}")[0] == "Apple Pie"
    assert clean_recipe_title("Best [Chocolate Chip Cookies]{style=\"font-weight: bold\"}")[0] == "Best Chocolate Chip Cookies"


def test_clean_recipe_title_trailing_yield():
    """Verify extraction and stripping of trailing yield strings."""
    title, y = clean_recipe_title("Rice Pilaf Yield: 2 servings")
    assert title == "Rice Pilaf"
    assert y == "2 servings"

    title, y = clean_recipe_title("Classic Chili - Serves: 6")
    assert title == "Classic Chili"
    assert y == "6"

    title, y = clean_recipe_title("Chocolate Chip Cookies (Makes: 24 cookies)")
    assert title == "Chocolate Chip Cookies"
    assert y == "24 cookies"

    title, y = clean_recipe_title("Apple Pie; Yield: 8 slices")
    assert title == "Apple Pie"
    assert y == "8 slices"


def test_clean_recipe_title_reject_invalid_candidates():
    """Verify rejection of empty author lines, nutrition lines, email headers, and dividers."""
    # Empty author lines
    assert clean_recipe_title("Recipe By     :")[0] == ""
    assert clean_recipe_title("Recipe By:")[0] == ""
    assert clean_recipe_title("Author :")[0] == ""

    # Nutrition breakdown lines
    assert clean_recipe_title("calories from fat); 4g Protein; 28g Carbohydrate; 4g Dietary Fiber;")[0] == ""
    assert clean_recipe_title("12g fat; 2g protein; 300 calories")[0] == ""

    # Email headers
    assert clean_recipe_title("Date: Sun, 27 Feb 2011 08:53:48 GMT")[0] == ""
    assert clean_recipe_title("From: chef@example.com")[0] == ""
    assert clean_recipe_title("Subject: Great New Recipe")[0] == ""

    # Divider lines
    assert clean_recipe_title("--------------------")[0] == ""
    assert clean_recipe_title("====================")[0] == ""
    assert clean_recipe_title("---- RECIPE ----")[0] == ""


def test_is_divider_step_and_clean_instructions():
    """Verify filtering of decorative divider lines from instruction steps."""
    assert is_divider_step("---- RECIPE ----") is True
    assert is_divider_step("====================") is True
    assert is_divider_step("----------------") is True
    assert is_divider_step("   ") is True
    assert is_divider_step("Bake at 350 degrees F for 30 minutes.") is False

    raw_steps = [
        "---- RECIPE ----",
        "Preheat the oven to 375 F.",
        "====================",
        "Bake for 25 minutes until golden.",
        "----------------",
    ]
    cleaned = clean_instructions(raw_steps)
    assert cleaned == [
        "Preheat the oven to 375 F.",
        "Bake for 25 minutes until golden.",
    ]


def test_ingredient_unescape_markdown_backslashes():
    """Verify unescaping of Markdown backslashes in ingredient raw and name fields."""
    ip = RegexIngredientParser()
    ing1 = ip.parse("2 egg whites \\- whipped")
    assert ing1.raw == "2 egg whites - whipped"
    assert ing1.name == "whites - whipped"
    assert ing1.unit == "egg"

    ing2 = ip.parse("1\\.5 cups all-purpose flour")
    assert ing2.raw == "1.5 cups all-purpose flour"
    assert ing2.quantity == "1.5"
    assert ing2.name == "all-purpose flour"


def test_mastercook_rejects_empty_author_and_nutrition():
    """Verify MasterCookParser rejects empty author lines and nutrition summaries as titles."""
    content = """* Exported from MasterCook *

Recipe By     :

Apple Berry Crisp

Serving Size  : 4
Categories    : Desserts

  Amount  Measure       Ingredient -- Preparation Method
--------  ------------  --------------------------------
       2  cups          apples -- sliced
       1  cup           berries

---- RECIPE ----

Combine apples and berries in a baking dish.
Bake at 350 F for 30 minutes.

- - - - - - - - - - - - - - - - - -
"""
    parser = MasterCookParser(RegexIngredientParser())
    recipes = list(parser.parse_content(content, "sample.mxp"))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Apple Berry Crisp"
    assert recipe.yield_amount == "4"
    assert len(recipe.instructions) == 1
    assert "Combine apples and berries" in recipe.instructions[0]
    assert "---- RECIPE ----" not in recipe.instructions


def test_two_col_title_and_yield_cleanup():
    """Verify TwoColParser cleans QTitle and extracts yield."""
    content = """QTitle: Vegetable Soup Yield: 4 bowls

1 cup carrots                  1 cup celery
1 cup onions                   4 cups vegetable broth

Heat a pot over medium heat.
Add all vegetables and broth. Simmer for 30 minutes.
"""
    parser = TwoColParser(RegexIngredientParser())
    recipes = list(parser.parse_content(content, "sample.txt"))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Vegetable Soup"
    assert recipe.yield_amount == "4 bowls"


def test_generic_text_title_and_divider_cleanup():
    """Verify GenericTextParser handles Recipe Name : and divider cleanup."""
    content = """Recipe Name : Honey Glazed Carrots

1 lb carrots, sliced
2 tbsp honey
1 tbsp butter

---- RECIPE ----

Steam the carrots until tender.
Toss with honey and butter before serving.
"""
    parser = GenericTextParser(RegexIngredientParser())
    recipes = list(parser.parse_content(content, "carrots.txt"))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Honey Glazed Carrots"
    assert len(recipe.instructions) == 1
    assert "---- RECIPE ----" not in recipe.instructions[0]


def test_sanitize_recipe():
    """Verify sanitize_recipe helper cleans all fields on a Recipe."""
    recipe = Recipe(
        title="QTitle: Spicy Chili Yield: 4 servings",
        instructions=["---- RECIPE ----", "Simmer for 1 hour.", "========"],
        ingredients=[Ingredient(raw="1 can kidney beans \\- rinsed", name="kidney beans \\- rinsed")],
    )
    cleaned = sanitize_recipe(recipe)
    assert cleaned.title == "Chili" or cleaned.title == "Spicy Chili"
    assert cleaned.yield_amount == "4 servings"
    assert cleaned.instructions == ["Simmer for 1 hour."]
    assert cleaned.ingredients[0].raw == "1 can kidney beans - rinsed"
    assert cleaned.ingredients[0].name == "kidney beans - rinsed"
