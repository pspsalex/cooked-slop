# SPDX-License-Identifier: MIT
"""Unit tests for VJJE recipe extraction and normalizer."""

import pytest
from parsers.generic_md import GenericMdParser
from parsers.ingredients import RegexIngredientParser
from tools.extract.vjje import (
    clean_line_text,
    format_recipes_markdown,
    is_ingredient_line,
    is_instruction_line,
    is_non_recipe_page,
    parse_book_pages,
    parse_vjje_page,
    strip_page_footer,
)


def test_clean_line_text() -> None:
    raw = "1−1/2 cups of flour\xa0with “fresh” herbs – and ‘garlic’"
    cleaned = clean_line_text(raw)
    assert cleaned == '1-1/2 cups of flour with "fresh" herbs - and \'garlic\''


def test_is_non_recipe_page() -> None:
    # Table of contents
    toc_lines = [
        "Table of Contents",
        "Thin Crust Dough ........................................................................ 3",
        "NY Style Dough .......................................................................... 4",
        "Sicilian Thick Crust .................................................................... 5",
    ]
    assert is_non_recipe_page(toc_lines) is True

    # Introduction
    intro_lines = [
        "Introduction",
        "The E-Cookbooks Library",
        "Home to over 100,000 recipes",
    ]
    assert is_non_recipe_page(intro_lines) is True

    # Apron form
    apron_lines = [
        "Personalized Cooking Aprons",
        "Make a mess - protect the dress!",
        "Click HERE For Cooking Aprons",
    ]
    assert is_non_recipe_page(apron_lines) is True

    # Short / blank page
    assert is_non_recipe_page(["Pizza Recipes", "VJJE Publishing Co."]) is True

    # Valid recipe page lines
    recipe_lines = [
        "Hot Chili Oil",
        "1/2 Cup corn oil",
        "20 dried hot chili peppers",
        "1/2 teaspoon Sichuan peppercorns",
        "1. In a saucepan heat the oil.",
        "2. Add the peppers and cook.",
    ]
    assert is_non_recipe_page(recipe_lines) is False


def test_strip_page_footer() -> None:
    lines = [
        "1. Wash and trim artichokes.",
        "2. Cook in boiling water.",
        "Yield: 4 servings",
        "FREE Cookbooks!! Stop Searching, Start Cooking!",
        "http://www.e-cookbooks.net",
        "Artichokes Dip",
        "5",
    ]
    cleaned, extracted_yield = strip_page_footer(lines, "Artichokes Dip")
    assert cleaned == [
        "1. Wash and trim artichokes.",
        "2. Cook in boiling water.",
    ]
    assert extracted_yield == "4 servings"


def test_is_ingredient_and_instruction_lines() -> None:
    assert is_ingredient_line("1/2 cup corn oil") is True
    assert is_ingredient_line("• 2 Medium acorn squash") is True
    assert is_ingredient_line("Salt and pepper to taste") is True
    assert is_ingredient_line("Dipping Sauce:") is True

    assert is_instruction_line("Preparation:") is True
    assert is_instruction_line("1. Preheat oven to 375F.") is True
    assert is_instruction_line("Preheat oven to 350 degrees.") is True
    assert is_instruction_line("In a shallow dish, mix together the soy sauce.") is True


def test_parse_vjje_page_and_markdown_generation() -> None:
    page_text = """Hot Chili Oil
1/2 Cup corn oil
20 dried hot chili peppers
1/2 teaspoon Sichuan peppercorns
1 teaspoon paprika

1. Line a small strainer with paper towel.
2. In a small saucepan heat oil until hot.
3. Pour oil through strainer into jar.
Yield: 1/2 cup

FREE Cookbooks!! Stop Searching, Start Cooking!
http://www.e-cookbooks.net

Hot Chili Oil

49
"""
    parsed = parse_vjje_page(page_text)
    assert parsed is not None
    assert parsed["title"] == "Hot Chili Oil"
    assert parsed["yield_amount"] == "1/2 cup"
    assert len(parsed["ingredients"]) == 4
    assert len(parsed["instructions"]) >= 3

    md = format_recipes_markdown([parsed])
    assert "<!-- format: generic_md -->" in md
    assert "# Hot Chili Oil" in md
    assert "Servings: 1/2 cup" in md
    assert "## Ingredients" in md
    assert "- 1/2 Cup corn oil" in md
    assert "## Preparation" in md
    assert "1. Line a small strainer with paper towel." in md

    # Verify ingestion with GenericMdParser
    parser = GenericMdParser(RegexIngredientParser())
    recipes = list(parser.parse_content(md, "test.md"))
    assert len(recipes) == 1
    rec = recipes[0]
    assert rec.title == "Hot Chili Oil"
    assert len(rec.ingredients) == 4
    assert len(rec.instructions) >= 3


def test_parse_book_pages_with_continuation() -> None:
    page1 = """Bienenstich (Bee Sting Cake)
1 cup flour
2 eggs
The filling:
1/2 cup sugar

Mix the flour and eggs.
Beat
Bienenstich (Bee Sting Cake)
9
"""
    page2 = """The Oktoberfest Cookbook
whites until stiff peaks form.
Spread with filling.
Bienenstich (Bee Sting Cake)
10
"""
    recipes = parse_book_pages([page1, page2], book_title="The Oktoberfest Cookbook")
    assert len(recipes) == 1
    rec = recipes[0]
    assert rec["title"] == "Bienenstich (Bee Sting Cake)"
    assert len(rec["ingredients"]) == 4  # 3 ingredients + 'The filling:' subheading
    # Instructions from page 2 should have been appended to page 1
    instructions_str = " ".join(rec["instructions"])
    assert "whites until stiff peaks form." in instructions_str
    assert "Spread with filling." in instructions_str
