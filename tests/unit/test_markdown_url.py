# SPDX-License-Identifier: MIT
"""Unit tests for Markdown recipe line number URL fragments (SPEC-022)."""

from pathlib import Path
import pytest
from parsers.generic_md import GenericMdParser
from parsers.ricette_md import RicetteMdParser
from parsers.ingredients import RegexIngredientParser


@pytest.fixture
def generic_parser():
    return GenericMdParser(RegexIngredientParser())


@pytest.fixture
def ricette_parser():
    return RicetteMdParser(RegexIngredientParser())


def test_generic_md_single_bold_title(generic_parser):
    """Test that a single markdown recipe with bold title gets line 1."""
    content = """**Simple Pancakes**

Ingredients:
- 1 cup flour
- 1 egg

Directions:
1. Mix and cook on skillet.
"""
    recipes = list(generic_parser.parse_content(content, filepath="sample.md"))
    assert len(recipes) == 1
    assert recipes[0].title == "Simple Pancakes"
    assert recipes[0].url == "file://sample.md#1"


def test_generic_md_preamble_and_blank_lines(generic_parser):
    """Test that preamble and blank lines offset the recipe start line properly."""
    content = """[format: generic_md]

Some introduction or notes.

# Hearty Beef Stew

Ingredients:
- 1 lb beef
- 2 carrots

Directions:
1. Simmer in pot for 2 hours.
"""
    recipes = list(generic_parser.parse_content(content, filepath="/path/to/stew.md"))
    assert len(recipes) == 1
    assert recipes[0].title == "Hearty Beef Stew"
    # Line 1: [format: ...]
    # Line 2: blank
    # Line 3: Some intro...
    # Line 4: blank
    # Line 5: # Hearty Beef Stew
    assert recipes[0].url == "file:///path/to/stew.md#5"


def test_generic_md_multi_separator(generic_parser):
    """Test multi-recipe markdown file separated by dash lines."""
    content = """**Chocolate Fudge Brownies**

Delish brownies!

Ingredients:
- 1 cup sugar
- 1/2 cup butter

Directions:
1. Bake at 350F.

----------------------------------------

**Simple Garlic Bread**

Great side for pasta!

Ingredients:
- 1 loaf bread
- 4 tbsp butter

Directions:
1. Broil for 5 minutes.
"""
    recipes = list(generic_parser.parse_content(content, filepath="cookbook.md"))
    assert len(recipes) == 2
    assert recipes[0].title == "Chocolate Fudge Brownies"
    assert recipes[0].url == "file://cookbook.md#1"
    assert recipes[1].title == "Simple Garlic Bread"
    assert recipes[1].url == "file://cookbook.md#14"


def test_generic_md_multi_heading_delimited(generic_parser):
    """Test multi-recipe markdown file delimited by headings."""
    content = """# First Recipe

Ingredients:
- 1 cup milk

Directions:
1. Heat and serve.

# Second Recipe

Ingredients:
- 2 apples

Directions:
1. Slice and eat.
"""
    recipes = list(generic_parser.parse_content(content, filepath="/recipes/multi.md"))
    assert len(recipes) == 2
    assert recipes[0].title == "First Recipe"
    assert recipes[0].url == "file:///recipes/multi.md#1"
    assert recipes[1].title == "Second Recipe"
    assert recipes[1].url == "file:///recipes/multi.md#9"


def test_generic_md_unrolled_table_anchoring(generic_parser):
    """Test that recipes appearing after an ASCII grid table remain anchored to source lines."""
    content = """# Table Recipe

Ingredients:
- 1 cup flour

Directions:
+-------------------+-------------------+
| Ingredients       | Directions        |
+===================+===================+
| 1 cup rice        | Boil in water.    |
+-------------------+-------------------+

# Subsequent Recipe

Ingredients:
- 1 cup oats

Directions:
1. Cook with water.
"""
    recipes = list(generic_parser.parse_content(content, filepath="tables.md"))
    assert len(recipes) == 2
    assert recipes[0].title == "Table Recipe"
    assert recipes[0].url == "file://tables.md#1"
    assert recipes[1].title == "Subsequent Recipe"
    # Line 1: # Table Recipe
    # Line 2: blank
    # Line 3: Ingredients:
    # Line 4: - 1 cup flour
    # Line 5: blank
    # Line 6: Directions:
    # Line 7: +-------+
    # Line 8: | ...   |
    # Line 9: +=...===+
    # Line 10: | ...   |
    # Line 11: +-------+
    # Line 12: blank
    # Line 13: # Subsequent Recipe
    assert recipes[1].url == "file://tables.md#13"


