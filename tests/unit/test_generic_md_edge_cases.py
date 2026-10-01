# SPDX-License-Identifier: MIT
"""Unit tests for Generic Markdown parser edge cases and refinements (SPEC-026)."""

import pytest
from parsers.generic_md import GenericMdParser
from parsers.ingredients import RegexIngredientParser


@pytest.fixture
def parser():
    return GenericMdParser(RegexIngredientParser())


def test_pandoc_escaped_list_numbering(parser):
    """Verify Pandoc escaped list numbering (1\\., 2\\.) matches in _looks_like_qty_or_ing and parses cleanly."""
    assert parser._looks_like_qty_or_ing(r"1\. cup peanut butter")
    assert parser._looks_like_qty_or_ing(r"2\. 1/2 cup sugar")
    assert parser._looks_like_qty_or_ing(r"3\. 1 large egg")

    content = """**Peanut Butter Cookies**

1\\. cup peanut butter

2\\. 1/2 cup sugar

3\\. 1 large egg

Mix well and bake at 350 for 10 minutes.
"""
    recipes = list(parser.parse_content(content))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Peanut Butter Cookies"
    assert len(recipe.ingredients) == 3
    assert recipe.ingredients[0].name == "peanut butter"
    assert recipe.ingredients[0].quantity == "1"
    assert recipe.ingredients[0].unit == "cup"
    assert recipe.ingredients[1].quantity == "1/2"
    assert recipe.ingredients[1].name == "sugar"
    assert recipe.ingredients[2].quantity == "1"
    assert len(recipe.instructions) == 1


def test_all_bold_recipe_documents(parser):
    """Verify all-bold recipe documents do not treat bold ingredients as titles and correctly extract content."""
    content = """**Beef Stroganoff**

**1 lb. ground beef**

**1 onion (size does not matter but not too small)**

**1 cup sliced mushrooms**

**1 can Campbells Cream of Chicken Soup**

**1/2 cup sour cream**

**Egg Noodles**

**Cook ground beef and onion. Add soup and mushrooms.**

**Heat through. Add sour cream. Salt and pepper to taste.**

**Serve over cooked egg noodles.**
"""
    recipes = list(parser.parse_content(content))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Beef Stroganoff"
    assert len(recipe.ingredients) == 6
    assert recipe.ingredients[0].quantity == "1"
    assert recipe.ingredients[0].unit == "pound"
    assert recipe.ingredients[0].name == "ground beef"
    assert recipe.ingredients[5].name == "Egg Noodles"
    assert len(recipe.instructions) == 3
    assert "Cook ground beef" in recipe.instructions[0]
    assert "Heat through" in recipe.instructions[1]
    assert "Serve over cooked" in recipe.instructions[2]


def test_multi_recipe_tilde_delimiters(parser):
    """Verify tilde lines (\\~\\~\\~ and ~~~~) trigger multi-recipe boundaries and capture plain numbered titles."""
    content = """\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~\\~

1\\. ALDILLA

1 large onion \\-- chopped

1 1/2 pound flank steak

Score steak and rub with chili powder; coat with flour. Cook on low for 8 hours.

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

2\\. ALL DAY BEEF

1 1/2 lb. Beef roast

1/2 tsp. Black pepper

Brown meat and cook in slow cooker for 8 hours.
"""
    recipes = list(parser.parse_content(content))
    assert len(recipes) == 2
    assert recipes[0].title == "1. ALDILLA"
    assert len(recipes[0].ingredients) == 2
    assert len(recipes[0].instructions) == 1
    assert "Score steak" in recipes[0].instructions[0]

    assert recipes[1].title == "2. ALL DAY BEEF"
    assert len(recipes[1].ingredients) == 2
    assert len(recipes[1].instructions) == 1
    assert "Brown meat" in recipes[1].instructions[0]


def test_blockquote_markers(parser):
    """Verify leading blockquote markers (> ) are stripped in _clean_line and detected in ingredients/instructions."""
    assert parser._clean_line("> 1 lb crab meat") == "1 lb crab meat"
    assert parser._clean_line("> > 2 tbsp butter") == "2 tbsp butter"
    assert parser._clean_line("> Melt butter in skillet.") == "Melt butter in skillet."

    content = """# Crab Noodles

> 1 lb crab meat
> 1 pkg egg noodles
> 2 tbsp butter

> Melt butter in skillet. Add crab meat and noodles. Cook for 5 minutes.
"""
    recipes = list(parser.parse_content(content))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Crab Noodles"
    assert len(recipe.ingredients) == 3
    assert recipe.ingredients[0].raw == "1 lb crab meat"
    assert recipe.ingredients[1].raw == "1 pkg egg noodles"
    assert recipe.ingredients[2].raw == "2 tbsp butter"
    assert len(recipe.instructions) == 1
    assert "Melt butter in skillet" in recipe.instructions[0]


def test_image_tags_in_heading_titles(parser):
    """Verify _clean_title strips Markdown/Pandoc image syntax from titles."""
    raw1 = '# ![](media/image1.png){width="1.6in"} Eggplant Timbale'
    assert parser._clean_title(raw1) == "Eggplant Timbale"

    raw2 = "## ![Cover Image](media/photo.jpg) Chocolate Mousse"
    assert parser._clean_title(raw2) == "Chocolate Mousse"

    raw3 = "### ![](media/thumb.png) Apple Pie"
    assert parser._clean_title(raw3) == "Apple Pie"

    content = """# ![](media/image1.png){width="1.6in"} Eggplant Timbale

1 large eggplant
2 tbsp olive oil

Bake at 375 for 20 minutes.
"""
    recipes = list(parser.parse_content(content))
    assert len(recipes) == 1
    assert recipes[0].title == "Eggplant Timbale"


def test_hyphenated_cooking_verbs(parser):
    """Verify _looks_like_instruction_start matches hyphenated cooking verbs like pre-heat."""
    assert parser._looks_like_instruction_start("Pre-heat oven to 325 degrees.")
    assert parser._looks_like_instruction_start("pre-heat oven to 400F.")
    assert parser._looks_like_instruction_start("Preheat oven to 350.")
    assert parser._looks_like_instruction_start("> Pre-heat the skillet.")

    content = """**Baked Apples**

4 apples
1/4 cup brown sugar

Pre-heat oven to 350 degrees. Core apples and fill with brown sugar. Bake for 30 minutes.
"""
    recipes = list(parser.parse_content(content))
    assert len(recipes) == 1
    assert len(recipes[0].ingredients) == 2
    assert len(recipes[0].instructions) == 1
    assert "Pre-heat oven" in recipes[0].instructions[0]
