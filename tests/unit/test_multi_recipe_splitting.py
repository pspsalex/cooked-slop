# SPDX-License-Identifier: MIT
"""Unit tests for multi-recipe boundary splitting in TwoColParser and GenericTextParser."""

import pytest
from parsers.two_col import TwoColParser
from parsers.generic import GenericTextParser
from parsers.mixed import MixedFormatParser
from parsers.ingredients import RegexIngredientParser
from parsers.registry import ParserRegistry
from pathlib import Path


@pytest.fixture
def ingredient_parser():
    return RegexIngredientParser()


def test_two_col_multi_recipe_splitting(ingredient_parser):
    content = """-----
For the after-school crowd.

				Oatmeal Cookies

1 c butter				3 c rolled oats
1/4 c honey				1 3/4 c whole wheat pastry flour
2 eggs					1/2 c walnuts (optional)

Cream together butter, honey, eggs. Bake at 350 for 10 minutes.

Makes 36

KEY WORDS:  bake sale, cookies, kids
-----
Welcome anytime, a healthy snack that's tasty too.

			      Wheat Germ Squares

1/4 c butter				1 c wheat germ
1/4 c molasses				1/2 c powdered dry milk
2 eggs					1 pinch salt

Melt butter, molasses together. Bake at 350 for 25 minutes.

Makes 16
"""
    parser = TwoColParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "two_col_multi.txt"))

    assert len(recipes) == 2

    # Recipe 1 assertions
    r1 = recipes[0]
    assert r1.title == "Oatmeal Cookies"
    assert r1.description == "For the after-school crowd."
    assert r1.yield_amount == "36"
    assert "cookies" in r1.categories
    assert "bake sale" in r1.categories
    assert len(r1.ingredients) == 6
    assert len(r1.instructions) == 1
    assert "Cream together butter" in r1.instructions[0]

    # Recipe 2 assertions
    r2 = recipes[1]
    assert r2.title == "Wheat Germ Squares"
    assert r2.description == "Welcome anytime, a healthy snack that's tasty too."
    assert r2.yield_amount == "16"
    assert len(r2.ingredients) == 6
    assert len(r2.instructions) == 1
    assert "Melt butter" in r2.instructions[0]


def test_two_col_centered_title_without_intro_blurb(ingredient_parser):
    content = """
				   Pecan Pie

3 eggs						1 T vanilla
1/4 c honey					1/4 c butter, melted

Beat eggs. Stir in honey and vanilla.

Serves 8
"""
    parser = TwoColParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "pecan_pie.txt"))

    assert len(recipes) == 1
    assert recipes[0].title == "Pecan Pie"
    assert recipes[0].description is None
    assert recipes[0].yield_amount == "8"
    assert len(recipes[0].ingredients) == 4


def test_two_col_intro_sentence_starting_with_a(ingredient_parser):
    content = """-----
A treat from "deep in the heart of Texas."

				   Pecan Pie

3 eggs						1 T vanilla
1/4 c honey					1/4 c butter, melted

Beat eggs. Stir in honey and butter.

Serves 8
"""
    parser = TwoColParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "texas_pie.txt"))

    assert len(recipes) == 1
    assert recipes[0].title == "Pecan Pie"
    assert recipes[0].description == 'A treat from "deep in the heart of Texas."'
    assert recipes[0].yield_amount == "8"


def test_generic_text_multi_recipe_splitting(ingredient_parser):
    content = """THE PHILADELPHIA CHEESECAKE COLLECTION
*****************************************************************

BANANA NUT CHEESECAKE

1 cup chocolate wafer crumbs
1/4 cup margarine, melted

Combine crumbs and margarine; press onto pan.

2 packages cream cheese
1/2 cup sugar
2 eggs

Combine cream cheese and sugar. Bake at 350 for 40 minutes.

*****************************************************************

NORTHWEST CHEESECAKE SUPREME

1 cup graham cracker crumbs
3 Tbsp sugar

Combine crumbs and sugar.

4 packages cream cheese
1 cup sugar
4 eggs

Combine cream cheese, sugar and eggs. Bake at 325 for 1 hour.
"""
    parser = GenericTextParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "cheesecakes.txt"))

    assert len(recipes) == 2
    titles = [r.title for r in recipes]
    assert "Banana Nut Cheesecake" in titles
    assert "Northwest Cheesecake Supreme" in titles
    for r in recipes:
        assert len(r.ingredients) > 0
        assert len(r.instructions) > 0


def test_generic_text_single_recipe_fallback(ingredient_parser):
    content = """SIMPLE PANCAKES

1 cup flour
1 cup milk
1 egg

Mix all ingredients together. Pour onto griddle. Cook until bubbly, flip and serve.
"""
    parser = GenericTextParser(ingredient_parser)
    recipes = list(parser.parse_content(content, "pancakes.txt"))

    assert len(recipes) == 1
    assert recipes[0].title == "Simple Pancakes"
    assert len(recipes[0].ingredients) == 3


def test_detection_prioritizes_two_col_over_mixed(ingredient_parser, tmp_path):
    content = """-----
For the after-school crowd.

				Oatmeal Cookies

1 c butter				3 c rolled oats
1/4 c honey				1 3/4 c whole wheat pastry flour
2 eggs					1/2 c walnuts (optional)

Cream together butter, honey, eggs. Bake at 350.

Makes 36
"""
    test_file = tmp_path / "test_cookies.txt"
    test_file.write_text(content)

    parser = ParserRegistry.get_parser(test_file, ingredient_parser)
    assert isinstance(parser, TwoColParser)
