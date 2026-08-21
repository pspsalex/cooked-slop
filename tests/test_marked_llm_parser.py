# SPDX-License-Identifier: MIT
"""Unit tests for marked Markdown recipe parsing and LLMRecipeParser text-marking strategy."""

from typing import Any, Dict
from parsers.generic_md import GenericMdParser
from parsers.ingredients import RegexIngredientParser
from parsers.llm_parser import LLMRecipeParser
import importlib
import pytest

pytestmark = pytest.mark.llm

test_ollama = importlib.import_module("nux.test-ollama")
parse_marked_markdown = test_ollama.parse_marked_markdown


def test_parse_marked_markdown_basic():
    marked_sample = """# Grandma's Secret Bolognese
Yield: Feeds 6 people
Categories: Italian, Pasta, Dinner

## Ingredients
- 500g ground beef
- 1 large onion, diced
- 2 cloves garlic, minced
- 1 can (400g) crushed tomatoes
- 2 tbsp tomato paste
- 1 splash red wine

## Instructions
1. First brown the beef in a hot pot. Remove it, then sauté onions and garlic until soft.
2. Pour in the wine to deglaze. Stir in tomato paste, crushed tomatoes, and put the beef back in.
3. Cover and cook on low heat for 2 hours stirring occasionally. Serve over tagliatelle.
"""

    result = parse_marked_markdown(marked_sample, source_path="sample.txt")

    assert result.name == "Grandma's Secret Bolognese"
    assert result.recipeYield == "Feeds 6 people"
    assert len(result.ingredientGroups) == 1
    assert len(result.ingredientGroups[0].items) == 6
    assert "500g ground beef" in result.ingredientGroups[0].items[0]
    assert len(result.recipeInstructions) == 3
    assert result.source_path == "sample.txt"


def test_parse_marked_markdown_grouped():
    marked_sample = """# Chocolate Banana Pie
Yield: 8 servings

## Ingredients
### Crust:
- 1 1/2 cups graham cracker crumbs
- 6 tbsp melted butter

### Filling:
- 3 ripe bananas, sliced
- 2 cups chocolate pudding
- 1 cup whipped cream

## Instructions
### Prepare Crust:
1. Mix graham cracker crumbs and melted butter. Press into pie dish and chill.

### Prepare Filling:
2. Layer banana slices in the crust.
3. Pour chocolate pudding over bananas. Top with whipped cream before serving.
"""

    ing_parser = RegexIngredientParser()
    md_parser = GenericMdParser(ing_parser)
    recipes = list(md_parser.parse_content(marked_sample, "pie.txt"))

    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Chocolate Banana Pie"
    assert recipe.yield_amount == "8 servings"
    assert len(recipe.ingredients) == 7  # 2 subheaders + 5 items
    assert len(recipe.instructions) == 5  # 2 subheaders + 3 steps

    # Test conversion to FinalRecipeSchema
    schema = parse_marked_markdown(marked_sample, source_path="pie.txt")
    assert schema.name == "Chocolate Banana Pie"
    assert len(schema.ingredientGroups) == 2
    assert schema.ingredientGroups[0].groupHeader == "Crust"
    assert len(schema.ingredientGroups[0].items) == 2
    assert schema.ingredientGroups[1].groupHeader == "Filling"
    assert len(schema.ingredientGroups[1].items) == 3


class MockLLMClient:
    """Mock LLM client returning marked markdown text."""

    def __init__(self, response_text: str):
        self.response_text = response_text

    def chat(self, system: str, user: str) -> str:
        return self.response_text


def test_llm_recipe_parser_marked_mode(tmp_path):
    marked_llm_output = """```markdown
# Quick Taco Bell Twists
Yield: 4 servings

## Ingredients
- 1 cup cinnamon sugar mix
- 1 package rotini pasta (fried)
- Vegetable oil for frying

## Instructions
1. Heat oil in a deep fryer to 350F.
2. Fry rotini pasta until puffy and golden.
3. Toss immediately in cinnamon sugar mix.
```"""

    cfg_file = tmp_path / "test_llm.yaml"
    cfg_file.write_text("""
provider:
  base_url: "http://localhost:11434/v1"
  model: "mock-model"
prompt:
  mode: "marked"
sanity:
  min_ingredients: 1
  min_instructions: 1
""")

    ing_parser = RegexIngredientParser()
    parser = LLMRecipeParser(ing_parser, config_path=str(cfg_file))
    parser._client = MockLLMClient(marked_llm_output)

    recipes = list(parser.parse_content("raw taco bell text sample", "sample_taco.txt"))
    assert len(recipes) == 1
    recipe = recipes[0]
    assert recipe.title == "Quick Taco Bell Twists"
    assert recipe.yield_amount == "4 servings"
    assert len(recipe.ingredients) == 3
    assert len(recipe.instructions) == 3
    assert recipe.ingredients[0].raw == "1 cup cinnamon sugar mix"
