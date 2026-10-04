# SPDX-License-Identifier: MIT
"""Unit tests for batch conversion hang, CPU load, error reporting, and parsing fixes."""

import time
from pathlib import Path
import pytest
from parsers.base import is_divider_step
from parsers.two_col import TwoColParser
from parsers.generic import GenericTextParser
from parsers.mastercook import MasterCookParser
from parsers.ingredients import RegexIngredientParser


@pytest.fixture
def ingredient_parser():
    return RegexIngredientParser()


def test_is_divider_step_no_catastrophic_backtracking():
    """Verify that long lines of repeated characters with trailing characters do not hang."""
    t0 = time.time()
    # 80 underscores followed by trailing characters
    pathological = "_" * 80 + " x"
    assert is_divider_step(pathological) is False
    assert time.time() - t0 < 0.1

    # Valid dividers
    assert is_divider_step("-" * 40) is True
    assert is_divider_step("=" * 40) is True
    assert is_divider_step("- - - - - - - - - - - -") is True
    assert is_divider_step("   ") is True

    # Real instruction step
    assert is_divider_step("Bake at 350 degrees for 45 minutes.") is False


def test_two_col_detection_precision():
    """Verify TwoColParser does not falsely claim single-column recipes or text files with Servings."""
    # Single column recipe with tabs between quantity, unit, and ingredient name
    single_col_tabbed = """Alfredo Sauce

8\toz.\tcream cheese, cut into cubes
3/4\tcup\tgrated parmesan cheese
1/2\tcup\tbutter
1/2\tcup\tcream

Combine all ingredients in a saucepan over low heat.
"""
    assert TwoColParser.detect("alfredo.txt", single_col_tabbed) == 0.0

    # Normal text recipe containing Servings
    single_col_servings = """Pancakes
Servings: 4

1 cup flour
1 cup milk
1 egg

Mix and cook on griddle.
"""
    assert TwoColParser.detect("pancakes.txt", single_col_servings) == 0.0

    # True two-column layout
    two_col_content = """Oatmeal Cookies

1 c butter\t\t\t\t3 c rolled oats
1/4 c honey\t\t\t\t1 3/4 c whole wheat pastry flour
2 eggs\t\t\t\t1/2 c walnuts

Mix and bake at 350.
"""
    assert TwoColParser.detect("cookies.txt", two_col_content) >= 0.80


def test_generic_text_single_block_recipe(ingredient_parser):
    """Verify GenericTextParser handles plain text recipes with no blank lines."""
    content = """Here is the potato chowder from Connie.
8 cups peeled potatoes, diced
1/3 cup onion, chopped
3 cans chicken broth
1 can cream of chicken soup
1/4 teaspoon pepper
1 pkg cream cheese, cubed
In a slow cooker combine ingredients. Cook on low for 8 hours. Add cream cheese and stir.
Enjoy!
"""
    parser = GenericTextParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "potato_chowder.txt"))
    assert len(recipes) == 1
    r = recipes[0]
    assert len(r.ingredients) >= 5
    assert len(r.instructions) >= 1
    assert any("slow cooker" in inst for inst in r.instructions)


def test_generic_text_section_headers_and_bullets(ingredient_parser):
    """Verify GenericTextParser extracts recipes delineated by section headers and bullets."""
    content = """Charlie Gibson's Doritos Casserole
This Doritos Casserole is a family favorite.
Casserole Ingredients:
• 1 large package of Doritos
• 2 tbsp onion, grated
• 1 can of chili with beans
• 8-ounce can tomato sauce
• 1 cup shredded cheddar cheese
Casserole Directions:
• Preheat oven to 375 degrees.
• Crumble Doritos into a large bowl.
• Add onion, chili, and tomato sauce.
• Bake for 20 minutes.
"""
    parser = GenericTextParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "doritos.txt"))
    assert len(recipes) == 1
    r = recipes[0]
    assert r.title == "Charlie Gibson's Doritos Casserole"
    assert len(r.ingredients) == 5
    assert len(r.instructions) == 4


def test_generic_text_continuation_chunk(ingredient_parser):
    """Verify that a decorative separator between ingredients and instructions does not drop instructions."""
    content = """Pico de Gallo

Notes: A great summer relish.
INGREDIENTS:
3 large tomatoes diced
1 large onion diced
2 Tbsp diced jalapenos
1/2 cup fresh cilantro
*********
Preparation Instructions: Mix all ingredients together in a large container.
Allow to sit for at least 6 hours.
"""
    parser = GenericTextParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "pico.txt"))
    assert len(recipes) == 1
    r = recipes[0]
    assert len(r.ingredients) == 4
    assert len(r.instructions) >= 1
    assert "Mix all ingredients together" in r.instructions[0]


def test_mastercook_multi_recipe_dump(ingredient_parser):
    """Verify MasterCookParser parses multi-recipe print dumps (holiday.prn style)."""
    content = """A Mardi Gras Cookbook
Page 1   (C) Copyright 1995 - One Command Software Inc.

          Baked Oyster Dressing
Serving Size  : 12
  Amount  Measure       Ingredient -- Preparation Method
--------  ------------  --------------------------------
   4      pounds        Chicken Gizzards
   2      pounds        Chicken Livers
     1/2  gallon        Oyster
Combine ingredients and bake at 350 for 1 hour.
- - - - - - - - - - - - - - - - - -

          Bean And Macaroni Soup
Serving Size  : 1
  Amount  Measure       Ingredient -- Preparation Method
--------  ------------  --------------------------------
   3 1/2  cups          White Beans
     1/4  pound         Bacon
In a large pot, simmer white beans and bacon.
- - - - - - - - - - - - - - - - - -
"""
    parser = MasterCookParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "holiday.prn"))
    assert len(recipes) == 2
    titles = [r.title for r in recipes]
    assert "Baked Oyster Dressing" in titles
    assert "Bean And Macaroni Soup" in titles
    for r in recipes:
        assert len(r.ingredients) > 0
        assert len(r.instructions) > 0