def test_generic_md_empty_filepath(generic_parser):
    """Test that in-memory parsing with empty or None filepath leaves recipe.url as None."""
    content = """**In-Memory Recipe**

Ingredients:
- 1 egg

Directions:
1. Fry egg.
"""
    recipes = list(generic_parser.parse_content(content, filepath=""))
    assert len(recipes) == 1
    assert recipes[0].url is None


def test_ricette_md_single_and_multi(ricette_parser):
    """Test Italian markdown recipes line numbers for single and multi-recipe documents."""
    content = """**DBRicette - l'ebook**

Elaborazione ricette.

# Pollo Arrosto

## Ricetta
Infornare il pollo.

## Ingredienti per 4 persone
+ 1 pollo intero
+ rosmarino
+ sale

# Ali Di Pollo

## Ricetta
Friggere le ali.

## Ingredienti per 2 persone
+ 8 ali di pollo
+ olio
"""
    recipes = list(ricette_parser.parse_content(content, filepath="ricette.md"))
    assert len(recipes) == 2
    assert recipes[0].title == "Pollo Arrosto"
    # Preceding lines:
    # 1: **DBRicette - l'ebook**
    # 2: blank
    # 3: Elaborazione ricette.
    # 4: blank
    # 5: # Pollo Arrosto
    assert recipes[0].url == "file://ricette.md#5"
    # Line 5: # Pollo Arrosto
    # Line 6: blank
    # Line 7: ## Ricetta
    # Line 8: Infornare...
    # Line 9: blank
    # Line 10: ## Ingredienti...
    # Line 11: + 1 pollo...
    # Line 12: + rosmarino
    # Line 13: + sale
    # Line 14: blank
    # Line 15: # Ali Di Pollo
    assert recipes[1].title == "Ali Di Pollo"
    assert recipes[1].url == "file://ricette.md#15"


def test_ricette_md_empty_filepath(ricette_parser):
    """Test Italian markdown parsing with empty filepath leaves recipe.url as None."""
    content = """# Pollo Semplice

## Ricetta
Cuocere bene.

## Ingredienti per 1 persona
+ 1 filetto di pollo
"""
    recipes = list(ricette_parser.parse_content(content, filepath=""))
    assert len(recipes) == 1
    assert recipes[0].url is None


def test_sample_files_deep_linking(generic_parser, ricette_parser):
    """Test line numbers on the actual repo sample files."""
    samples_dir = Path(__file__).parents[1] / "samples"

    # generic_md_recipe.md
    recipes = list(generic_parser.parse_file(str(samples_dir / "generic_md_recipe.md")))
    assert len(recipes) == 1
    assert recipes[0].url == f"file://{samples_dir / 'generic_md_recipe.md'}#1"

    # generic_md_multi.md
    recipes = list(generic_parser.parse_file(str(samples_dir / "generic_md_multi.md")))
    assert len(recipes) == 2
    assert recipes[0].url == f"file://{samples_dir / 'generic_md_multi.md'}#1"
    assert recipes[1].url == f"file://{samples_dir / 'generic_md_multi.md'}#21"

    # ricette_sample.md
    recipes = list(ricette_parser.parse_file(str(samples_dir / "ricette_sample.md")))
    assert len(recipes) == 2
    assert recipes[0].url == f"file://{samples_dir / 'ricette_sample.md'}#16"
    assert recipes[1].url == f"file://{samples_dir / 'ricette_sample.md'}#50"
